# engine3d-wire handoff

## Completed

- Added `backend/app/refine.py`: one daemon worker, four queued jobs, same-room queued-job replacement, version and room-fingerprint checks, disk cache, persisted status, safe failure fallback, and short compliance warnings. A listener or material change supersedes a running result. A restart marks an interrupted job failed and restores the quick layout stage.
- `POST /rooms/{id}/optimize` now validates preset/standard, returns the existing quick six-role result immediately, and queues refinement unless disabled or cached. `GET /layout` exposes `refining` and `refined`; `GET /optimize/status` reports `idle|queued|running|done|failed|superseded`. Cache hits return `refined` immediately. `ENGINE3D_BACKEND=off` keeps the quick path only.
- Extended layout/speaker schemas and scoring for 3D roles; kept stub and products adapter compatible with legacy 5.1 roles. Added optional refined polling to `tools/e2e.py` and kept deploy smoke quick-only.
- Added API, cache, supersession, failure, schema, products, and contract tests. Real CLI parity and `--validate` tests are marked `slow` and `live` so default tests do not run the engine.

## Validation

- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/test_refine.py backend/tests/test_engine3d_wire.py -q --basetemp=.pytest_refine4`: 10 passed, 2 deselected.
- `python -m pytest -q --basetemp=.pytest_full2`: 360 passed, 1 failed, 12 deselected. The failure is `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax`: on this Windows host `bash` resolves to the WSL launcher, which exits 1 with an access-denied message in stdout. This test is outside OWNS.txt. The default pytest temp directory is also inaccessible here, so tests need `--basetemp` in the writable worktree.
- `git diff --check`: passed.

## Unfinished / orchestrator action

- The merged, unowned `backend/app/engine3d.py` has `run_scene(..., timeout_s, workdir)` with no `fast` argument and calls `build_command` with its default `fast=True`. The brief requires `run_scene(..., fast=False)` for full search. Please have the engine3d-core owner add and forward that parameter, then change the call in `refine.py` to pass `fast=False` and update the fake runner tests accordingly. Current real refinement uses fast search. No change was made to the unowned file.
- `docs/API.md` section 2a lists optimize states `idle|running|failed`, while the brief requires `idle|queued|running|done|failed|superseded` and `from_cache`. The brief also adds `ENGINE3D_BACKEND` and `ENGINE3D_TIMEOUT_S`, which are not yet in the orchestrator-owned API/env contract. Default timeout is 150 seconds.
- Worktree-local `.pytest_*` directories are generated test artifacts and must not be committed. The prior worktree already contained several; this run added `.pytest_full2`, `.pytest_refine3`, and `.pytest_refine4`. Automated deletion was rejected by the environment policy.

## Design questions

- none
