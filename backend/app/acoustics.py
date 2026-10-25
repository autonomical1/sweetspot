"""Small, deterministic room-acoustics metrics for the backend contract."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np

SPEED_OF_SOUND_FT_S = 1125.0
_EPSILON = 1e-7


def _vector(value: Iterable[float]) -> np.ndarray:
    return np.asarray(list(value), dtype=float)


def _polygon_area(points: list[list[float]]) -> float:
    """Area of a planar polygon, split into triangles from its first point."""
    if len(points) < 3:
        return 0.0
    base = _vector(points[0])
    return float(sum(np.linalg.norm(np.cross(_vector(points[i]) - base, _vector(points[i + 1]) - base)) / 2
                     for i in range(1, len(points) - 1)))


def _contains_polygon(point: np.ndarray, polygon: list[list[float]]) -> bool:
    """Point-in-convex-planar-polygon check, projected along the dominant normal."""
    if len(polygon) < 3:
        return False
    vertices = [_vector(vertex) for vertex in polygon]
    normal = np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0])
    if np.linalg.norm(normal) < _EPSILON or abs(float(np.dot(point - vertices[0], normal))) > 1e-4:
        return False
    axis = int(np.argmax(np.abs(normal)))
    projected = [np.delete(vertex, axis) for vertex in vertices]
    p = np.delete(point, axis)
    signs: list[float] = []
    for start, end in zip(projected, projected[1:] + projected[:1], strict=False):
        edge = end - start
        signs.append(float(edge[0] * (p[1] - start[1]) - edge[1] * (p[0] - start[0])))
    return all(sign >= -1e-5 for sign in signs) or all(sign <= 1e-5 for sign in signs)


def _surface_for_hit(room: dict, point: np.ndarray, axis: int, value: float) -> dict | None:
    """Find the actual room surface at a boundary hit; openings beat their wall."""
    matching: list[dict] = []
    for surface in room.get("surfaces", []):
        polygon = surface.get("polygon", [])
        if polygon and all(abs(float(vertex[axis]) - value) < 1e-4 for vertex in polygon) and _contains_polygon(point, polygon):  # noqa: E501  # preserve behavior while retaining the existing expression
            matching.append(surface)
    if not matching:
        return None
    priority = {"window": 0, "door": 0, "opening": 0, "wall": 1, "floor": 1, "ceiling": 1}
    return min(matching, key=lambda item: priority.get(item.get("kind"), 2))


def _reflections(room: dict, layout: dict) -> list[dict]:
    dimensions = room["dimensions"]
    width, length, height = (float(dimensions[key]) for key in ("width", "length", "height"))
    listener = _vector(room["listener"]["position"])
    planes = ((0, 0.0), (0, width), (2, 0.0), (2, length), (1, 0.0), (1, height))
    found: list[dict] = []
    for speaker in layout.get("speakers", []):
        if speaker.get("role") in {"LFE", "LFE2"}:
            continue
        source = _vector(speaker["position"])
        direct = float(np.linalg.norm(listener - source))
        if direct < _EPSILON:
            continue
        for axis, plane in planes:
            image = source.copy()
            image[axis] = 2.0 * plane - image[axis]
            path = listener - image
            if abs(path[axis]) < _EPSILON:
                continue
            fraction = (plane - image[axis]) / path[axis]
            if not _EPSILON < fraction < 1.0 - _EPSILON:
                continue
            hit = image + fraction * path
            if not (-1e-5 <= hit[0] <= width + 1e-5 and -1e-5 <= hit[1] <= height + 1e-5
                    and -1e-5 <= hit[2] <= length + 1e-5):
                continue
            surface = _surface_for_hit(room, hit, axis, plane)
            if surface is None:
                continue
            reflected = float(np.linalg.norm(listener - image))
            delay = (reflected - direct) / SPEED_OF_SOUND_FT_S * 1000.0
            if delay < -1e-5 or delay > 20.0:
                continue
            alpha = min(0.999999, max(0.0, float(surface.get("absorption", {}).get("1000", 0.09))))
            level = 20.0 * math.log10(max(direct / reflected, _EPSILON)) + 10.0 * math.log10(1.0 - alpha)
            found.append({"speaker": str(speaker.get("role", "")), "surface_id": str(surface["id"]),
                          "delay_ms": float(max(0.0, delay)), "level_db": float(level),
                          "point": [float(item) for item in hit]})
    return sorted(found, key=lambda item: item["level_db"], reverse=True)


def _patches(room: dict, reflections: list[dict]) -> list[dict]:
    """Return merged treatment suggestions for reflective vertical surfaces.

    Floor and ceiling reflections remain useful metrics, but are deliberately
    not treatment-patch candidates for the MVP UI.  Doors and openings are
    likewise omitted: only walls and windows can receive a patch.
    """
    kinds_by_id = {str(surface.get("id")): surface.get("kind") for surface in room.get("surfaces", [])}
    merged: list[dict] = []
    counts: list[int] = []
    for reflection in reflections:
        if (reflection["level_db"] <= -10 or not reflection["surface_id"]
                or kinds_by_id.get(reflection["surface_id"]) not in {"wall", "window"}):
            continue
        center = _vector(reflection["point"])
        for index, patch in enumerate(merged):
            if patch["surface_id"] == reflection["surface_id"] and np.linalg.norm(center - _vector(patch["center"])) <= 1.0:  # noqa: E501  # preserve behavior while retaining the existing expression
                counts[index] += 1
                old = _vector(patch["center"])
                patch["center"] = [float(value) for value in old + (center - old) / counts[index]]
                break
        else:
            merged.append({"surface_id": reflection["surface_id"], "center": [float(value) for value in center],
                           "size": [2.0, 2.0]})
            counts.append(1)
    return merged


def _coplanar(surface: dict, candidate: dict) -> bool:
    """Whether an opening lies in the same plane as a boundary surface."""
    polygon = surface.get("polygon", [])
    opening = candidate.get("polygon", [])
    if len(polygon) < 3 or len(opening) < 3:
        return False
    base = _vector(polygon[0])
    normal = np.cross(_vector(polygon[1]) - base, _vector(polygon[2]) - base)
    length = float(np.linalg.norm(normal))
    return length > _EPSILON and all(abs(float(np.dot(_vector(point) - base, normal))) / length < 1e-4
                                   for point in opening)


def _absorption_area(room: dict) -> float:
    """Sabine absorption area, counting wall openings exactly once."""
    surfaces = room.get("surfaces", [])
    openings = [surface for surface in surfaces if surface.get("kind") in {"window", "door", "opening"}]
    total = 0.0
    for surface in surfaces:
        kind = surface.get("kind")
        if kind not in {"wall", "floor", "ceiling"}:
            continue
        area = _polygon_area(surface.get("polygon", []))
        alpha = float(surface.get("absorption", {}).get("500", 0.08))
        if kind == "wall":
            for opening in openings:
                if _coplanar(surface, opening):
                    opening_area = _polygon_area(opening.get("polygon", []))
                    area -= opening_area
                    total += opening_area * float(opening.get("absorption", {}).get("500", 0.08))
        total += max(0.0, area) * alpha
    return total


def _sub_modes(room: dict, layout: dict) -> dict:
    dimensions = room["dimensions"]
    dim_values = [float(dimensions[key]) for key in ("width", "length", "height")]
    modes = [float(number * SPEED_OF_SOUND_FT_S / (2.0 * dimension))
             for dimension in dim_values if dimension > 0 for number in (1, 2, 3)]
    volume = math.prod(dim_values)
    absorption_area = _absorption_area(room)
    t60 = 0.161 * volume / max(absorption_area, _EPSILON)
    lfe = next((speaker for speaker in layout.get("speakers", []) if speaker.get("role") == "LFE"), None)
    return {"schroeder_hz": float(2000.0 * math.sqrt(t60 / max(volume, _EPSILON))),
            "axial_modes_hz": modes, "sub_position": list(map(float, lfe["position"])) if lfe else None}


def _angle_score(room: dict, layout: dict) -> float:
    listener = _vector(room["listener"]["position"])
    facing = _vector(room["listener"]["facing"])
    length = float(np.linalg.norm(facing))
    if length < _EPSILON:
        return 0.0
    facing /= length
    left = np.asarray([facing[1], -facing[0]])
    targets = {"L": 30.0, "R": 30.0, "C": 0.0, "Ls": 110.0, "Rs": 110.0,
               "Lss": 90.0, "Rss": 90.0, "Lrs": 140.0, "Rrs": 140.0}
    values: list[float] = []
    for speaker in layout.get("speakers", []):
        role = speaker.get("role")
        if role not in targets:
            continue
        position = _vector(speaker["position"])
        direction = np.asarray([position[0] - listener[0], position[2] - listener[2]])
        if np.linalg.norm(direction) < _EPSILON:
            values.append(0.0)
            continue
        angle = abs(math.degrees(math.atan2(float(np.dot(direction, left)), float(np.dot(direction, facing)))))
        values.append(max(0.0, 1.0 - abs(angle - targets[role]) / 30.0))
    return float(np.mean(values)) if values else 0.0


def evaluate(room: dict, layout: dict) -> dict:
    """Return inexpensive first-order metrics in the shared JSON contract.

    The score is intentionally a documented heuristic: 70% speaker-angle fit,
    30% penalty for strong, early first-order reflections.
    """
    reflections = _reflections(room, layout)
    strong = sum(item["level_db"] > -10.0 and item["delay_ms"] < 15.0 for item in reflections)
    reflection_score = 1.0 - min(1.0, strong / 12.0)
    score = round(0.7 * _angle_score(room, layout) + 0.3 * reflection_score, 4)
    return {"score": score, "reflections": reflections, "treatment_patches": _patches(room, reflections),
            "sub_modes": _sub_modes(room, layout), "warnings": []}
