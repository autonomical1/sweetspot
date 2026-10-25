"""Tunable price and quality model for shopping listings."""

import math
import re

PRICE_PENALTY = 0.35
PRIOR_RATING = 4.0
PRIOR_REVIEWS = 20
NEUTRAL_SPEC = 0.5


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def number(value: str | None) -> float | None:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(value or ""))
    return float(match.group().replace(",", "")) if match else None


def scale(value: float | None, lo: float, hi: float, *, log: bool = False) -> float:
    if value is None:
        return NEUTRAL_SPEC
    if log:
        return clamp(math.log(max(value, 0.001) / lo) / math.log(hi / lo))
    return clamp((value - lo) / (hi - lo))


def quality(row: dict, role: str, screen: dict | None) -> float:
    rating = number(row.get("rating")) or PRIOR_RATING
    reviews = number(row.get("reviews")) or 0
    bayes = (rating * reviews + PRIOR_RATING * PRIOR_REVIEWS) / (reviews + PRIOR_REVIEWS)
    rating_part = clamp((bayes - 3) / 2)
    specs = row.get("specs") or {}
    power = number(specs.get("power_w"))
    if role in {"L", "R", "C", "Ls", "Rs"}:
        factor = specs.get("form_factor")
        preferred = {"bookshelf"} if role in {"Ls", "Rs"} else {"floorstanding", "bookshelf"}
        fit = NEUTRAL_SPEC if factor is None else float(factor in preferred)
        terms = [fit, scale(power, 20, 300, log=True)]
    elif role == "LFE":
        terms = [scale(number(specs.get("driver_in")), 8, 15), scale(power, 100, 1000, log=True)]
    elif role == "projector":
        resolution = number(specs.get("resolution"))
        res = NEUTRAL_SPEC if resolution is None else 1.0 if resolution >= 2160 else 0.5 if resolution >= 1080 else 0.0
        laser = specs.get("light_source")
        terms = [res, scale(number(specs.get("brightness_lumens")), 1000, 4000, log=True),
                 NEUTRAL_SPEC if laser is None else float("laser" in laser.lower())]
    else:
        diagonal = number(specs.get("diagonal_in"))
        target = math.hypot(screen["width"], screen["height"]) * 12 if screen else None
        closeness = NEUTRAL_SPEC if diagonal is None or not target else clamp(1 - abs(diagonal - target) / target)
        alr = specs.get("ambient_light_rejecting")
        terms = [closeness, NEUTRAL_SPEC if alr is None else float(str(alr).lower() in {"yes", "true", "1"})]
    return clamp(0.5 * rating_part + 0.5 * sum(terms) / len(terms))


def value(row: dict, role: str, share: float, screen: dict | None) -> float:
    return quality(row, role, screen) - PRICE_PENALTY * row["price"] / max(share, 0.01)
