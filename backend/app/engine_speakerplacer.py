"""Adapter from :mod:`speakerplacer`'s 2-D metre API to the backend contract."""

from __future__ import annotations

import copy
import dataclasses
import functools
import json
import math
from typing import Any

import numpy as np

import speakerplacer
from speakerplacer import DEFAULT_SPEAKER_TYPES

from . import acoustics
from .stubs import engine_stub

_METRES_PER_FOOT = 0.3048


def _plain(value: Any) -> Any:
    """Convert numpy/dataclass values returned by the optimizer to JSON values."""
    if isinstance(value, np.ndarray):
        return [_plain(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _normalised_facing(room: dict) -> tuple[float, float]:
    fx, fz = (float(value) for value in room["listener"]["facing"])
    magnitude = math.hypot(fx, fz)
    return (fx / magnitude, fz / magnitude) if magnitude else (0.0, -1.0)


def _engine_facing(room: dict) -> tuple[str, list[str]]:
    fx, fz = _normalised_facing(room)
    # Room north is -z; speakerplacer north is +v.
    vector = np.asarray([fx, -fz])
    choices = {"north": np.asarray([0.0, 1.0]), "south": np.asarray([0.0, -1.0]),
               "east": np.asarray([1.0, 0.0]), "west": np.asarray([-1.0, 0.0])}
    name, direction = max(choices.items(), key=lambda item: float(np.dot(vector, item[1])))
    error = math.degrees(math.acos(float(np.clip(np.dot(vector, direction), -1.0, 1.0))))
    warnings = [f"listener facing snapped to {name} for speakerplacer ({error:.1f} deg)"] if error > 10.0 else []
    return name, warnings


def _mean_absorption(room: dict, options: dict | None) -> float:
    if options and "absorption" in options:
        return min(0.99, max(0.01, float(options["absorption"])))
    values = [float(surface.get("absorption", {}).get(band, 0.09))
              for surface in room.get("surfaces", []) if surface.get("kind") == "wall" for band in ("500", "1000")]
    return min(0.99, max(0.01, sum(values) / len(values))) if values else 0.09


def _inside_object(position: list[float], obj: dict) -> bool:
    x, y, z = (float(item) for item in position)
    cx, cy, cz = (float(item) for item in obj["center"])
    sx, sy, sz = (float(item) for item in obj["size"])
    theta = math.radians(float(obj.get("rotation_y", 0.0)))
    local_x = (x - cx) * math.cos(theta) - (z - cz) * math.sin(theta)
    local_z = (x - cx) * math.sin(theta) + (z - cz) * math.cos(theta)
    return abs(local_x) < sx / 2 and abs(y - cy) < sy / 2 and abs(local_z) < sz / 2


def _inside_room(position: list[float], room: dict) -> list[float]:
    dimensions = room["dimensions"]
    return [min(max(float(position[0]), 0.001), float(dimensions["width"]) - 0.001),
            min(max(float(position[1]), 0.001), float(dimensions["height"]) - 0.001),
            min(max(float(position[2]), 0.001), float(dimensions["length"]) - 0.001)]


def _avoid_objects(position: list[float], room: dict, role: str) -> tuple[list[float], list[str]]:
    """Slide a wall placement along its current wall out of furniture."""
    result = _inside_room(position, room)
    warnings: list[str] = []
    dimensions = room["dimensions"]
    width, length = float(dimensions["width"]), float(dimensions["length"])

    # speakerplacer and the geometric center placement both provide a wall
    # coordinate (possibly with a small inward inset).  Preserve that exact
    # coordinate while varying only the along-wall axis.
    distances = ((result[0], "west"), (width - result[0], "east"),
                 (result[2], "north"), (length - result[2], "south"))
    wall = min(distances, key=lambda item: item[0])[1]
    along_is_z = wall in {"west", "east"}
    original_along = result[2] if along_is_z else result[0]
    lower, upper = 0.5, (length if along_is_z else width) - 0.5

    def point_at(along: float) -> list[float]:
        return [result[0], result[1], along] if along_is_z else [along, result[1], result[2]]

    def footprint_interval(obj: dict) -> tuple[float, float] | None:
        """The segment of this wall line occupied by the rotated object box."""
        cx, _, cz = (float(item) for item in obj["center"])
        sx, _, sz = (float(item) for item in obj["size"])
        theta = math.radians(float(obj.get("rotation_y", 0.0)))
        cos_theta, sin_theta = math.cos(theta), math.sin(theta)
        # local_x/local_z are affine in the coordinate along this wall line.
        if along_is_z:
            x_const = result[0]
            coefficients = ((-sin_theta, (x_const - cx) * cos_theta + cz * sin_theta),
                            (cos_theta, (x_const - cx) * sin_theta - cz * cos_theta))
        else:
            z_const = result[2]
            coefficients = ((cos_theta, -cx * cos_theta - (z_const - cz) * sin_theta),
                            (sin_theta, -cx * sin_theta + (z_const - cz) * cos_theta))
        interval = (-math.inf, math.inf)
        for index, (coefficient, intercept) in enumerate(coefficients):
            half_size = (sx, sz)[index] / 2
            if abs(coefficient) < 1e-10:
                if abs(intercept) >= half_size:
                    return None
                continue
            values = sorted(((-half_size - intercept) / coefficient, (half_size - intercept) / coefficient))
            interval = (max(interval[0], values[0]), min(interval[1], values[1]))
        return interval if interval[0] < interval[1] else None

    objects = room.get("objects", [])
    blocking = [obj for obj in objects if _inside_object(result, obj)]
    if not blocking:
        return result, warnings
    names = ", ".join(str(obj.get("id", "unknown")) for obj in blocking)
    # Candidate stops are just outside every object's footprint on this wall line; a stop is legal only
    # if it clears all objects at once, so sliding out of one box can never land inside another.
    stops = []
    for obj in objects:
        interval = footprint_interval(obj)
        if interval is not None:
            stops.extend((interval[0] - 0.02, interval[1] + 0.02))
    legal = [point_at(value) for value in stops if lower <= value <= upper]
    legal = [candidate for candidate in legal if not any(_inside_object(candidate, obj) for obj in objects)]
    if legal:
        result = min(legal, key=lambda item: abs((item[2] if along_is_z else item[0]) - original_along))
        warnings.append(f"{role} slid to avoid object {names}")
    else:
        warnings.append(f"{role} could not avoid object {names} on its wall")
    return result, warnings


def _center(room: dict) -> tuple[dict, list[str]]:
    dimensions = room["dimensions"]
    width, length = float(dimensions["width"]), float(dimensions["length"])
    listener = room["listener"]["position"]
    fx, fz = _normalised_facing(room)
    distances = []
    if fx > 1e-8:
        distances.append((width - listener[0]) / fx)
    elif fx < -1e-8:
        distances.append(-listener[0] / fx)
    if fz > 1e-8:
        distances.append((length - listener[2]) / fz)
    elif fz < -1e-8:
        distances.append(-listener[2] / fz)
    distance = min(value for value in distances if value > 0)
    position = [float(listener[0] + fx * max(0.001, distance - 0.16)), 3.6,
                float(listener[2] + fz * max(0.001, distance - 0.16))]
    wall_position = list(position)
    position, warnings = _avoid_objects(position, room, "C")
    # A TV mounted on the front wall can span the whole useful wall segment.
    # In that case preserve the contract's straight-ahead C position by moving
    # the speaker just into the room rather than placing it inside the TV box.
    if math.hypot(position[0] - wall_position[0], position[2] - wall_position[2]) > 1e-6:
        candidate = _inside_room([listener[0] + fx * max(0.001, distance - 0.32), 3.6,
                                  listener[2] + fz * max(0.001, distance - 0.32)], room)
        if not any(_inside_object(candidate, obj) for obj in room.get("objects", [])):
            position = candidate
            warnings.append("C moved slightly inward to avoid front-wall object")
    return {"role": "C", "position": position, "aim": [float(item) for item in listener]}, warnings


def _screen(room: dict) -> dict | None:
    return copy.deepcopy(engine_stub.optimize(room)["layout"].get("screen"))


def _safe_fallback_layout(room: dict) -> dict:
    """Preserve 5.1 angle invariants when the wall optimiser has no candidates."""
    dimensions = room["dimensions"]
    width, length = float(dimensions["width"]), float(dimensions["length"])
    listener = room["listener"]["position"]
    fx, fz = _normalised_facing(room)
    forward = np.asarray([fx, fz])
    left = np.asarray([fz, -fx])

    def ray(direction: np.ndarray, height: float) -> list[float]:
        distances: list[float] = []
        if direction[0] > 1e-9:
            distances.append((width - 0.001 - listener[0]) / direction[0])
        elif direction[0] < -1e-9:
            distances.append((0.001 - listener[0]) / direction[0])
        if direction[1] > 1e-9:
            distances.append((length - 0.001 - listener[2]) / direction[1])
        elif direction[1] < -1e-9:
            distances.append((0.001 - listener[2]) / direction[1])
        distance = max(0.02, min(2.5, 0.8 * min(value for value in distances if value > 0)))
        return _inside_room([listener[0] + direction[0] * distance, height,
                             listener[2] + direction[1] * distance], room)

    def direction(angle: float, side: float) -> np.ndarray:
        return forward * math.cos(math.radians(angle)) + left * side * math.sin(math.radians(angle))

    positions = {"L": ray(direction(30, 1), 3.6), "R": ray(direction(30, -1), 3.6),
                 "Ls": ray(direction(110, 1), 5.0), "Rs": ray(direction(110, -1), 5.0),
                 "C": ray(forward, 3.6), "LFE": ray(forward, 1.0)}
    speakers = [{"role": role, "position": positions[role], "aim": [float(item) for item in listener]}
                for role in ("L", "R", "C", "LFE", "Ls", "Rs")]
    return {"speakers": speakers, "screen": _screen(room)}


def _canonical_room(room: dict) -> dict:
    return {key: room.get(key) for key in ("dimensions", "surfaces", "objects", "listener")}


@functools.lru_cache(maxsize=32)
def _optimise_cached(room_json: str, absorption: float) -> dict:
    room = json.loads(room_json)
    dimensions = room["dimensions"]
    width, length = float(dimensions["width"]), float(dimensions["length"])
    listener = room["listener"]["position"]
    polygon_m = np.asarray([[0.0, width * _METRES_PER_FOOT, width * _METRES_PER_FOOT, 0.0],
                            [0.0, 0.0, length * _METRES_PER_FOOT, length * _METRES_PER_FOOT]])
    listener_m = np.asarray([float(listener[0]) * _METRES_PER_FOOT,
                             (length - float(listener[2])) * _METRES_PER_FOOT])
    facing, adapter_warnings = _engine_facing(room)
    # The current teammate build's mirrored-surround candidate helper rejects
    # otherwise legal side-wall pairs; asking it for two independent surround
    # candidates retains the same model/targets and lets the adapter assign Ls/Rs.
    layout_types = [DEFAULT_SPEAKER_TYPES["front"], dataclasses.replace(DEFAULT_SPEAKER_TYPES["surround"], symmetric=False),  # noqa: E501  # preserve behavior while retaining the existing expression
                    dataclasses.replace(DEFAULT_SPEAKER_TYPES["bass"], count=1, symmetric=False)]
    result = speakerplacer.optimize_layout(polygon_m, listener_m, layout_types, facing=facing, absorption=absorption)
    raw = result.best_pair["speakers"]
    listener_ft = [float(item) for item in listener]
    fx, fz = _normalised_facing(room)
    left = np.asarray([fz, -fx])
    grouped = {"front": [], "surround": [], "bass": []}
    for item in raw:
        grouped[str(item["type"])].append(item)
    speakers: list[dict] = []
    placement_metadata: list[dict] = []
    heights = {"L": 3.6, "R": 3.6, "Ls": 5.0, "Rs": 5.0, "LFE": 1.0}
    for kind, role_names in (("front", ("L", "R")), ("surround", ("Ls", "Rs")), ("bass", ("LFE",))):
        entries = grouped[kind]
        if kind == "bass":
            assignments = [("LFE", entries[0])]
        else:
            def side(entry: dict) -> float:
                u, v = (float(value) for value in entry["position_m"])
                point = np.asarray([u / _METRES_PER_FOOT, length - v / _METRES_PER_FOOT])
                return float(np.dot(point - np.asarray([listener_ft[0], listener_ft[2]]), left))
            ordered = sorted(entries, key=side, reverse=True)
            assignments = list(zip(role_names, ordered, strict=False))
        for role, entry in assignments:
            u, v = (float(value) for value in entry["position_m"])
            position, collision_warnings = _avoid_objects([u / _METRES_PER_FOOT, heights[role], length - v / _METRES_PER_FOOT], room, role)  # noqa: E501  # preserve behavior while retaining the existing expression
            if role == "LFE":
                aim = listener_ft
            else:
                direction = np.asarray(entry.get("aim_direction", [0.0, 0.0]), dtype=float)
                room_direction = np.asarray([direction[0], -direction[1]])
                norm = float(np.linalg.norm(room_direction))
                if norm < 1e-8:
                    room_direction = np.asarray([listener_ft[0] - position[0], listener_ft[2] - position[2]])
                    norm = float(np.linalg.norm(room_direction))
                room_direction /= max(norm, 1e-8)
                distance = math.hypot(listener_ft[0] - position[0], listener_ft[2] - position[2])
                aim = [position[0] + float(room_direction[0]) * distance, 3.6,
                       position[2] + float(room_direction[1]) * distance]
            speakers.append({"role": role, "position": [float(value) for value in position],
                             "aim": [float(value) for value in aim]})
            adapter_warnings.extend(collision_warnings)
            placement_metadata.append({"role": role, "model_id": str(entry.get("model_id", "")),
                                       "toe_in_deg": float(entry.get("toe_in_deg", 0.0)),
                                       "predicted_spl_db": float(entry.get("predicted_spl_db", 0.0)),
                                       "headroom_db": float(entry.get("headroom_db", 0.0))})
    center, center_warnings = _center(room)
    speakers.append(center)
    adapter_warnings.extend(center_warnings)
    adapter_warnings.append("C placed geometrically (speakerplacer has no center model)")
    # Stable role order makes cached and fresh responses byte-for-byte alike.
    role_order = {"L": 0, "R": 1, "C": 2, "LFE": 3, "Ls": 4, "Rs": 5}
    speakers.sort(key=lambda item: role_order[item["role"]])
    layout = {"speakers": speakers, "screen": _screen(room)}
    metrics = acoustics.evaluate(room, layout)
    metrics["engine"] = {"name": "speakerplacer", "score_db": float(result.best_pair["score_db"]),
                         "placements": placement_metadata}
    metrics["warnings"] = [str(item) for item in result.warnings] + adapter_warnings
    return _plain({"layout": layout, "metrics": metrics})


def optimize(room: dict, options: dict | None = None) -> dict:
    """Optimise a 5.1 layout, returning a safe fallback if the engine rejects it."""
    try:
        absorption = _mean_absorption(room, options)
        room_json = json.dumps(_canonical_room(room), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return copy.deepcopy(_optimise_cached(room_json, absorption))
    except Exception as exc:  # Engine errors must never turn an API request into a 500.
        try:
            fallback_layout = copy.deepcopy(engine_stub.optimize(room)["layout"])
        except Exception:
            fallback_layout = _safe_fallback_layout(room)
        metrics = acoustics.evaluate(room, fallback_layout)
        metrics["engine"] = {"name": "speakerplacer", "score_db": None, "placements": []}
        metrics["warnings"].append(f"speakerplacer failed: {type(exc).__name__}: {exc}")
        return {"layout": _plain(fallback_layout), "metrics": _plain(metrics)}


def score(room: dict, layout: dict) -> dict:
    """Score any submitted layout using the same fast metrics as optimize."""
    try:
        return {"metrics": _plain(acoustics.evaluate(room, layout))}
    except Exception as exc:
        metrics = acoustics.evaluate(room, {"speakers": [], "screen": None})
        metrics["warnings"].append(f"speakerplacer score failed: {type(exc).__name__}: {exc}")
        return {"metrics": _plain(metrics)}


def clear_cache() -> None:
    """Test helper for forcing the next optimization through speakerplacer."""
    _optimise_cached.cache_clear()
