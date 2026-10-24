import io

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import materials, store
from backend.app.main import create_app


def _client(monkeypatch):
    monkeypatch.setenv("MATERIALS_BACKEND", "mock")
    client = TestClient(create_app())
    room = client.post("/rooms/rect", json={"width": 12, "length": 15}).json()
    return client, room["room_id"]


def _upload(client, room_id, surface_id, data=None):
    if data is None:
        stream = io.BytesIO()
        Image.new("RGB", (30, 20), "blue").save(stream, "PNG")
        data = stream.getvalue()
    return client.post(f"/rooms/{room_id}/photos", data={"surface_id": surface_id},
                       files={"file": ("photo.png", data, "image/png")})


def test_upload_validation(data_dir, monkeypatch):
    client, room_id = _client(monkeypatch)
    assert _upload(client, "r_missing", "floor").status_code == 404
    assert _upload(client, room_id, "bad_surface").status_code == 422
    assert _upload(client, room_id, "floor", b"bad").status_code == 400
    assert _upload(client, room_id, "floor").json() == {"stored": True}
    saved = store.list_photos(room_id)["floor"]
    with Image.open(saved) as image:
        assert image.format == "JPEG"


def test_materials_mock_persistence_and_idempotence(data_dir, monkeypatch):
    client, room_id = _client(monkeypatch)
    route = f"/rooms/{room_id}/materials"
    assert client.post("/rooms/r_missing/materials", json={}).status_code == 404
    assert client.post(route, json={}).json() == {"surfaces": []}
    initial = {s["id"]: s for s in client.get(f"/rooms/{room_id}").json()["surfaces"]}
    _upload(client, room_id, "floor")
    _upload(client, room_id, "wall_n")
    first = client.post(route, json={}).json()
    assert first == {"surfaces": [
        {"surface_id": "floor", "material": "hardwood", "confidence": 0.9, "applied": True},
        {"surface_id": "wall_n", "material": "drywall", "confidence": 0.8, "applied": True},
    ]}
    assert client.post(route, json={}).json() == first
    saved = {s.id: s for s in store.load_room(room_id).surfaces}
    assert saved["floor"].material == "hardwood"
    assert saved["floor"].absorption == materials.ABSORPTION["hardwood"]
    for surface_id in initial.keys() - {"floor", "wall_n"}:
        assert saved[surface_id].model_dump() == initial[surface_id]
    assert TestClient(create_app()).get(f"/rooms/{room_id}").json()["surfaces"][4]["material"] == "hardwood"


def test_low_confidence_and_unknown_not_applied(data_dir, monkeypatch):
    client, room_id = _client(monkeypatch)
    _upload(client, room_id, "floor")
    original = store.load_room(room_id).surfaces[4].model_dump()
    monkeypatch.setattr(materials, "classify_materials", lambda photos: [
        {"surface_id": "floor", "material": "carpet", "confidence": 0.49}])
    result = client.post(f"/rooms/{room_id}/materials", json={}).json()["surfaces"]
    assert result[0]["applied"] is False
    assert store.load_room(room_id).surfaces[4].model_dump() == original
    monkeypatch.setattr(materials, "classify_materials", lambda photos: [
        {"surface_id": "floor", "material": "unknown", "confidence": 1.0}])
    assert client.post(f"/rooms/{room_id}/materials", json={}).json()["surfaces"][0]["applied"] is False
    assert store.load_room(room_id).surfaces[4].model_dump() == original
