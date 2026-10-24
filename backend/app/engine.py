"""Optional external engine with a deterministic offline fallback."""
import importlib
import os

from .schemas import Room
from .stubs import engine_stub


def _backend():
    if os.getenv("ENGINE_BACKEND", "auto") == "stub":
        return engine_stub
    try:
        return importlib.import_module("speakerplacer")
    except ImportError:
        return engine_stub


def _run(method: str, room: Room, *args) -> dict:
    backend = _backend()
    try:
        return getattr(backend, method)(room.model_dump(mode="json"), *args)
    except Exception as exc:
        result = getattr(engine_stub, method)(room.model_dump(mode="json"), *args)
        result.setdefault("metrics", {}).setdefault("warnings", []).append(f"engine fallback: {type(exc).__name__}")
        return result


def run_optimize(room: Room, options: dict | None = None) -> dict:
    return _run("optimize", room, options)


def run_score(room: Room, layout: dict) -> dict:
    return _run("score", room, layout)
