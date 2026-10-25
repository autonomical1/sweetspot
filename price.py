"""
price.py - Search av_prices.db using customer restrictions (price and spec ranges).

Range syntax (works for --price and for numeric specs):
    500..1500    between 500 and 1500 (inclusive)
    3000..       at least 3000
    ..1200       at most 1200
    1080         exactly 1080
    laser        text match (case-insensitive), e.g. light_source=laser

Examples:
    python price.py --category projector --price 500..1500 \
        --spec brightness_lumens=3000.. --spec resolution=1080.. --spec condition=new
    python price.py --category projection_screen --spec diagonal_in=100..120 --spec aspect_ratio=16:9
    python price.py --list-specs projector          # see which specs/values exist
    python price.py --profile customer_profile.json # pick the cheapest match per component

If fewer than --min-results (default 3) listings match, Gemini is asked (via main.py) to find
compatible products on the web; their listings are fetched with SerpAPI, stored, and searched
again. Needs GEMINI_API_KEY and SERPAPI_KEY in .env. Use --no-expand to skip this.
If there are still no matches, the closest stored listings (fewest restrictions missed) are shown.
"""
import argparse
import json
import os
import re
import sqlite3
import sys

from dotenv import load_dotenv

load_dotenv()  # lets AV_DB be set in .env

DB_PATH = os.environ.get("AV_DB", "av_prices.db")

NUM = r"-?\d[\d,]*\.?\d*"
RANGE_RE = re.compile(rf"^\s*({NUM})?\s*\.\.\s*({NUM})?\s*$")


def to_float(s):
    return float(str(s).replace(",", ""))


def parse_restriction(value):
    """
    Normalise a restriction into one of:
        ("range", lo, hi)        lo/hi may be None for open-ended
        ("exact", number, text)  matches the number OR the text value
        ("text", None, text)
    Accepts strings ("500..1500"), numbers (1080), or dicts ({"min": 500, "max": 1500}).
    """
    if isinstance(value, dict):
        lo, hi = value.get("min"), value.get("max")
        if lo is None and hi is None:
            raise ValueError("restriction needs a min and/or max")
        return ("range", None if lo is None else to_float(lo), None if hi is None else to_float(hi))
    value = str(value).strip()
    m = RANGE_RE.match(value)
    if m:
        lo = to_float(m.group(1)) if m.group(1) else None
        hi = to_float(m.group(2)) if m.group(2) else None
        if lo is None and hi is None:
            raise ValueError(f"empty range: {value!r}")
        return ("range", lo, hi)
    try:
        return ("exact", to_float(value), value)
    except ValueError:
        return ("text", None, value)


def condition(num_col, text_col, restriction):
    """Build an SQL condition + params for one restriction."""
    kind, a, b = restriction
    if kind == "range":
        parts, params = [], []
        if a is not None:
            parts.append(f"{num_col} >= ?")
            params.append(a)
        if b is not None:
            parts.append(f"{num_col} <= ?")
            params.append(b)
        return "(" + " AND ".join(parts) + ")", params
    if kind == "exact":
        if text_col is None:
            return f"({num_col} = ?)", [a]
        return f"({num_col} = ? OR lower({text_col}) = lower(?))", [a, b]
    if text_col is None:
        raise ValueError(f"price restriction must be numeric, got {b!r}")
    return f"(lower({text_col}) = lower(?))", [b]


def search(conn, category=None, price=None, specs=None, include_unknown=False,
           include_mismatches=False, history=False, limit=10):
    """
    Return listings (cheapest first) matching the restrictions.
      price: restriction for the price, e.g. "500..1500"
      specs: {"brightness_lumens": "3000..", "light_source": "laser"}
      include_unknown: keep listings where a requested spec could not be parsed
      include_mismatches: keep listings flagged as probably the wrong product type
      history: search every stored fetch, not just the most recent one per query
    """
    conn.row_factory = sqlite3.Row
    joins, join_params, where, where_params = [], [], [], []

    def add(sql, params=()):
        where.append(sql)
        where_params.extend(params)

    if not history:
        add("l.fetched_at = (SELECT MAX(fetched_at) FROM listings WHERE query = l.query)")
    if not include_mismatches:
        add("l.category_ok = 1")
    if category:
        add("l.category = ?", [category])
    if price is not None:
        sql, params = condition("l.price", None, parse_restriction(price))
        add(sql, params)

    for i, (name, value) in enumerate((specs or {}).items()):
        alias = f"s{i}"
        joins.append(f"LEFT JOIN specs {alias} ON {alias}.listing_id = l.id AND {alias}.name = ?")
        join_params.append(name)
        sql, params = condition(f"{alias}.value_num", f"{alias}.value_text", parse_restriction(value))
        if include_unknown:
            sql = f"({sql} OR {alias}.listing_id IS NULL)"
        else:
            sql = f"({alias}.listing_id IS NOT NULL AND {sql})"
        add(sql, params)

    query = f"""
        SELECT l.id, l.category, l.title, l.seller, l.price, l.link, l.fetched_at
        FROM listings l
        {' '.join(joins)}
        {'WHERE ' + ' AND '.join(where) if where else ''}
        ORDER BY l.price ASC
        LIMIT ?
    """
    rows = [dict(r) for r in conn.execute(query, join_params + where_params + [limit])]
    return attach_specs(conn, rows)


