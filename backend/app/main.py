"""FastAPI entry point."""
import importlib
import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import rooms, sessions


class CodeRequest(BaseModel):
    code: str


def create_app() -> FastAPI:
    application = FastAPI()

    @application.get("/health")
    def health() -> dict:
        return {"ok": True}

    @application.post("/sessions")
    def create_session() -> dict:
        item = sessions.create()
        domain = os.getenv("DOMAIN", "localhost")
        return {"session_id": item["session_id"], "code": item["code"],
                "expires_at": datetime.fromtimestamp(item["expires_at"], timezone.utc).isoformat(),
                "pair_url": f"https://{domain}/pair/{item['session_id']}"}

    @application.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        item = sessions.get(session_id)
        if item is None:
            raise HTTPException(404, "session not found")
        return {key: item[key] for key in ("session_id", "status", "room_id")}

    @application.post("/sessions/by-code")
    def session_by_code(body: CodeRequest) -> dict:
        item = sessions.by_code(body.code)
        if item is None:
            raise HTTPException(404, "session not found")
        return {"session_id": item["session_id"]}

    application.include_router(rooms.router)
    if importlib.util.find_spec("backend.app.materials_router") is not None:
        materials_router = importlib.import_module("backend.app.materials_router").router
        application.include_router(materials_router)
    web_dir = Path(__file__).resolve().parents[2] / "web"
    if web_dir.is_dir():
        application.mount("/app", StaticFiles(directory=web_dir, html=True), name="web")
    return application


app = create_app()
