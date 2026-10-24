"""FastAPI entry point."""
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
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
    try:
        from .materials_router import router as materials_router
    except ImportError:
        pass
    else:
        application.include_router(materials_router)
    return application


app = create_app()