def attach_specs(conn, rows):
    for row in rows:
        row["specs"] = {
            s["name"]: format_spec(s)
            for s in conn.execute(
                "SELECT name, value_num, value_text, unit FROM specs WHERE listing_id = ? ORDER BY name",
                (row["id"],))
        }
    return rows


def search_closest(conn, category, price=None, specs=None, include_unknown=False,
                   include_mismatches=False, history=False, limit=5):
    """
    Fallback when nothing matches exactly: rank stored listings in `category` by how many
    restrictions they miss (fewest first, then cheapest). Listings that miss EVERY
    restriction are not "close", so they are dropped. Each row gets row["unmet"], a list of
    human-readable misses such as "brightness_lumens=3000.. (has 2800lm)".
    """
    conn.row_factory = sqlite3.Row
    constraints = []  # (name, requested value, sql condition, params)
    joins, join_params = [], []
    if price is not None:
        sql, params = condition("l.price", None, parse_restriction(price))
        constraints.append(("price", price, sql, params))
    for i, (name, value) in enumerate((specs or {}).items()):
        alias = f"s{i}"
        joins.append(f"LEFT JOIN specs {alias} ON {alias}.listing_id = l.id AND {alias}.name = ?")
        join_params.append(name)
        sql, params = condition(f"{alias}.value_num", f"{alias}.value_text", parse_restriction(value))
        if include_unknown:
            sql = f"({sql} OR {alias}.listing_id IS NULL)"
        constraints.append((name, value, sql, params))
    if not constraints:
        return []

    # A missing spec makes the condition NULL, which CASE treats as "not met".
    cases = [f"CASE WHEN {sql} THEN 0 ELSE 1 END" for _, _, sql, _ in constraints]
    case_params = [x for _, _, _, params in constraints for x in params]
    where, where_params = ["l.category = ?"], [category]
    if not history:
        where.append("l.fetched_at = (SELECT MAX(fetched_at) FROM listings WHERE query = l.query)")
    if not include_mismatches:
        where.append("l.category_ok = 1")

    query = f"""
        SELECT * FROM (
            SELECT l.id, l.category, l.title, l.seller, l.price, l.link, l.fetched_at,
                   {', '.join(f'{c} AS m{i}' for i, c in enumerate(cases))},
                   ({' + '.join(cases)}) AS misses
            FROM listings l
            {' '.join(joins)}
            WHERE {' AND '.join(where)}
        ) WHERE misses < ?
        ORDER BY misses ASC, price ASC
        LIMIT ?
    """
    # placeholders appear in SQL order: the CASEs twice (m cols, then misses), joins, where
    params = case_params * 2 + join_params + where_params + [len(constraints), limit]
    rows = [dict(r) for r in conn.execute(query, params)]
    attach_specs(conn, rows)
    for row in rows:
        row["unmet"] = []
        for i, (name, value, _, _) in enumerate(constraints):
            if not row[f"m{i}"]:
                continue
            actual = f"${row['price']:,.2f}" if name == "price" else row["specs"].get(name, "unknown")
            row["unmet"].append(f"{name}={value} (has {actual})")
    return rows


def search_with_expansion(conn, category=None, price=None, specs=None, min_results=3,
                          expand=True, max_queries=5, limit=10, **flags):
    """
    1. search() the database.
    2. If fewer than `min_results` match, ask Gemini (via main.py) for compatible products,
       store their SerpAPI listings, and search again.
    3. If there are STILL no matches, fall back to search_closest(): the stored listings
       that miss the fewest restrictions (rows carry an "unmet" list).
    """
    kwargs = dict(category=category, price=price, specs=specs, limit=limit, **flags)
    rows = search(conn, **kwargs)

    if len(rows) < min_results and expand:
        if not category:
            print(f"  (only found {len(rows)} matches; pass a category to look for more online)")
        else:
            print(f"  Only {len(rows)} match(es) in the database (wanted {min_results}). "
                  f"Asking Gemini for more '{category}' products...")
            try:
                import main as catalog  # lazy import: main.py never imports price.py
                saved = catalog.expand_catalog(conn, category, price, specs, max_queries=max_queries)
            except Exception as exc:
                print(f"  Could not expand the catalog: {exc}")
                saved = 0
            if saved:
                rows = search(conn, **kwargs)
                print(f"  Now {len(rows)} match(es) after adding {saved} new listings.")

    if not rows and category:
        rows = search_closest(conn, category, price, specs, limit=limit, **flags)
    return rows


def format_spec(s):
    if s["value_text"] and s["value_num"] is not None and s["name"] in ("resolution",):
        return s["value_text"]
    if s["value_text"]:
        return s["value_text"]
    num = s["value_num"]
    text = f"{num:g}"
    return f"{text}{s['unit'] or ''}"


