"""End-to-end checks for the phone's partial scan and the complete sample."""

import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import Room

ROOT = Path(__file__).resolve().parents[2]


def to_world_m(point: list[float], frame: dict) -> list[float]:
    angle = math.radians(frame["yaw_deg"])
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = point
    ox, oy, oz = frame["offset"]
    return [(c * x + s * z + ox) * 0.3048, (y + oy) * 0.3048,
            (-s * x + c * z + oz) * 0.3048]


def scan_wall_corners(item: dict) -> list[list[float]]:
    transform = item["transform"]
    width, height, _ = item["dimensions"]
    norm = math.hypot(transform[0], transform[2])
    return [[transform[12] + side * width / 2 * transform[0] / norm,
             transform[13] + up * height / 2,
             transform[14] + side * width / 2 * transform[2] / norm]
            for side, up in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]


def scan_floor_centre(floor: dict) -> list[float]:
    corners = floor["polygon_corners"]
    area = x_sum = y_sum = 0.0
    for first, second in zip(corners, corners[1:] + corners[:1], strict=False):
        cross = first[0] * second[1] - second[0] * first[1]
        area += cross
        x_sum += (first[0] + second[0]) * cross
        y_sum += (first[1] + second[1]) * cross
    local_x, local_y = x_sum / (3 * area), y_sum / (3 * area)
    transform = floor["transform"]
    return [transform[12 + axis] + transform[axis] * local_x +
            transform[4 + axis] * local_y for axis in range(3)]


@pytest.mark.parametrize("fixture", ["partial_scan_upload_test.json", "roomplan_sample.json"])
def test_phone_scan_round_trip_and_layout(fixture, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    dto = json.loads((ROOT / "fixtures" / fixture).read_text())
    with TestClient(create_app()) as client:
        response = client.post("/rooms", json={"captured_room": dto})
        assert response.status_code == 200, response.text
        room = Room.model_validate(response.json())
        assert room.source == "roomplan" and room.frame is not None
        assert all(value > 0 for value in (room.dimensions.width, room.dimensions.height,
                                           room.dimensions.length))
        bounds = [room.dimensions.width, room.dimensions.height, room.dimensions.length]
        assert all(0 <= value <= bound for value, bound in zip(room.listener.position, bounds, strict=True))
        if not room.objects:
            centre = [room.dimensions.width / 2, room.dimensions.length / 2]
            assert math.dist(room.listener.position[::2], centre) <= 1.5
        assert math.hypot(*room.listener.facing) == pytest.approx(1)

        frame = room.frame.model_dump()
        surfaces = {surface.id: surface for surface in room.surfaces}
        scan_points = []
        for item in dto["surfaces"]:
            if item["category"] == "floor":
                continue
            expected = scan_wall_corners(item)
            if item["category"] == "wall":
                scan_points.extend(expected)
            for vertex, scan_vertex in zip(surfaces[item["id"]].polygon, expected, strict=True):
                assert to_world_m(vertex, frame) == pytest.approx(scan_vertex, abs=0.05)
        listener_world = to_world_m(room.listener.position, frame)
        assert all(math.isfinite(value) for value in listener_world)
        if not room.objects:
            floor = next(item for item in dto["surfaces"] if item["category"] == "floor")
            if floor["polygon_corners"]:
                transform = floor["transform"]
                expected_centre = scan_floor_centre(floor)
                assert listener_world[::2] == pytest.approx(expected_centre[::2], abs=0.05)
                scan_points.extend([
                    [transform[12 + axis] + transform[axis] * corner[0] +
                     transform[4 + axis] * corner[1] for axis in range(3)]
                    for corner in floor["polygon_corners"]
                ])
            for axis in (0, 2):
                values = [point[axis] for point in scan_points]
                assert min(values) - 0.3 <= listener_world[axis] <= max(values) + 0.3

        optimized = client.post(f"/rooms/{room.room_id}/optimize", json={})
        assert optimized.status_code == 200, optimized.text
        speakers = optimized.json()["layout"]["speakers"]
        assert {speaker["role"] for speaker in speakers} == {"L", "R", "C", "LFE", "Ls", "Rs"}
        for speaker in speakers:
            position = speaker["position"]
            assert all(0 <= value <= bound for value, bound in zip(position, bounds, strict=True))
            world = to_world_m(position, frame)
            for axis in (0, 2):
                values = [point[axis] for point in scan_points]
                assert min(values) - 0.3 <= world[axis] <= max(values) + 0.3
            assert min(point[1] for point in scan_points) - 0.3 <= world[1]
            assert world[1] <= max(point[1] for point in scan_points) + 0.3


def test_contract_frame_vectors():
    vectors = json.loads((ROOT / "phoneapp_context" / "sample_payloads" /
                          "frame_test_vectors.json").read_text())
    for case in vectors["points"]:
        frame = {"yaw_deg": case["yaw_deg"], "offset": case["offset_ft"]}
        assert to_world_m(case["room_ft"], frame) == pytest.approx(case["world_m"], abs=1e-4)
    for case in vectors["directions"]:
        frame = {"yaw_deg": case["yaw_deg"], "offset": [0, 0, 0]}
        world = to_world_m(case["room_dir"], frame)
        assert world == pytest.approx([value * 0.3048 for value in case["world_dir"]], abs=1e-4)
