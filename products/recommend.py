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
from .theater import bundle_roles, choose_tv, passive_speaker, receiver_eligible
from .value import PRICE_PENALTY, number, quality, value
from .variety import family_key, model_key, same_family

ORDER = ("C", "L", "R", "LFE", "Ls", "Rs", "receiver", "projector", "screen",
         "tv", "mount", "hdmi_cable", "speaker_wire")
WEIGHTS = {"C": 3, "L": 2, "R": 2, "LFE": 2, "Ls": 1, "Rs": 1, "receiver": 3,
           "projector": 3, "screen": 1, "tv": 4, "mount": 0.5, "hdmi_cable": 0.5,
           "speaker_wire": 0.5}
PAIR = re.compile(r"\bpairs?\b|\(2\)|set of 2", re.I)


def _category(role: str) -> str:
    return {"LFE": "subwoofer", "screen": "projection_screen", "projector": "projector",
            "receiver": "av_receiver", "tv": "display", "mount": "mount",
            "hdmi_cable": "cable", "speaker_wire": "cable"}.get(role, "speaker")


def _candidates(conn, category: str) -> list[dict]:
    rows = search.search(conn, category=category, include_mismatches=category == "speaker", limit=10000)
    if not rows:
        return []
    ids = [row["id"] for row in rows]
    extras = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" for _ in chunk)
        sql = f"SELECT id, snippet, extensions, rating, reviews, query, category_ok FROM listings WHERE id IN ({marks})"
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
                and condition == "new" and item["price"] >= medians.get(item["query"], 0) * 0.25
                and (item["category_ok"] or category == "speaker" and len(bundle_roles(item["title"])) >= 5)):
            result.append(item)
    return result


