# mc-wire: use the process-pool helper inside the speakerplacer search

## Depends on
`speakerplacer-speed` (serial speed-ups in `optimize.py`, `room.py`, `room_acoustics.py`, `scoring.py`) and `mc-pool` (`speakerplacer/parallel.py` with `worker_count()` and `ordered_map()`). Both are merged into your branch before you start; read them first.

## Goal
Run the independent heavy loops of `speakerplacer.optimize_layout` through `parallel.ordered_map` so a 4-core machine is at least 2.5x faster than `SPEAKERPLACER_WORKERS=1`, with results IDENTICAL to serial.

## What to do
1. Profile the sped-up serial code (`python -m cProfile` on `tools/golden_speakerplacer.py check` with `SPEAKERPLACER_WORKERS=1`) and pick the coarsest independent unit that scales: typically candidate groups in `_evaluate_group`, candidates in `_imaging_terms` / `_wall_box_fits`, or modal evaluations per pair. Work units must be top-level picklable functions with small picklable arguments (convert dataclasses/arrays as needed; avoid shipping the whole room per item: use a per-pool initializer or pass it once per chunk).
2. Per-process caches added by the serial task (lru_cache etc.) are warm per worker: chunk so each worker reuses them.
3. Keep the merge order fixed so ties break exactly as in serial.
4. `SPEAKERPLACER_WORKERS=1` must run the original serial code path.

## Check
`PYTHONPATH=. python tools/golden_speakerplacer.py check` must print IDENTICAL with the default worker count and with `SPEAKERPLACER_WORKERS=1`. `python tools/bench_speakerplacer.py 1 2 4` prints timings; put the table in HANDOFF.md. Also run `python -m ruff check .`, `python tools/smoke_tests.py`, `python -m pytest backend/tests/test_engine_speakerplacer.py backend/tests/test_speakerplacer_parallel.py -q`. Do not run the full pytest suite.

## Constraints
No new dependencies. Keep function signatures compatible. The backend may kill this process on a deadline: no orphan workers (the helper handles it; do not bypass it).

## Out of scope
Backend adapter, web, iOS, the helper module itself (report helper bugs in HANDOFF.md).

## Files you own
`speakerplacer/optimize.py`, `speakerplacer/scoring.py`, `speakerplacer/room_acoustics.py`, `speakerplacer/room.py`, `speakerplacer/candidates.py`, `orchestrate/tasks/mc-wire/HANDOFF.md`.
