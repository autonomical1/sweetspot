"""Room creation and layout endpoints."""
import importlib
import importlib.util
import json
import math
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from . import engine, engine3d, products, refine, sessions, store
from .schemas import Dimensions, Listener, Room, Surface

router = APIRouter()
ABSORPTION = {"125": 0.05, "250": 0.06, "500": 0.08, "1000": 0.09, "2000": 0.09, "4000": 0.09}
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


class RectRequest(BaseModel):
    width: float = Field(ge=3, le=100, allow_inf_nan=False)
    length: float = Field(ge=3, le=100, allow_inf_nan=False)
    height: float = Field(default=9, ge=3, le=100, allow_inf_nan=False)
    listener: list[float] | None = None
    facing: list[float] | None = None
    budget: float | None = None
    session_id: str | None = None


class ListenerRequest(BaseModel):
    position: list[float]
    facing: list[float]


class LayoutRequest(BaseModel):
    layout: dict


class OptimizeRequest(BaseModel):
    options: "OptimizeOptions" = Field(default_factory=lambda: OptimizeOptions())


class OptimizeOptions(BaseModel):
    preset: str = "5.1"
    standard: str = "dolby"
    refine: bool = True


def _room(room_id: str) -> Room:
    try:
        return store.load_room(room_id)
    except store.NotFound:
        raise HTTPException(404, "room not found") from None
    except Exception:
        raise HTTPException(500, "stored room is invalid") from None


def _session_check(session_id: str | None) -> None:
    if session_id is None:
        return
    item = sessions.get(session_id)
    if item is None:
        raise HTTPException(404, "session not found")
    if item["status"] == "expired":
        raise HTTPException(410, "session expired")


def _save(room: Room) -> Room:
    _session_check(room.session_id)
    try:
        store.save_room(room)
    except store.NotFound:
        raise HTTPException(422, "invalid room_id") from None
    if room.session_id:
        sessions.link_room(room.session_id, room.room_id)
    return room


def validate_listener(position: list[float], facing: list[float], dims: Dimensions) -> tuple[list[float], list[float]]:
    if len(position) != 3 or not all(math.isfinite(value) for value in position):
        raise HTTPException(422, "invalid listener position")
    if len(facing) != 2 or not all(math.isfinite(value) for value in facing):
        raise HTTPException(422, "invalid facing")
    magnitude = math.hypot(*facing)
    if magnitude == 0:
        raise HTTPException(422, "invalid facing")
    x, y, z = position
    if not (0 <= x <= dims.width and 0 <= y <= dims.height and 0 <= z <= dims.length):
        raise HTTPException(400, "listener outside room")
    return position, [value / magnitude for value in facing]


def build_rect(request: RectRequest) -> Room:
    w, length, h = request.width, request.length, request.height
    polygons = {
        "wall_n": [[0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0]],
        "wall_s": [[0, 0, length], [w, 0, length], [w, h, length], [0, h, length]],
        "wall_w": [[0, 0, 0], [0, 0, length], [0, h, length], [0, h, 0]],
        "wall_e": [[w, 0, 0], [w, 0, length], [w, h, length], [w, h, 0]],
        "floor": [[0, 0, 0], [w, 0, 0], [w, 0, length], [0, 0, length]],
        "ceiling": [[0, h, 0], [w, h, 0], [w, h, length], [0, h, length]],
    }
    surfaces = [Surface(id=key, kind="wall" if key.startswith("wall") else key,
                        polygon=polygon, absorption=ABSORPTION.copy()) for key, polygon in polygons.items()]
    position = request.listener if request.listener is not None else [w / 2, min(3.6, h), 0.7 * length]
    facing = request.facing if request.facing is not None else [0, -1]
    dimensions = Dimensions(width=w, length=length, height=h)
    position, facing = validate_listener(position, facing, dimensions)
    return Room(room_id=store.new_id("r"), session_id=request.session_id, dimensions=Dimensions(width=w, length=length, height=h),  # noqa: E501  # preserve behavior while retaining the existing expression
                surfaces=surfaces, listener=Listener(position=position, facing=facing), budget=request.budget)


@router.post("/rooms/rect", response_model=Room)
def create_rect(request: RectRequest) -> Room:
    _session_check(request.session_id)
    return _save(build_rect(request))


@router.post("/rooms/demo", response_model=Room)
def create_demo(body: dict | None = None) -> Room:
    session_id = (body or {}).get("session_id")
    _session_check(session_id)
    # Fixture absorption values are provisional; keep them aligned with materials.ABSORPTION later.
    data = json.loads((FIXTURES / "room_demo.json").read_text(encoding="utf-8"))
    data.update(room_id=store.new_id("r"), session_id=session_id)
    return _save(Room.model_validate(data))


