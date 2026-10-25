# gemini-limits: stop duplicate Gemini calls (join, cache, rate limit) and expose progress

## Goal
Bug seen on the live server: the user tapped the app's photo/classify button 5 times and 5 Gemini calls ran at once (each 5 to 20 s), with no feedback. `POST /rooms/{room_id}/materials` is a plain `def` endpoint, so every request runs its own `classify_materials` call. Add join / cache / limits and a status endpoint exactly as docs/API.md section 6 specifies (paragraph "Gemini limits on `POST /rooms/{id}/materials`" and the `GET /rooms/{id}/materials/status` row; env vars in section 8).

## Read first
docs/API.md section 6 (that paragraph and the status row; authoritative), backend/app/materials_router.py, backend/app/materials.py (`classify_materials`, the Gemini and mock backends, `prepare_image`, `MIN_CONFIDENCE`), backend/app/store.py (`list_photos`, `save_room`), backend/tests/test_materials_router.py, test_materials.py, backend/tests/contract/test_materials_contract.py.

## Design decisions this brief encodes (do not change)
- New module `backend/app/gemini_limits.py` (pure, threadsafe, no network) holding: a per-room in-flight registry (join: the first request runs the classification, later requests for the same room wait on it with a 120 s cap and return the SAME result with `"status": "joined"`; if the first fails, joiners get the same HTTP error), a result cache (10 min TTL, max 128 entries, key = room id + sorted `(surface_id, sha256(image bytes))` + backend name; a cached result still re-applies materials to the room idempotently), a token-bucket/sliding-window limiter for REAL Gemini calls only (`GEMINI_MAX_PER_MINUTE` default 6) and a concurrency semaphore (`GEMINI_MAX_CONCURRENT` default 2, waits up to 30 s, else 429). An injectable clock for tests.
- 429 response: HTTP 429, header `Retry-After: <int seconds>`, JSON `{"detail": "Gemini is busy; retry in N s", "retry_after_s": N}` with N >= 1.
- The mock backend (`MATERIALS_BACKEND=mock`), rooms with no photos and cached/joined responses never consume the limiter. Only an actual Gemini classification call does.
- `POST /rooms/{id}/materials` stays synchronous (no job queue, no 202). The success body stays `{"surfaces": [...]}` plus the optional `"status": "fresh" | "cached" | "joined"`.
- `GET /rooms/{id}/materials/status` returns `{"state": "idle"|"running", "started_at": iso|null, "elapsed_s": float|null, "photos": int}` from the registry (and the stored photo count); 404 for an unknown room; never calls Gemini.
- Photo upload (`POST /rooms/{id}/photos`) is not rate limited by this task, but replacing a photo changes the cache key naturally.
- Handle the case where the Gemini SDK raises or times out: the in-flight entry must always be released (try/finally) so later requests do not hang; failures are not cached.
- Do not change the classification prompt, parsing, absorption table, `applied` semantics or the contract tests; update `backend/tests/test_materials_router.py` only where an assertion encodes the old behaviour (say so in HANDOFF.md).

## Deliverables
1. `backend/app/gemini_limits.py` and the changes in `backend/app/materials_router.py` (and `backend/app/materials.py` only if needed to expose the backend name).
2. Tests in `backend/tests/test_gemini_limits.py` (the only new test file; fake clock, fake classifier counting calls, threads for concurrency): 5 simultaneous requests for one room -> exactly 1 classifier call, 4 `joined`, identical bodies; a repeat with unchanged photos -> `cached`, 0 calls; changed photo -> fresh call; per-minute limit -> 429 with `Retry-After` and body; concurrency cap; limiter not consumed by mock/cached/joined; failure releases the in-flight entry and later requests work; status endpoint idle/running (use a blocking fake classifier) and 404; 5 rapid HTTP requests through TestClient against a slow fake classifier (threads) prove the single call.
3. HANDOFF.md: what changed, the defaults, any contract doubt.

## Done when
`python -m ruff check . && python -m pytest -q` passes; no edits outside OWNS.txt.

## Out of scope
The Swift app (another task), prompts and models, products, polygon work, docs. Put unsettled choices under `## Design questions` in HANDOFF.md.
