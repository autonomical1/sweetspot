#!/usr/bin/env python3
"""Validate the JSON RoomPlan DTO without importing the backend."""
import json
import math
import sys
from collections import Counter
from pathlib import Path

SURFACE_CATEGORIES = {"wall", "door", "window", "opening", "floor"}
OBJECT_CATEGORIES = {
    "bathtub", "bed", "chair", "dishwasher", "fireplace", "oven", "refrigerator", "sink", "sofa", "stairs",
    "storage", "stove", "table", "television", "toilet", "washerDryer",
}


def _numbers(value, count, nonnegative=False):
    return (
        isinstance(value, list)
        and len(value) == count
        and all(
            isinstance(x, (int, float))
            and not isinstance(x, bool)
            and math.isfinite(x)
            and (not nonnegative or x >= 0)
            for x in value
        )
    )


def validate(data: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    dto = data.get("captured_room") if isinstance(data, dict) and "captured_room" in data else data
    if not isinstance(dto, dict):
        return ["DTO must be an object"], []
    for key in ("format", "room_identifier", "story", "surfaces", "objects"):
        if key not in dto:
            errors.append(f"missing key: {key}")
    if dto.get("format") != "sweetspot.roomplan.v1":
        errors.append("format must be sweetspot.roomplan.v1")
    surfaces = dto.get("surfaces")
    objects = dto.get("objects")
    if not isinstance(surfaces, list):
        errors.append("surfaces must be a list")
    if not isinstance(objects, list):
        errors.append("objects must be a list")
    if not isinstance(surfaces, list):
        surfaces = []
    if not isinstance(objects, list):
        objects = []
    ids = set()
    walls = 0
    has_floor = False
    has_sofa = False
    has_tv = False
    def inspect(item, category, label):
        nonlocal walls, has_floor, has_sofa, has_tv
        for key in ("id", "dimensions", "transform"):
            if key not in item:
                errors.append(f"{label} missing {key}")
        ident = item.get("id")
        if not isinstance(ident, str) or not ident:
            errors.append(f"{label} id must be a nonempty string")
        elif ident in ids:
            errors.append(f"duplicate id: {ident}")
        else:
            ids.add(ident)
        actual = item.get("category")
        allowed = SURFACE_CATEGORIES if category == "surface" else OBJECT_CATEGORIES
        if not isinstance(actual, str) or actual not in allowed:
            errors.append(f"{label} category is invalid: {actual}")
        if category == "surface":
            if actual == "wall":
                walls += 1
            if actual == "floor":
                has_floor = True
            if (
                actual == "wall"
                and _numbers(item.get("dimensions"), 3, True)
                and not (1.5 <= item["dimensions"][1] <= 6)
            ):
                warnings.append(f"wall {ident} height is outside 1.5-6 m")
            if actual != "door" and item.get("is_open") is not None:
                errors.append(f"is_open set on non-door {ident}")
        else:
            has_sofa |= actual == "sofa"
            has_tv |= actual == "television"
        dims = item.get("dimensions")
        if not _numbers(dims, 3, True):
            errors.append(f"{label} dimensions must be 3 finite non-negative numbers")
        transform = item.get("transform")
        if not _numbers(transform, 16):
            errors.append(f"{label} transform must contain 16 finite numbers")
            return
        if abs(transform[15] - 1) > 1e-3:
            errors.append(f"{label} transform[15] must be 1")
        translation = [transform[12], transform[13], transform[14]]
        if any(abs(v) > 100 for v in translation):
            warnings.append(f"{label} translation is unusually large")
        # Column-major 3x3 rotation; rows/columns should each be unit and orthogonal.
        cols = [
            (transform[0], transform[1], transform[2]),
            (transform[4], transform[5], transform[6]),
            (transform[8], transform[9], transform[10]),
        ]
        bad = any(
            abs(sum(a * b for a, b in zip(c1, c2, strict=False))) > 0.02
            for i, c1 in enumerate(cols)
            for c2 in cols[i + 1:]
        ) or any(abs(sum(v * v for v in col) - 1) > 0.02 for col in cols)
        if bad:
            warnings.append(f"{label} rotation is not orthonormal")
    for item in surfaces:
        if isinstance(item, dict):
            inspect(item, "surface", "surface")
        else:
            errors.append("surface must be an object")
    for item in objects:
        if isinstance(item, dict):
            inspect(item, "object", "object")
        else:
            errors.append("object must be an object")
    if walls < 3:
        warnings.append("fewer than 3 walls")
    if not has_floor:
        warnings.append("no floor")
    if not has_sofa:
        warnings.append("no sofa")
    if not has_tv:
        warnings.append("no television")
    return errors, warnings


def _summary(data, errors, warnings):
    dto = data.get("captured_room", data) if isinstance(data, dict) else data
    if not isinstance(dto, dict):
        dto = {}
    entries = [
        x
        for group in (dto.get("surfaces", []), dto.get("objects", []))
        if isinstance(group, list)
        for x in group
        if isinstance(x, dict) and _numbers(x.get("transform"), 16)
    ]
    points = [(x["transform"][12], x["transform"][13], x["transform"][14]) for x in entries]
    counts = Counter(str(x.get("category")) for x in entries)
    print(f"findings: {len(errors)} errors, {len(warnings)} warnings")
    print("counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    if points:
        mins = [min(p[i] for p in points) for i in range(3)]
        maxs = [max(p[i] for p in points) for i in range(3)]
        print(f"translation bounds (m): {mins} to {maxs}")
        print(f"translation bounds (ft): {[round(v * 3.28084, 4) for v in mins]} to {[round(v * 3.28084, 4) for v in maxs]}")  # noqa: E501  # preserve behavior while retaining the existing expression
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARN: {message}")


def main(argv):
    if not argv:
        print("usage: validate_dto.py FILE [FILE...]", file=sys.stderr)
        return 2
    status = 0
    for filename in argv:
        try:
            with Path(filename).open(encoding="utf-8") as source:
                data = json.load(source)
            errors, warnings = validate(data)
            print(filename + ":")
            _summary(data, errors, warnings)
            status = max(status, 1 if errors else 0)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"{filename}: ERROR: {exc}")
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
