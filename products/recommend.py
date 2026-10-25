"""Choose budgeted catalog items for each layout role."""

import math
import os
import re
from collections.abc import Iterator
from statistics import median

from . import search
from .db import connect, working_path
from .dimensions import dimensions
from .expand import expand
from .value import PRICE_PENALTY, quality, value
from .variety import family_key, model_key, same_family

ORDER = ("C", "L", "R", "LFE", "Ls", "Rs", "screen", "projector")
WEIGHTS = {"C": 3, "L": 2, "R": 2, "LFE": 2, "Ls": 1, "Rs": 1, "screen": 1, "projector": 1}
PAIR = re.compile(r"\bpairs?\b|\(2\)|set of 2", re.I)


def _category(role: str) -> str:
    return {"LFE": "subwoofer", "screen": "projection_screen", "projector": "projector"}.get(role, "speaker")


def _candidates(conn, category: str) -> list[dict]:
    rows = search.search(conn, category=category, limit=10000)
    if not rows:
        return []
    ids = [row["id"] for row in rows]
    extras = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" for _ in chunk)
        sql = f"SELECT id, snippet, extensions, rating, reviews, query FROM listings WHERE id IN ({marks})"
        for row in conn.execute(sql, chunk):
            extras[row["id"]] = dict(row)
    prices_by_query = {}
    for row in conn.execute("""SELECT query, price FROM listings l WHERE fetched_at =
                            (SELECT MAX(fetched_at) FROM listings WHERE query = l.query) AND price > 0"""):
        prices_by_query.setdefault(row["query"], []).append(row["price"])
    medians = {query: median(prices) for query, prices in prices_by_query.items()}
    result = []
    for row in rows:
        item = {**row, **extras[row["id"]]}
        condition = str(item["specs"].get("condition", "new")).lower()
        if (item["link"] and math.isfinite(item["price"]) and item["price"] > 0
                and condition == "new" and item["price"] >= medians.get(item["query"], 0) * 0.25):
            result.append(item)
    return result


def _best(rows: list[dict], role: str, cap: float, screen: dict | None, *, paired: bool = False,
          value_share: float | None = None) -> dict | None:
    eligible = [row for row in rows if row["price"] <= cap + 0.001 and bool(PAIR.search(row["title"])) == paired
                and not (role == "C" and "center channel" in row["title"].lower() and paired)]
    return max(eligible, key=lambda row: value(row, role, value_share or cap, screen), default=None)


def _choice(rows: list[dict], roles: tuple[str, ...], cap: float, screen: dict | None) -> dict:
    if len(roles) == 1:
        row = _best(rows, roles[0], cap, screen)
        return {roles[0]: row} if row else {}
    first, second = roles
    singles = [_best(rows, role, cap / 2, screen) for role in roles]
    pair = _best(rows, first, cap, screen, paired=True)
    if pair and (not all(singles) or quality(pair, first, screen) - PRICE_PENALTY * pair["price"] / cap
                 >= sum(value(row, role, cap / 2, screen) for row, role in zip(singles, roles, strict=True)) / 2):
        return {first: pair, second: pair}
    return {role: row for role, row in zip(roles, singles, strict=True) if row}


def _center_rows(rows: list[dict], front: dict, cap: float) -> list[dict]:
    eligible = [row for row in rows if row["price"] <= cap and not PAIR.search(row["title"])]
    series = [row for row in eligible if same_family(row, front)]
    if series:
        return series
    brand = family_key(front)[0]
    branded = [row for row in eligible if family_key(row)[0] == brand] if brand else []
    return branded or rows


def _surround_rows(rows: list[dict], front: dict, cap: float, screen: dict | None) -> list[dict]:
    eligible = [row for row in rows if row["price"] <= cap]
    if not eligible:
        return rows
    best = max(quality(row, "Ls", screen) for row in eligible)
    different = [row for row in eligible if model_key(row) != model_key(front)
                 and quality(row, "Ls", screen) >= 0.85 * best]
    return different if different else rows


def _valid_variety(picks: dict, catalog: dict, shares: dict, screen: dict | None,
                   surround_scores: dict[float, tuple[float, set[str]]]) -> bool:
    selected = {role: row for choice in picks.values() for role, row in choice.items()}
    front = selected.get("L") or selected.get("R")
    if selected.get("L") and selected.get("R") and model_key(selected["L"]) != model_key(selected["R"]):
        return False
    if not front:
        return True
    center = selected.get("C")
    if center and center not in _center_rows(catalog["speaker"], front, center["price"]):
        return False
    for role in ("Ls", "Rs"):
        row = selected.get(role)
        if not row:
            continue
        paired = row is selected.get("Rs") and role == "Ls" and bool(PAIR.search(row["title"]))
        cap = 2 * (shares["Ls"] + shares.get("Rs", 0)) if paired else 2 * shares[role]
        best, good_models = surround_scores[cap]
        row_model = model_key(row)
        if (row_model == model_key(front) and any(key != row_model for key in good_models)
                or row_model != model_key(front) and quality(row, role, screen) < 0.85 * best):
            return False
    if selected.get("Ls") and selected.get("Rs") and model_key(selected["Ls"]) != model_key(selected["Rs"]):
        return False
    return True


