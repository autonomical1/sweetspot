"""Offline geometry, frame, and HTTP coverage for raw RoomPlan exports."""

import json
import math
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.materials import ABSORPTION
from backend.app.roomplan import convert_dto, dir_to_world, frame_to_world, world_to_room
from backend.app.rooms import validate_listener
from backend.app.schemas import Frame

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "phoneapp_context" / "sample_payloads"
FT = 3.28084
VECTORS = json.loads((SAMPLES / "frame_test_vectors.json").read_text())
YAWS = [0, 17, 45, 90, -120, 179]
OFFSETS = [(0, 0, 0), (-4, -2, -7), (15, 12, -20)]


def rotate(point: list[float], yaw: float) -> list[float]:
    """Independent test generator using polar x-z coordinates."""
    x, y, z = point
    radius = math.hypot(x, z)
    angle = math.atan2(z, x) - math.radians(yaw)
    return [radius * math.cos(angle), y, radius * math.sin(angle)]


def synthetic(yaw: float = 0, offset: tuple = (0, 0, 0)) -> dict:
    def item(ident: str, category: str, center: list, size: list, angle: float = 0) -> dict:
        translation = [v + shift for v, shift in zip(rotate([v / FT for v in center], yaw), offset)]
        a = math.radians(angle + yaw)
        c, s = math.cos(a), math.sin(a)
        return {"id": ident, "category": category, "dimensions": [v / FT for v in size],
                "transform": [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, *translation, 1]}

    return {
        "format": "sweetspot.roomplan.v1", "room_identifier": "synthetic", "story": 0,
        "surfaces": [
            item("north", "wall", [9, 4.5, 0], [18, 9, 0]),
            item("east", "wall", [18, 4.5, 6.5], [13, 9, 0], -90),
            item("south", "wall", [9, 4.5, 13], [18, 9, 0], 180),
            item("west", "wall", [0, 4.5, 6.5], [13, 9, 0], 90),
            item("door", "door", [3, 3.5, 13], [3, 7, 0], 180),
            item("window", "window", [18, 5, 6.5], [4, 3, 0], -90),
            item("opening", "opening", [0, 3.5, 3], [3, 7, 0], 90),
            item("scan-floor", "floor", [9, 0, 6.5], [18, 13, 0]),
        ],
        "objects": [
            item("sofa", "sofa", [9, 1.5, 10.5], [7, 3, 3], 180),
            item("tv", "television", [9, 4, 0.25], [5, 3, 0.5]),
        ],
    }


def convert(dto: dict, listener: dict | None = None):
    return convert_dto(dto, room_id="r_test", session_id=None, budget=1500, listener=listener)


def assert_round_trip(room, dto: dict) -> None:
    by_id = {surface.id: surface for surface in room.surfaces}
    for item in dto["surfaces"]:
        if item["category"] == "floor":
            continue
        m = item["transform"]
        w, h, _ = item["dimensions"]
        norm = math.hypot(m[0], m[2])
        for point, (side, vertical) in zip(by_id[item["id"]].polygon, [(-1, -1), (1, -1), (1, 1), (-1, 1)]):
            expected = [(m[12] + side * w / 2 * m[0] / norm) * FT,
                        (m[13] + vertical * h / 2) * FT,
                        (m[14] + side * w / 2 * m[2] / norm) * FT]
            assert frame_to_world(point, room.frame) == pytest.approx(expected, abs=0.01)
    by_id = {obj.id: obj for obj in room.objects}
    for item in dto["objects"]:
        obj = by_id[item["id"]]
        assert frame_to_world(obj.center, room.frame) == pytest.approx([v * FT for v in item["transform"][12:15]], abs=0.01)
        assert obj.size == pytest.approx([v * FT for v in item["dimensions"]])
        # Object yaw and frame yaw must reconstruct its original local x axis.
        direction = rotate([1, 0, 0], obj.rotation_y)
        assert dir_to_world(direction, room.frame) == pytest.approx(item["transform"][:3], abs=1e-8)


@pytest.mark.parametrize("case", VECTORS["points"])
@pytest.mark.parametrize("as_model", [False, True])
def test_frame_points(case, as_model):
    frame = {"yaw_deg": case["yaw_deg"], "offset": case["offset_ft"]}
    if as_model:
        frame = Frame(**frame)
    world = frame_to_world(case["room_ft"], frame)
    assert world == pytest.approx(case["world_ft"], abs=1e-4)
    assert [v * 0.3048 for v in world] == pytest.approx(case["world_m"], abs=1e-4)
    assert world_to_room(world, frame) == pytest.approx(case["room_ft"], abs=1e-10)


