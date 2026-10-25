"""API state transitions for the background 3D refinement worker."""

import json
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import engine3d, refine, store
from backend.app.main import create_app

SCENES = Path(__file__).resolve().parents[2] / "fixtures" / "engine"


def _room(client):
    response = client.post("/rooms/rect", json={"width": 15, "length": 12,
                                                 "listener": [7.5, 3.6, 8], "facing": [0, -1]})
    assert response.status_code == 200
    return f"/rooms/{response.json()['room_id']}"


def _wait(client, root, state, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        status = client.get(root + "/optimize/status").json()
        if status["state"] == state:
            return status
        time.sleep(0.01)
    raise AssertionError(f"state did not become {state}: {status}")


def _scene(name):
    return json.loads((SCENES / name).read_text(encoding="utf-8"))


def test_quick_refining_refined_and_cache(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "auto")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    entered, release = threading.Event(), threading.Event()
    calls = []

    def fake(room, listener, **kwargs):
        calls.append(kwargs)
        entered.set()
        assert release.wait(3)
        return _scene("layout_5.1.json")

    monkeypatch.setattr(engine3d, "run_scene", fake)
    client = TestClient(create_app())
    root = _room(client)
    started = time.perf_counter()
    result = client.post(root + "/optimize", json={}).json()
    assert time.perf_counter() - started < 1
    assert result["layout"]["stage"] == "quick"
    assert result["layout"]["preset"] == "5.1"
    assert entered.wait(1)
    assert client.get(root + "/layout").json()["layout"]["stage"] == "refining"
    assert _wait(client, root, "running")["started_at"]
    release.set()
    assert _wait(client, root, "done")["from_cache"] is False
    refined = client.get(root + "/layout").json()
    assert refined["layout"]["stage"] == "refined"
    assert "engine" in refined["metrics"]
    assert any("WARN" in warning for warning in refined["metrics"]["warnings"])
    assert calls[0]["timeout_s"] == 150
    assert calls[0]["fast"] is False
    cached = client.post(root + "/optimize", json={}).json()
    assert cached["layout"]["stage"] == "refined"
    assert client.get(root + "/optimize/status").json()["from_cache"] is True
    assert len(calls) == 1


def test_full_scene_omits_fast_with_legacy_runner(data_dir, monkeypatch):
    commands = []

    class FakeProcess:
        returncode = 0

        def __init__(self, command, **kwargs):
            commands.append(command)
            output = Path(command[command.index("--save-layout") + 1])
            output.write_text((SCENES / "layout_5.1.json").read_text(encoding="utf-8"),
                              encoding="utf-8")

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr(engine3d.subprocess, "Popen", FakeProcess)
    room = json.loads((SCENES.parent / "room_rect.json").read_text(encoding="utf-8"))
    job = refine.Job(("test", room["room_id"]), room, 1, "test", "5.1", "dolby")
    assert refine._run_full_scene(job, 150)["schema_version"] == 2
    assert len(commands) == 1
    assert "--fast" not in commands[0]


def test_superseded_by_listener_edit(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "auto")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    entered, release = threading.Event(), threading.Event()

    def fake(room, listener, **kwargs):
        entered.set()
        assert release.wait(3)
        return _scene("layout_5.1.json")

    monkeypatch.setattr(engine3d, "run_scene", fake)
    client = TestClient(create_app())
    root = _room(client)
    client.post(root + "/optimize", json={})
    assert entered.wait(1)
    changed = client.patch(root + "/listener", json={"position": [7.6, 3.6, 8],
                                                     "facing": [0, -1]})
    assert changed.status_code == 200
    release.set()
    assert _wait(client, root, "superseded")["state"] == "superseded"
    assert client.get(root + "/layout").json()["layout"]["stage"] == "quick"


def test_material_change_supersedes_running_job(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "auto")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    entered, release = threading.Event(), threading.Event()

    def fake(room, listener, **kwargs):
        entered.set()
        assert release.wait(3)
        return _scene("layout_5.1.json")

    monkeypatch.setattr(engine3d, "run_scene", fake)
    client = TestClient(create_app())
    root = _room(client)
    client.post(root + "/optimize", json={})
    assert entered.wait(1)
    room_id = root.rsplit("/", 1)[1]
    room = store.load_room(room_id)
    room.surfaces[0].material = "curtain"
    store.save_room(room)
    release.set()
    assert _wait(client, root, "superseded")["state"] == "superseded"
    assert client.get(root + "/layout").json()["layout"]["stage"] == "quick"


def test_room_write_cannot_pass_final_check_before_refined_save(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "auto")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    checking, allow_check = threading.Event(), threading.Event()
    writer_started, writer_done = threading.Event(), threading.Event()
    monkeypatch.setattr(engine3d, "run_scene", lambda *args, **kwargs: _scene("layout_5.1.json"))
    original_fingerprint = refine._fingerprint

    def paused_fingerprint(room, preset, standard):
        if threading.current_thread().name == "engine3d-refine":
            checking.set()
            assert allow_check.wait(3)
        return original_fingerprint(room, preset, standard)

    monkeypatch.setattr(refine, "_fingerprint", paused_fingerprint)
    client = TestClient(create_app())
    root = _room(client)
    assert client.post(root + "/optimize", json={}).status_code == 200
    assert checking.wait(2)
    room_id = root.rsplit("/", 1)[1]

    def change_material():
        writer_started.set()
        room = store.load_room(room_id)
        room.surfaces[0].material = "curtain"
        store.save_room(room)
        writer_done.set()

    writer = threading.Thread(target=change_material, daemon=True)
    writer.start()
    assert writer_started.wait(1)
    assert not writer_done.wait(0.05)
    allow_check.set()
    assert _wait(client, root, "done")["state"] == "done"
    assert writer_done.wait(2)
    writer.join(timeout=2)


def test_layout_read_repairs_interrupted_job_after_restart(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "off")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    client = TestClient(create_app())
    root = _room(client)
    quick = client.post(root + "/optimize", json={}).json()
    room_id = root.rsplit("/", 1)[1]
    quick["layout"]["stage"] = "refining"
    store.save_layout(room_id, quick)
    store.save_optimize_status(room_id, refine._status("running", started_at="2026-01-01T00:00:00+00:00"))
    refine._statuses.pop(refine._key(room_id), None)

    layout = client.get(root + "/layout").json()
    assert layout["layout"]["stage"] == "quick"
    assert layout["metrics"]["warnings"].count("3D refinement failed: server restarted") == 1
    assert store.load_optimize_status(room_id)["state"] == "failed"


def test_start_repairs_interrupted_job_with_worker_disabled(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "off")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    client = TestClient(create_app())
    root = _room(client)
    quick = client.post(root + "/optimize", json={}).json()
    room_id = root.rsplit("/", 1)[1]
    quick["layout"]["stage"] = "refining"
    store.save_layout(room_id, quick)
    store.save_optimize_status(room_id, refine._status("queued"))
    refine._statuses.pop(refine._key(room_id), None)

    refine.start()
    assert store.load_layout(room_id)["layout"]["stage"] == "quick"
    assert store.load_optimize_status(room_id)["state"] == "failed"


def test_second_optimize_replaces_running_result(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "auto")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    entered, release = threading.Event(), threading.Event()
    calls = []

    def fake(room, listener, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
        return _scene("layout_5.1.json")

    monkeypatch.setattr(engine3d, "run_scene", fake)
    client = TestClient(create_app())
    root = _room(client)
    first = client.post(root + "/optimize", json={}).json()
    assert entered.wait(1)
    second = client.post(root + "/optimize", json={}).json()
    assert second["layout_version"] == first["layout_version"] + 1
    release.set()
    _wait(client, root, "done")
    saved = client.get(root + "/layout").json()
    assert saved["layout_version"] == second["layout_version"]
    assert saved["layout"]["stage"] == "refined"
    assert len(calls) == 2


def test_failure_keeps_quick(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "auto")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")

    def fake(room, listener, **kwargs):
        raise engine3d.EngineError("engine exit code 3\n/private/path/secret")

    monkeypatch.setattr(engine3d, "run_scene", fake)
    client = TestClient(create_app())
    root = _room(client)
    assert client.post(root + "/optimize", json={}).status_code == 200
    assert _wait(client, root, "failed")["error"] == "engine process failed"
    layout = client.get(root + "/layout").json()
    assert layout["layout"]["stage"] == "quick"
    assert "3D refinement failed: engine process failed" in layout["metrics"]["warnings"]
    assert "/private" not in str(layout)


def test_invalid_options_and_714(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE3D_BACKEND", "auto")
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    monkeypatch.setattr(engine3d, "run_scene", lambda *args, **kwargs: _scene("layout_7.1.4.json"))
    client = TestClient(create_app())
    root = _room(client)
    for options in ({"preset": "9.1"}, {"standard": "none"}):
        assert client.post(root + "/optimize", json={"options": options}).status_code == 422
    quick = client.post(root + "/optimize", json={"options": {"preset": "7.1.4"}}).json()
    assert len(quick["layout"]["speakers"]) == 6
    assert any("5.1 only" in item for item in quick["metrics"]["warnings"])
    _wait(client, root, "done")
    layout = client.get(root + "/layout").json()["layout"]
    assert len(layout["speakers"]) == 12
    assert client.post(root + "/score", json={"layout": layout}).status_code == 200
