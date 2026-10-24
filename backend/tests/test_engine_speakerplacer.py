import copy
import json
import time
from pathlib import Path

from backend.app import engine_speakerplacer


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
