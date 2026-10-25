import copy
import json
import math
import statistics
import time
from pathlib import Path

import pytest

from backend.app.rooms import RectRequest, build_rect

from .checks import assert_valid_layout_result, assert_valid_metrics

ROOT = Path(__file__).resolve().parents[3]


def fixture_room(name):
    return json.loads((ROOT / "fixtures" / name).read_text())


def assert_geometry(room, layout):
    listener = room["listener"]["position"]
    fx, fz = room["listener"]["facing"]
    norm = math.hypot(fx, fz)
    assert norm > 0, "listener facing must be nonzero"
    fx, fz = fx / norm, fz / norm
    left = (fz, -fx)
    for speaker in layout["speakers"]:
        role = speaker["role"]
        x, y, z = speaker["position"]
        dx, dz = x - listener[0], z - listener[2]
        forward = dx * fx + dz * fz
        side = dx * left[0] + dz * left[1]
        angle = math.degrees(math.atan2(abs(side), forward))
        if role in ("L", "R"):
            assert 25 <= angle <= 35 and (side > 0 if role == "L" else side < 0), f"{role} front angle {angle:.2f}, side {side:.2f}"  # noqa: E501  # preserve behavior while retaining the existing expression
        elif role == "C":
            assert angle <= 5, f"C angle {angle:.2f}"
        elif role in ("Ls", "Rs"):
            assert 90 <= angle <= 135 and (side > 0 if role == "Ls" else side < 0), f"{role} surround angle {angle:.2f}, side {side:.2f}"  # noqa: E501  # preserve behavior while retaining the existing expression
        for obj in room.get("objects", []):
            cx, cy, cz = obj["center"]
            theta = math.radians(obj.get("rotation_y", 0))
            local_x = (x - cx) * math.cos(theta) - (z - cz) * math.sin(theta)
            local_z = (x - cx) * math.sin(theta) + (z - cz) * math.cos(theta)
            sx, sy, sz = obj["size"]
            assert not (abs(local_x) < sx / 2 and abs(y - cy) < sy / 2 and abs(local_z) < sz / 2), f"{role} inside object {obj['id']}"  # noqa: E501  # preserve behavior while retaining the existing expression


@pytest.mark.parametrize("room_name", ["room_rect.json", "room_demo.json"])
def test_optimize_contract(engine_impl, room_name):
    room = fixture_room(room_name)
    original = copy.deepcopy(room)
    result = engine_impl.optimize(room)
    assert_valid_layout_result(result, room)
    assert_geometry(room, result["layout"])
    assert room == original
    assert result == engine_impl.optimize(room)


def test_engine_score_contract(engine_impl):
    room = fixture_room("room_rect.json")
    result = engine_impl.optimize(room)
    scores = []
    for _ in range(5):
        start = time.perf_counter()
        scored = engine_impl.score(room, result["layout"])
        scores.append((time.perf_counter() - start) * 1000)  # noqa: E501  # preserve behavior while retaining the existing expression
        assert_valid_metrics(scored["metrics"], room)
    assert statistics.median(scores) < 100
    assert math.isclose(scored["metrics"]["score"], result["metrics"]["score"], abs_tol=1e-6)


@pytest.mark.parametrize("rect_request", [RectRequest(width=4, length=4, height=9), RectRequest(width=60, length=8, height=9), RectRequest(width=10, length=10, listener=[0.3, 3.6, 5], facing=[0, -1])])  # noqa: E501  # preserve behavior while retaining the existing expression
def test_degenerate_rooms_do_not_raise(engine_impl, rect_request):
    room = build_rect(rect_request).model_dump()
    result = engine_impl.optimize(room)
    assert_valid_layout_result(result, room)
    if rect_request.listener == [0.3, 3.6, 5]:
        # Listener 0.3 ft from the west wall: no position exists 25-35 deg to the listener's left, so the
        # contract (TESTING.md 3.3) only requires a valid layout plus an explanatory warning, not ITU geometry.
        assert result["metrics"].get("warnings"), "degenerate placement must explain itself in metrics.warnings"
        return
    assert_geometry(room, result["layout"])


@pytest.mark.skipif(__import__("importlib").util.find_spec("backend.app.engine_speakerplacer") is None, reason="speakerplacer adapter (backend/app/engine_speakerplacer.py) is not present")  # noqa: E501  # preserve behavior while retaining the existing expression
def test_real_engine_reflection_case():
    from backend.app import engine_speakerplacer as speakerplacer
    room = build_rect(RectRequest(width=18, length=13, height=9, listener=[9, 3.6, 6.5], facing=[0, -1])).model_dump()
    # Image source at x=-3: reflected path is 12 ft, direct path is 6 ft.
    layout = {"speakers": [{"role": "L", "position": [3, 3.6, 6.5], "aim": [9, 3.6, 6.5]}]}
    metrics = speakerplacer.score(room, layout)["metrics"]
    reflection = next(item for item in metrics["reflections"] if item["speaker"] == "L" and item["surface_id"] == "wall_w")  # noqa: E501  # preserve behavior while retaining the existing expression
    assert abs(reflection["delay_ms"] - ((12 - 6) / 1125 * 1000)) <= 0.15
    assert reflection["level_db"] <= 0