def _best(rows: list[dict], role: str, cap: float, screen: dict | None, *, paired: bool = False,
          value_share: float | None = None) -> dict | None:
    eligible = [row for row in rows if row["price"] <= cap + 0.001
                and (role not in {"C", "L", "R", "Ls", "Rs"} or bool(PAIR.search(row["title"])) == paired)
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


def _surround_rows(rows: list[dict], front: dict | list[dict], cap: float, screen: dict | None) -> list[dict]:
    eligible = [row for row in rows if row["price"] <= cap]
    if not eligible:
        return rows
    best = max(quality(row, "Ls", screen) for row in eligible)
    fronts = front if isinstance(front, list) else [front]
    front_models = {model_key(row) for row in fronts}
    different = [row for row in eligible if model_key(row) not in front_models
                 and quality(row, "Ls", screen) >= 0.85 * best]
    return different if different else rows


def _valid_variety(picks: dict, catalog: dict, shares: dict, screen: dict | None,
                   surround_scores: dict[float, tuple[float, set[str]]]) -> bool:
    selected = {role: row for choice in picks.values() for role, row in choice.items()}
    front = selected.get("L") or selected.get("R") or selected.get("C")
    if selected.get("L") and selected.get("R") and model_key(selected["L"]) != model_key(selected["R"]):
        return False
    center = selected.get("C")
    if center and front is not center and center not in _center_rows(catalog["speaker"], front, 2 * shares["C"]):
        return False
    front_models = {model_key(row) for role, row in selected.items() if role in {"L", "R", "C"}}
    for role in ("Ls", "Rs"):
        row = selected.get(role)
        if not row:
            continue
        paired = row is selected.get("Rs") and role == "Ls" and bool(PAIR.search(row["title"]))
        cap = 2 * (shares["Ls"] + shares.get("Rs", 0)) if paired else 2 * shares[role]
        best, good_models = surround_scores[cap]
        row_model = model_key(row)
        if (row_model in front_models and any(key not in front_models for key in good_models)
                or row_model not in front_models and quality(row, role, screen) < 0.85 * best):
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
    for role in group if len(group) == 1 or len(choice) < 2 else ():
        for row in rows:
            limit = 2.05 * shares[role] if role == "projector" else 2 * shares[role]
            if PAIR.search(row["title"]) or row["price"] > limit + 0.001:
                continue
            candidate = {**choice, role: row}
            if _cost(candidate) <= old_cost + leftover + 1e-8:
                yield role, candidate
    if len(group) == 2 and len(choice) == 2:
        first, second = group
        cap = min(2 * shares[first], 2 * shares[second])
        for row in _single_frontier(rows, first, cap, screen):
            candidate = {first: row, second: row.copy()}
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
    result = []
    for pool, rank in (([other for other in candidates if other["price"] < row["price"]],
                        lambda other: value(other, role, cap, screen)),
                       ([other for other in candidates if other["price"] > row["price"]],
                        lambda other: quality(other, role, screen)),
                       (candidates, lambda other: value(other, role, cap, screen))):
        ordered = sorted(pool, key=rank, reverse=True)
        for other in ordered:
            if model_key(other) not in {model_key(chosen) for chosen in result}:
                result.append(other)
                break
        if len(result) == 3:
            break
    return [{key: value_ for key, value_ in _item(role, other, screen, None).items()
             if key not in {"role", "pair_with"}} | {"price_delta": round(other["price"] - row["price"], 2)}
            for other in sorted(result, key=lambda other: other["price"])]


def _role_rows(catalog: dict, role: str, screen: dict | None, needed: int,
               projector: dict | None = None) -> list[dict]:
    rows = catalog[_category(role)]
    if role in {"L", "R", "C", "Ls", "Rs"}:
        rows = [row for row in rows if passive_speaker(row)]
        if role in {"L", "R", "C"}:
            rows = [row for row in rows if (row["specs"].get("form_factor")
                    in {None, "bookshelf", "floorstanding"})]
        if role in {"Ls", "Rs"}:
            rows = [row for row in rows if row["specs"].get("form_factor") in {None, "bookshelf"}]
    elif role == "receiver":
        rows = [row for row in rows if receiver_eligible(row, needed, projector)]
    elif role == "mount":
        rows = [row for row in rows if "projector" in row["title"].lower()
                and "ceiling" in row["title"].lower()]
    elif role == "hdmi_cable":
        rows = [row for row in rows if "hdmi" in row["title"].lower()]
    elif role == "speaker_wire":
        rows = [row for row in rows if "speaker wire" in row["title"].lower()
                and row["price"] >= 10]
    elif role == "screen" and screen:
        target = math.hypot(screen["width"], screen["height"]) * 12
        rows = [row for row in rows if not row["specs"].get("diagonal_in")
                or 0.8 * target <= (number(row["specs"]["diagonal_in"]) or 0) <= 1.2 * target]
    elif role == "projector":
        rows = [row for row in rows if not row["specs"].get("resolution")
                or (number(row["specs"]["resolution"]) or 0) >= 1080]
    return rows


def _total(picks: dict) -> float:
    seen: set[int] = set()
    amount = 0.0
    for choice in picks.values():
        for role, row in choice.items():
            covered = bundle_roles(row["title"], ("Ls", "Rs") if role in {"Ls", "Rs"} else ("L", "R"))
            if role in covered and id(row) in seen:
                continue
            amount += row["price"]
            if role in covered:
                seen.add(id(row))
    return amount


def _context_ok(picks: dict, pools: dict, shares: dict, screen: dict | None,
                surround_good: dict[str, set[str]] | None = None) -> bool:
    selected = {role: row for choice in picks.values() for role, row in choice.items()}
    left, right = selected.get("L"), selected.get("R")
    if left and right and model_key(left) != model_key(right):
        return False
    front = left or right
    center = selected.get("C")
    if front and center and center is not front:
        if center not in _center_rows(pools["C"], front, 2 * shares["C"]):
            return False
    fronts = {model_key(row) for role, row in selected.items() if role in {"L", "R", "C"}}
    surrounds = [selected[role] for role in ("Ls", "Rs") if role in selected]
    if len(surrounds) == 2 and model_key(surrounds[0]) != model_key(surrounds[1]):
        return False
    for role in ("Ls", "Rs"):
        row = selected.get(role)
        if not row:
            continue
        if surround_good is None:
            eligible = [other for other in pools[role] if other["price"] <= 2 * shares[role]]
            best = max((quality(other, role, screen) for other in eligible), default=0)
            good_models = {model_key(other) for other in eligible
                           if quality(other, role, screen) >= 0.85 * best}
        else:
            good_models = surround_good.get(role, set())
        good_different = bool(good_models - fronts)
        if model_key(row) in fronts and good_different:
            return False
    return True


def _bundle_upgrade(picks: dict, groups: list[tuple[str, ...]], rows: list[dict],
                    shares: dict[str, float], budget: float, screen: dict | None,
                    pools: dict, surround_good: dict[str, set[str]]) -> dict:
    selected_roles = {role for group in groups for role in group}
    for row in rows:
        covered = bundle_roles(row["title"])
        if len(covered) <= 2 or not set(covered) <= selected_roles:
            continue
        if row["price"] > 2 * sum(shares[role] for role in covered):
            continue
        proposed = {key: value.copy() for key, value in picks.items()}
        before = {role: item for choice in picks.values() for role, item in choice.items()}
        for role in covered:
            key = next(group for group in groups if role in group)
            proposed[key][role] = row
        after_total = _total(proposed)
        if after_total > budget + 0.001 or not _context_ok(proposed, pools, shares, screen, surround_good):
            continue
        old_quality = sum(quality(before[role], role, screen) for role in covered if role in before)
        new_quality = sum(quality(row, role, screen) for role in covered)
        old_cost = _total(picks)
        if (len(covered) > sum(role in before for role in covered)
                or new_quality - old_quality > PRICE_PENALTY * (after_total - old_cost) / max(budget, 1)):
            picks = proposed
    return picks


def get_products(layout: dict, budget: float, *, serpapi_key: str | None = None) -> dict:
    budget = max(0.0, float(budget))
    screen = layout.get("screen")
    speaker_roles = {speaker.get("role") for speaker in layout.get("speakers", [])}
    roles = [role for role in ORDER if role in speaker_roles]
    roles.append("receiver")
    roles.append("projector")
    if screen:
        roles.append("screen")
    roles.extend(("mount", "hdmi_cable"))
    unit = budget / sum(WEIGHTS[role] for role in roles)
    shares = {role: WEIGHTS[role] * unit for role in roles}
    path = working_path()
    with connect(path) as conn:
        categories = {_category(role) for role in roles} | {"display"}
        catalog = {category: _candidates(conn, category) for category in categories}
    requests = {}
    with connect(path) as conn:
        for role in roles:
            category = _category(role)
            matches = search.search(conn, category=category, price=f"..{shares[role]:.2f}", limit=10000)
            needed = len(speaker_roles - {"LFE"})
            valid_ids = {row["id"] for row in _role_rows(catalog, role, screen, needed)}
            if sum(row["id"] in valid_ids for row in matches) < 3:
                requests.setdefault(category, (shares[role], _constraints(role, screen)))
    warnings = expand(path, requests, serpapi_key or os.getenv("SERPAPI_KEY")) if requests else []
    if requests and not any("skipped" in warning for warning in warnings):
        with connect(path) as conn:
            catalog = {category: _candidates(conn, category) for category in catalog}
    tv = choose_tv(catalog["display"], screen, shares.get("projector", 0) + shares.get("screen", 0))
    if tv:
        roles = [role for role in roles if role not in {"projector", "screen", "mount"}] + ["tv"]
        shares["tv"] = shares["projector"] + shares["screen"]
    groups = []
    for role in roles:
        if role in {"R", "Rs"} and ("L" if role == "R" else "Ls") in roles:
            continue
        partner = {"L": "R", "Ls": "Rs"}.get(role)
        groups.append((role, partner) if partner in roles else (role,))
    groups.sort(key=lambda group: 0 if group[0] in {"L", "R"} else 1 if group[0] == "C" else 2)
    needed = len(speaker_roles - {"LFE"})
    pools = {role: _role_rows(catalog, role, screen, needed) for role in roles}
    surround_good = {}
    for role in ("Ls", "Rs"):
        if role not in pools:
            continue
        eligible = [row for row in pools[role] if row["price"] <= 2 * shares[role]]
        best_quality = max((quality(row, role, screen) for row in eligible), default=0)
        surround_good[role] = {model_key(row) for row in eligible
                               if quality(row, role, screen) >= 0.85 * best_quality}
    picks = {}
    for group in groups:
        role = group[0]
        rows = pools[role]
        front = next((row for choice in picks.values() for key, row in choice.items()
                      if key in {"L", "R"}), None)
        if role == "C" and front:
            rows = _center_rows(rows, front, shares["C"])
        elif role in {"Ls", "Rs"}:
            fronts = [row for choice in picks.values() for key, row in choice.items()
                      if key in {"L", "R", "C"}]
            if fronts:
                varied = _surround_rows(rows, fronts, sum(shares[key] for key in group), screen)
                if len(_choice(varied, group, sum(shares[key] for key in group), screen)) == len(group):
                    rows = varied
        if role == "tv":
            picks[group] = {role: tv}
        else:
            cap = sum(shares[key] for key in group)
            if role == "projector":
                cap *= 2.05
            picks[group] = _choice(rows, group, cap, screen)
    picks = _bundle_upgrade(picks, groups, pools.get("C", []), shares, budget, screen,
                            pools, surround_good)
    total = _total(picks)
    # The second pass may spend leftover budget, but each ordinary item stays within twice its share.
    for _ in range(30):
        best = None
        for group in groups:
            role = group[0]
            if role == "tv":
                continue
            old = picks[group]
            for _, candidate in _upgrades(old, group, pools[role], shares, budget - total, screen):
                proposed = {**picks, group: candidate}
                if role in {"L", "R"} and "C" in shares:
                    front = candidate.get("L") or candidate.get("R")
                    center_group = next((key for key in groups if key[0] == "C"), None)
                    if front and center_group:
                        center_rows = _center_rows(pools["C"], front, 2 * shares["C"])
                        center = _best(center_rows, "C", 2 * shares["C"], screen)
                        if center:
                            proposed[center_group] = {"C": center}
                if not _context_ok(proposed, pools, shares, screen, surround_good):
                    continue
                cost = _total(proposed)
                if cost > budget + 0.001 or cost < total - 0.001:
                    continue
                gain = sum(_choice_quality(choice, screen) - _choice_quality(picks[key], screen)
                           for key, choice in proposed.items())
                if gain <= 0.000001:
                    continue
                ratio = gain / max(cost - total, 0.01)
                if best is None or ratio > best[0]:
                    best = (ratio, proposed)
        if best is None:
            break
        picks = best[1]
        total = _total(picks)
    picks = _bundle_upgrade(picks, groups, pools.get("C", []), shares, budget, screen,
                            pools, surround_good)
    selected = {role: row for choice in picks.values() for role, row in choice.items()}
    if "projector" in selected and "receiver" in selected:
        if not receiver_eligible(selected["receiver"], needed, selected["projector"]):
            receivers = _role_rows(catalog, "receiver", screen, needed, selected["projector"])
            receiver_group = next(group for group in groups if group[0] == "receiver")
            for replacement in sorted(receivers, key=lambda row: value(row, "receiver", shares["receiver"], screen),
                                      reverse=True):
                proposed = {**picks, receiver_group: {"receiver": replacement}}
                if replacement["price"] <= 2 * shares["receiver"] and _total(proposed) <= budget:
                    picks = proposed
                    break
            else:
                projector_group = next(group for group in groups if group[0] == "projector")
                compatible = [row for row in pools["projector"]
                              if receiver_eligible(selected["receiver"], needed, row)]
                for replacement in sorted(compatible, key=lambda row: value(row, "projector", shares["projector"],
                                                                                screen), reverse=True):
                    proposed = {**picks, projector_group: {"projector": replacement}}
                    if replacement["price"] <= 2.05 * shares["projector"] and _total(proposed) <= budget:
                        picks = proposed
                        break
            selected = {role: row for choice in picks.values() for role, row in choice.items()}
            if not receiver_eligible(selected["receiver"], needed, selected["projector"]):
                projector_group = next(group for group in groups if group[0] == "projector")
                picks[projector_group] = {}
                mount_group = next((group for group in groups if group[0] == "mount"), None)
                if mount_group:
                    picks[mount_group] = {}
                selected = {role: row for choice in picks.values() for role, row in choice.items()}
                warnings.append("no compatible receiver and projector within budget")
    # Speaker wire is optional and is funded only from actual leftover.
    wire_rows = _role_rows(catalog, "speaker_wire", screen, needed)
    wire = _best(wire_rows, "speaker_wire", min(2 * unit * 0.5, budget - _total(picks)), screen)
    if wire:
        selected["speaker_wire"] = wire
        shares["speaker_wire"] = unit * 0.5
        roles.append("speaker_wire")
    paid: dict[int, str] = {}
    for role in ("C", "L", "R", "LFE", "Ls", "Rs"):
        row = selected.get(role)
        if row and role in bundle_roles(row["title"], ("Ls", "Rs") if role in {"Ls", "Rs"} else ("L", "R")):
            paid.setdefault(id(row), role)
    items = []
    total = _total(picks) + (wire["price"] if wire else 0)
    for role in ORDER:
        if role not in roles:
            continue
        row = selected.get(role)
        if not row:
            warnings.append(f"no product within budget for {role}")
            continue
        covered = bundle_roles(row["title"], ("Ls", "Rs") if role in {"Ls", "Rs"} else ("L", "R"))
        primary = paid.get(id(row)) if role in covered else None
        pair_with = ({"L": "R", "R": "L", "Ls": "Rs", "Rs": "Ls"}.get(role)
                     if len(covered) == 2 and any(selected.get(other) is row for other in covered if other != role)
                     else None)
        item = _item(role, row, screen, pair_with)
        if primary and primary != role:
            item["price"] = 0.0
            item["included_in"] = primary
            item["alternatives"] = []
        else:
            context = pools.get(role, _role_rows(catalog, role, screen, needed))
            if role in {"C", "Ls", "Rs"}:
                front = selected.get("L") or selected.get("R")
                if role == "C" and front and not covered:
                    context = _center_rows(context, front, 2 * shares[role])
                if role in {"Ls", "Rs"}:
                    fronts = [selected[key] for key in ("L", "R", "C") if key in selected]
                    if fronts:
                        surround_cap = 2 * sum(shares[key] for key in covered) if covered else 2 * shares[role]
                        context = _surround_rows(context, fronts, surround_cap, screen)
            if role == "receiver" and selected.get("projector"):
                context = [other for other in context
                           if receiver_eligible(other, needed, selected["projector"])]
            if role == "projector" and selected.get("receiver"):
                context = [other for other in context
                           if receiver_eligible(selected["receiver"], needed, other)]
            if covered:
                context = [other for other in context if set(bundle_roles(other["title"],
                           ("Ls", "Rs") if role in {"Ls", "Rs"} else ("L", "R"))) == set(covered)]
            elif role in {"L", "R", "C", "Ls", "Rs"}:
                context = [other for other in context if not bundle_roles(other["title"]) ]
            cap = 2 * sum(shares[key] for key in covered if key in shares) if covered else 2 * shares[role]
            if role == "projector":
                cap *= 1.02
            item["alternatives"] = _alternatives(role, row, context, cap, total, budget, screen,
                                                  bool(covered and PAIR.search(row["title"])))
        items.append(item)
    return {"budget": budget, "total": round(sum(item["price"] for item in items), 2),
            "items": items, "warnings": warnings}
