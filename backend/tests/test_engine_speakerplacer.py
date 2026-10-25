import copy
import json
import time
from pathlib import Path

from backend.app import engine_speakerplacer
from backend.app.stubs import engine_stub

ROOT = Path(__file__).resolve().parents[2]


def fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / name).read_text())


def test_optimize_uses_real_engine_and_cache():
    room = fixture("room_rect.json")
    engine_speakerplacer.clear_cache()
    first = engine_speakerplacer.optimize(copy.deepcopy(room))
    start = time.perf_counter()
    second = engine_speakerplacer.optimize(copy.deepcopy(room))
    assert time.perf_counter() - start < .1
    assert first == second
    assert {item["role"] for item in first["layout"]["speakers"]} == {"L", "R", "C", "LFE", "Ls", "Rs"}
    assert first["metrics"]["engine"]["name"] == "speakerplacer"
    assert next(item for item in first["layout"]["speakers"] if item["role"] == "LFE")["position"][1] == 1.0
    assert engine_speakerplacer.score(room, first["layout"])["metrics"]["score"] == first["metrics"]["score"]
    json.dumps(first)


def test_engine_error_is_a_warning(monkeypatch):
    room = fixture("room_rect.json")
    engine_speakerplacer.clear_cache()

    def fail(*args, **kwargs):
        raise RuntimeError("test failure")

    monkeypatch.setattr(engine_speakerplacer.speakerplacer, "optimize_layout", fail)
    result = engine_speakerplacer.optimize(room)
    assert any("speakerplacer failed: RuntimeError: test failure" == item for item in result["metrics"]["warnings"])
    assert result["layout"] == engine_stub.optimize(room)["layout"]


def test_object_avoidance_slides_along_the_same_wall():
    room = fixture("room_demo.json")
    # The sofa occupies x=5.5..12.5 at the back wall.  An LFE placed there
    # must move along x while retaining its south-wall inset and height.
    position, warnings = engine_speakerplacer._avoid_objects([9.0, 1.0, 12.9], room, "LFE")
    assert position[1] == 1.0
    assert position[2] == 12.9
    assert not engine_speakerplacer._inside_object(position, room["objects"][0])
    assert any("LFE slid to avoid object obj_sofa" == warning for warning in warnings)


def test_object_avoidance_clears_all_objects_at_once():
    room = {"dimensions": {"width": 18.0, "length": 13.0, "height": 9.0},
            "objects": [{"id": "a", "center": [6.0, 2.0, 1.0], "size": [4.0, 4.0, 2.0], "rotation_y": 0.0},
                        {"id": "b", "center": [9.5, 2.0, 1.0], "size": [3.5, 4.0, 2.0], "rotation_y": 0.0}]}
    position, warnings = engine_speakerplacer._avoid_objects([7.0, 1.0, 0.16], room, "LFE")
    assert not any(engine_speakerplacer._inside_object(position, obj) for obj in room["objects"])
    assert position[1] == 1.0 and position[2] == 0.16  # stays on the north wall at the same height
    assert position[0] < 4.0 or position[0] > 11.25
    assert any("slid" in warning for warning in warnings)