@router.post("/rooms", response_model=Room)
def create_room(body: dict) -> Room:
    session_id = body.get("session_id")
    _session_check(session_id)
    if body.get("captured_room") is not None and "surfaces" not in body:
        if importlib.util.find_spec("backend.app.roomplan") is None:
            raise HTTPException(501, "scan conversion not available yet") from None
        convert_dto = importlib.import_module("backend.app.roomplan").convert_dto
        try:
            room = convert_dto(body["captured_room"], room_id=store.new_id("r"), session_id=session_id,
                               budget=body.get("budget"), listener=body.get("listener"))
        except (ValueError, ValidationError) as exc:
            raise HTTPException(422, str(exc)) from None
    else:
        try:
            room = Room.model_validate(body)
        except ValidationError as exc:
            raise HTTPException(422, str(exc)) from None
        position, facing = validate_listener(room.listener.position, room.listener.facing, room.dimensions)
        room.listener = Listener(position=position, facing=facing)
    return _save(room)


@router.get("/rooms/{room_id}", response_model=Room)
def get_room(room_id: str) -> Room:
    return _room(room_id)


@router.patch("/rooms/{room_id}/listener", response_model=Room)
def update_listener(room_id: str, body: ListenerRequest) -> Room:
    room = _room(room_id)
    position, facing = validate_listener(body.position, body.facing, room.dimensions)
    room.listener = Listener(position=position, facing=facing)
    store.save_room(room)
    refine.invalidate(room_id)
    return room


def _wall_area(surface: Surface) -> float:
    if len(surface.polygon) < 3:
        return 0
    cross_sum = [0.0, 0.0, 0.0]
    for point, next_point in zip(surface.polygon, surface.polygon[1:] + surface.polygon[:1], strict=False):
        cross_sum[0] += point[1] * next_point[2] - point[2] * next_point[1]
        cross_sum[1] += point[2] * next_point[0] - point[0] * next_point[2]
        cross_sum[2] += point[0] * next_point[1] - point[1] * next_point[0]
    return math.sqrt(sum(value * value for value in cross_sum)) / 2


@router.get("/rooms/{room_id}/photo-targets")
def photo_targets(room_id: str) -> list[dict]:
    room = _room(room_id)
    fx, fz = room.listener.facing
    walls = sorted((s for s in room.surfaces if s.kind == "wall"), key=lambda s: (-_wall_area(s), s.id))[:4]
    named = []
    for surface in walls:
        points = surface.polygon
        cx = sum(p[0] for p in points) / len(points)
        cz = sum(p[2] for p in points) / len(points)
        dx, dz = cx - room.listener.position[0], cz - room.listener.position[2]
        forward = dx * fx + dz * fz
        side = dx * fz - dz * fx
        label = ("Front wall" if forward > 0 else "Back wall") if abs(forward) >= abs(side) else ("Left wall" if side > 0 else "Right wall")  # noqa: E501  # preserve behavior while retaining the existing expression
        named.append({"surface_id": surface.id, "kind": surface.kind, "label": label})
    for kind in ("floor", "ceiling"):
        surface = next((s for s in room.surfaces if s.kind == kind), None)
        if surface:
            named.append({"surface_id": surface.id, "kind": kind, "label": kind.title()})
    return named


@router.post("/rooms/{room_id}/optimize")
def optimize(room_id: str, body: OptimizeRequest | None = None) -> dict:
    room = _room(room_id)
    options = (body.options if body else OptimizeOptions()).model_dump()
    if options["preset"] not in engine3d.PRESETS or options["standard"] not in {"dolby", "itu", "thx"}:
        raise HTTPException(422, "invalid preset or standard")
    return refine.optimize(room, options)


@router.get("/rooms/{room_id}/optimize/status")
def optimize_status(room_id: str) -> dict:
    _room(room_id)
    return refine.status(room_id)


@router.post("/rooms/{room_id}/score")
def score(room_id: str, body: LayoutRequest) -> dict:
    return engine.run_score(_room(room_id), body.layout)


@router.get("/rooms/{room_id}/layout")
def get_layout(room_id: str) -> dict:
    _room(room_id)
    try:
        result = refine.latest_layout(room_id)
    except Exception:
        raise HTTPException(500, "stored layout is invalid") from None
    if result is None:
        raise HTTPException(404, "layout not found")
    return result


@router.get("/rooms/{room_id}/products")
def get_products(room_id: str, budget: float | None = Query(default=None, gt=0, allow_inf_nan=False)) -> dict:
    room = _room(room_id)
    result = get_layout(room_id)
    chosen_budget = budget if budget is not None else room.budget
    if chosen_budget is None or not math.isfinite(chosen_budget) or chosen_budget <= 0:
        raise HTTPException(422, "positive budget required")
    return products.run_products(result["layout"], chosen_budget)
