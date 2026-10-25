"""Thread-safe deduplication, caching, and limits for material classification."""

import hashlib
import math
import os
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import HTTPException


def photo_key(room_id: str, photos: list[dict], backend: str) -> tuple:
    """Identify the stored image set independently of filesystem timestamps."""
    images = tuple(sorted((item["surface_id"], hashlib.sha256(item["image_bytes"]).hexdigest())
                          for item in photos))
    return room_id, images, backend


def _busy(seconds: float) -> HTTPException:
    retry = max(1, math.ceil(seconds))
    return HTTPException(
        status_code=429,
        detail={"detail": f"Photo analysis is busy; retry in {retry} s", "retry_after_s": retry},
        headers={"Retry-After": str(retry)},
    )


class _Flight:
    def __init__(self, started: float, started_at: str):
        self.started = started
        self.started_at = started_at
        self.done = threading.Event()
        self.result: list[dict] | None = None
        self.error: Exception | None = None
        self.waiters = 0


class GeminiLimits:
    """One process's classification coordinator; inject a monotonic clock in tests."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 max_concurrent: int | None = None, max_per_minute: int | None = None,
                 join_timeout: float = 120, concurrency_timeout: float = 30):
        self.clock = clock
        self.max_concurrent = max(1, max_concurrent if max_concurrent is not None
                                  else int(os.getenv("GEMINI_MAX_CONCURRENT", "2")))
        self.max_per_minute = max(1, max_per_minute if max_per_minute is not None
                                  else int(os.getenv("GEMINI_MAX_PER_MINUTE", "6")))
        self.join_timeout = join_timeout
        self.concurrency_timeout = concurrency_timeout
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(self.max_concurrent)
        self._calls: deque[float] = deque()
        self._flights: dict[str, _Flight] = {}
        self._cache: OrderedDict[tuple, tuple[float, list[dict]]] = OrderedDict()

    def status(self, room_id: str) -> dict:
        with self._lock:
            flight = self._flights.get(room_id)
            if flight is None:
                return {"state": "idle", "started_at": None, "elapsed_s": None}
            return {"state": "running", "started_at": flight.started_at,
                    "elapsed_s": max(0.0, self.clock() - flight.started)}

    def execute(self, room_id: str, key: tuple, backend: str,
                classify: Callable[[], list[dict]]) -> tuple[list[dict], str]:
        with self._lock:
            flight = self._flights.get(room_id)
            if flight is None:
                cached = self._cache.get(key)
                if cached and self.clock() - cached[0] < 600:
                    self._cache.move_to_end(key)
                    return cached[1], "cached"
                if cached:
                    del self._cache[key]
                flight = _Flight(self.clock(), datetime.now(UTC).isoformat())
                self._flights[room_id] = flight
                leader = True
            else:
                leader = False
                flight.waiters += 1
        if not leader:
            if not flight.done.wait(self.join_timeout):
                raise HTTPException(504, "material classification timed out")
            if flight.error is not None:
                raise flight.error
            assert flight.result is not None
            return flight.result, "joined"

        try:
            if backend == "gemini":
                if not self._slots.acquire(timeout=self.concurrency_timeout):
                    raise _busy(1)
                try:
                    with self._lock:
                        now = self.clock()
                        while self._calls and now - self._calls[0] >= 60:
                            self._calls.popleft()
                        if len(self._calls) >= self.max_per_minute:
                            raise _busy(60 - (now - self._calls[0]))
                        self._calls.append(now)
                    result = classify()
                finally:
                    self._slots.release()
            else:
                result = classify()
            with self._lock:
                flight.result = result
                self._cache[key] = (self.clock(), result)
                self._cache.move_to_end(key)
                while len(self._cache) > 128:
                    self._cache.popitem(last=False)
            return result, "fresh"
        except Exception as exc:
            flight.error = exc
            raise
        finally:
            with self._lock:
                del self._flights[room_id]
                flight.done.set()


limits = GeminiLimits()
