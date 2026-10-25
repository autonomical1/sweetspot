"""Per-request connections to a writable copy of the seed catalog."""

import os
import shutil
import sqlite3
from pathlib import Path

SEED = Path(__file__).with_name("av_prices.db")


def working_path() -> Path:
    return Path(os.getenv("AV_DB") or Path(os.getenv("DATA_DIR", "data")) / "av_prices.db")


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or working_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(SEED, target)
    conn = sqlite3.connect(target, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