def print_results(rows):
    if not rows:
        print("  No listings match these restrictions.")
        return
    if "unmet" in rows[0]:
        print("  No exact matches. Closest listings in the database (fewest restrictions missed):")
    for r in rows:
        print(f"  ${r['price']:>9,.2f}  {r['title'][:80]}  ({r['seller']})")
        if r.get("unmet"):
            print(f"             MISSES {len(r['unmet'])}: " + "; ".join(r["unmet"]))
        shown = {k: v for k, v in r["specs"].items() if k != "brand"}
        if shown:
            print("             " + ", ".join(f"{k}={v}" for k, v in shown.items()))
        if r["link"]:
            print(f"             {r['link']}")


def list_specs(conn, category):
    total = conn.execute("SELECT COUNT(*) FROM listings WHERE category = ?", (category,)).fetchone()[0]
    print(f"{total} stored listings in '{category}'. Specs found:\n")
    rows = conn.execute("""
        SELECT s.name, COUNT(*), MIN(s.value_num), MAX(s.value_num), group_concat(DISTINCT s.value_text)
        FROM specs s JOIN listings l ON l.id = s.listing_id
        WHERE l.category = ?
        GROUP BY s.name ORDER BY COUNT(*) DESC
    """, (category,)).fetchall()
    for name, count, lo, hi, texts in rows:
        extra = []
        if lo is not None:
            extra.append(f"range {lo:g}..{hi:g}")
        if texts:
            extra.append(f"values: {texts[:60]}")
        print(f"  {name:<24} {count:>4}/{total} listings   {'; '.join(extra)}")


def run_profile(conn, profile, limit, min_results=3, expand=True, **flags):
    """A profile describes a whole setup. Each component gets its own restrictions."""
    print(f"Customer profile: {profile.get('name', 'unnamed')}")
    total, missing, approx = 0.0, [], []
    for component, req in profile["components"].items():
        category = req.get("category", component)
        print(f"\n== {component} ({category}) ==")
        rows = search_with_expansion(conn, category=category, price=req.get("price"),
                                     specs=req.get("specs"), min_results=min_results,
                                     expand=expand, limit=limit, **flags)
        print_results(rows)
        if rows:
            total += rows[0]["price"]
            if "unmet" in rows[0]:
                approx.append(component)
        else:
            missing.append(component)
    print(f"\nCheapest matching setup: ${total:,.2f}")
    if approx:
        print(f"Note: {', '.join(approx)} use closest-match substitutes that miss some restrictions.")
    if missing:
        print(f"No match for: {', '.join(missing)} (try widening those ranges)")
    budget = profile.get("total_budget")
    if budget is not None:
        diff = budget - total
        status = f"${diff:,.2f} under budget" if diff >= 0 else f"${-diff:,.2f} OVER budget"
        print(f"Budget ${budget:,.2f}: {status}")


def main():
    p = argparse.ArgumentParser(description="Search AV listings with customer restrictions.")
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--category", help="projector, projection_screen, display, speaker, soundbar, ...")
    p.add_argument("--price", help="price range, e.g. 500..1500")
    p.add_argument("--spec", action="append", default=[], metavar="NAME=RESTRICTION",
                   help="spec restriction, repeatable (e.g. brightness_lumens=3000..)")
    p.add_argument("--include-unknown", action="store_true",
                   help="keep listings whose requested specs couldn't be parsed")
    p.add_argument("--include-mismatches", action="store_true",
                   help="keep listings flagged as the wrong product type (lamps, mounts, ...)")
    p.add_argument("--history", action="store_true", help="search all fetches, not just the latest")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--min-results", type=int, default=3,
                   help="if fewer listings match, ask Gemini for more products (default 3)")
    p.add_argument("--no-expand", action="store_true",
                   help="never call Gemini/SerpAPI, only search the database")
    p.add_argument("--profile", help="JSON file describing a customer's full setup")
    p.add_argument("--list-specs", metavar="CATEGORY", help="show parsed specs for a category")
    args = p.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"{args.db} not found. Run main.py first.")
    conn = sqlite3.connect(args.db)

    if args.list_specs:
        list_specs(conn, args.list_specs)
        return

    flags = dict(include_unknown=args.include_unknown,
                 include_mismatches=args.include_mismatches, history=args.history)

    if args.profile:
        with open(args.profile) as f:
            run_profile(conn, json.load(f), args.limit, min_results=args.min_results,
                        expand=not args.no_expand, **flags)
        return

    specs = {}
    for item in args.spec:
        if "=" not in item:
            sys.exit(f"--spec expects NAME=RESTRICTION, got {item!r}")
        name, value = item.split("=", 1)
        specs[name.strip()] = value.strip()

    print_results(search_with_expansion(conn, category=args.category, price=args.price,
                                        specs=specs, min_results=args.min_results,
                                        expand=not args.no_expand, limit=args.limit, **flags))


if __name__ == "__main__":
    main()