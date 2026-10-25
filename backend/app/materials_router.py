"""Photo upload and material application endpoints."""

import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from . import gemini_limits, materials, store

router = APIRouter()


def _room(room_id: str):
    try:
        return store.load_room(room_id)
    except store.NotFound:
        raise HTTPException(404, "room not found") from None
    except Exception:
        raise HTTPException(500, "stored room is invalid") from None


@router.post("/rooms/{room_id}/photos")
def upload_photo(room_id: str, surface_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    room = _room(room_id)
    if surface_id not in {surface.id for surface in room.surfaces}:
        raise HTTPException(422, "unknown surface_id")
    try:
        image = materials.prepare_image(file.file.read())
        store.save_photo(room_id, surface_id, image)
    except ValueError:
        raise HTTPException(400, "file is not an image") from None
    except store.NotFound:
        raise HTTPException(422, "invalid surface_id") from None
    finally:
        file.file.close()
    return {"stored": True}


@router.post("/rooms/{room_id}/materials")
def apply_materials(room_id: str, body: dict | None = None) -> dict:
    room = _room(room_id)
    try:
        photos = store.list_photos(room_id)
    except store.NotFound:
        raise HTTPException(404, "room not found") from None
    valid_ids = {surface.id for surface in room.surfaces}
    inputs = [
        {"surface_id": surface_id, "image_bytes": path.read_bytes(), "mime": "image/jpeg"}
        for surface_id, path in photos.items() if surface_id in valid_ids
    ]
    backend = os.getenv("MATERIALS_BACKEND", "gemini")
    key = gemini_limits.photo_key(room_id, inputs, backend)
    # GeminiClassifier returns unknown without a key; that path never calls the API.
    limited_backend = backend if inputs and (backend != "gemini" or os.getenv("GEMINI_API_KEY")) else "mock"
    try:
        results, status = gemini_limits.limits.execute(
            room_id, key, limited_backend,
            lambda: materials.classify_materials(inputs) if inputs else [],
        )
    except HTTPException as exc:
        if exc.status_code == 429:
            return JSONResponse(status_code=429, content=exc.detail, headers=exc.headers)
        raise
    surfaces = {surface.id: surface for surface in room.surfaces}
    response = []
    for result in results:
        surface = surfaces.get(result["surface_id"])
        material = result["material"]
        applied = bool(surface and material != "unknown" and result["confidence"] >= materials.MIN_CONFIDENCE)
        if applied:
            surface.material = material
            surface.absorption = materials.ABSORPTION[material].copy()
        response.append({**result, "applied": applied})
    if response:
        store.save_room(room)
    return {"surfaces": response, "status": status}


@router.get("/rooms/{room_id}/materials/status")
def materials_status(room_id: str) -> dict:
    _room(room_id)
    try:
        photos = store.list_photos(room_id)
    except store.NotFound:
        raise HTTPException(404, "room not found") from None
    return {**gemini_limits.limits.status(room_id), "photos": len(photos)}
