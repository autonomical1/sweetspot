"""End-to-end smoke flow for the Sweet Spot API."""

from __future__ import annotations

import argparse
import io
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOM = ROOT / "fixtures" / "room_demo.json"
ROOMPLAN = ROOT / "fixtures" / "roomplan_sample.json"


def _jpeg_bytes() -> bytes:
    """Create a tiny valid image; Pillow is already a backend dependency."""
    from PIL import Image

    output = io.BytesIO()
    Image.new("RGB", (1, 1), (128, 128, 128)).save(output, format="JPEG")
    return output.getvalue()


JPEG = _jpeg_bytes()


@dataclass
class StepResult:
    step: str
    status: str
    elapsed_ms: float
    detail: str = ""
    warnings: list[str] = field(default_factory=list)


def _json(response: Any) -> dict[str, Any] | list[Any]:
    try:
        return response.json()
    except Exception as exc:
        raise AssertionError(f"invalid JSON ({exc})") from exc


def _require(response: Any, status: int = 200) -> Any:
    if response.status_code != status:
        raise AssertionError(f"HTTP {response.status_code}: {_json(response)}")
    return _json(response)


def _warnings(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    warnings = [str(item) for item in payload.get("warnings", [])]
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        warnings.extend(str(item) for item in metrics.get("warnings", []))
    return warnings


def run_e2e(client: Any, *, budget: float = 1500.0, wait_refined: float = 0,
            preset: str = "5.1") -> list[StepResult]:
    """Run the complete demo API flow against an httpx-compatible client."""
    results: list[StepResult] = []
    state: dict[str, Any] = {}

    def step(name: str, action: Any) -> bool:
        started = time.perf_counter()
        try:
            payload = action()
            warnings = _warnings(payload)
            detail = payload.get("_step_detail", "ok") if isinstance(payload, dict) else "ok"
            if warnings:
                detail = f"{detail}; {'; '.join(warnings)}"
            results.append(StepResult(name, "PASS", (time.perf_counter() - started) * 1000, detail, warnings))
            return True
        except Exception as exc:
            results.append(StepResult(name, "FAIL", (time.perf_counter() - started) * 1000, str(exc)))
            return False

    if not step("GET /health", lambda: _health(client)):
        return results
    if not step("pairing", lambda: _pair(client, state)):
        return results
    if not step("POST /rooms/demo", lambda: _demo(client, state)):
        return results
    if not step("photos and materials", lambda: _materials(client, state)):
        return results
    if not step("optimize and saved layout", lambda: _optimize(client, state, preset)):
        return results
    if wait_refined and not step("refined", lambda: _refined(client, state, wait_refined, preset)):
        return results
    if not step("score and moved speaker", lambda: _score(client, state)):
        return results
    if not step("move listener and optimize", lambda: _move_listener(client, state)):
        return results
    if not step("products", lambda: _products(client, state, budget)):
        return results
    if not step("scan room path", lambda: _scan(client, state)):
        return results
    if not step("rectangle room path", lambda: _rectangle(client, state)):
        return results
    if not step("web shell", lambda: _web(client)):
        return results
    step("unknown room error", lambda: _missing_room(client))
    return results


def _health(client: Any) -> Any:
    payload = _require(client.get("/health"))
    assert payload == {"ok": True}, payload
    return payload


def _pair(client: Any, state: dict[str, Any]) -> Any:
    created = _require(client.post("/sessions"))
    session_id = created["session_id"]
    assert _require(client.post("/sessions/by-code", json={"code": created["code"]}))["session_id"] == session_id
    current = _require(client.get(f"/sessions/{session_id}"))
    assert current["status"] == "waiting", current
    state["session_id"] = session_id
    return current


def _demo(client: Any, state: dict[str, Any]) -> Any:
    room = _require(client.post("/rooms/demo", json={"session_id": state["session_id"]}))
    state["room_id"] = room["room_id"]
    session = _require(client.get(f"/sessions/{state['session_id']}"))
    assert session["status"] == "ready" and session["room_id"] == state["room_id"], session
    return room


def _materials(client: Any, state: dict[str, Any]) -> Any:
    room_id = state["room_id"]
    targets = _require(client.get(f"/rooms/{room_id}/photo-targets"))
    assert targets, "no photo targets"
    surface_id = targets[0]["surface_id"]
    uploaded = _require(client.post(
        f"/rooms/{room_id}/photos",
        files={"surface_id": (None, surface_id), "file": ("surface.jpg", JPEG, "image/jpeg")},
    ))
    assert uploaded.get("stored") is True, uploaded
    result = _require(client.post(f"/rooms/{room_id}/materials", json={}))
    assert isinstance(result.get("surfaces"), list), result
    return result


def _optimize(client: Any, state: dict[str, Any], preset: str = "5.1") -> Any:
    room_id = state["room_id"]
    result = _require(client.post(f"/rooms/{room_id}/optimize", json={"options": {"preset": preset}}))
    speakers = result["layout"]["speakers"]
    roles = {speaker["role"] for speaker in speakers}
    if result["layout"].get("stage") == "refined" and preset == "7.1.4":
        expected = {"L", "R", "C", "LFE", "Lss", "Rss", "Lrs", "Rrs", "Ltf", "Rtf", "Ltr", "Rtr"}
    else:
        expected = {"L", "R", "C", "LFE", "Ls", "Rs"}
    assert len(speakers) == len(expected) and roles == expected, speakers
    assert "metrics" in result
    assert result["layout"].get("stage") in (None, "quick", "refined"), result
    saved = _require(client.get(f"/rooms/{room_id}/layout"))
    assert saved["layout"]["speakers"] == result["layout"]["speakers"], "saved layout differs"
    state["layout"] = result["layout"]
    return result


def _refined(client: Any, state: dict[str, Any], wait_s: float, preset: str) -> Any:
    root = f"/rooms/{state['room_id']}"
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        status = _require(client.get(root + "/optimize/status"))
        if status["state"] == "done":
            result = _require(client.get(root + "/layout"))
            assert result["layout"]["stage"] == "refined", result
            expected = ({"L", "R", "C", "LFE", "Lss", "Rss", "Lrs", "Rrs",
                         "Ltf", "Rtf", "Ltr", "Rtr"} if preset == "7.1.4"
                        else {"L", "R", "C", "LFE", "Ls", "Rs"})
            assert {speaker["role"] for speaker in result["layout"]["speakers"]} == expected, result
            state["layout"] = result["layout"]
            return result
        if status["state"] in {"failed", "superseded"}:
            raise AssertionError(f"3D refinement {status['state']}: {status.get('error')}")
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    raise AssertionError(f"3D refinement did not finish within {wait_s}s")


def _score(client: Any, state: dict[str, Any]) -> Any:
    room_id = state["room_id"]
    first = _require(client.post(f"/rooms/{room_id}/score", json={"layout": state["layout"]}))
    moved = json.loads(json.dumps(state["layout"]))
    left = next((speaker for speaker in moved["speakers"] if speaker.get("role") == "L"), None)
    assert left is not None, "optimized layout has no L speaker"
    left["position"][0] += 1.0
    second = _require(client.post(f"/rooms/{room_id}/score", json={"layout": moved}))
    assert isinstance(first.get("metrics"), dict) and isinstance(second.get("metrics"), dict)
    return second


def _move_listener(client: Any, state: dict[str, Any]) -> Any:
    room_id = state["room_id"]
    room = _require(client.get(f"/rooms/{room_id}"))
    position = list(room["listener"]["position"])
    position[0] += 0.25
    _require(client.patch(
        f"/rooms/{room_id}/listener",
        json={"position": position, "facing": room["listener"]["facing"]},
    ))
    return _require(client.post(f"/rooms/{room_id}/optimize", json={}))


def _products(client: Any, state: dict[str, Any], budget: float) -> Any:
    result = _require(client.get(f"/rooms/{state['room_id']}/products", params={"budget": budget}))
    assert result["total"] <= budget, result
    for item in result.get("items", []):
        assert all(item.get(key) for key in ("role", "title", "link")) and isinstance(item["price"], (int, float)), item
    sources = sorted({str(item["source"]) for item in result.get("items", []) if item.get("source")})
    detail = "ok" if not sources else f"ok source={','.join(sources)}"
    return {**result, "_step_detail": detail}


def _scan(client: Any, state: dict[str, Any]) -> Any:
    payload = {"captured_room": json.loads(ROOMPLAN.read_text(encoding="utf-8"))}
    room = _require(client.post("/rooms", json=payload))
    assert room.get("frame") is not None, room
    result = _require(client.post(f"/rooms/{room['room_id']}/optimize", json={}))
    assert result["layout"]["speakers"], result
    # run_e2e adds result["metrics"]["warnings"] itself, so only add the room's and the top-level ones here.
    warnings = _warnings(room) + [str(item) for item in result.get("warnings", [])]
    return {**result, "warnings": warnings}


def _rectangle(client: Any, state: dict[str, Any]) -> Any:
    room = _require(client.post("/rooms/rect", json={"width": 15, "length": 12}))
    result = _require(client.post(f"/rooms/{room['room_id']}/optimize", json={}))
    assert len(result["layout"]["speakers"]) == 6
    return result


def _missing_room(client: Any) -> Any:
    response = client.get("/rooms/does-not-exist")
    payload = _require(response, 404)
    assert "detail" in payload, payload
    return payload


def _web(client: Any) -> Any:
    """Check the built web shell when this deployment includes it."""
    response = client.get("/app/")
    if response.status_code == 404:
        return {"_step_detail": "skipped: web build not present"}
    payload = response.text
    assert response.status_code == 200, response.status_code
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', payload)
    assert scripts, "web shell has no module script"
    script = scripts[0]
    script_response = client.get(script if script.startswith("/") else f"/app/{script}")
    assert script_response.status_code == 200, script_response.status_code
    return {"_step_detail": "ok"}


def _print_results(results: list[StepResult], *, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps([asdict(result) for result in results]))
        return
    for result in results:
        print(f"{result.status} {result.step} {result.elapsed_ms:.0f}ms {result.detail}")
        for warning in result.warnings:
            print(f"WARN {result.step} 0ms {warning}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Sweet Spot backend demo flow")
    parser.add_argument("base_url")
    parser.add_argument("--budget", type=float, default=1500.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--wait-refined", type=float, default=0.0, metavar="SECONDS")
    parser.add_argument("--preset", choices=("5.1", "7.1.4"), default="5.1")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        results = run_e2e(client, budget=args.budget, wait_refined=args.wait_refined, preset=args.preset)
    _print_results(results, json_output=args.json_output)
    return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
