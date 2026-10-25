# engine3d-wire: staged quick/refined layouts using the 3D engine (backend wiring)

## Goal
`backend/app/engine3d.py` (task engine3d-core, merged) can run the teammate's 3D speakerplacer headless and map its output into our layout. Wire it into the API exactly as docs/API.md section 2a specifies: `POST /rooms/{id}/optimize` keeps answering immediately with the existing QUICK result (`stage: "quick"`) and starts ONE background 3D run; `GET /rooms/{id}/layout` returns the latest layout with `stage` `"refining"` while it runs and `"refined"` when done; `GET /rooms/{id}/optimize/status` reports the job. A full run takes about 90 s (placement about 12 s, the rest is reports and plots), so it must never block a request.

## Read first
docs/API.md sections 2, 2a, 3 and 6 (authoritative), docs/ENGINE_INTEGRATION_AUDIT.md (rows 2-7, 10, 11, 12), backend/app/engine3d.py (`run_scene`, `to_layout`, `build_command`, `EngineError`, `PRESETS`), backend/app/engine.py and engine_speakerplacer.py (the quick path; do not change its behaviour), backend/app/rooms.py (optimize/score/layout routes), backend/app/schemas.py (`Role`, `Layout`, speaker models), backend/app/store.py, backend/app/acoustics.py (`/score`), backend/app/stubs/engine_stub.py, backend/app/products.py (the loader), backend/tests/contract/checks.py and test_engine_contract.py, tools/e2e.py, deploy/smoke.sh, fixtures/engine/*.json.

## Design decisions this brief encodes (user-confirmed staged design; do not change)
- **Quick stays quick and unchanged**: same code path, same response shape; add `"stage": "quick"` (or `"refined"` on a cache hit) and `"preset"` to the response and to the stored layout. Clients that ignore new fields keep working.
- **Refinement job**: new module `backend/app/refine.py` with a single worker thread and a small queue (max 4; a newer job for the same room replaces an older queued one). One 3D run at a time on the whole server. The job calls `engine3d.run_scene(..., fast=False)` (the full search is the default: measured fast 74 s vs full 86 s and fast moves the subwoofer) with timeout `ENGINE3D_TIMEOUT_S` (default 150), then `engine3d.to_layout`. Env `ENGINE3D_BACKEND=auto|off` (default auto; `off` never starts a job; the test suite sets `off` in `conftest.py` by default and tests that need jobs monkeypatch `engine3d.run_scene` with a fake: NO test may run the real engine unless marked `slow`/`live`).
- **Request options**: `POST /rooms/{id}/optimize` body `{"options": {"preset": "5.1|7.1|5.1.2|5.1.4|7.1.2|7.1.4", "standard": "dolby|itu|thx", "refine": true}}`; defaults 5.1 / dolby / true; invalid preset or standard -> 422. The quick result is ALWAYS the six-role 5.1 layout (the quick engine only does 5.1); for other presets the quick result still has six roles and a warning `quick preview is 5.1 only; waiting for the 3D <preset> result`.
- **Versioning**: every optimize bumps a per-room `layout_version`; a finished job applies its result ONLY if the room's version, listener and materials fingerprint still match the ones it started with; a stale result is dropped (job state `superseded`). A manual drag/score never changes the stored layout version; saving a dragged layout (if the code stores one) makes a later refined result not overwrite it unless a new optimize ran.
- **Cache**: refined results are cached on disk per `(room fingerprint, listener, preset, standard, materials)` under `$DATA_DIR/cache/engine3d/` (JSON); a cache hit makes `POST optimize` return the refined layout immediately with `stage: "refined"` and `from_cache: true` in the status. Cache entries are validated by `schema_version` and ignored when corrupt.
- **Status endpoint**: `GET /rooms/{id}/optimize/status` -> `{"state": "idle|queued|running|done|failed|superseded", "preset", "standard", "started_at", "elapsed_s", "error": null|str, "from_cache": bool}`; 404 for unknown rooms; never starts work.
- **Failure handling**: any `EngineError`/exception -> state `failed`, the stored layout stays the quick one with `stage: "quick"` and `warnings` gets `3D refinement failed: <short reason>` (no stack traces, no paths); the API never returns 5xx because of the engine.
- **Layout storage**: `store` persists `stage`, `preset`, `standard`; `GET /rooms/{id}/layout` returns the latest stored layout (quick while refining with `"stage": "refining"`, refined after). Metrics for a refined layout: compute our usual `metrics` via `acoustics.py` for the 5.1-compatible subset (consistency with `/score`), and attach `metrics.engine` from `to_layout` plus compliance warnings: every non-PASS compliance row becomes a short line in `metrics.warnings` (at most 10, e.g. `C elevation 4 deg outside -10..+15: WARN`).
- **Schema**: widen `Role` to `L R C LFE Ls Rs Lss Rss Lrs Rrs Ltf Rtf Ltr Rtr Ltm Rtm LFE2`; speakers gain the optional fields from API.md 2a; Layout gains optional `preset`, `standard`, `stage`, `seats`, `projector`; existing fixtures and `fixtures/room_*.json` must still validate unchanged.
- **`/score`**: must accept layouts with the new roles and 3D positions: extend the ITU angle target table in `acoustics.py` for `Lss/Rss` (90 deg), `Lrs/Rrs` (140 deg) and ignore overhead/`LFE2` roles for angle penalties (still count them for coverage); never raise on unknown roles; stays fast (< 1 s).
- **Stub**: `engine_stub` accepts the preset option, keeps six roles, adds the 5.1-only warning for other presets.
- **Products loader** (`backend/app/products.py`): pass the recommender a layout reduced to the legacy roles (map `Lss/Rss` to `Ls/Rs`, drop `Lrs Rrs` overheads and `LFE2` for now) so the recommender never sees roles it does not know; the products task adds the new roles later.
- **Contract tests**: widen `ROLES` in `backend/tests/contract/checks.py`, keep `full_51` strict for the default preset; add a refined-layout contract check using `fixtures/engine/*.json` through `to_layout`.
- **e2e + smoke**: `tools/e2e.py` keeps its quick-path steps and adds an optional step `refined` (flag `--wait-refined SECONDS`, default 0 = skip) that polls `/optimize/status` and then checks `stage == "refined"` and the layout roles; `deploy/smoke.sh` stays quick-path only but its `optimize` step must accept the new `stage` field and a `--max-time` large enough for a cold start (90 s).
- **Robustness extras requested by the user**: (1) a `slow`-marked parity test: `engine3d.run_scene` output equals what the engine CLI itself writes for the same arguments (compare speaker positions to 1e-6); (2) a `slow`-marked test that runs the engine's `--validate` once on a small room and asserts exit 0; (3) compliance warnings visible as described above.
- No changes to anything under `speakerplacer/`, `products/`, web/, iOS, or docs/API.md (the orchestrator owns the contract; report doubts in HANDOFF.md).

## Deliverables
1. `backend/app/refine.py` (job queue, worker thread, versioning, cache, status), changes in `rooms.py`, `store.py`, `schemas.py`, `acoustics.py`, `engine.py` (only to expose the stage/preset plumbing), `stubs/engine_stub.py`, `products.py`, `main.py` (startup/shutdown of the worker thread; the thread must be a daemon and must not start when `ENGINE3D_BACKEND=off`).
2. Tests: `backend/tests/test_refine.py` and `backend/tests/test_engine3d_wire.py` (fake `run_scene` that sleeps a little and returns the 5.1 fixture): quick response contains `stage: quick` immediately (< 1 s) while the job runs; `GET layout` shows `refining` then `refined` after the fake finishes; status transitions; cache hit returns refined at once and skips the runner; superseded job dropped after a second optimize or a listener change; failure leaves quick + warning; invalid options 422; 7.1.4 fake returns 12 roles and `/score` accepts it; stub preset warning; compliance WARN rows appear in `metrics.warnings`; contract checks pass; the whole existing suite stays green. Slow tests for parity and `--validate` marked `slow`/`live` (deselected by default).
3. `conftest.py` setting `ENGINE3D_BACKEND=off` for the default test run.
4. HANDOFF.md: what changed, env vars (`ENGINE3D_BACKEND`, `ENGINE3D_TIMEOUT_S`), the job state machine, anything in docs/API.md that disagrees with the implementation.

## Done when
`python -m ruff check . && python -m pytest -q` passes (slow/live deselected); no edits outside OWNS.txt.

## Out of scope
Polygon rooms, products roles (products-theater later), plot2d, iOS, web, docs, deploy config, teammate engine code. Put unsettled choices under `## Design questions` in HANDOFF.md.


## RETRY 1 (review VERDICT: ISSUES) - fix, keep full suite green
VERDICT: ISSUES
backend/app/refine.py:249 â€” Refinement invokes `run_scene` without `fast=False`; `engine3d.run_scene` therefore uses `--fast`, violating the required full-search refinement.
Also: do NOT create .pytest_* / --basetemp directories inside the repo (the sandbox user owns them and the orchestrator cannot read or delete them). If pytest needs a temp dir, use the default or one under the system temp. Add a test that refine passes fast=False.



## RETRY 2 (second review VERDICT: ISSUES) - fix both, keep the full suite green
VERDICT: ISSUES
backend/app/refine.py:285 Listener/material fingerprint validation and result save are not atomic; an update between the check and line 307 can leave a stale refined layout applied, violating stale-result protection.
backend/app/refine.py:92 Interrupted jobs are repaired only when the status endpoint is called; after restart, `GET /layout` alone can return `stage: "refining"` forever although no job exists.
Fix guidance: make the fingerprint validation and the result save one atomic step under the same lock (re-check inside the lock); repair interrupted jobs also on read paths (GET /layout and at startup), not only in the status endpoint. Add tests for both. Do NOT create .pytest_* dirs in the repo.

