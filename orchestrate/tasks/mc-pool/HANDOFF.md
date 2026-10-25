# mc-pool handoff

## Done
- Added `speakerplacer/parallel.py` with `worker_count`, ordered spawn-based mapping, serial fallbacks, one lazy reusable pool, thread-limit environment during worker spawn, and `shutdown_pool` registered with `atexit`.
- Added focused tests for order and values (200 items), worker count parsing, serial paths, user exception propagation, pool reuse, broken-pool fallback, and killed-parent cleanup.
- Nothing imports the helper yet; the `mc-wire` task can wire it into the optimizer.

## Orphan handling
- `ProcessPoolExecutor` workers normally exit when their call queue closes, but an abruptly killed parent may not close it cleanly. Each worker also starts a daemon watchdog. On Unix it detects reparenting with `os.getppid()`; on Windows it polls the parent process handle. It calls `os._exit(0)` when the parent is gone. The subprocess test kills the parent and verifies the worker PIDs disappear within five seconds.

## Verification
- `python -m pytest backend/tests/test_speakerplacer_parallel.py -q`: 6 passed in 15.00 s.
- `python -m ruff check .`: passed.
- `python tools/smoke_tests.py`: 117 passed in 12.45 s when run with a fresh writable `TMP`/`TEMP` directory. The initial run hit an existing inaccessible pytest temp directory at `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm`; it was an environment permission issue.
- Measured on this Windows sandbox with 2 workers and 200 trivial items: first call 2.375 s, reused call 0.003 s. The first call includes process startup, import and task overhead.

## Unfinished
- None within this task's scope.

## Design questions
- `workers` versus the single pool size: I kept the pool fixed at `worker_count()` as the brief specifies, using an explicit `workers` value for the serial threshold and default chunksize. An alternative is to resize or recreate the pool for each different explicit value, which would change the one-pool lifetime rule.
