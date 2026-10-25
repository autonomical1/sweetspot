# products-spend handoff

## Done

- Set `PRICE_PENALTY = 0.15` and used it for pair comparisons as well as individual value picks.
- Replaced the one-sweep second pass with a greedy quality-gain-per-extra-dollar loop. It keeps filled roles, can fill an unfilled role when its cap allows, upgrades pairs together, enforces each single role's `2 * share` cap and each pair's `2 * combined share` cap, and uses role order for ties.
- Kept filters, catalog expansion, dimensions, response shape, and pair listing matching. Corrected the cost and output accounting for two separately purchased copies of the same non-pair listing; they now charge both roles.
- Added demo seed spend, budget, cap, and multiple-upgrade tests. Updated two assertions that encoded the old 0.35 price preference: the higher-quality Premium and Slightly Better listings now win.

## Demo room results

Measured with `fixtures/room_demo.json` through `run_optimize`, with a fresh seed catalog copy, no API keys, and no network. The before values run the original `HEAD` recommender with the original 0.35 penalty against this same demo layout. `Rs` costs $0 when a pair listing covers both surround roles.

| Budget | Before | After |
| --- | ---: | ---: |
| $500 | $402.46 | $475.45 |
| $1,500 | $950.24 | $1,447.95 |
| $4,000 | $1,111.64 | $2,514.95 |

### $500 picks

| Role | Before: title, price | After: title, price |
| --- | --- | --- |
| C | Edifier R980T Bookshelf Speakers, $79.99 | Edifier R980T Bookshelf Speakers, $79.99 |
| L | Pair Of Edifier R1280db Bookshelf Speakers - Tested, $99.99 | Edifier R980T Bookshelf Speakers, $79.99 |
| R | Same pair, $0 | Edifier R980T Bookshelf Speakers, $79.99 |
| LFE | Polk Audio PSW Series PSW505 12" Powered Subwoofer Single, $60.50 | Same, $60.50 |
| Ls | Pair Of Edifier R1280db Bookshelf Speakers - Tested, $99.99 | Same, $99.99 |
| Rs | Same pair, $0 | Same pair, $0 |
| screen | Portable Metal Projection Screen 120 Inch Anti Light Movie Screen 16:9 3D 4K 1080P HD Foldable Projection Screen for Home Theater Indoor & Outdoor Ent, $61.99 | Onn 120" Portable Indoor/Outdoor 16:9 Theater Projection Screen with Stand, $74.99 |

### $1,500 picks

| Role | Before: title, price | After: title, price |
| --- | --- | --- |
| C | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers, $134.38 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| L | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers, $134.38 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| R | Same listing, $0 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| LFE | Polk Audio PSW Series PSW505 12" Powered Subwoofer Single, $60.50 | Klipsch R-120SW Subwoofer, $329.00 |
| Ls | Edifier R980T Bookshelf Speakers, $79.99 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| Rs | Same listing, $0 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| screen | Portable Metal Projection Screen 120 Inch Anti Light Movie Screen 16:9 3D 4K 1080P HD Foldable Projection Screen for Home Theater Indoor & Outdoor Ent, $61.99 | Elite Screens 100 inch Manual Pull-down B Series Projection Screen M100H, $169.00 |
| projector | XGIMI MoGo 4 1920 x 1080 DLP Portable Projector with 450 Lumens, $479.00 | Unfilled within cap |

### $4,000 picks

| Role | Before: title, price | After: title, price |
| --- | --- | --- |
| C | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers, $134.38 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| L | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers, $134.38 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| R | Same listing, $0 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| LFE | Polk Audio PSW Series PSW505 12" Powered Subwoofer Single, $60.50 | SVS PB-2000 Pro Subwoofer, $699.00 |
| Ls | Edifier R1280DB 2.0 Lifestyle Bookshelf Bluetooth Studio Speakers, $134.38 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| Rs | Same listing, $0 | Edifier R1280DB Bluetooth Bookshelf Speakers, $189.99 |
| screen | Elite Screens 100 inch Manual Pull-down B Series Projection Screen M100H, $169.00 | Elite Screens Aeon CineWhite UHD-B Series 115 Inch Diagonal Fixed Frame Screen, $387.00 |
| projector | XGIMI MoGo 4 1920 x 1080 DLP Portable Projector with 450 Lumens, $479.00 | Same, $479.00 |

## Verification and unfinished

- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/products -q --basetemp backend/tests/products/.pytest_tmp --tb=short`: 17 passed.
- Full `python -m pytest -q --basetemp backend/tests/products/.pytest_tmp --tb=short`: 273 passed, 9 deselected, 1 failed. The sole failure is `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax`: Windows `bash.exe` returns `E_ACCESSDENIED` in this sandbox before checking script syntax. This is outside owned files. Generated test data was removed.
- The brief's live-room before totals ($521 at $1,500 and $733 at $4,000) differ from the current fixture baseline above; the before/after table uses the same fixture and seed for a controlled comparison.

## Design questions

- none
