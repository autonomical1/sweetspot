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


@pytest.mark.parametrize("room_name", ["room_rect.json", "room_demo.json"])
def test_optimize_contract(engine_impl, room_name):
    room = fixture_room(room_name); original = copy.deepcopy(room)
    result = engine_impl.optimize(room)
    assert_valid_layout_result(result, room)
    assert room == original
    assert result == engine_impl.optimize(room)


def test_engine_score_contract(engine_impl):
    room = fixture_room("room_rect.json")
    result = engine_impl.optimize(room)
    scores = []
    for _ in range(5):
        start = time.perf_counter(); scored = engine_impl.score(room, result["layout"]); scores.append((time.perf_counter() - start) * 1000)
        assert_valid_metrics(scored["metrics"], room)
    assert statistics.median(scores) < 100
    assert math.isclose(scored["metrics"]["score"], result["metrics"]["score"], abs_tol=1e-6)


@pytest.mark.parametrize("rect_request", [RectRequest(width=4, length=4, height=9), RectRequest(width=60, length=8, height=9), RectRequest(width=10, length=10, listener=[0.3, 3.6, 5], facing=[0, -1])])
def test_degenerate_rooms_do_not_raise(engine_impl, rect_request):
    room = build_rect(rect_request).model_dump()
    result = engine_impl.optimize(room)
    assert_valid_layout_result(result, room)


@pytest.mark.skipif("speakerplacer" not in __import__("importlib").util.find_spec("speakerplacer").name if __import__("importlib").util.find_spec("speakerplacer") else True, reason="real engine is not installed")
def test_real_engine_reflection_case():
    import speakerplacer
    room = build_rect(RectRequest(width=18, length=13, height=9, listener=[9, 3.6, 6.5], facing=[0, -1])).model_dump()
    # Image source at x=-3: reflected path is 12 ft, direct path is 6 ft.
    layout = {"speakers": [{"role": "L", "position": [3, 3.6, 6.5], "aim": [9, 3.6, 6.5]}]}
    metrics = speakerplacer.score(room, layout)["metrics"]
    reflection = next(item for item in metrics["reflections"] if item["speaker"] == "L" and item["surface_id"] == "wall_w")
    assert abs(reflection["delay_ms"] - ((12 - 6) / 1125 * 1000)) <= 0.15
    assert reflection["level_db"] <= 0
