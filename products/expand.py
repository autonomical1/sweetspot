"""Deadline-bound catalog expansion with an independent SQLite connection."""

import os
import threading
import time
from pathlib import Path

from . import catalog
from .db import connect

_ENV_LOCK = threading.Lock()


def expand(path: Path, requests: dict[str, tuple[float, dict]], serpapi_key: str | None) -> list[str]:
    if not os.getenv("GEMINI_API_KEY") or not serpapi_key:
        return ["catalog expansion skipped: GEMINI_API_KEY/SERPAPI_KEY not set"]
    deadline = time.monotonic() + max(0, float(os.getenv("PRODUCTS_EXPAND_DEADLINE_S", "20")))
    warnings: list[str] = []
    errors: list[str] = []
    threads = []
    override_key = not os.getenv("SERPAPI_KEY")

    def run(category: str, share: float, specs: dict) -> None:
        try:
            with connect(path) as conn:
                if not override_key:
                    catalog.expand_catalog(conn, category, price=f"..{share:.2f}", specs=specs, max_queries=3)
                else:
                    # The teammate's interface reads this key from the process environment.
                    with _ENV_LOCK:
                        os.environ["SERPAPI_KEY"] = serpapi_key
                        try:
                            catalog.expand_catalog(conn, category, price=f"..{share:.2f}", specs=specs,
                                                   max_queries=3)
                        finally:
                            os.environ.pop("SERPAPI_KEY", None)
        except Exception as exc:
            errors.append(f"catalog expansion failed for {category}: {type(exc).__name__}")

    for category, (share, specs) in requests.items():
        thread = threading.Thread(target=run, args=(category, share, specs), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join(max(0, deadline - time.monotonic()))
    if any(thread.is_alive() for thread in threads):
        warnings.append("catalog expansion timed out; results will appear on a later request")
    return warnings + errors
