"""Fetch a fixed set of catalog gaps into an explicitly chosen working database."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from products import catalog  # noqa: E402

EXTRA_QUERIES = [
    ("Klipsch R-52C center channel speaker", "speaker"),
    ("Polk Audio Monitor XT30 center channel speaker", "speaker"),
    ("ELAC Debut C5.2 center channel speaker", "speaker"),
    ("Sony SS-CS5 center speaker", "speaker"),
    ("KEF Q250c center speaker", "speaker"),
    ("Klipsch R-41M bookshelf speakers", "speaker"),
    ("ELAC Debut B6.2 bookshelf speakers", "speaker"),
    ("Polk Audio Monitor XT20 bookshelf speaker", "speaker"),
    ("Sony SS-CS3 floorstanding speaker", "speaker"),
    ("Dayton Audio B652 bookshelf speaker", "speaker"),
    ("Klipsch Reference 5.1 home theater speaker system", "speaker"),
    ("Polk Audio 5.1 home theater speaker system", "speaker"),
    ("Sony 5.1 home theater speaker package passive", "speaker"),
    ("Denon AVR-S570BT 5.2 AV receiver", "av_receiver"),
    ("Sony STR-DH590 5.2 channel AV receiver", "av_receiver"),
    ("Onkyo TX-SR494 7.2 channel receiver", "av_receiver"),
    ("Yamaha RX-V4A AV receiver", "av_receiver"),
    ("16 AWG speaker wire 100 ft", "cable"),
    ("Mounting Dream projector ceiling mount", "mount"),
    ("Belkin Ultra High Speed HDMI 2.1 cable 10 ft", "cable"),
]


def selected_queries(only: str | None, maximum: int | None) -> list[tuple[str, str]]:
    rows = [entry for entry in EXTRA_QUERIES if not only or only.lower() in entry[0].lower()
            or only.lower() == entry[1]]
    return rows[:maximum] if maximum is not None else rows


def run(db: Path, queries: list[tuple[str, str]], key: str | None, *, dry_run: bool = False) -> int:
    if not dry_run and not key:
        raise ValueError("SERPAPI_KEY is required unless --dry-run is set")
    if dry_run:
        for query, category in queries:
            print(f"DRY RUN [{category}] {query}")
        return 0
    failures = 0
    conn = catalog.init_db(str(db))
    try:
        for query, category in queries:
            try:
                listings = catalog.fetch_with_retry(query, key)
                saved, flagged = catalog.save_listings(conn, query, category, listings)
                print(f"[{category}] {query}: saved {saved}, flagged {flagged}")
            except Exception as exc:
                failures += 1
                print(f"[{category}] {query}: {type(exc).__name__}: {exc}")
    finally:
        conn.close()
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--only")
    parser.add_argument("--max-queries", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.max_queries is not None and args.max_queries < 0:
        parser.error("--max-queries must be non-negative")
    key = os.getenv("SERPAPI_KEY")
    if not args.dry_run and not key:
        parser.error("SERPAPI_KEY is required unless --dry-run is set")
    return int(run(args.db, selected_queries(args.only, args.max_queries), key, dry_run=args.dry_run) > 0)


if __name__ == "__main__":
    raise SystemExit(main())
