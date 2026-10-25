"""Catalog expansion that never holds a request for long, with a cooldown per category and price band.

The request waits at most PRODUCTS_EXPAND_DEADLINE_S (default 2 s) for the expansion threads, which keep
running in the background and improve later requests. A (category, price band) that was already tried is
not tried again for PRODUCTS_EXPAND_COOLDOWN_S (default 6 h), so repeat requests are fast.
"""

import math
import os
import sqlite3
import threading
import time
from pathlib import Path

from . import catalog
from .db import connect

_ENV_LOCK = threading.Lock()
_IN_FLIGHT: set[str] = set()
_IN_FLIGHT_LOCK = threading.Lock()


def _attempt_key(category: str, share: float) -> str:
    """Price bands grow by 1.5x so nearby budgets share one attempt."""
    return f"{category}:{int(math.log(max(share, 1.0), 1.5))}"


def _claim(path: Path, key: str, cooldown_s: float) -> bool:
    """True if this key may be tried now; records the attempt so repeats are skipped."""
    with _IN_FLIGHT_LOCK:
        if key in _IN_FLIGHT:
            return False
        try:
            with sqlite3.connect(path, timeout=10) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS expand_attempts (key TEXT PRIMARY KEY, at REAL)")
                row = conn.execute("SELECT at FROM expand_attempts WHERE key = ?", (key,)).fetchone()
                if row and time.time() - float(row[0]) < cooldown_s:
                    return False
                conn.execute("INSERT OR REPLACE INTO expand_attempts (key, at) VALUES (?, ?)", (key, time.time()))
        except sqlite3.Error:
            return True
        _IN_FLIGHT.add(key)
        return True


def _release(path: Path, key: str, failed: bool) -> None:
    with _IN_FLIGHT_LOCK:
        _IN_FLIGHT.discard(key)
    if failed:
        try:
            with sqlite3.connect(path, timeout=10) as conn:
                conn.execute("DELETE FROM expand_attempts WHERE key = ?", (key,))
        except sqlite3.Error:
            pass


def expand(path: Path, requests: dict[str, tuple[float, dict]], serpapi_key: str | None) -> list[str]:
    if not os.getenv("GEMINI_API_KEY") or not serpapi_key:
        return ["catalog expansion skipped: GEMINI_API_KEY/SERPAPI_KEY not set"]
    deadline = time.monotonic() + max(0, float(os.getenv("PRODUCTS_EXPAND_DEADLINE_S", "2")))
    warnings: list[str] = []
    errors: list[str] = []
    threads = []

    cooldown = float(os.getenv("PRODUCTS_EXPAND_COOLDOWN_S", str(6 * 3600)))

    def run(category: str, share: float, specs: dict, key: str) -> None:
        failed = False
        try:
            with connect(path) as conn:
                # The teammate's interface reads this key from the process environment.
                with _ENV_LOCK:
                    previous_key = os.environ.get("SERPAPI_KEY")
                    if previous_key != serpapi_key:
                        # Only an explicit key that differs from the environment overrides it, and only while
                        # this thread holds the lock; the normal case (key from the environment) mutates nothing.
                        os.environ["SERPAPI_KEY"] = serpapi_key
                    try:
                        catalog.expand_catalog(conn, category, price=f"..{share:.2f}", specs=specs,
                                               max_queries=3)
                    finally:
                        if previous_key is None:
                            os.environ.pop("SERPAPI_KEY", None)
                        else:
                            os.environ["SERPAPI_KEY"] = previous_key
        except Exception as exc:
            failed = True
            errors.append(f"catalog expansion failed for {category}: {type(exc).__name__}")
        finally:
            _release(path, key, failed)

    for category, (share, specs) in requests.items():
        key = _attempt_key(category, share)
        if not _claim(path, key, cooldown):
            continue
        thread = threading.Thread(target=run, args=(category, share, specs, key), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join(max(0, deadline - time.monotonic()))
    if any(thread.is_alive() for thread in threads):
        warnings.append("catalog expansion timed out; results will appear on a later request")
    return warnings + errors
