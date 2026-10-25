"""Choose budgeted catalog items for each layout role."""

import math
import os
import re
from statistics import median

from . import search
from .db import connect, working_path
from .dimensions import dimensions
from .expand import expand
from .value import quality, value

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


def _best(rows: list[dict], role: str, cap: float, screen: dict | None, *, paired: bool = False) -> dict | None:
    eligible = [row for row in rows if row["price"] <= cap + 0.001 and bool(PAIR.search(row["title"])) == paired
                and not (role == "C" and "center channel" in row["title"].lower() and paired)]
    return max(eligible, key=lambda row: value(row, role, cap, screen), default=None)


def _choice(rows: list[dict], roles: tuple[str, ...], cap: float, screen: dict | None) -> dict:
    if len(roles) == 1:
        row = _best(rows, roles[0], cap, screen)
        return {roles[0]: row} if row else {}
    first, second = roles
    singles = [_best(rows, role, cap / 2, screen) for role in roles]
    pair = _best(rows, first, cap, screen, paired=True)
    if pair and (not all(singles) or quality(pair, first, screen) - 0.35 * pair["price"] / cap
                 >= sum(value(row, role, cap / 2, screen) for row, role in zip(singles, roles, strict=True)) / 2):
        return {first: pair, second: pair}
    return {role: row for role, row in zip(roles, singles, strict=True) if row}


def _cost(choice: dict) -> float:
    total = 0.0
    for role, row in choice.items():
        if role in {"R", "Rs"} and row is choice.get("L" if role == "R" else "Ls"):
            continue
        total += row["price"]
    return total


def _choice_value(choice: dict, roles: tuple[str, ...], cap: float, screen: dict | None) -> float:
    if not choice:
        return float("-inf")
    if len(roles) == 2 and len(choice) == 2 and choice[roles[0]] is choice[roles[1]]:
        row = choice[roles[0]]
        return (sum(quality(row, role, screen) for role in roles) / 2
                - 0.35 * row["price"] / cap)
    return sum(value(row, role, cap / len(roles), screen) for role, row in choice.items()) / len(roles)


def _constraints(role: str, screen: dict | None) -> dict:
    if role in {"Ls", "Rs"}:
        return {"form_factor": "bookshelf"}
    if role in {"L", "R", "C"}:
        return {"form_factor": "bookshelf"}
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
            if sum(row["id"] in valid_ids for row in matches) < 3:
                requests.setdefault(category, (shares[role], constraints))
    warnings = expand(path, requests, serpapi_key or os.getenv("SERPAPI_KEY")) if requests else []
    if requests and not any("skipped" in warning for warning in warnings):
        with connect(path) as conn:
            catalog = {category: _candidates(conn, category) for category in catalog}
    picks = {}
    for group in groups:
        cap = sum(shares[role] for role in group)
        picks[group] = _choice(catalog[_category(group[0])], group, cap, screen)
    total = sum(_cost(choice) for choice in picks.values())
    for group in groups:
        old = picks[group]
        base_share = sum(shares[role] for role in group)
        cap = min(budget - total + _cost(old), base_share + budget - total)
        candidate = _choice(catalog[_category(group[0])], group, cap, screen)
        if not candidate or _cost(candidate) > budget - total + _cost(old) + 0.001:
            continue
        old_value = _choice_value(old, group, base_share, screen)
        new_value = _choice_value(candidate, group, base_share, screen)
        if new_value > old_value + 0.001:
            total += _cost(candidate) - _cost(old)
            picks[group] = candidate
    selected = {role: row for choice in picks.values() for role, row in choice.items()}
    items = []
    for role in roles:
        row = selected.get(role)
        if not row:
            warnings.append(f"no product within budget for {role}")
            continue
        partner = {"L": "R", "R": "L", "Ls": "Rs", "Rs": "Ls"}.get(role)
        paired = partner if partner and selected.get(partner) is row else None
        items.append(_item(role, row, screen, paired))
    return {"budget": budget, "total": round(sum(item["price"] for item in items), 2), "items": items,
            "warnings": warnings}
