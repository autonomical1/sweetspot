from __future__ import annotations

from fastapi.testclient import TestClient


def test_web_consumed_contract(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    monkeypatch.setenv("PRODUCTS_BACKEND", "stub")
    from backend.app.main import app

    with TestClient(app) as client:
        session = client.post("/sessions").json()
        assert {"session_id", "code", "expires_at", "pair_url"} <= session.keys()
        room_response = client.post("/rooms/demo", json={"session_id": session["session_id"]})
        assert room_response.status_code == 200
        room = room_response.json()
        assert {"room_id", "dimensions", "listener", "surfaces", "warnings"} <= room.keys()
        assert {"position", "facing"} <= room["listener"].keys()

        optimized_response = client.post(f"/rooms/{room['room_id']}/optimize", json={})
        assert optimized_response.status_code == 200
        optimized = optimized_response.json()
        assert {"layout", "metrics"} <= optimized.keys()
        assert {"speakers"} <= optimized["layout"].keys()
        assert {"role", "position", "aim"} <= optimized["layout"]["speakers"][0].keys()
        assert isinstance(optimized["metrics"], dict)

        scored = client.post(f"/rooms/{room['room_id']}/score", json={"layout": optimized["layout"]})
        assert scored.status_code == 200
        assert isinstance(scored.json().get("metrics"), dict)
        saved = client.get(f"/rooms/{room['room_id']}/layout")
        assert saved.status_code == 200
        assert {"layout", "metrics"} <= saved.json().keys()

        products = client.get(f"/rooms/{room['room_id']}/products", params={"budget": 1500})
        assert products.status_code == 200
        product_payload = products.json()
        assert {"budget", "total", "items"} <= product_payload.keys()
        assert product_payload["total"] <= product_payload["budget"]
        for item in product_payload["items"]:
            assert {"role", "title", "price", "link", "source"} <= item.keys()

        status = client.get(f"/sessions/{session['session_id']}")
        assert status.status_code == 200
        assert {"session_id", "status", "room_id"} <= status.json().keys()
