"""Ephemeral pairing sessions."""
import secrets
import time
from collections.abc import Callable

from . import store

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LIFETIME = 30 * 60
now: Callable[[], float] = time.time
_sessions: dict[str, dict] = {}


def create() -> dict:
    code = "".join(secrets.choice(ALPHABET) for _ in range(6))
    while any(item["code"] == code for item in _sessions.values()):
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
    session_id = store.new_id("s")
    item = {"session_id": session_id, "code": code, "expires_at": now() + LIFETIME, "room_id": None, "linked_at": None}
    _sessions[session_id] = item
    return item


def get(session_id: str) -> dict | None:
    item = _sessions.get(session_id)
    if item is None:
        return None
    if now() >= item["expires_at"]:
        status = "expired"
    elif item["room_id"]:
        status = "ready"
    else:
        status = "linked" if item["linked_at"] else "waiting"
    return {**item, "status": status}


def link_room(session_id: str, room_id: str) -> str:
    item = get(session_id)
    if item is None:
        return "missing"
    if item["status"] == "expired":
        return "expired"
    _sessions[session_id]["room_id"] = room_id
    return "ready"


def link(session_id: str) -> str:
    """Phone handshake right after it scans the QR: marks the session linked."""
    item = get(session_id)
    if item is None:
        return "missing"
    if item["status"] == "expired":
        return "expired"
    if _sessions[session_id]["linked_at"] is None:
        _sessions[session_id]["linked_at"] = now()
    return get(session_id)["status"]


def by_code(code: str) -> dict | None:
    for item in _sessions.values():
        if item["code"] == code.upper() and get(item["session_id"])["status"] != "expired":
            return item
    return None
