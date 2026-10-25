"""Convert raw RoomPlan world metres to room-frame feet (docs/API.md 1a)."""

import importlib.util
import math
from copy import deepcopy
from pathlib import Path

from .materials import ABSORPTION
from .schemas import Dimensions, Frame, Listener, Room, RoomObject, Surface

METRES_TO_FEET = 3.28084

_validator_spec = importlib.util.spec_from_file_location(
    "roomplan_dto_validator", Path(__file__).resolve().parents[2] / "tools" / "validate_dto.py"
)
assert _validator_spec is not None and _validator_spec.loader is not None
_validator = importlib.util.module_from_spec(_validator_spec)
_validator_spec.loader.exec_module(_validator)


def _rotate(point: list[float], yaw_deg: float) -> list[float]:
    x, y, z = point
    angle = math.radians(yaw_deg)
    c, s = math.cos(angle), math.sin(angle)
    return [c * x + s * z, y, -s * x + c * z]


def _angle(degrees: float) -> float:
    result = degrees % 360
    return result - 360 if result > 180 else result


def dir_to_world(direction: list[float], frame: Frame | dict) -> list[float]:
    """Rotate a 3D direction or an x-z facing vector, without translating."""
    frame = Frame.model_validate(frame)
    if len(direction) == 2:
        x, _, z = _rotate([direction[0], 0.0, direction[1]], frame.yaw_deg)
        return [x, z]
    return _rotate(direction, frame.yaw_deg)


def frame_to_world(point_ft: list[float], frame: Frame | dict) -> list[float]:
    """Map a room-frame point to scan world coordinates, both in feet."""
    frame = Frame.model_validate(frame)
    return [v + offset for v, offset in zip(_rotate(point_ft, frame.yaw_deg), frame.offset, strict=False)]


def world_to_room(point_ft: list[float], frame: Frame | dict) -> list[float]:
    """Invert frame_to_world; input and output are feet."""
    frame = Frame.model_validate(frame)
    return _rotate([v - offset for v, offset in zip(point_ft, frame.offset, strict=False)], -frame.yaw_deg)


def _surface_polygon(item: dict) -> list[list[float]]:
    transform = item["transform"]
    x, y, z = transform[12:15]
    magnitude = math.hypot(transform[0], transform[2])
    if magnitude == 0:
        raise ValueError(f"surface {item['id']} has no horizontal width direction")
    w, h, _ = item["dimensions"]
    dx, dz = transform[0] / magnitude * w / 2, transform[2] / magnitude * w / 2
    return [[x - dx, y - h / 2, z - dz], [x + dx, y - h / 2, z + dz],
            [x + dx, y + h / 2, z + dz], [x - dx, y + h / 2, z - dz]]


def _toward(seat: list[float], target: list[float]) -> list[float]:
    return [target[0] - seat[0], target[2] - seat[2]]


def _farthest_wall_facing(seat: list[float], walls: list[dict]) -> list[float]:
    # Round only the distance used for tie-breaking, preserving DTO order for ties.
    target = max(walls, key=lambda wall: round(math.hypot(
        *_toward(seat, wall["transform"][12:15])), 10))
    return _toward(seat, target["transform"][12:15])


def _floor_centre(surfaces: list[dict]) -> list[float] | None:
    """Centroid of RoomPlan's local floor polygon, mapped into world metres."""
    for floor in (item for item in surfaces if item["category"] == "floor"):
        corners = floor.get("polygon_corners") or []
        if len(corners) < 3:
            continue
        twice_area = cx = cy = 0.0
        for first, second in zip(corners, corners[1:] + corners[:1], strict=False):
            cross = first[0] * second[1] - second[0] * first[1]
            twice_area += cross
            cx += (first[0] + second[0]) * cross
            cy += (first[1] + second[1]) * cross
        if abs(twice_area) < 1e-10:
            continue
        local_x, local_y = cx / (3 * twice_area), cy / (3 * twice_area)
        transform = floor["transform"]
        return [transform[12 + axis] + transform[axis] * local_x +
                transform[4 + axis] * local_y for axis in range(3)]
    return None


def _wall_box_centre(endpoints: list[list[float]], yaw: float) -> list[float]:
    rotated = [_rotate(point, -yaw) for point in endpoints]
    return _rotate([(min(point[axis] for point in rotated) +
                     max(point[axis] for point in rotated)) / 2 for axis in range(3)], yaw)


