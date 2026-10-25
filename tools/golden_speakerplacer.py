"""Capture or check speakerplacer quick-layout results so speed work cannot change the answers.

Usage: python tools/golden_speakerplacer.py capture|check
"""
import json
import sys
import time
from pathlib import Path

from backend.app import engine_speakerplacer

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "fixtures" / "speakerplacer_golden.json"


def rooms() -> dict[str, dict]:
    large = json.loads((ROOT / "fixtures" / "speed_room_large_scan.json").read_text(encoding="utf-8"))
    def rect(width: float, length: float, height: float) -> dict:
        return {"dimensions": {"width": width, "length": length, "height": height}, "surfaces": [], "objects": [],
                "listener": {"position": [width / 2, 3.6, length * 0.65], "facing": [0, -1]}}
    return {"large_scan": large, "rect_15x18": rect(15, 18, 9), "rect_12x14": rect(12, 14, 8.5)}


def summarise(result: dict) -> dict:
    return {"speakers": [{"role": item["role"], "position": item["position"], "aim": item["aim"]}
                         for item in result["layout"]["speakers"]],
            "score_db": result["metrics"]["engine"].get("score_db")}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    found: dict[str, dict] = {}
    for name, room in rooms().items():
        started = time.time()
        found[name] = summarise(engine_speakerplacer._optimize(room, None))
        print(f"{name}: {time.time() - started:.1f} s")
    if mode == "capture":
        GOLDEN.write_text(json.dumps(found, indent=1), encoding="utf-8")
        return 0
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    bad = []
    for name, expected in golden.items():
        for want, got in zip(expected["speakers"], found[name]["speakers"], strict=True):
            for key in ("position", "aim"):
                if any(abs(a - b) > 1e-6 for a, b in zip(want[key], got[key], strict=True)):
                    bad.append(f"{name} {want['role']} {key}: {want[key]} != {got[key]}")
        if (expected["score_db"] is None) != (found[name]["score_db"] is None) or (
                expected["score_db"] is not None and abs(expected["score_db"] - found[name]["score_db"]) > 1e-6):
            bad.append(f"{name} score_db {expected['score_db']} != {found[name]['score_db']}")
    print("IDENTICAL" if not bad else "\n".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
