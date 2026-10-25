# integrate: end-to-end script, in-process e2e tests, demo runbook

## Goal
One command proves the whole backend demo path works on any deployment: `python tools/e2e.py https://144-202-27-51.sslip.io` (or `http://localhost:8000`). The same flow runs in the normal test suite in-process (no network), and DEMO.md tells a teammate exactly how to run the demo and what to do when something breaks.

## Read first
docs/API.md section 6 (endpoints, errors), docs/TESTING.md sections 2 (L4/L5) and 3.9, deploy/smoke.sh (do not edit; e2e goes deeper than smoke), DEPLOY.md, fixtures/room_demo.json, fixtures/roomplan_sample.json, phoneapp_context/sample_payloads/post_rooms_request.example.json, backend/tests/conftest.py (DATA_DIR tmp setup), pytest.ini (`live` marker is opt-in).

## Design decisions this brief encodes (do not change)
- `tools/e2e.py` is a library + CLI. Core: `run_e2e(client, *, budget=1500.0) -> list[StepResult]`, where `client` is anything with the `get/post/patch` interface of httpx.Client (so FastAPI TestClient works too). CLI: `python tools/e2e.py BASE_URL [--budget N] [--timeout S] [--json]` builds an `httpx.Client(base_url=..., timeout=...)`, prints one line per step `PASS|FAIL|WARN <step> <ms>ms <detail>`, exits 1 on any FAIL. Dependencies: stdlib + httpx (+ Pillow only if you need to synthesize a JPEG). No new packages.
- Steps, in order (stop the flow at the first FAIL whose output later steps need):
  1. `GET /health`.
  2. Pairing: `POST /sessions` -> `POST /sessions/by-code` with its code returns the same session_id -> `GET /sessions/{id}` is `waiting`.
  3. Demo room: `POST /rooms/demo` with the session_id -> session becomes `ready` with that room_id.
  4. `GET /rooms/{id}/photo-targets` non-empty; upload one small valid JPEG to the first target (`POST /rooms/{id}/photos`, multipart); `POST /rooms/{id}/materials` returns `surfaces`.
  5. `POST /rooms/{id}/optimize` -> six speakers (roles L R C LFE Ls Rs), metrics present; `GET /rooms/{id}/layout` equals it.
  6. `POST /rooms/{id}/score` with that layout returns metrics; then move L by 1 ft (staying inside the room) and score again: metrics returned, no 5xx.
  7. `PATCH /rooms/{id}/listener` (small move, same facing), then optimize again succeeds.
  8. `GET /rooms/{id}/products?budget=N`: `total <= budget`, items have role/title/price/link.
  9. Scan path: `POST /rooms` with `{"captured_room": <fixtures/roomplan_sample.json>}` -> Room JSON with `frame`; optimize it.
  10. Rect path: `POST /rooms/rect` 15 x 12 ft -> optimize.
  11. Error path: `GET /rooms/does-not-exist` is 404 with `detail`.
- Any `warnings` in responses are printed as WARN lines, not failures. API keys are NOT set on the server yet: materials (Gemini mock) and products (stub) results are acceptable; report which provider answered if the response says so, never require real providers.
- Fixture paths are resolved relative to the repo root (`Path(__file__).resolve().parents[1]`), so the CLI works from any cwd.

## Deliverables
1. `tools/e2e.py` as above, type-hinted, small functions, no print debugging beyond the step lines.
2. `backend/tests/e2e/__init__.py`, `backend/tests/e2e/test_e2e_inprocess.py`: runs `run_e2e(TestClient(app))` with DATA_DIR in a tmp dir and asserts every step PASS; plus unit tests for the CLI output/exit code using a fake client that fails one step. `backend/tests/e2e/test_e2e_live.py`: marked `live`, skipped unless env `E2E_BASE_URL` is set, runs the CLI flow against it.
3. `DEMO.md` (repo root): (a) pre-demo checklist (server up, `bash deploy/smoke.sh <url>`, `python tools/e2e.py <url>`, phone on cellular, laptop browser open at `/app/plot2d/`, saved scan ready); (b) the demo script with timings: laptop QR -> phone pairs -> scan (or saved scan) -> photos -> optimize -> 2D plot / AR -> shopping list; (c) failure drills from TESTING.md 3.9/L5, each with symptom -> what to do -> how to verify: Gemini key missing/invalid, SerpApi quota exhausted (products stub), Wi-Fi off (phone on hotspot), live scan fails (saved scan / `POST /rooms/demo`), backend restarted mid-demo (sessions are in memory: re-pair; rooms persist in /data), browser refresh mid-demo, deploy broke (rollback to `demo-ok` per DEPLOY.md). Mark steps that depend on the unfinished web app or products module as "pending".

## Done when
`python -m pytest -q` passes (in-process e2e included; live test skipped); `python -m ruff check tools/e2e.py backend/tests/e2e` passes (ruff.toml at the root); `python tools/e2e.py --help` works; no edits outside OWNS.txt.

## Out of scope
Changing backend endpoints or fixtures (if the API disagrees with docs/API.md, report it in HANDOFF.md instead of patching), deploy/*, smoke.sh, web app, iOS. Put unsettled choices under `## Design questions` in HANDOFF.md.

## Retry 1: review findings to fix (all valid)
- tools/e2e.py:53 warning extraction must also read `metrics.warnings` (optimize and score responses), printing each as a WARN line.
- tools/e2e.py:139 the optimize step must verify there are exactly six speakers whose roles are exactly {L,R,C,LFE,Ls,Rs} (no duplicates).
- tools/e2e.py:152 the score step must move the speaker whose `role == "L"`, not the first speaker in the list (order is not guaranteed).
Add or extend tests for each (fake client responses). Keep `ruff check tools/e2e.py backend/tests/e2e` and the full suite green.
