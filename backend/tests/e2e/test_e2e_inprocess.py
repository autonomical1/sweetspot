from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("e2e_runner", ROOT / "tools" / "e2e.py")
assert SPEC and SPEC.loader
e2e = importlib.util.module_from_spec(SPEC)
sys.modules["e2e_runner"] = e2e
SPEC.loader.exec_module(e2e)


def test_complete_flow_in_process(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    monkeypatch.setenv("PRODUCTS_BACKEND", "stub")
    monkeypatch.setenv("MATERIALS_BACKEND", "mock")
    from backend.app.main import app

    results = e2e.run_e2e(TestClient(app))
    assert results
    assert all(result.status == "PASS" for result in results), results


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FailingClient:
    def get(self, path, **kwargs):
        return FakeResponse(503, {"detail": "offline"})

    def post(self, path, **kwargs):
        return FakeResponse(503, {"detail": "offline"})

    def patch(self, path, **kwargs):
        return FakeResponse(503, {"detail": "offline"})


def test_runner_records_a_failed_step():
    results = e2e.run_e2e(FailingClient())
    assert len(results) == 1
    assert results[0].status == "FAIL"


def test_cli_output_and_exit_code(monkeypatch, capsys):
    class FakeHttpClient(FailingClient):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(e2e.httpx, "Client", lambda **kwargs: FakeHttpClient())
    assert e2e.main(["http://example.test"]) == 1
    assert "FAIL GET /health" in capsys.readouterr().out


def test_warnings_include_metrics_warnings():
    assert e2e._warnings({"warnings": ["room warning"], "metrics": {"warnings": ["metric warning"]}}) == [
        "room warning",
        "metric warning",
    ]


class LayoutClient:
    def __init__(self, optimize_payload):
        self.optimize_payload = optimize_payload
        self.score_payloads = []

    def post(self, path, **kwargs):
        if path.endswith("/optimize"):
            return FakeResponse(200, self.optimize_payload)
        self.score_payloads.append(kwargs["json"])
        return FakeResponse(200, {"metrics": {}})

    def get(self, path, **kwargs):
        return FakeResponse(200, self.optimize_payload)


def _speakers():
    return [
        {"role": role, "position": [0.0, 0.0, 0.0]}
        for role in ("R", "C", "LFE", "Ls", "Rs", "L")
    ]


def test_optimize_requires_exactly_six_expected_roles():
    payload = {"layout": {"speakers": _speakers()}, "metrics": {}}
    client = LayoutClient(payload)
    assert e2e._optimize(client, {"room_id": "r_test"}) == payload

    duplicate = {"layout": {"speakers": _speakers() + [{"role": "L"}]}, "metrics": {}}
    try:
        e2e._optimize(LayoutClient(duplicate), {"room_id": "r_test"})
    except AssertionError:
        pass
    else:
        raise AssertionError("duplicate speaker role should fail validation")


def test_score_moves_the_left_speaker_by_role():
    layout = {"speakers": _speakers()}
    client = LayoutClient({"layout": layout, "metrics": {}})
    e2e._score(client, {"room_id": "r_test", "layout": layout})
    original = {speaker["role"]: speaker["position"][0] for speaker in layout["speakers"]}
    moved = client.score_payloads[1]["layout"]
    assert moved["speakers"][0]["role"] == "R"
    assert moved["speakers"][0]["position"][0] == original["R"]
    left = next(speaker for speaker in moved["speakers"] if speaker["role"] == "L")
    assert left["position"][0] == original["L"] + 1.0
