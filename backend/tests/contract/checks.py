"""Readable, implementation-independent checks for the shared contracts."""
import math
from typing import Any

from backend.app.schemas import LayoutResult, Room

MATERIALS = {"drywall", "glass", "brick", "carpet", "hardwood", "tile", "curtain", "unknown"}
ROLES = {"L", "R", "C", "LFE", "Ls", "Rs"}
BANDS = {"125", "250", "500", "1000", "2000", "4000"}


def _finite_vec(value: Any, size: int, label: str) -> None:
    assert isinstance(value, (list, tuple)) and len(value) == size, f"{label} must be a finite {size}-list"
    assert all(isinstance(x, (int, float)) and math.isfinite(x) for x in value), f"{label} must be a finite {size}-list"


def assert_valid_room(obj: Any) -> None:
    try:
        room = Room.model_validate(obj)
    except Exception as exc:
        raise AssertionError(f"room does not satisfy schemas.Room: {exc}") from exc
    assert room.units == "ft", "room units must be ft"
    assert room.surfaces, "room must have surfaces"
    assert room.dimensions.width > 0 and room.dimensions.length > 0 and room.dimensions.height > 0, "room dimensions must be positive"
    for surface in room.surfaces:
        assert len(surface.polygon) >= 3, f"surface {surface.id} polygon is too short"
        for point in surface.polygon:
            _finite_vec(point, 3, f"surface {surface.id} polygon point")
        assert set(surface.absorption) >= BANDS, f"surface {surface.id} absorption is missing octave bands"
        assert all(0 <= float(value) <= 1 for value in surface.absorption.values()), f"surface {surface.id} absorption is out of range"
    _finite_vec(room.listener.position, 3, "listener position")
    _finite_vec(room.listener.facing, 2, "listener facing")


def assert_valid_metrics(obj: Any, room: Any = None) -> None:
    assert isinstance(obj, dict), "metrics must be an object"
    assert isinstance(obj.get("score"), (int, float)) and math.isfinite(obj["score"]), "metrics.score must be finite"
    reflections = obj.get("reflections", [])
    assert isinstance(reflections, list), "metrics.reflections must be a list"
    surface_ids = {s.id for s in Room.model_validate(room).surfaces} if room is not None else None
    for reflection in reflections:
        assert isinstance(reflection, dict), "reflection must be an object"
        assert isinstance(reflection.get("speaker"), str), "reflection speaker is required"
        assert isinstance(reflection.get("surface_id"), str), "reflection surface_id is required"
        if surface_ids is not None:
            assert reflection["surface_id"] in surface_ids, f"unknown reflection surface {reflection['surface_id']}"
        assert isinstance(reflection.get("delay_ms"), (int, float)) and math.isfinite(reflection["delay_ms"]) and reflection["delay_ms"] >= 0, "reflection delay_ms must be non-negative"
        assert isinstance(reflection.get("level_db"), (int, float)) and reflection["level_db"] <= 6, "reflection level_db is too high"
        _finite_vec(reflection.get("point"), 3, "reflection point")
    assert isinstance(obj.get("warnings", []), list) and all(isinstance(w, str) for w in obj.get("warnings", [])), "metrics.warnings must be strings"


def assert_valid_layout_result(obj: Any, room: Any = None, full_51: bool = True) -> None:
    try:
        result = LayoutResult.model_validate(obj)
    except Exception as exc:
        raise AssertionError(f"layout result does not satisfy schemas.LayoutResult: {exc}") from exc
    speakers = result.layout.speakers
    roles = [speaker.role for speaker in speakers]
    if full_51:
        assert set(roles) == ROLES and len(roles) == 6, "layout must contain six unique 5.1 roles"
    assert len(roles) == len(set(roles)), "speaker roles must be unique"
    room_model = Room.model_validate(room) if room is not None else None
    if room_model:
        width, length, height = room_model.dimensions.width, room_model.dimensions.length, room_model.dimensions.height
    for speaker in speakers:
        _finite_vec(speaker.position, 3, f"speaker {speaker.role} position")
        _finite_vec(speaker.aim, 3, f"speaker {speaker.role} aim")
        if room_model:
            x, y, z = speaker.position
            assert 0 <= x <= width and 0 <= y <= height and 0 <= z <= length, f"speaker {speaker.role} is outside room"
    if result.layout.screen is not None:
        screen = result.layout.screen
        assert screen.width > 0 and screen.height > 0, "screen dimensions must be positive"
        _finite_vec(screen.center, 3, "screen center")
        if room_model:
            assert screen.wall_id in {s.id for s in room_model.surfaces}, "screen wall_id must exist in room"
    assert_valid_metrics(result.metrics, room)


def assert_valid_products(obj: Any, budget: float, layout: Any = None) -> None:
    assert isinstance(obj, dict) and {"budget", "total", "items"} <= set(obj), "products result needs budget, total, items"
    assert abs(float(obj["budget"]) - budget) <= 0.01, "products budget differs from requested budget"
    assert isinstance(obj["total"], (int, float)) and obj["total"] <= budget, "products total must not exceed budget"
    assert isinstance(obj["items"], list), "products items must be a list"
    prices = 0.0
    item_roles = set()
    for item in obj["items"]:
        for key in ("role", "title", "currency", "link", "source"):
            assert key in item and isinstance(item[key], str), f"product item missing string {key}"
        assert "thumbnail" in item and (item["thumbnail"] is None or isinstance(item["thumbnail"], str)), "thumbnail must be string or null"
        assert isinstance(item.get("price"), (int, float)) and math.isfinite(item["price"]) and item["price"] >= 0, "product price must be non-negative"
        prices += item["price"]
        item_roles.add(item["role"])
    assert abs(float(obj["total"]) - prices) <= 0.01, "products total does not equal item prices"
    if layout is not None:
        for speaker in layout.get("speakers", []):
            assert speaker["role"] in item_roles, f"no product for speaker role {speaker['role']}"


def assert_valid_classification(items: Any, expected_ids: Any) -> None:
    expected = set(expected_ids)
    assert isinstance(items, list), "classification must be a list"
    assert {item.get("surface_id") for item in items} == expected, "classification ids do not match expected ids"
    for item in items:
        assert item.get("material") in MATERIALS, f"invalid material for {item.get('surface_id')}"
        assert isinstance(item.get("confidence"), (int, float)) and 0 <= item["confidence"] <= 1, "confidence must be between 0 and 1"
