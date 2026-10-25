from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.main import create_app


def test_layout_flow(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    monkeypatch.setenv("PRODUCTS_BACKEND", "stub")
    client = TestClient(create_app())
    room = client.post("/rooms/rect", json={"width": 12, "length": 15, "budget": 1500}).json()
    root = f'/rooms/{room["room_id"]}'
    assert client.get(root + "/layout").status_code == 404
    assert client.get(root + "/products").status_code == 404
    result = client.post(root + "/optimize", json={}).json()
    assert {s["role"] for s in result["layout"]["speakers"]} == {"L", "R", "C", "LFE", "Ls", "Rs"}
    assert client.get(root + "/layout").json() == result
    start = perf_counter()
    score = client.post(root + "/score", json={"layout": result["layout"]}).json()
    assert perf_counter() - start < 0.1
    assert score["metrics"] == result["metrics"]
    assert client.get(root + "/products?budget=0").status_code == 422
    assert client.get(root + "/products?budget=-1").status_code == 422
    products = client.get(root + "/products?budget=1000").json()
    assert products["budget"] == 1000 and products["total"] <= 1000
    assert TestClient(create_app()).get(root + "/layout").json() == result


def test_openapi_paths(data_dir):
    paths = TestClient(create_app()).get("/openapi.json").json()["paths"]
    for path in ("/health", "/sessions", "/sessions/{session_id}", "/sessions/by-code", "/rooms", "/rooms/rect",
                 "/rooms/demo", "/rooms/{room_id}", "/rooms/{room_id}/listener", "/rooms/{room_id}/photo-targets",
                 "/rooms/{room_id}/optimize", "/rooms/{room_id}/score", "/rooms/{room_id}/layout", "/rooms/{room_id}/products"):  # noqa: E501  # preserve behavior while retaining the existing expression
        assert path in paths


def test_materials_import_error_is_not_hidden(monkeypatch):
    monkeypatch.setattr(main.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(main.importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("missing dependency")))  # noqa: E501  # preserve behavior while retaining the existing expression
    with pytest.raises(ImportError, match="missing dependency"):
        create_app()
