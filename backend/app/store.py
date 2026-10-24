"""File-backed storage (docs/API.md section 7). Shared module: no task edits it."""
import json
import os
import re
import secrets
from pathlib import Path

from .schemas import Room

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class NotFound(KeyError):
    pass


def data_dir() -> Path:
    p = Path(os.environ.get("DATA_DIR", "data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(8)}"


def _safe(name: str) -> str:
    if not _SAFE.match(name):
        raise NotFound(name)
    return name


def _room_path(room_id: str) -> Path:
    d = data_dir() / "rooms"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{_safe(room_id)}.json"


def save_room(room: Room) -> None:
    _room_path(room.room_id).write_text(room.model_dump_json(indent=2), encoding="utf-8")


def load_room(room_id: str) -> Room:
    p = _room_path(room_id)
    if not p.exists():
        raise NotFound(room_id)
    return Room.model_validate_json(p.read_text(encoding="utf-8"))


def save_layout(room_id: str, result: dict) -> None:
    _safe(room_id)
    p = data_dir() / "rooms" / f"{room_id}.layout.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=2), encoding="utf-8")


def load_layout(room_id: str) -> dict | None:
    p = data_dir() / "rooms" / f"{_safe(room_id)}.layout.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_photo(room_id: str, surface_id: str, data: bytes) -> Path:
    d = data_dir() / "photos" / _safe(room_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{_safe(surface_id)}.jpg"
    p.write_bytes(data)
    return p


def list_photos(room_id: str) -> dict[str, Path]:
    d = data_dir() / "photos" / _safe(room_id)
    return {p.stem: p for p in sorted(d.glob("*.jpg"))} if d.exists() else {}