def _cost(choice: dict) -> float:
    total = 0.0
    for role, row in choice.items():
        if (role in {"R", "Rs"} and row is choice.get("L" if role == "R" else "Ls")
                and PAIR.search(row["title"])):
            continue
        total += row["price"]
    return total


def _choice_quality(choice: dict, screen: dict | None) -> float:
    return sum(quality(row, role, screen) for role, row in choice.items())


def _single_frontier(rows: list[dict], role: str, cap: float, screen: dict | None) -> list[dict]:
    best_quality = float("-inf")
    frontier = []
    for row in sorted(rows, key=lambda item: item["price"]):
        if PAIR.search(row["title"]) or row["price"] > cap + 0.001:
            continue
        score = quality(row, role, screen)
        if score > best_quality + 0.000001:
            frontier.append(row)
            best_quality = score
    return frontier


def _upgrades(choice: dict, group: tuple[str, ...], rows: list[dict], shares: dict[str, float],
              leftover: float, screen: dict | None) -> Iterator[tuple[str, dict]]:
    """Yield affordable choices without dropping a filled role."""
    old_cost = _cost(choice)
    paired = (len(group) == 2 and len(choice) == 2 and choice[group[0]] is choice[group[1]]
              and PAIR.search(choice[group[0]]["title"]))
    for role in group:
        if paired:
            continue
        for row in rows:
            if PAIR.search(row["title"]) or row["price"] > 2 * shares[role] + 0.001:
                continue
            candidate = {**choice, role: row}
            if _cost(candidate) <= old_cost + leftover + 1e-8:
                yield role, candidate
    if paired:
        first, second = group
        first_rows = _single_frontier(rows, first, 2 * shares[first], screen)
        second_rows = _single_frontier(rows, second, 2 * shares[second], screen)
        for left in first_rows:
            for right in second_rows:
                candidate = {first: left, second: right.copy() if left is right else right}
                if _cost(candidate) <= old_cost + leftover + 1e-8:
                    yield first, candidate
    if len(group) == 2:
        cap = 2 * sum(shares[role] for role in group)
        for row in rows:
            if PAIR.search(row["title"]) and row["price"] <= cap + 0.001:
                candidate = {group[0]: row, group[1]: row}
                if _cost(candidate) <= old_cost + leftover + 1e-8:
                    yield group[0], candidate


def _constraints(role: str, screen: dict | None) -> dict:
    if role in {"Ls", "Rs"}:
        return {"form_factor": "bookshelf"}
    if role in {"L", "R", "C"}:
        # The teammate search interface has no OR restriction for spec values.
        return {}
    if role == "LFE":
        return {"driver_in": "8.."}
    if role == "projector":
        return {"resolution": "1080.."}
    if screen:
        diagonal = math.hypot(screen["width"], screen["height"]) * 12
        return {"diagonal_in": f"{diagonal * 0.8:.0f}..{diagonal * 1.2:.0f}"}
    return {}


def _item(role: str, row: dict, screen: dict | None, pair_with: str | None) -> dict:
    return {"role": role, "title": row["title"], "price": 0.0 if pair_with and role in {"R", "Rs"} else row["price"],
            "currency": "USD", "link": row["link"], "thumbnail": None, "source": "google_shopping",
            "seller": row["seller"], "specs": row["specs"], "dimensions": dimensions(row, role, screen),
            **({"pair_with": pair_with} if pair_with else {})}


def _alternatives(role: str, row: dict, rows: list[dict], cap: float, total: float,
                  budget: float, screen: dict | None, paired: bool) -> list[dict]:
    candidates = [other for other in rows if other["price"] <= cap + 0.001
                  and total - row["price"] + other["price"] <= budget + 0.001
                  and bool(PAIR.search(other["title"])) == paired
                  and model_key(other) != model_key(row)]
    unique = {}
    for other in candidates:
        key = model_key(other)
        if key not in unique or value(other, role, cap, screen) > value(unique[key], role, cap, screen):
            unique[key] = other
    candidates = list(unique.values())
    cheaper = [other for other in candidates if other["price"] < row["price"]]
    pricier = [other for other in candidates if other["price"] > row["price"]]
    result = []
    if cheaper:
        result.append(max(cheaper, key=lambda other: value(other, role, cap, screen)))
    if pricier:
        result.append(max(pricier, key=lambda other: quality(other, role, screen)))
    remaining = [other for other in candidates if other not in result]
    if remaining:
        result.append(max(remaining, key=lambda other: value(other, role, cap, screen)))
    return [{key: value_ for key, value_ in _item(role, other, screen, None).items()
             if key not in {"role", "pair_with"}} | {"price_delta": round(other["price"] - row["price"], 2)}
            for other in sorted(result, key=lambda other: other["price"])]


