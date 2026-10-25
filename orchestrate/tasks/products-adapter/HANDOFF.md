# Products adapter handoff

## Completed

- Added `products.get_products` with a copied working SQLite catalog (`AV_DB` or `$DATA_DIR/av_prices.db`), latest-query/category/condition/link/outlier filters, quality scoring, budget shares, a second upgrade pass, pair accounting, and warnings for omitted roles.
- Added dimensions in feet from listing copy with category defaults, catalog specs and seller fields, and deadline-bound expansion in worker threads with independent SQLite connections. Explicit `serpapi_key` is passed through to the teammate expansion interface via a guarded temporary environment override.
- Added offline fixture, seed catalog, expansion deadline, and demo HTTP tests under `backend/tests/products/`.

## Verification

- `python -m ruff check products backend/tests/products`: passed.
- `python -m pytest backend/tests/products -q --basetemp .pytest_products_tmp`: 10 passed.
- `python -m pytest backend -q --basetemp .pytest_all_tmp -k 'not smoke_script_has_valid_bash_syntax'`: 226 passed, 9 deselected. The initial unmodified full `python -m pytest -q` run failed in unrelated tests because Windows sandbox denied Bash startup and out-of-workspace temporary paths. The excluded smoke test needs Bash access in the runner.

## Demo room sample at $1,500

Total: $1,176.14 (no API keys, working seed copy).

| Role | Title | Price |
|---|---|---:|
| C | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $134.38 |
| L | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $134.38 |
| R | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $0.00, paired with L |
| LFE | Klipsch R-120SW Subwoofer | $125.00 |
| Ls | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $134.38 |
| Rs | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $0.00, paired with Ls |
| screen | Elite Screens 100 inch Manual Pull-down B Series Projection Screen M100H | $169.00 |
| projector | XGIMI MoGo 4 1920 x 1080 DLP Portable Projector with 450 Lumens | $479.00 |

## Known data gaps

- Seed database has no thumbnail or stored physical dimensions; size defaults often apply.
- No standalone center speakers in the seed. A bookshelf listing fills C separately, and the same model can also fill other roles.
- Seed listings can include low-brightness projectors and incomplete specs. The requested quality formula ranks only the specs that exist.

## Design questions

- none. The price penalty (0.35), Bayesian prior (4.0 over 20 reviews), neutral missing-spec score (0.5), role weights, and dimension defaults follow the brief.
