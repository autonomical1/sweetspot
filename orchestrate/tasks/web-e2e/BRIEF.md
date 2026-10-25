# web-e2e: end-to-end tests for the web flows

## Goal
Automated proof that the web flows work against the real backend contract: demo room, optimize (quick then refined), score on drag, pairing by QR, and shop/panels data.

## Design decisions encoded
- No browser automation dependency (no network to install Playwright). Two layers: (1) **vitest + jsdom integration tests** that mount `App` with a fake `fetch` driven by `webapp_context/sample_payloads/*` and `fixtures/engine/*.json`, covering the user flows; (2) **Python tests** that run the real FastAPI app in-process (TestClient, `DATA_DIR` tmp) and assert the exact response shapes the web client types expect (a contract test: parse each real response with the TypeScript types' JSON schema or a hand-written shape check kept next to the fixtures).
- Extend `tools/e2e.py` with a web section: after the API flow, fetch `/app/` and its main script and assert 200 (works against the live site when the web build exists; skipped with a clear message otherwise).
- The orchestrator performs the final manual browser run on https://sweetspotav.tech; this task does not.

## Deliverables
1. `webapp/src/e2e/*.test.tsx`: flows: (a) Use demo room -> loading -> layout drawn (scene model has all roles) -> panels show score; (b) quick layout then refined replaces it; user edit wins conflict; (c) drag -> score request throttled, stale response ignored; (d) Pair your iPhone -> QR value equals `pair_url` verbatim, no 6-character code anywhere in the DOM, polling stops when ready, switches to the viewer; (e) Gemini 429 countdown; (f) WebGL unavailable -> 2D default.
2. `backend/tests/e2e/test_web_contract.py`: calls demo, optimize, score, layout, products, sessions through TestClient and checks the fields the web client reads.
3. `tools/e2e.py`: optional web checks.

## Done when
`cd webapp && npm test && npm run typecheck` pass; `python -m ruff check . && python -m pytest -q` pass. Flaky timing is replaced by fake timers.

## Out of scope
Production code changes (report failing flows in HANDOFF.md instead of fixing them), Dockerfile, backend.

## Files you own
`webapp/src/e2e/**`, `backend/tests/e2e/test_web_contract.py`, `tools/e2e.py`.
