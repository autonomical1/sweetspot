"""API state transitions for the background 3D refinement worker."""

import json
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import engine3d, store
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
    cached = client.post(root + "/optimize", json={}).json()
    assert cached["layout"]["stage"] == "refined"
    assert client.get(root + "/optimize/status").json()["from_cache"] is True
    assert len(calls) == 1


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
