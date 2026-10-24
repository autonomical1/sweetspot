import sys
from types import SimpleNamespace

from backend.app import engine, products
from backend.app.schemas import Room


def test_runtime_fallback(room_rect, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("offline")
    monkeypatch.setenv("ENGINE_BACKEND", "auto")
    monkeypatch.setenv("PRODUCTS_BACKEND", "auto")
    monkeypatch.setitem(sys.modules, "speakerplacer", SimpleNamespace(optimize=fail, score=fail))
    monkeypatch.setitem(sys.modules, "products", SimpleNamespace(get_products=fail))
    room = Room.model_validate(room_rect)
    result = engine.run_optimize(room)
    assert "fallback" in " ".join(result["metrics"]["warnings"])
    assert "fallback" in " ".join(engine.run_score(room, result["layout"])["metrics"]["warnings"])
    output = products.run_products(result["layout"], 1000)
    assert output["total"] <= 1000 and output["warnings"]


def test_invalid_engine_results_fall_back(room_rect, monkeypatch):
    monkeypatch.setenv("ENGINE_BACKEND", "auto")
    monkeypatch.setitem(sys.modules, "speakerplacer", SimpleNamespace(optimize=lambda *args: {"layout": "bad"},
                                                                  score=lambda *args: {"metrics": "bad"}))
    room = Room.model_validate(room_rect)
    optimized = engine.run_optimize(room)
    assert "engine fallback: invalid result" in optimized["metrics"]["warnings"]
    scored = engine.run_score(room, optimized["layout"])
    assert "engine fallback: invalid result" in scored["metrics"]["warnings"]


def test_products_stub_total_never_exceeds_budget():
    from backend.app.stubs import products_stub
    layout = {"speakers": [{"role": r} for r in ("L", "R", "C", "LFE", "Ls", "Rs")], "screen": None}
    for budget in (0.034, 0.5, 1.0, 17.77, 1500.0):
        result = products_stub.get_products(layout, budget)
        assert result["total"] <= budget
        assert all(item["price"] >= 0 for item in result["items"])
