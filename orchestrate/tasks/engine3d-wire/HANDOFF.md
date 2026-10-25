# engine3d-wire handoff

## Completed

- Added staged 3D refinement: optimize returns the existing quick six-speaker result, queues one full-search run (`fast=False`), and exposes `refining` then `refined` through `GET /layout`. `ENGINE3D_BACKEND=off` keeps the quick path only. `ENGINE3D_TIMEOUT_S` defaults to 150 seconds.
- The daemon worker has a four-job queue, same-room queued-job replacement, per-room layout versions, a room/listener/material fingerprint, a validated disk cache, and safe failure fallback. States are `idle -> queued -> running -> done|failed|superseded`; cache hits go directly to `done` with `from_cache: true`.
- Extended the 3D layout schema, scoring, stub, legacy product adapter, contracts, and optional e2e refined polling. Slow CLI parity and validation tests remain deselected by default.
- Retry 1: the worker requests `fast=False` from runners that support it. For the current merged runner, a compatibility path makes its CLI command omit `--fast`. Tests cover both paths.
- Retry 2: room writes and the worker's final fingerprint check plus layout save now share `store.room_layout_lock`, so a room update cannot pass between validation and commit. Room files also use atomic replacement. Optimization refreshes its room snapshot under that lock. `GET /layout` repairs persisted interrupted jobs on its own, and startup scans for and repairs them even when the worker is disabled. Added regression tests for both the write race and restart repair.

## Validation

- `python -m ruff check .`: passed.
- `backend/tests/test_refine.py`: 10 passed after the final edits, using a system-temp pytest base directory.
- Full `python -m pytest -q`: 365 passed, 12 deselected, 1 failed in 7m44s. The sole failure is `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax`: on this Windows host, `bash` resolves to the WSL launcher, which exits 1 with access denied before checking the script. That test is outside OWNS.txt. No pytest temporary directories were created in the repo by this retry.
- `git diff --check`: passed before the final handoff update.

## Unfinished / orchestrator action

- The engine3d-core owner should expose `fast: bool` directly on `engine3d.run_scene` and pass it to `build_command`; then the owned compatibility path can be removed. The core runner is outside OWNS.txt.
- `docs/API.md` section 2a lists optimize states only `idle|running|failed`, while the brief requires `idle|queued|running|done|failed|superseded` and `from_cache`. The brief's `ENGINE3D_BACKEND` and `ENGINE3D_TIMEOUT_S` are also absent from the orchestrator-owned env contract.
- The Bash syntax test's WSL access-denied behavior is an environment/test issue for the deploy test owner. No deploy test file was changed.

## Design questions

- Should the core runner expose `fast: bool` directly? This task uses a reversible compatibility path in the owned refinement module; the alternative is to update the unowned core runner and remove that path.