def convert_dto(
    captured_room: dict, *, room_id: str, session_id: str | None,
    budget: float | None, listener: dict | None,
) -> Room:
    """Validate and normalize an iOS sweetspot.roomplan.v1 export."""
    errors, warnings = _validator.validate({"captured_room": captured_room})
    if errors:
        raise ValueError("; ".join(errors))
    items = captured_room["surfaces"] + captured_room["objects"]
    if any(abs(value) > 100 for item in items for value in item["transform"][12:15]):
        raise ValueError("translation component exceeds 100 m; expected world metres")
    walls = [item for item in captured_room["surfaces"] if item["category"] == "wall"]
    if len(walls) < 3:
        raise ValueError("fewer than 3 walls")

    polygons = {item["id"]: _surface_polygon(item)
                for item in captured_room["surfaces"] if item["category"] != "floor"}
    endpoints = [point for wall in walls for point in polygons[wall["id"]][:2]]
    sin_sum = cos_sum = 0.0
    for wall in walls:
        transform = wall["transform"]
        phi = math.atan2(transform[2], transform[0])
        width = wall["dimensions"][0]
        sin_sum += width * math.sin(4 * phi)
        cos_sum += width * math.cos(4 * phi)
    yaw0 = -math.degrees(math.atan2(sin_sum, cos_sum)) / 4
    centre = _floor_centre(captured_room["surfaces"]) or _wall_box_centre(endpoints, yaw0)

    if listener is not None:
        override = Listener.model_validate(listener)
        seat, facing = override.position, override.facing
        if len(seat) != 3 or not all(math.isfinite(v) for v in seat):
            raise ValueError("invalid listener position")
        if len(facing) != 2 or not all(math.isfinite(v) for v in facing) or math.hypot(*facing) == 0:
            raise ValueError("invalid listener facing")
    else:
        sofas = [item for item in captured_room["objects"] if item["category"] == "sofa"]
        televisions = [item for item in captured_room["objects"] if item["category"] == "television"]
        if sofas:
            sofa = max(sofas, key=lambda item: item["dimensions"][0] * item["dimensions"][2])
            seat = sofa["transform"][12:15]
        else:
            seat = centre
            warnings.append("no sofa detected; listener at room centre")
        if televisions:
            facing = _toward(seat, televisions[0]["transform"][12:15])
        elif sofas:
            facing = _toward(seat, centre)
        else:
            facing = _farthest_wall_facing(seat, walls)
        if math.hypot(*facing) < 1e-10:
            facing = _farthest_wall_facing(seat, walls)
            warnings.append("listener facing is ambiguous; using farthest wall")
        if math.hypot(*facing) == 0:
            raise ValueError("cannot determine listener facing from wall midpoints")

    magnitude = math.hypot(*facing)
    world_facing = [facing[0] / magnitude, 0.0, facing[1] / magnitude]
    yaw = min((_angle(yaw0 + k * 90) for k in range(4)),
              key=lambda candidate: _rotate(world_facing, -candidate)[2])
    rotated_endpoints = [_rotate(point, -yaw) for point in endpoints]
    floor_level = min([point[1] for point in endpoints] + [
        item["transform"][13] for item in captured_room["surfaces"] if item["category"] == "floor"
    ])
    base = [min(point[0] for point in rotated_endpoints), floor_level,
            min(point[2] for point in rotated_endpoints)]

    def room_point(point: list[float]) -> list[float]:
        return [(v - origin) * METRES_TO_FEET for v, origin in zip(_rotate(point, -yaw), base, strict=False)]

    width = (max(point[0] for point in rotated_endpoints) - base[0]) * METRES_TO_FEET
    length = (max(point[2] for point in rotated_endpoints) - base[2]) * METRES_TO_FEET
    height = (max(polygons[wall["id"]][2][1] for wall in walls) - floor_level) * METRES_TO_FEET
    if not all(math.isfinite(v) and v > 0 for v in (width, length, height)):
        raise ValueError("wall bounding box must have positive finite dimensions")
    dimensions = Dimensions(width=width, length=length, height=height)
    frame = Frame(yaw_deg=yaw, offset=[v * METRES_TO_FEET for v in _rotate(base, yaw)])

    surfaces = []
    for item in captured_room["surfaces"]:
        kind = item["category"]
        if kind == "floor":
            continue
        material = "glass" if kind == "window" else "drywall"
        surfaces.append(Surface(id=item["id"], kind=kind,
                                polygon=[room_point(p) for p in polygons[item["id"]]],
                                material=material, absorption=ABSORPTION[material].copy()))
    for kind, y in (("floor", 0.0), ("ceiling", height)):
        surfaces.append(Surface(id=kind, kind=kind,
                                polygon=[[0, y, 0], [width, y, 0], [width, y, length], [0, y, length]],
                                material="drywall", absorption=ABSORPTION["drywall"].copy()))
    objects = []
    for item in captured_room["objects"]:
        transform = item["transform"]
        objects.append(RoomObject(
            id=item["id"], category=item["category"], center=room_point(transform[12:15]),
            size=[v * METRES_TO_FEET for v in item["dimensions"]],
            rotation_y=_angle(math.degrees(math.atan2(-transform[2], transform[0])) - yaw),
        ))

    position = room_point(seat)
    position[1] = 3.6
    position = [max(0.0, min(v, bound)) for v, bound in zip(position, (width, height, length), strict=False)]
    fx, _, fz = _rotate(world_facing, -yaw)
    from .rooms import validate_listener

    position, facing = validate_listener(position, [fx, fz], dimensions)
    return Room(room_id=room_id, session_id=session_id, source="roomplan", dimensions=dimensions,
                surfaces=surfaces, objects=objects, listener=Listener(position=position, facing=facing),
                budget=budget, warnings=warnings, frame=frame, captured_room=deepcopy(captured_room))
