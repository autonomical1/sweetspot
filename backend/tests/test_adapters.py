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
