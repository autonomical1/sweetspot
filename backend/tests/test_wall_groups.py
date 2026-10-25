"""Photo targets group any number of walls into front/left/back/right (max 6 photos)."""
import copy

from fastapi.testclient import TestClient

from backend.app import store
from backend.app.main import app
from backend.app.walls import wall_groups


def _split_wall_room(client: TestClient) -> str:
    room_id = client.post("/rooms/demo", json={}).json()["room_id"]
    room = store.load_room(room_id)
    extra = []
    for surface in room.surfaces:
        if surface.kind == "wall":
            twin = copy.deepcopy(surface)
            twin.id = f"{surface.id}_extra"
            extra.append(twin)
    room.surfaces.extend(extra)
    store.save_room(room)
    return room_id


def test_more_than_four_walls_still_give_one_photo_per_direction(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    client = TestClient(app)
    room_id = _split_wall_room(client)
    targets = client.get(f"/rooms/{room_id}/photo-targets").json()
    labels = [t["label"] for t in targets]
    assert sorted(labels) == sorted(["Front wall", "Left wall", "Back wall", "Right wall", "Floor", "Ceiling"])
    assert len(labels) <= 6
    assert len({t["surface_id"] for t in targets}) == len(targets)
    assert all(len(group) == 2 for group in wall_groups(store.load_room(room_id)).values())
