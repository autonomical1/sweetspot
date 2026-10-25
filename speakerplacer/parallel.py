"""Ordered process mapping for the speaker placement search."""

from __future__ import annotations

import atexit
import math
import os
import pickle
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from itertools import repeat
from multiprocessing import get_context
from typing import Any, Callable, Iterable, TypeVar

_Input = TypeVar("_Input")
_Output = TypeVar("_Output")
_pool: ProcessPoolExecutor | None = None
_pool_pid: int | None = None
_lock = threading.RLock()
_thread_limits = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def worker_count() -> int:
    """Return the configured positive process count, with a bounded CPU default."""
    default = max(1, min(os.cpu_count() or 1, 8))
    try:
        value = int(os.environ["SPEAKERPLACER_WORKERS"])
    except (KeyError, ValueError):
        return default
    return value if value > 0 else default


def _parent_is_gone(parent_pid: int) -> bool:
    if os.name == "nt":
        # On Windows a parent's PID remains valid until its last handle closes.
        # Waiting on the process handle detects termination without PID reuse.
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = (ctypes.c_uint, ctypes.c_int, ctypes.c_uint)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = kernel32.OpenProcess(0x00100000, False, parent_pid)
        if not handle:
            return True
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0
        finally:
            kernel32.CloseHandle(handle)
    return os.getppid() != parent_pid


def _watch_parent(parent_pid: int) -> None:
    while True:
        if _parent_is_gone(parent_pid):
            os._exit(0)
        time.sleep(0.2)


def _init_worker(parent_pid: int) -> None:
    threading.Thread(target=_watch_parent, args=(parent_pid,), daemon=True).start()


def _apply(function: Callable[[_Input], _Output], item: _Input) -> tuple[bool, Any]:
    try:
        return True, function(item)
    except BaseException as exc:
        # Return user errors as data so an OSError raised by the function is not
        # mistaken for a pool failure and retried.
        return False, exc


def _get_pool() -> ProcessPoolExecutor:
    global _pool, _pool_pid
    with _lock:
        if _pool is not None and _pool_pid == os.getpid():
            return _pool
        _pool = ProcessPoolExecutor(
            max_workers=worker_count(),
            mp_context=get_context("spawn"),
            initializer=_init_worker,
            initargs=(os.getpid(),),
        )
        _pool_pid = os.getpid()
        return _pool


def _submit_map(
    function: Callable[[_Input], _Output], values: list[_Input], chunksize: int
) -> Any:
    # ProcessPoolExecutor starts workers on submission, not construction. Keep
    # the limits in place through map() so spawned children inherit them.
    with _lock:
        previous = {name: os.environ.get(name) for name in _thread_limits}
        try:
            for name in _thread_limits:
                os.environ[name] = "1"
            return _get_pool().map(_apply, repeat(function), values, chunksize=chunksize)
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def shutdown_pool() -> None:
    """Stop the cached pool and discard pending work."""
    global _pool, _pool_pid
    with _lock:
        pool = _pool
        _pool = None
        _pool_pid = None
    if pool is not None:
        pool.shutdown(wait=True, cancel_futures=True)


atexit.register(shutdown_pool)


def ordered_map(
    function: Callable[[_Input], _Output],
    items: Iterable[_Input],
    *,
    workers: int | None = None,
    chunksize: int | None = None,
) -> list[_Output]:
    """Map in input order, falling back to serial work if processes fail."""
    values = list(items)
    count = worker_count() if workers is None else workers
    if count < 1:
        raise ValueError("workers must be positive")
    if count == 1 or len(values) < 2 * count:
        return [function(item) for item in values]
    try:
        pickle.dumps(function)
        pickle.dumps(values)
    except (pickle.PicklingError, TypeError, AttributeError):
        return [function(item) for item in values]
    if chunksize is None:
        chunksize = max(1, math.ceil(len(values) / (count * 4)))
    if chunksize < 1:
        raise ValueError("chunksize must be positive")
    try:
        results = list(_submit_map(function, values, chunksize))
    except (BrokenProcessPool, OSError, pickle.PicklingError):
        shutdown_pool()
        return [function(item) for item in values]
    output: list[_Output] = []
    for ok, value in results:
        if not ok:
            raise value
        output.append(value)
    return output
