"""Concurrency and HTTP coverage for Gemini request coordination."""

import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import gemini_limits, materials
from backend.app.main import create_app


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _key(room="r_one", image=b"one", backend="gemini"):
    return gemini_limits.photo_key(room, [{"surface_id": "floor", "image_bytes": image}], backend)


def _wait_for_joiners(limits, room_id, count):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with limits._lock:
            flight = limits._flights.get(room_id)
            if flight is not None and flight.waiters == count:
                return
        time.sleep(0.005)
    pytest.fail(f"{count} requests did not join")


def test_join_cache_changed_photo_and_mock():
    clock = Clock()
    limits = gemini_limits.GeminiLimits(clock=clock, max_per_minute=1)
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def classify():
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(5)
        return [{"surface_id": "floor", "material": "glass", "confidence": 0.9}]

    with ThreadPoolExecutor(max_workers=5) as pool:
        first = pool.submit(limits.execute, "r_one", _key(), "gemini", classify)
        assert entered.wait(5)
        others = [pool.submit(limits.execute, "r_one", _key(), "gemini", classify)
                  for _ in range(4)]
        _wait_for_joiners(limits, "r_one", 4)
        release.set()
        results = [task.result(timeout=5) for task in [first, *others]]
    assert calls == 1
    assert [status for _, status in results].count("joined") == 4
    assert all(result == results[0][0] for result, _ in results)
    assert limits.execute("r_one", _key(), "gemini", classify)[1] == "cached"
    assert calls == 1
    assert limits.execute("r_two", _key("r_two", backend="mock"), "mock", classify)[1] == "fresh"
    assert calls == 2
    clock.now = 60
    assert limits.execute("r_one", _key(image=b"two"), "gemini", classify)[1] == "fresh"
    assert calls == 3


def test_rate_limit_and_concurrency_cap():
    clock = Clock()
    limits = gemini_limits.GeminiLimits(clock=clock, max_concurrent=1, max_per_minute=1,
                                        concurrency_timeout=0.01)
    entered = threading.Event()
    release = threading.Event()

    def blocked():
        entered.set()
        assert release.wait(5)
        return []

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(limits.execute, "r_one", _key(), "gemini", blocked)
        assert entered.wait(5)
        with pytest.raises(HTTPException) as exc:
            limits.execute("r_two", _key("r_two"), "gemini", lambda: [])
        assert exc.value.status_code == 429
        assert exc.value.headers == {"Retry-After": "1"}
        release.set()
        first.result(timeout=5)
    with pytest.raises(HTTPException) as exc:
        limits.execute("r_two", _key("r_two"), "gemini", lambda: [])
    assert exc.value.detail == {"detail": "Photo analysis is busy; retry in 60 s", "retry_after_s": 60}
    assert exc.value.headers == {"Retry-After": "60"}


def test_failure_releases_flight():
    limits = gemini_limits.GeminiLimits(max_per_minute=2)

    def fail():
        raise RuntimeError("model failed")

    with pytest.raises(RuntimeError, match="model failed"):
        limits.execute("r_one", _key(), "gemini", fail)
    assert limits.status("r_one")["state"] == "idle"
    assert limits.execute("r_one", _key(), "gemini", lambda: [])[1] == "fresh"


def test_joiners_receive_same_failure():
    limits = gemini_limits.GeminiLimits(max_per_minute=2)
    entered = threading.Event()
    release = threading.Event()

    def fail():
        entered.set()
        assert release.wait(5)
        raise RuntimeError("model failed")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(limits.execute, "r_one", _key(), "gemini", fail)
        assert entered.wait(5)
        joined = pool.submit(limits.execute, "r_one", _key(), "gemini", fail)
        _wait_for_joiners(limits, "r_one", 1)
        release.set()
        for future in (first, joined):
            with pytest.raises(RuntimeError, match="model failed"):
                future.result(timeout=5)
    assert limits.status("r_one")["state"] == "idle"


def _upload(client, room_id, color="blue"):
    stream = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(stream, "PNG")
    return client.post(f"/rooms/{room_id}/photos", data={"surface_id": "floor"},
                       files={"file": ("photo.png", stream.getvalue(), "image/png")})


def test_http_join_status_cache_and_changed_photo(data_dir, monkeypatch):
    monkeypatch.setenv("MATERIALS_BACKEND", "mock")
    monkeypatch.setattr(gemini_limits, "limits", gemini_limits.GeminiLimits(max_per_minute=1))
    client = TestClient(create_app())
    room_id = client.post("/rooms/rect", json={"width": 12, "length": 15}).json()["room_id"]
    url = f"/rooms/{room_id}/materials"
    status_url = f"{url}/status"
    assert client.get("/rooms/r_missing/materials/status").status_code == 404
    assert client.get(status_url).json() == {
        "state": "idle", "started_at": None, "elapsed_s": None, "photos": 0}
    assert _upload(client, room_id).status_code == 200
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def classify(photos):
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(5)
        return [{"surface_id": "floor", "material": "hardwood", "confidence": 0.9}]

    monkeypatch.setattr(materials, "classify_materials", classify)
    with ThreadPoolExecutor(max_workers=5) as pool:
        first = pool.submit(client.post, url, json={})
        assert entered.wait(5)
        running = client.get(status_url).json()
        assert running["state"] == "running" and running["elapsed_s"] >= 0
        assert running["started_at"] and running["photos"] == 1
        others = [pool.submit(client.post, url, json={}) for _ in range(4)]
        _wait_for_joiners(gemini_limits.limits, room_id, 4)
        release.set()
        bodies = [future.result(timeout=5).json() for future in [first, *others]]
    assert calls == 1
    assert [body["status"] for body in bodies].count("joined") == 4
    assert len({str(body["surfaces"]) for body in bodies}) == 1
    assert client.get(status_url).json()["state"] == "idle"
    assert client.post(url, json={}).json()["status"] == "cached"
    assert calls == 1
    assert _upload(client, room_id, "red").status_code == 200
    assert client.post(url, json={}).json()["status"] == "fresh"
    assert calls == 2


def test_http_rate_limit_body_and_header(data_dir, monkeypatch):
    monkeypatch.setenv("MATERIALS_BACKEND", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    clock = Clock()
    monkeypatch.setattr(gemini_limits, "limits", gemini_limits.GeminiLimits(
        clock=clock, max_per_minute=1))
    monkeypatch.setattr(materials, "classify_materials", lambda photos: [])
    client = TestClient(create_app())
    room_id = client.post("/rooms/rect", json={"width": 12, "length": 15}).json()["room_id"]
    assert _upload(client, room_id).status_code == 200
    url = f"/rooms/{room_id}/materials"
    assert client.post(url, json={}).json()["status"] == "fresh"
    assert client.post(url, json={}).json()["status"] == "cached"
    assert _upload(client, room_id, "red").status_code == 200
    response = client.post(url, json={})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json() == {"detail": "Photo analysis is busy; retry in 60 s", "retry_after_s": 60}
