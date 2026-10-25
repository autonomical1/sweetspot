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
SPEED IS THE ONLY PRIORITY (user order). DO NOT run any tests, benchmarks, golden checks, ruff, smoke tests or pytest, and do not profile with cProfile. Read optimize.py and parallel.py, pick the coarsest independent loop by reading the code, wire it through `parallel.ordered_map` keeping the merge order identical to serial, keep `SPEAKERPLACER_WORKERS=1` on the original serial path, check syntax only with `python -m py_compile`, write a 5-line HANDOFF.md and stop. Finish in as few steps as possible.

## Constraints
No new dependencies. Keep function signatures compatible. The backend may kill this process on a deadline: no orphan workers (the helper handles it; do not bypass it).

## Out of scope
Backend adapter, web, iOS, the helper module itself (report helper bugs in HANDOFF.md).

## Files you own
`speakerplacer/optimize.py`, `speakerplacer/scoring.py`, `speakerplacer/room_acoustics.py`, `speakerplacer/room.py`, `speakerplacer/candidates.py`, `orchestrate/tasks/mc-wire/HANDOFF.md`.
