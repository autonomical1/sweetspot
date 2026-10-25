# speakerplacer-speed handoff

## Done
- Kept the golden quick-layout answers identical while caching repeated polygon validation, room modal basis data, RIR clarity terms, imaging terms, headroom, and cabinet fit checks. Vectorized the model response over modal frequencies, removed duplicate toe-angle scoring, and deferred plotting imports until a viewer is opened.
- Golden timings on this machine (seconds): `large_scan` 37.9 -> 16.5; `rect_15x18` 36.2 -> 10.6; `rect_12x14` 38.9 -> 9.1. `python tools/golden_speakerplacer.py check` prints `IDENTICAL`.
- `python -m ruff check .` and `git diff --check` pass. `python tools/smoke_tests.py` passes (117 tests) and `python -m pytest backend/tests/test_engine_speakerplacer.py -q` passes (4 tests).

## Unfinished
- Pytest's default system temp location is inaccessible in this sandbox, so the passing runs used `PYTEST_ADDOPTS=--basetemp=...`. Windows argument parsing created an untracked temporary directory at `UsersneelmDesktopsweetspot-wtspeakerplacer-speed.pytest_speakerplacer_speed/` in the repository root. Automatic approval review rejected both recursive and verified per-item deletion. The harness must exclude or remove this test directory before committing; it is not source code. An ignored `.pytest_cache/` may also have been created by pytest.

## Decisions
- Cache keys use exact numeric values and array bytes, with bounded caches. No rounding was introduced in scoring or geometry.
- The first smoke run failed 26 test setups because pytest could not access `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm`; rerunning with a writable workspace temp path passed all 117 tests.

## Design questions
- none
