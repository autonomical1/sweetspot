# engine3d-wire handoff

## Completed

- Added `backend/app/refine.py`: one daemon worker, four queued jobs, same-room queued-job replacement, version and room-fingerprint checks, disk cache, persisted status, safe failure fallback, and short compliance warnings. A listener or material change supersedes a running result. A restart marks an interrupted job failed and restores the quick layout stage.
- `POST /rooms/{id}/optimize` now validates preset/standard, returns the existing quick six-role result immediately, and queues refinement unless disabled or cached. `GET /layout` exposes `refining` and `refined`; `GET /optimize/status` reports `idle|queued|running|done|failed|superseded`. Cache hits return `refined` immediately. `ENGINE3D_BACKEND=off` keeps the quick path only.
- Extended layout/speaker schemas and scoring for 3D roles; kept stub and products adapter compatible with legacy 5.1 roles. Added optional refined polling to `tools/e2e.py` and kept deploy smoke quick-only.
- Added API, cache, supersession, failure, schema, products, and contract tests. Real CLI parity and `--validate` tests are marked `slow` and `live` so default tests do not run the engine.
- Fixed the retry issue: refinement requests `fast=False` when the runner supports it. The current merged runner lacks that argument, so a compatibility path makes its CLI builder omit `--fast` while retaining its timeout and cleanup. Added tests for both call paths without running the real engine.

## Validation

- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/test_refine.py -q` with a system-temp `--basetemp`: 7 passed. The tests verify `fast=False` reaches a runner that accepts it and that the current runner constructs a CLI command without `--fast`.
- `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax` fails on this Windows host: `bash` resolves to the WSL launcher, which exits 1 with access denied before checking the script. This test is outside OWNS.txt.
- `python -m pytest -q -k 'not test_smoke_script_has_valid_bash_syntax'` with a system-temp `--basetemp`: 362 passed, 13 deselected in 7m18s. Twelve are the default `live` deselections; the thirteenth is the Bash test above.
- `git diff --check`: passed.

## Unfinished / orchestrator action

- The engine3d-core owner should add `fast: bool` to `engine3d.run_scene` and pass it to `build_command`. The compatibility path can then be removed. This file is outside OWNS.txt.
- `docs/API.md` section 2a lists optimize states `idle|running|failed`, while the brief requires `idle|queued|running|done|failed|superseded` and `from_cache`. The brief also adds `ENGINE3D_BACKEND` and `ENGINE3D_TIMEOUT_S`, which are not yet in the orchestrator-owned API/env contract. Default timeout is 150 seconds.
- The previous run's worktree-local `.pytest_*` artifacts should not be committed. This retry creates pytest temporary files under the system temp directory.

## Design questions

- Should the core runner expose `fast: bool` directly? This task uses a reversible compatibility path in the owned refinement module; the alternative is to update the unowned core runner now and remove the compatibility path.
