"""Group a room's walls into front / left / back / right for photo prompts and materials.

Scanned rooms can have more than four wall surfaces, but the phone asks for at most six
photos (front, left, back, right, floor, ceiling). Every wall is assigned to the direction
it lies in relative to the listener, one photo is taken per direction and the classified
material is applied to the whole group.
"""
from __future__ import annotations

import math

from .schemas import Room, Surface

DIRECTIONS = ("Front wall", "Left wall", "Back wall", "Right wall")


def wall_area(surface: Surface) -> float:
    if len(surface.polygon) < 3:
        return 0.0
    cross_sum = [0.0, 0.0, 0.0]
    for point, next_point in zip(surface.polygon, surface.polygon[1:] + surface.polygon[:1], strict=False):
        cross_sum[0] += point[1] * next_point[2] - point[2] * next_point[1]
        cross_sum[1] += point[2] * next_point[0] - point[0] * next_point[2]
        cross_sum[2] += point[0] * next_point[1] - point[1] * next_point[0]
    return math.sqrt(sum(value * value for value in cross_sum)) / 2


def wall_direction(room: Room, surface: Surface) -> str:
    """Direction label of a wall as seen from the listener (facing = forward)."""
    fx, fz = room.listener.facing
    points = surface.polygon
    cx = sum(p[0] for p in points) / len(points)
    cz = sum(p[2] for p in points) / len(points)
    dx, dz = cx - room.listener.position[0], cz - room.listener.position[2]
    forward = dx * fx + dz * fz
    side = dx * fz - dz * fx
    if abs(forward) >= abs(side):
        return "Front wall" if forward > 0 else "Back wall"
    return "Left wall" if side > 0 else "Right wall"


def wall_groups(room: Room) -> dict[str, list[Surface]]:
    """Walls per direction, largest first; empty directions are omitted."""
    groups: dict[str, list[Surface]] = {}
    for surface in room.surfaces:
        if surface.kind == "wall" and len(surface.polygon) >= 3:
            groups.setdefault(wall_direction(room, surface), []).append(surface)
    for walls in groups.values():
        walls.sort(key=lambda s: (-wall_area(s), s.id))
    return {name: groups[name] for name in DIRECTIONS if name in groups}
