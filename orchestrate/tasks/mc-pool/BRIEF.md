# mc-pool: a small, safe, deterministic process-pool helper for speakerplacer (new file only)

## Why
We are making the speakerplacer search use all CPU cores. This task builds ONLY the reusable helper; a later task (`mc-wire`) calls it from the search loops. Nothing else imports your module yet, so you can work in parallel with the task that is speeding up `optimize.py`.

## Deliverable: `speakerplacer/parallel.py`
- `worker_count() -> int`: reads env `SPEAKERPLACER_WORKERS` (positive integer; invalid or missing -> `min(os.cpu_count() or 1, 8)`; never below 1).
- `ordered_map(function, items, *, workers=None, chunksize=None) -> list`: returns exactly `[function(item) for item in items]` (same order, same values), computed on a `concurrent.futures.ProcessPoolExecutor` using the `spawn` start method. `function` must be a picklable top-level function; `items` picklable.
  - Falls back to the plain serial list comprehension when: workers == 1, fewer than `2 * workers` items, `function`/items cannot be pickled (probe with `pickle.dumps(function)`), or the pool cannot start / breaks (catch `BrokenProcessPool`, `OSError`, `PicklingError` and recompute serially so the caller never sees a pool failure). Exceptions raised BY `function` must propagate unchanged (same type and message).
  - `chunksize` default: `max(1, ceil(len(items) / (workers * 4)))`.
  - One pool per process, created lazily on first use and reused (starting a pool per call would waste seconds), sized by `worker_count()` at creation; `shutdown_pool()` helper and an `atexit` hook that shuts it down with `cancel_futures=True`.
  - Limit hidden thread oversubscription: while creating the pool set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` to `1` in `os.environ` (children inherit them at spawn), then restore the parent's previous values.
  - If the parent process is killed (SIGKILL on Linux, TerminateProcess on Windows) the workers must not linger: verify and document how (executor workers exit when their queue closes); if they can linger, add a watchdog in the worker initializer that exits when the parent pid changes/disappears.
- Pure Python + stdlib only (no new dependencies, no numpy import needed here).

## Tests (`backend/tests/test_speakerplacer_parallel.py`, fast: whole file under 30 s)
Order and value equality against serial for 200 items; `SPEAKERPLACER_WORKERS` parsing (valid, invalid, 1); serial fallback paths (lambda, 1 worker, few items); exception propagation; pool reuse (two calls, same pool object); parent-killed-leaves-no-workers test using `subprocess` + `psutil` ONLY if psutil is already installed, otherwise check via `os.kill(pid, 0)` polling.

## Done when
`python -m ruff check .`, `python tools/smoke_tests.py` and the new test file pass. No edits outside your files. Report in HANDOFF.md how the orphan case is handled and the measured pool start-up cost.

## Out of scope
Calling the helper from the optimizer (task `mc-wire`), backend, web, iOS.

## Files you own
`speakerplacer/parallel.py`, `backend/tests/test_speakerplacer_parallel.py`, `orchestrate/tasks/mc-pool/HANDOFF.md`.
