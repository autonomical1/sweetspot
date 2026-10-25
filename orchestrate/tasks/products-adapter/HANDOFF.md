# Products adapter handoff

## Completed

- Added `products.get_products` with a copied working SQLite catalog (`AV_DB` or `$DATA_DIR/av_prices.db`), latest-query/category/condition/link/outlier filters, quality scoring, budget shares, a second upgrade pass, pair accounting, and warnings for omitted roles.
- Added dimensions in feet from listing copy with category defaults, catalog specs and seller fields, and deadline-bound expansion in worker threads with independent SQLite connections.
- Fixed the retry findings: explicit `serpapi_key` overrides an existing environment key during expansion and restores it afterward; the second pass compares the same value formula using the original role share; screen quality reads the catalog's `ambient_light_rejecting` spec. Expansion calls are serialized because the teammate interface reads a process-wide environment variable.
- Added offline fixture, seed catalog, expansion deadline, key precedence, value regression, ALR quality, and demo HTTP tests under `backend/tests/products/`.

## Verification

- `python -m ruff check products backend/tests/products`: passed.
- `python -m pytest backend/tests/products -q --basetemp .pytest_products_tmp`: 12 passed.
- `python -m pytest -q --basetemp .pytest_all_tmp`: 260 passed, 8 deselected, 1 failed. The only failure is `test_smoke_script_has_valid_bash_syntax`: Windows `bash.exe` returned `E_ACCESSDENIED` while starting WSL in this sandbox. The deploy smoke test needs a runner with working Bash/WSL.

## Demo room sample at $1,500

Total: $1,004.63 (no API keys, working seed copy).

| Role | Title | Price |
|---|---|---:|
| C | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $134.38 |
| L | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $134.38 |
| R | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $0.00, paired with L |
| LFE | Polk Audio PSW Series PSW505 12" Powered Subwoofer Single | $60.50 |
| Ls | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $134.38 |
| Rs | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers | $0.00, paired with Ls |
| screen | Portable Metal Projection Screen 120 Inch Anti Light Movie Screen 16:9 3D 4K 1080P HD Foldable Projection Screen for Home Theater Indoor & Outdoor Ent | $61.99 |
| projector | XGIMI MoGo 4 1920 x 1080 DLP Portable Projector with 450 Lumens | $479.00 |

## Known data gaps

- Seed database has no thumbnail or stored physical dimensions; size defaults often apply.
- No standalone center speakers in the seed. A bookshelf listing fills C separately, and the same model can also fill other roles.
- Seed listings can include low-brightness projectors and incomplete specs. The requested quality formula ranks only the specs that exist.

## Unfinished

- The deploy Bash syntax test cannot run successfully in this Windows sandbox because WSL startup is denied. Re-run the full suite in a runner with Bash/WSL access.

## Value constants

- Price penalty: 0.35; Bayesian rating prior: 4.0 over 20 reviews; missing-spec term: 0.5. These follow the brief; none were tuned.

## Design questions

- none
