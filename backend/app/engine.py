"""Optional external engine with a deterministic offline fallback."""
import importlib
import os

from pydantic import ValidationError

from .schemas import LayoutResult, Room
from .stubs import engine_stub


def _backend():
    if os.getenv("ENGINE_BACKEND", "auto") == "stub":
        return engine_stub
    try:
        return importlib.import_module("backend.app.engine_speakerplacer")  # adapter around the teammate package
    except ImportError:
        return engine_stub


def _run(method: str, room: Room, *args) -> dict:
    backend = _backend()
    try:
        result = getattr(backend, method)(room.model_dump(mode="json"), *args)
        if method == "optimize":
            LayoutResult.model_validate(result)
        elif not isinstance(result, dict) or not isinstance(result.get("metrics"), dict):
            raise ValueError("invalid result")
        return result
    except Exception as exc:
        result = getattr(engine_stub, method)(room.model_dump(mode="json"), *args)
        reason = "invalid result" if isinstance(exc, (ValueError, ValidationError)) else type(exc).__name__
        result.setdefault("metrics", {}).setdefault("warnings", []).append(f"engine fallback: {reason}")
        return result


def run_optimize(room: Room, options: dict | None = None) -> dict:
    return _run("optimize", room, options)


def run_score(room: Room, layout: dict) -> dict:
    return _run("score", room, layout)
