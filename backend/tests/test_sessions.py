from fastapi.testclient import TestClient

from backend.app import sessions
from backend.app.main import create_app


def test_lifecycle(monkeypatch):
    sessions._sessions.clear()
    tick = [1000.0]
    monkeypatch.setattr(sessions, "now", lambda: tick[0])
    client = TestClient(create_app())
    item = client.post("/sessions").json()
    assert len(item["code"]) == 6
    assert item["pair_url"].endswith(item["session_id"])
    url = f'/sessions/{item["session_id"]}'
    assert client.get(url).json()["status"] == "waiting"
    assert client.post("/sessions/by-code", json={"code": item["code"].lower()}).json()["session_id"] == item["session_id"]  # noqa: E501  # preserve behavior while retaining the existing expression
    assert client.post("/sessions/by-code", json={"code": "NOPE"}).status_code == 404
    tick[0] += 1800
    assert client.get(url).json()["status"] == "expired"
    assert client.post("/sessions/by-code", json={"code": item["code"]}).status_code == 404
