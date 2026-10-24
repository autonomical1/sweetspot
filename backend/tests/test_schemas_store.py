import pytest

from backend.app import store
from backend.app.schemas import Room


def test_fixture_validates(room_rect):
    room = Room.model_validate(room_rect)
    assert room.units == "ft" and room.dimensions.width == 12.0 and len(room.surfaces) == 6


def test_store_roundtrip(data_dir, room_rect):
    room = Room.model_validate(room_rect)
    store.save_room(room)
    assert store.load_room(room.room_id) == room
    assert store.load_layout(room.room_id) is None
    store.save_layout(room.room_id, {"layout": {"speakers": []}})
    assert store.load_layout(room.room_id)["layout"]["speakers"] == []


def test_store_rejects_bad_ids(data_dir):
    with pytest.raises(store.NotFound):
        store.load_room("../etc/passwd")
    with pytest.raises(store.NotFound):
        store.load_room("r_missing")


def test_photos(data_dir):
    store.save_photo("r_a", "floor", b"x")
    assert list(store.list_photos("r_a")) == ["floor"]
    assert store.list_photos("r_none") == {}
