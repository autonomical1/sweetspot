# speakerplacer-multicore: spread the speakerplacer search over all CPU cores

## Why
The search (`speakerplacer.optimize_layout`, called by `backend/app/engine_speakerplacer._optimize` and by the 3D engine CLI `python -m speakerplacer`) runs on ONE core. The VPS has 4 cores and this machine has more. Task `speakerplacer-speed` (merged before this one) removed single-thread waste; this task parallelises what is left.

## Deliverables
1. Evaluate independent candidates / candidate pairs / speaker types in parallel with `concurrent.futures.ProcessPoolExecutor` (spawn-safe: top-level worker functions, picklable arguments, no globals that differ per process). Typical hot loops: `_evaluate_group` per candidate group, `_imaging_terms` per candidate, `_wall_box_fits` per candidate, the modal evaluation per pair. Pick the coarsest independent unit that gives good scaling (chunk work so process start-up and pickling stay small).
2. Worker count: env `SPEAKERPLACER_WORKERS` (integer; default `min(os.cpu_count(), 8)`; `1` = today's serial code path, used by tests). Add a keyword argument to `optimize_layout` only if needed, defaulting to the env value. Reuse one pool per call (do not start a pool per candidate). Fall back to serial if the pool cannot start or the work is tiny.
3. Deterministic: the merge order must be fixed so results are IDENTICAL to serial (ties broken exactly as before).
4. Do not oversubscribe: BLAS/numpy threads inside workers must be limited (`OMP_NUM_THREADS=1` etc. set in the worker initializer).

## Golden check and targets
`PYTHONPATH=. python tools/golden_speakerplacer.py check` must print IDENTICAL with the default worker count AND with `SPEAKERPLACER_WORKERS=1`. Report the three room timings with 1, 2 and 4 workers in HANDOFF.md. Target on a 4-core machine: at least 2.5x faster than `SPEAKERPLACER_WORKERS=1` on `large_scan`.

## Constraints
No new dependencies. Keep function signatures compatible. The backend runs the search inside a child process it may kill on a deadline (`engine_speakerplacer._optimize_isolated`): make sure killing the parent leaves no orphan workers (daemon workers / pool shut down on exit; test it by killing a run midway). Do not run the whole pytest suite: run `python -m ruff check .`, `python tools/smoke_tests.py`, the golden check, `python -m pytest backend/tests/test_engine_speakerplacer.py -q`.

## Out of scope
Backend adapter, web, iOS, 3D engine CLI flags (the CLI picks the env var up on its own).

## Files you own
`speakerplacer/*.py`, `orchestrate/tasks/speakerplacer-multicore/HANDOFF.md`.