@pytest.mark.parametrize("case", VECTORS["directions"])
def test_frame_directions(case):
    frame = Frame(yaw_deg=case["yaw_deg"], offset=[10, -4, 30])
    assert dir_to_world(case["room_dir"], frame) == pytest.approx(case["world_dir"], abs=1e-4)
    assert dir_to_world(case["room_dir"][::2], frame) == pytest.approx(case["world_dir"][::2], abs=1e-4)


@pytest.mark.parametrize("yaw", YAWS)
@pytest.mark.parametrize("offset", OFFSETS)
def test_normalization_is_invariant(yaw, offset):
    dto = synthetic(yaw, offset)
    original = deepcopy(dto)
    room, baseline = convert(dto), convert(synthetic())
    assert dto == original == room.captured_room
    assert room.source == "roomplan" and room.units == "ft"
    assert room.room_id == "r_test" and room.budget == 1500
    assert -180 < room.frame.yaw_deg <= 180
    assert room.dimensions.model_dump() == pytest.approx({"width": 18, "length": 13, "height": 9}, abs=0.01)
    wall_points = []
    for surface, expected in zip(room.surfaces, baseline.surfaces):
        assert surface.id == expected.id and surface.kind == expected.kind
        assert surface.absorption == ABSORPTION[surface.material]
        for point, expected_point in zip(surface.polygon, expected.polygon):
            assert point == pytest.approx(expected_point, abs=0.01)
        if surface.kind == "wall":
            wall_points.extend(surface.polygon)
            start, end = surface.polygon[:2]
            angle = math.degrees(math.atan2(end[2] - start[2], end[0] - start[0]))
            assert abs((angle + 45) % 90 - 45) < 0.5
        if surface.kind == "floor":
            assert all(point[1] == 0 for point in surface.polygon)
    assert [min(p[i] for p in wall_points) for i in range(3)] == pytest.approx([0, 0, 0], abs=1e-8)
    assert [max(p[i] for p in wall_points) for i in range(3)] == pytest.approx([18, 9, 13], abs=0.01)
    for obj, expected in zip(room.objects, baseline.objects):
        assert obj.center == pytest.approx(expected.center, abs=0.01)
    assert room.listener.position == pytest.approx([9, 3.6, 10.5], abs=0.01)
    assert room.listener.facing == pytest.approx(baseline.listener.facing, abs=1e-8)
    assert -room.listener.facing[1] >= math.cos(math.radians(45)) - 1e-8
    validate_listener(room.listener.position, room.listener.facing, room.dimensions)
    assert_round_trip(room, dto)


def test_listener_override_world_metres_and_clamping():
    yaw, offset = 17, (15, -2, -20)
    point = [v + shift for v, shift in zip(rotate([6 / FT, 2 / FT, 8 / FT], yaw), offset)]
    direction = rotate([1, 0, 0], yaw)
    room = convert(synthetic(yaw, offset), {"position": point, "facing": direction[::2]})
    assert room.listener.facing == pytest.approx([0, -1], abs=1e-8)
    world = frame_to_world(room.listener.position, room.frame)
    assert world[::2] == pytest.approx([v * FT for v in point[::2]], abs=1e-8)
    assert room.listener.position[1] == 3.6
    room = convert(synthetic(), {"position": [-20, 100, 100], "facing": [0, -2]})
    assert room.listener.position == pytest.approx([0, 3.6, 13])


@pytest.mark.parametrize("remove", [{"sofa"}, {"television"}, {"sofa", "television"}])
def test_missing_furniture_deterministic_facing(remove):
    normalized = []
    for yaw in YAWS:
        dto = synthetic(yaw, OFFSETS[2])
        dto["objects"] = [obj for obj in dto["objects"] if obj["category"] not in remove]
        room = convert(dto)
        assert room.listener.facing == pytest.approx([0, -1], abs=1e-8)
        if "sofa" in remove:
            assert "no sofa detected; listener at room centre" in room.warnings
            assert room.listener.position == pytest.approx([room.dimensions.width / 2, 3.6, room.dimensions.length / 2])
        normalized.append(room.listener.position)
    for position in normalized:
        assert position == pytest.approx(normalized[0], abs=0.01)


def test_largest_sofa_and_ambiguous_facing():
    dto = synthetic()
    small = deepcopy(dto["objects"][0])
    small.update(id="small-sofa", dimensions=[1, 2, 1])
    small["transform"][12] = 1
    dto["objects"].insert(0, small)
    assert convert(dto).listener.position == pytest.approx([9, 3.6, 10.5])
    dto["objects"] = [dto["objects"][1]]
    dto["objects"][0]["transform"][14] = 6.5 / FT
    room = convert(dto)
    assert "listener facing is ambiguous; using farthest wall" in room.warnings
    assert math.hypot(*room.listener.facing) == pytest.approx(1)


