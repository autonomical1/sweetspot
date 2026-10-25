"""Physical size in feet, from listing copy or display defaults."""

import json
import re

LENGTH = r"(\d+(?:\.\d+)?)\s*(\"|”|inches|inch|in\b|cm\b|mm\b)"
TRIPLE = re.compile(rf"{LENGTH}\s*[x×]\s*{LENGTH}\s*[x×]\s*{LENGTH}", re.I)
LABELLED = re.compile(
    rf"\bW(?:idth)?\s*[:=]?\s*{LENGTH}\s*[,; ]+"
    rf"H(?:eight)?\s*[:=]?\s*{LENGTH}\s*[,; ]+D(?:epth)?\s*[:=]?\s*{LENGTH}", re.I,
)


def _feet(value: str, unit: str) -> float:
    return float(value) / (30.48 if unit.lower() == "cm" else 304.8 if unit.lower() == "mm" else 12)


def dimensions(row: dict, role: str, screen: dict | None) -> dict:
    raw = row.get("extensions") or "[]"
    try:
        extensions = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        extensions = []
    copy = " ".join([row.get("title") or "", row.get("snippet") or "", *map(str, extensions)])
    found = LABELLED.search(copy) or TRIPLE.search(copy)
    if found:
        parts = [_feet(found.group(i), found.group(i + 1)) for i in (1, 3, 5)]
        if all(0.05 <= part <= 20 for part in parts):
            return dict(zip(("width", "height", "depth"), parts, strict=True), source="listing")
    factor = (row.get("specs") or {}).get("form_factor")
    defaults = {"LFE": (1.1, 1.2, 1.2), "projector": (1.3, 0.5, 1.1), "C": (1.6, 0.6, 0.7)}
    if role == "screen" and screen:
        size = (screen["width"], screen["height"], 0.15)
    elif role in defaults:
        size = defaults[role]
    elif factor == "floorstanding":
        size = (0.8, 3.3, 1.0)
    elif role in {"L", "R", "Ls", "Rs"}:
        size = (0.6, 1.0, 0.7)
    else:
        size = (1.0, 1.0, 1.0)
    return dict(zip(("width", "height", "depth"), size, strict=True), source="default")
