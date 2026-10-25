"""Process pool contract and orphan prevention."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures.process import BrokenProcessPool

import pytest

from speakerplacer import parallel


def _square(value: int) -> int:
    return value * value


def _worker_pid(_: int) -> int:
    return os.getpid()


def _raise_os_error(_: int) -> int:
    raise OSError("user failure")


@pytest.fixture(autouse=True)
def _stop_pool() -> None:
    parallel.shutdown_pool()
    yield
    parallel.shutdown_pool()


def test_worker_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parallel.os, "cpu_count", lambda: 16)
    for raw, expected in (("3", 3), ("1", 1), ("0", 8), ("bad", 8), ("-2", 8)):
        monkeypatch.setenv("SPEAKERPLACER_WORKERS", raw)
        assert parallel.worker_count() == expected
    monkeypatch.delenv("SPEAKERPLACER_WORKERS")
    assert parallel.worker_count() == 8


def test_order_and_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEAKERPLACER_WORKERS", "2")
    values = list(range(200))
    assert parallel.ordered_map(_square, values) == [_square(value) for value in values]
    first = parallel._pool
    assert first is not None
    assert parallel.ordered_map(_square, values) == [_square(value) for value in values]
    assert parallel._pool is first


def test_serial_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEAKERPLACER_WORKERS", "2")
    assert parallel.ordered_map(lambda x: x + 1, range(20)) == list(range(1, 21))
    assert parallel.ordered_map(_square, range(20), workers=1) == [x * x for x in range(20)]
    assert parallel.ordered_map(_square, range(3)) == [0, 1, 4]
    assert parallel._pool is None


def test_function_exception_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEAKERPLACER_WORKERS", "2")
    with pytest.raises(OSError, match="^user failure$"):
        parallel.ordered_map(_raise_os_error, range(8))
    assert parallel._pool is not None


def test_broken_pool_recomputes_serially(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEAKERPLACER_WORKERS", "2")

    def fail_submit(*_args: object) -> None:
        raise BrokenProcessPool("worker exited")

    monkeypatch.setattr(parallel, "_submit_map", fail_submit)
    assert parallel.ordered_map(_square, range(8)) == [x * x for x in range(8)]


def test_killed_parent_leaves_no_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEAKERPLACER_WORKERS", "2")
    script = (
        "import json, time\n"
        "from backend.tests.test_speakerplacer_parallel import _worker_pid\n"
        "from speakerplacer.parallel import ordered_map\n"
        "print(json.dumps(sorted(set(ordered_map(_worker_pid, range(40), chunksize=1)))), flush=True)\n"
        "time.sleep(60)\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )
    try:
        assert process.stdout is not None
        pids = json.loads(process.stdout.readline())
        assert pids and all(pid != process.pid for pid in pids)
        process.kill()
        process.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and any(not parallel._parent_is_gone(pid) for pid in pids):
            time.sleep(0.1)
        assert all(parallel._parent_is_gone(pid) for pid in pids)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
