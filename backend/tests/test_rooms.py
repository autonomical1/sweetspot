import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app import sessions
from backend.app.main import create_app
from backend.app.schemas import Room


def test_rect_and_demo(data_dir, fixtures_dir):
    sessions._sessions.clear()
    client = TestClient(create_app())
    assert client.get("/health").json() == {"ok": True}
    assert client.get("/rooms/missing").status_code == 404
    assert client.post("/rooms/rect", json={"width": 2, "length": 15}).status_code == 422
    assert client.post("/rooms/rect", json={"width": 101, "length": 15}).status_code == 422
    assert client.post("/rooms/rect", json={"width": 12, "length": 15, "session_id": "s_missing"}).status_code == 404
    session_id = client.post("/sessions").json()["session_id"]
    room = client.post("/rooms/rect", json={"width": 12, "length": 15, "session_id": session_id}).json()
    assert room["listener"] == {"position": [6, 3.6, 10.5], "facing": [0, -1]}
    assert [s["id"] for s in room["surfaces"]] == ["wall_n", "wall_s", "wall_w", "wall_e", "floor", "ceiling"]
    assert all(len(s["absorption"]) == 6 for s in room["surfaces"])
    assert client.get(f'/rooms/{room["room_id"]}').json() == room
    assert client.get(f"/sessions/{session_id}").json()["room_id"] == room["room_id"]
    targets = client.get(f'/rooms/{room["room_id"]}/photo-targets').json()
    assert len(targets) == 6 and targets[-2]["label"] == "Floor"
    patch = f'/rooms/{room["room_id"]}/listener'
    assert client.patch(patch, json={"position": [6, 3.6, 11], "facing": [0, -1]}).json()["listener"]["position"][2] == 11
    assert client.patch(patch, json={"position": [99, 3.6, 11], "facing": [0, -1]}).status_code == 400
    demo = client.post("/rooms/demo", json={}).json()
    fixture = json.loads((fixtures_dir / "room_demo.json").read_text())
    assert Room.model_validate(demo)
    assert {**demo, "room_id": fixture["room_id"]} == Room.model_validate(fixture).model_dump(mode="json")
    assert client.get(f'/rooms/{demo["room_id"]}').json() == demo


def test_full_room_and_expiry(data_dir, room_rect, monkeypatch):
    sessions._sessions.clear()
    client = TestClient(create_app())
    room = client.post("/rooms", json=room_rect)
    assert room.status_code == 200
    assert room.json() == room_rect
    assert client.post("/rooms", json={"surfaces": []}).status_code == 422
    assert client.post("/rooms", json={"captured_room": {"format": "sweetspot.roomplan.v1"}}).status_code == 501
    tick = [1.0]
    monkeypatch.setattr(sessions, "now", lambda: tick[0])
    session_id = client.post("/sessions").json()["session_id"]
    tick[0] += 1800
    assert client.post("/rooms/demo", json={"session_id": session_id}).status_code == 410


def test_persistence_corruption_and_concurrency(data_dir):
    client = TestClient(create_app())
    def create(_):
        result = client.post("/rooms/rect", json={"width": 12, "length": 15})
        assert result.status_code == 200
        return result.json()["room_id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(create, range(20)))
    assert len(set(ids)) == 20
    fresh = TestClient(create_app())
    assert fresh.get(f"/rooms/{ids[0]}").status_code == 200
    (data_dir / "rooms" / f"{ids[0]}.json").write_text("broken")
    result = fresh.get(f"/rooms/{ids[0]}")
    assert result.status_code == 500 and "detail" in result.json()
