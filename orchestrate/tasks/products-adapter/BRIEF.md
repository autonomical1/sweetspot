# products-adapter: get_products() on top of the teammate's price database

## Goal
`GET /rooms/{id}/products?budget=N` returns real Google Shopping products from the teammate's SQLite catalog, one item per layout role, best price-to-performance within the budget, with parsed specs and physical dimensions (feet) so the AR view can size the models. Implement `products.get_products` exactly per docs/API.md section 4; `backend/app/products.py` already imports `products` and falls back to the stub on any exception.

## Read first
docs/API.md section 4 (the contract and all behaviour rules; it is authoritative), products/search.py (`search`, `search_closest`, `attach_specs`, `parse_restriction`), products/catalog.py (`init_db`, `save_listings`, `classify`, `extract_specs`, `RULES`, `expand_catalog`), backend/app/products.py, backend/app/stubs/products_stub.py, backend/tests/contract/checks.py (`assert_valid_products`), docs/API.md section 2 (layout: `speakers[].role`, `screen` with `width`/`height` in feet).
Database facts (products/av_prices.db, 2,866 listings): tables `listings` (category, category_ok, title, seller, price, link, snippet, extensions JSON, rating, reviews, query, fetched_at) and `specs` (listing_id, name, value_num, value_text, unit). No thumbnails, no dimensions stored. Many speaker titles contain "(Pair)"; there are no standalone center speakers. Junk exists (a Sonos Move 2 at 1.12 USD).

## Design decisions this brief encodes (user-approved; do not change)
- Teammate files `products/catalog.py`, `products/search.py` and `products/av_prices.db` are read-only for you. Write new modules under `products/` and export `get_products` from `products/__init__.py`. Call their functions; do not copy or rewrite them.
- Working DB: `AV_DB` env, default `<DATA_DIR>/av_prices.db` (`DATA_DIR` env, default `data`); if missing, copy `products/av_prices.db` there first (create the dir). Never write the repo copy.
- Filters, role -> category mapping, front-weighted shares, pairs (`pair_with`, second role price 0), `total <= budget`, omitted role -> warning: exactly as API.md section 4.
- Price-to-performance (put it in one small module with named constants so it can be tuned):
  - quality `q` in [0,1] = 0.5 * rating part + 0.5 * spec part.
  - rating part: Bayesian rating `(rating*reviews + 4.0*20) / (reviews + 20)` (missing rating/reviews -> 4.0 / 0), mapped `(r - 3) / 2` and clamped to [0,1].
  - spec part (missing spec -> 0.5 neutral for that term, average the terms): speaker: form_factor fits the role (fronts floorstanding/bookshelf, surrounds bookshelf) and `power_w` on a log scale 20..300 W; subwoofer: `driver_in` 8..15 in and `power_w` log 100..1000 W; projector: `resolution` (2160 -> 1, 1080 -> 0.5, lower -> 0), `brightness_lumens` log 1000..4000, laser bonus; screen: closeness of `diagonal_in` to the layout screen diagonal (from `screen.width`/`height` in feet), ALR bonus.
  - pick, among filtered listings with `price <= share`: maximise `q - 0.35 * price / share`. Second pass: walk roles by weight (C, L, R, LFE, Ls, Rs, screen, projector), give each the leftover added to its share, re-pick if the value improves and the total still fits.
- Pairs: a listing whose title matches `\bpairs?\b` or `\(2\)` / `set of 2` is a pair. For L+R (and Ls+Rs) consider pair listings against the combined share of both roles; if a pair wins, the first role gets the price, the second gets price 0, both get `pair_with`. Bundles containing a center (`center channel` in a pair listing) may not fill C by themselves; C is picked separately.
- Dimensions (feet, `{"width","height","depth","source"}`): parse from title + snippet + extensions (`W x H x D` with `"`/in/inches/cm/mm, also labelled `W ... H ... D`); else defaults per category/form factor (bookshelf 0.6 x 1.0 x 0.7, floorstanding 0.8 x 3.3 x 1.0, center 1.6 x 0.6 x 0.7, subwoofer 1.1 x 1.2 x 1.2, projector 1.3 x 0.5 x 1.1, screen = layout screen width/height x 0.15, else 1 x 1 x 1) with `source: "default"`. Never null for a returned item.
- `specs` on each item: the listing's spec dict as `attach_specs` formats it (strings). `seller` from the listing. `thumbnail` null. `source` "google_shopping". `currency` "USD".
- Expansion (only when a role has fewer than 3 filtered listings within its share AND both `GEMINI_API_KEY` and `SERPAPI_KEY` are set): call `catalog.expand_catalog(conn, category, price="..<share>", specs=<role constraints>, max_queries=3)` at most once per category per request, in a worker thread with its OWN sqlite connection to the working DB; wait at most `PRODUCTS_EXPAND_DEADLINE_S` (default 20) seconds in total for all expansions of the request, then re-query. A still-running expansion keeps going in the background (its listings help the next request); add a warning. No keys -> no expansion, warning `"catalog expansion skipped: GEMINI_API_KEY/SERPAPI_KEY not set"` once.
- `serpapi_key` keyword from the contract: use it when given, else env `SERPAPI_KEY`.
- Read paths open a fresh sqlite connection per call. No network in tests.