def test_floor_level_and_validator_warnings():
    dto = synthetic()
    dto["surfaces"][-1]["transform"][13] = -0.5
    room = convert(dto)
    assert room.dimensions.height == pytest.approx(9 + 0.5 * FT)
    assert room.frame.offset[1] == pytest.approx(-0.5 * FT)
    assert_round_trip(room, dto)
    dto["surfaces"].pop()
    assert "no floor" in convert(dto).warnings


@pytest.mark.parametrize("problem, message", [
    ("format", "format must be sweetspot.roomplan.v1"),
    ("walls", "fewer than 3 walls"),
    ("translation", "translation component exceeds 100 m"),
    ("nan", "transform must contain 16 finite numbers"),
    ("short", "transform must contain 16 finite numbers"),
    ("missing", "surface missing transform"),
])
def test_invalid_dto(problem, message):
    dto = synthetic()
    if problem == "format":
        dto["format"] = "wrong"
    elif problem == "walls":
        dto["surfaces"] = dto["surfaces"][:2]
    elif problem == "translation":
        dto["objects"][0]["transform"][12] = 300
    elif problem == "nan":
        dto["surfaces"][0]["transform"][12] = float("nan")
    elif problem == "short":
        dto["surfaces"][0]["transform"].pop()
    elif problem == "missing":
        del dto["surfaces"][0]["transform"]
    with pytest.raises(ValueError, match=message):
        convert(dto)


@pytest.mark.parametrize("listener", [
    {"position": [0, 1], "facing": [0, -1]},
    {"position": [0, 1, 2], "facing": [0, 0]},
    {"position": [0, 1, 2], "facing": [float("nan"), 1]},
])
def test_invalid_listener(listener):
    with pytest.raises(ValueError):
        convert(synthetic(), listener)


def test_sample_fixture_round_trip():
    dto = json.loads((ROOT / "fixtures" / "roomplan_sample.json").read_text())
    room = convert(dto)
    assert room.captured_room == dto
    assert_round_trip(room, dto)


def test_scan_endpoints(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    monkeypatch.setenv("PRODUCTS_BACKEND", "stub")
    monkeypatch.setenv("MATERIALS_BACKEND", "mock")
    request = json.loads((SAMPLES / "post_rooms_request.example.json").read_text())
    with TestClient(create_app()) as client:
        session_id = client.post("/sessions").json()["session_id"]
        request["session_id"] = session_id
        response = client.post("/rooms", json=request)
        assert response.status_code == 200, response.text
        room = response.json()
        assert room["source"] == "roomplan" and room["frame"] is not None
        assert room["captured_room"] == request["captured_room"]
        assert room["session_id"] == session_id and room["budget"] == request["budget"]
        dto = request["captured_room"]
        expected_ids = {item["id"] for item in dto["surfaces"] if item["category"] != "floor"} | {"floor", "ceiling"}
        assert {surface["id"] for surface in room["surfaces"]} == expected_ids
        assert {obj["id"] for obj in room["objects"]} == {obj["id"] for obj in dto["objects"]}
        assert client.get(f"/sessions/{session_id}").json() == {
            "session_id": session_id, "status": "ready", "room_id": room["room_id"]}
        path = f"/rooms/{room['room_id']}"
        assert client.get(path).json() == room
        targets = client.get(path + "/photo-targets")
        assert targets.status_code == 200
        assert {target["surface_id"] for target in targets.json()} == {
            surface["id"] for surface in room["surfaces"] if surface["kind"] in {"wall", "floor", "ceiling"}}
        assert len(targets.json()) == 6
        optimized = client.post(path + "/optimize", json={})
        assert optimized.status_code == 200
        speakers = optimized.json()["layout"]["speakers"]
        assert {speaker["role"] for speaker in speakers} == {"L", "R", "C", "LFE", "Ls", "Rs"}
        assert len(speakers) == 6
        bounds = [room["dimensions"][key] for key in ("width", "height", "length")]
        assert all(0 <= v <= limit for speaker in speakers for v, limit in zip(speaker["position"], bounds))
        request["captured_room"]["format"] = "wrong"
        invalid = client.post("/rooms", json=request)
        assert invalid.status_code == 422
        assert "format must be sweetspot.roomplan.v1" in invalid.json()["detail"]
