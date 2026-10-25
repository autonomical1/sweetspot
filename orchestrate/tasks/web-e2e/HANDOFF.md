# Handoff: web-e2e

## What I did

- Added `webapp/src/e2e/flows.test.tsx` covering demo-room loading and six-speaker rendering, quick/refined replacement with user-edit conflict handling, throttled drag scoring with latest-result behavior, QR pairing/poll-stop behavior, Gemini 429 retry messaging, and the WebGL-unavailable 2D fallback.
- Added `backend/tests/e2e/test_web_contract.py` covering the web-consumed response shapes for sessions, demo rooms, optimize, score, saved layout, and products using the real FastAPI app with stub backends.
- Extended `tools/e2e.py` with an optional `/app/` shell and main-script check that skips clearly when no web build is present.
- Made the jsdom flow tests deterministic with a local-storage stub, cleanup between tests, and fake timers around polling/score queue behavior.

## Verification

- `cd webapp && npm.cmd test` — 53 passed.
- `cd webapp && npm.cmd run typecheck` — passed.
- `python -m pytest backend/tests/e2e/test_web_contract.py -q --basetemp .pytest-web-e2e` — 1 passed (one unrelated deprecation warning).
- `python -m ruff check tools/e2e.py backend/tests/e2e/test_web_contract.py` — passed.

## Unfinished

- None within this task. The final manual browser run against the deployed site remains orchestrator-owned per the brief.

## Design questions

- none