## Deliverables
1. `products/__init__.py` exporting `get_products`, plus new modules with exactly these names (OWNS.txt): `products/recommend.py` for selection/budget/pairs, `products/value.py` for quality + value constants, `products/dimensions.py`, `products/db.py` for working-DB seeding/connection, `products/expand.py` for the deadline-bound expansion).
2. Tests in `backend/tests/products/` (with `__init__.py`), DATA_DIR/AV_DB in tmp:
   - tiny fixture DB built with `catalog.init_db` + `catalog.save_listings` from hand-made listing dicts (no network): filters (used/refurb, no link, outlier, category mismatch), role mapping, pair handling, value pick vs cheap junk, second-pass upgrade, `total <= budget`, omitted role warning at a tiny budget, dimensions parsed vs default, `pair_with` symmetry.
   - expansion: monkeypatch `catalog.expand_catalog`; triggered only with both keys and fewer than 3 matches; at most once per category; slow fake (sleep > deadline with deadline set to 0.2 s) returns in time with a warning.
   - real seed DB (copied to tmp, no keys): `assert_valid_products` from `backend.tests.contract.checks` for budgets 1500 and 5000, with and without a screen, all six speaker roles present at 1500, each call under 2 s, every item has `dimensions` and `specs`.
   - one API test: `POST /rooms/demo`, optimize, `GET /rooms/{id}/products?budget=1500` returns `source == "google_shopping"` items (PRODUCTS_BACKEND unset).
3. HANDOFF.md: the value constants you chose to tune (if any), sample output for the demo room at 1500 USD (role, title, price), known data gaps.

## Done when
`python -m pytest -q` passes; `python -m ruff check products backend/tests/products` passes (ruff.toml at the root already excludes the teammate files); no edits outside OWNS.txt.

## Out of scope
Editing teammate files or the seed DB, backend/app/** (the existing loader is enough; if it is not, report it), docs, deploy, thumbnails, fetching new data, the web/iOS apps. Put unsettled choices (weights, value formula, dimension defaults) under `## Design questions` in HANDOFF.md.

## Retry 1: review findings to fix (all valid)
- products/expand.py:18 an explicit `serpapi_key` argument must take precedence over env `SERPAPI_KEY` (use it for the expansion even when the env var is set; do not mutate global env permanently).
- products/recommend.py:141 the second (leftover-upgrade) pass must compare the same price-to-performance value (`q - 0.35 * price/share`) as the first pass, not raw quality, so it never replaces a pick with a worse-value one; add a test where the pricier higher-quality item has worse value and is NOT chosen.
- products/value.py:53 screen ALR bonus must read the catalog's spec name `ambient_light_rejecting` (catalog.py RULES), not `alr`; add a test with a listing carrying that spec.
Keep ruff and the full suite green.

## Retry 2: review findings to fix (all valid)
- products/recommend.py:91 front roles (L, R, C) accept both `bookshelf` and `floorstanding` form factors: the expansion trigger and the "fewer than 3 matches" count must not require `form_factor=bookshelf`. Surrounds stay bookshelf-preferred. Add a test where only floorstanding listings exist and no expansion is triggered.
- products/recommend.py:145 the second pass must upgrade roles individually in the order C, L, R, LFE, Ls, Rs, screen, projector. For a pair listing, the pair's cap is the combined leftover plus both shares, and the pair is upgraded as one unit at the position of its first role; do not split the cap equally. Add a test where an L/R upgrade is available with leftover budget and is taken.
Keep ruff and the full suite green.