def get_products(layout: dict, budget: float, *, serpapi_key: str | None = None) -> dict:
    budget = max(0.0, float(budget))
    roles = [role for role in ORDER if role in {speaker.get("role") for speaker in layout.get("speakers", [])}
             or role == "projector" or role == "screen" and layout.get("screen")]
    screen = layout.get("screen")
    total_weight = sum(WEIGHTS[role] for role in roles)
    shares = {role: budget * WEIGHTS[role] / total_weight for role in roles}
    groups = []
    for role in roles:
        if role in {"R", "Rs"} and ("L" if role == "R" else "Ls") in roles:
            continue
        partner = {"L": "R", "Ls": "Rs"}.get(role)
        groups.append((role, partner) if partner in roles else (role,))
    path = working_path()
    with connect(path) as conn:
        catalog = {category: _candidates(conn, category) for category in {_category(role) for role in roles}}
    requests = {}
    with connect(path) as conn:
        for role in roles:
            category = _category(role)
            constraints = _constraints(role, screen)
            matches = search.search(conn, category=category, price=f"..{shares[role]:.2f}",
                                    specs=constraints, limit=10000)
            valid_ids = {row["id"] for row in catalog[category]}
            if role in {"L", "R", "C"}:
                matches = [row for row in matches if row["specs"].get("form_factor")
                           in {"bookshelf", "floorstanding"}]
            partner = {"L": "R", "R": "L", "Ls": "Rs", "Rs": "Ls"}.get(role)
            pair_usable = partner in roles
            matches = [row for row in matches if pair_usable or not PAIR.search(row["title"])]
            if sum(row["id"] in valid_ids for row in matches) < 3:
                requests.setdefault(category, (shares[role], constraints))
    warnings = expand(path, requests, serpapi_key or os.getenv("SERPAPI_KEY")) if requests else []
    if requests and not any("skipped" in warning for warning in warnings):
        with connect(path) as conn:
            catalog = {category: _candidates(conn, category) for category in catalog}
    groups.sort(key=lambda group: 0 if group[0] == "L" else 1 if group[0] == "C" else 2)
    picks = {}
    for group in groups:
        cap = sum(shares[role] for role in group)
        rows = catalog[_category(group[0])]
        front = next((choice["L"] for choice in picks.values() if "L" in choice), None)
        if front and group[0] == "C":
            rows = _center_rows(rows, front, cap)
        elif front and group[0] == "Ls":
            varied = _surround_rows(rows, front, cap, screen)
            if len(_choice(varied, group, cap, screen)) == len(group):
                rows = varied
        picks[group] = _choice(rows, group, cap, screen)
    total = sum(_cost(choice) for choice in picks.values())
    surround_scores = {}
    for role in ("Ls", "Rs"):
        if role not in shares:
            continue
        caps = [2 * shares[role]]
        if role == "Ls" and "Rs" in shares:
            caps.append(2 * (shares["Ls"] + shares["Rs"]))
        for cap in caps:
            eligible = [row for row in catalog["speaker"] if row["price"] <= cap]
            best = max((quality(row, role, screen) for row in eligible), default=0)
            surround_scores[cap] = (best, {model_key(row) for row in eligible
                                          if quality(row, role, screen) >= 0.85 * best})
    while True:
        best_upgrade = None
        best_ratio = float("-inf")
        for group in groups:
            old = picks[group]
            old_quality = _choice_quality(old, screen)
            by_role = {}
            for role, candidate in _upgrades(old, group, catalog[_category(group[0])], shares,
                                             budget - total, screen):
                if (group[0] in {"L", "C", "Ls"}
                        and not _valid_variety({**picks, group: candidate}, catalog, shares,
                                               screen, surround_scores)):
                    continue
                gain = _choice_quality(candidate, screen) - old_quality
                if gain <= 0.000001:
                    continue
                if (role not in by_role or gain > by_role[role][0] + 1e-8
                        or (abs(gain - by_role[role][0]) <= 1e-8
                            and _cost(candidate) < _cost(by_role[role][1]))):
                    by_role[role] = (gain, candidate)
            for role in group:
                if role not in by_role:
                    continue
                gain, candidate = by_role[role]
                extra = _cost(candidate) - _cost(old)
                ratio = gain / extra if extra > 0.000001 else float("inf")
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_upgrade = (group, candidate, extra)
        if best_upgrade is None:
            break
        group, candidate, extra = best_upgrade
        picks[group] = candidate
        total += extra
    selected = {role: row for choice in picks.values() for role, row in choice.items()}
    items = []
    for role in roles:
        row = selected.get(role)
        if not row:
            warnings.append(f"no product within budget for {role}")
            continue
        partner = {"L": "R", "R": "L", "Ls": "Rs", "Rs": "Ls"}.get(role)
        paired = partner if partner and selected.get(partner) is row and PAIR.search(row["title"]) else None
        item = _item(role, row, screen, paired)
        if paired and role in {"R", "Rs"}:
            item["alternatives"] = []
        else:
            cap = 2 * (shares[role] + shares[paired]) if paired else 2 * shares[role]
            item["alternatives"] = _alternatives(role, row, catalog[_category(role)], cap, total,
                                                  budget, screen, bool(paired))
        items.append(item)
    return {"budget": budget, "total": round(sum(item["price"] for item in items), 2), "items": items,
            "warnings": warnings}
