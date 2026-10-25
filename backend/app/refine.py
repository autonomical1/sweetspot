"""Single-server background 3D refinement, with stale-result protection."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import patch

from . import acoustics, engine3d, store
from .schemas import LayoutResult, Room

_lock = threading.RLock()
_wake = threading.Condition(_lock)
_queue: deque[Job] = deque()
_statuses: dict[tuple[str, str], dict] = {}
_worker: threading.Thread | None = None
_stopping = False


@dataclass
class Job:
    key: tuple[str, str]
    room: dict
    version: int
    fingerprint: str
    preset: str
    standard: str


def _key(room_id: str) -> tuple[str, str]:
    return str(store.data_dir().resolve()), room_id


def _fingerprint(room: dict, preset: str, standard: str) -> str:
    # The source scan and display-only metadata do not affect engine placement.
    relevant = {name: room.get(name) for name in
                ("dimensions", "outline", "surfaces", "objects", "listener")}
    relevant.update(preset=preset, standard=standard)
    encoded = json.dumps(relevant, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _cache_path(fingerprint: str):
    return store.data_dir() / "cache" / "engine3d" / f"{fingerprint}.json"


def _cache_get(fingerprint: str) -> dict | None:
    path = _cache_path(fingerprint)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != 1 or value.get("fingerprint") != fingerprint:
            return None
        result = value["result"]
        LayoutResult.model_validate(result)
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _cache_put(fingerprint: str, result: dict) -> None:
    path = _cache_path(fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    store.write_json_atomic(path, {"schema_version": 1, "fingerprint": fingerprint, "result": result})


def _status(state: str = "idle", preset: str = "5.1", standard: str = "dolby",
            *, started_at: str | None = None, error: str | None = None,
            from_cache: bool = False) -> dict:
    elapsed = None
    if started_at and state in {"done", "failed", "superseded"}:
        elapsed = max(0.0, (datetime.now(UTC) - datetime.fromisoformat(started_at)).total_seconds())
    return {"state": state, "preset": preset, "standard": standard,
            "started_at": started_at, "elapsed_s": elapsed, "error": error,
            "from_cache": from_cache}


def _set_status(key: tuple[str, str], value: dict) -> None:
    _statuses[key] = value
    store.save_optimize_status(key[1], value)


def status(room_id: str) -> dict:
    with _lock:
        key = _key(room_id)
        value = _statuses.get(key) or store.load_optimize_status(room_id) or _status()
        if key not in _statuses and value["state"] in {"queued", "running"}:
            value = _status("failed", value["preset"], value["standard"],
                            started_at=value["started_at"], error="server restarted")
            _set_status(key, value)
            current = store.load_layout(room_id)
            if current and current.get("layout", {}).get("stage") == "refining":
                current["layout"]["stage"] = "quick"
                current.setdefault("metrics", {}).setdefault("warnings", []).append(
                    "3D refinement failed: server restarted")
                store.save_layout(room_id, current)
        result = value.copy()
        if result["state"] == "running" and result["started_at"]:
            started = datetime.fromisoformat(result["started_at"])
            result["elapsed_s"] = max(0.0, (datetime.now(UTC) - started).total_seconds())
        return result


def start() -> None:
    global _worker, _stopping
    if os.getenv("ENGINE3D_BACKEND", "auto") == "off":
        return
    with _wake:
        if _worker is None or not _worker.is_alive():
            _stopping = False
            _worker = threading.Thread(target=_work, name="engine3d-refine", daemon=True)
            _worker.start()


def stop() -> None:
    global _stopping
    with _wake:
        _stopping = True
        _wake.notify_all()


def optimize(room: Room, options: dict) -> dict:
    """Return the quick result; queue a full run or return a verified cache hit."""
    from . import engine

    room_id = room.room_id
    key = _key(room_id)
    snapshot = room.model_dump(mode="json")
    preset, standard = options["preset"], options["standard"]
    fingerprint = _fingerprint(snapshot, preset, standard)
    with _wake:
        previous = store.load_layout(room_id) or {}
        version = int(previous.get("layout_version", 0)) + 1
        _queue_items = [job for job in _queue if job.key == key]
        for job in _queue_items:
            _queue.remove(job)
        enabled = options["refine"] and os.getenv("ENGINE3D_BACKEND", "auto") != "off"
        cached = _cache_get(fingerprint) if enabled else None
        if cached is not None:
            result = json.loads(json.dumps(cached))
            result["layout"]["stage"] = "refined"
            result["layout_version"] = version
            store.save_layout(room_id, result)
            _set_status(key, _status("done", preset, standard, from_cache=True))
            return result

        result = engine.run_optimize(room, options)
        result["layout"].update(stage="quick", preset=preset, standard=standard)
        result["layout_version"] = version
        if preset != "5.1":
            warning = f"quick preview is 5.1 only; waiting for the 3D {preset} result"
            warnings = result.setdefault("metrics", {}).setdefault("warnings", [])
            if warning not in warnings:
                warnings.append(warning)
        store.save_layout(room_id, result)
        if not options["refine"] or os.getenv("ENGINE3D_BACKEND", "auto") == "off":
            _set_status(key, _status("idle", preset, standard))
            return result
        if len(_queue) >= 4:
            result["metrics"]["warnings"].append("3D refinement failed: queue full")
            store.save_layout(room_id, result)
            _set_status(key, _status("failed", preset, standard, error="queue full"))
            return result
        start()
        _queue.append(Job(key, snapshot, version, fingerprint, preset, standard))
        _set_status(key, _status("queued", preset, standard))
        saved = json.loads(json.dumps(result))
        saved["layout"]["stage"] = "refining"
        store.save_layout(room_id, saved)
        _wake.notify()
        return result


def invalidate(room_id: str) -> None:
    """A listener edit makes pending work stale without starting an optimization."""
    key = _key(room_id)
    with _wake:
        _queue_copy = [job for job in _queue if job.key == key]
        for job in _queue_copy:
            _queue.remove(job)
        current = store.load_layout(room_id)
        if current and current.get("layout", {}).get("stage") == "refining":
            current["layout"]["stage"] = "quick"
            store.save_layout(room_id, current)
        old = _statuses.get(key)
        if old and old["state"] in {"queued", "running"}:
            _set_status(key, _status("superseded", old["preset"], old["standard"],
                                     started_at=old["started_at"]))


def _compatible(layout: dict) -> dict:
    legacy = {"L", "R", "C", "LFE", "Ls", "Rs"}
    roles = {item["role"] for item in layout["speakers"]}
    speakers = []
    for item in layout["speakers"]:
        role = item["role"]
        if role in legacy:
            speakers.append(item)
        elif role in {"Lss", "Rss"} and {"Ls", "Rs"}.isdisjoint(roles):
            speakers.append({**item, "role": {"Lss": "Ls", "Rss": "Rs"}[role]})
    return {"speakers": speakers, "screen": layout.get("screen")}


def _warnings(rows: list[dict]) -> list[str]:
    warnings = []
    for row in rows:
        if row.get("status") in {None, "PASS"}:
            continue
        role = row.get("channel", row.get("role", "speaker"))
        elevation = row.get("elevation_deg")
        allowed = row.get("elevation_allowed", "allowed range")
        if isinstance(elevation, (int, float)):
            warnings.append(f"{role} elevation {elevation:.0f} deg outside {allowed}: {row['status']}")
        else:
            warnings.append(f"{role} compliance: {row['status']}")
        if len(warnings) == 10:
            break
    return warnings


def _safe_reason(exc: Exception) -> str:
    if isinstance(exc, engine3d.EngineError):
        first = str(exc).splitlines()[0]
        if first.startswith("engine timed out"):
            return "engine timed out"
        if first.startswith("engine exit code"):
            return "engine process failed"
    return type(exc).__name__


def _run_full_scene(job: Job, timeout: float) -> dict:
    kwargs = {"preset": job.preset, "standard": job.standard, "timeout_s": timeout}
    parameters = inspect.signature(engine3d.run_scene).parameters
    accepts_fast = "fast" in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    if accepts_fast:
        return engine3d.run_scene(job.room, job.room["listener"], fast=False, **kwargs)

    # The merged runner predates its fast parameter. Until it gains one, force
    # its CLI builder to omit --fast while keeping the runner's timeout handling.
    build_command = engine3d.build_command

    def full_command(*args, **command_kwargs):
        return build_command(*args, **{**command_kwargs, "fast": False})

    with patch.object(engine3d, "build_command", full_command):
        return engine3d.run_scene(job.room, job.room["listener"], **kwargs)


def _work() -> None:
    while True:
        with _wake:
            while not _queue and not _stopping:
                _wake.wait()
            if _stopping:
                return
            job = _queue.popleft()
            current = _statuses.get(job.key)
            if not current or current["state"] != "queued":
                continue
            started = datetime.now(UTC).isoformat()
            _set_status(job.key, _status("running", job.preset, job.standard, started_at=started))
        try:
            timeout = float(os.getenv("ENGINE3D_TIMEOUT_S", "150"))
            scene = _run_full_scene(job, timeout)
            mapped = engine3d.to_layout(scene, job.room)
            layout = mapped["layout"]
            layout.update(stage="refined", preset=job.preset, standard=job.standard)
            metrics = acoustics.evaluate(job.room, _compatible(layout))
            metrics["engine"] = mapped["engine"]
            metrics["warnings"].extend(_warnings(mapped["engine"].get("compliance", [])))
            result = {"layout": layout, "metrics": metrics}
            LayoutResult.model_validate(result)
            _cache_put(job.fingerprint, result)
            failure = None
        except Exception as exc:
            failure = _safe_reason(exc)
        with _wake:
            current = store.load_layout(job.key[1])
            room = store.load_room(job.key[1]).model_dump(mode="json")
            active = (current is not None and current.get("layout_version") == job.version
                      and _fingerprint(room, job.preset, job.standard) == job.fingerprint
                      and _statuses.get(job.key, {}).get("state") == "running")
            if not active:
                old = _statuses.get(job.key)
                if old and old["state"] == "running":
                    if current and current.get("layout_version") == job.version:
                        current["layout"]["stage"] = "quick"
                        store.save_layout(job.key[1], current)
                    _set_status(job.key, _status("superseded", job.preset, job.standard,
                                                 started_at=old["started_at"]))
                continue
            old = _statuses[job.key]
            if failure:
                current["layout"]["stage"] = "quick"
                current["metrics"].setdefault("warnings", []).append(f"3D refinement failed: {failure}")
                store.save_layout(job.key[1], current)
                _set_status(job.key, _status("failed", job.preset, job.standard,
                                             started_at=old["started_at"], error=failure))
            else:
                result["layout_version"] = job.version
                store.save_layout(job.key[1], result)
                _set_status(job.key, _status("done", job.preset, job.standard,
                                             started_at=old["started_at"]))
