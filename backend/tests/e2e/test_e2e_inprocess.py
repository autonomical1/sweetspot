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
