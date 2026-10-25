# products-options handoff

## Done

- Added `products/variety.py` with `model_key`, family matching, and cached title parsing.
- Updated the initial choices and greedy upgrades to keep L/R/C matched and prefer a good different surround model. The 1,500 USD demo chooses Edifier fronts and a Polk surround pair.
- Added budget-safe, model-distinct swap alternatives to every returned item. Pair swaps appear on L or Ls; R or Rs has an empty list when covered by a pair.
- Added `backend/tests/products/test_options.py` for model identity, family matching, surround variety, pair swaps, alternative order/deltas/budgets, contract validity, and seed demo timing.
- No existing test assertions were edited.

## Validation

- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/products/test_options.py -q --basetemp orchestrate/tasks/products-options/.pytest-tmp`: 6 passed.
- Full `python -m pytest -q --basetemp orchestrate/tasks/products-options/.pytest-tmp`: 279 passed, 9 deselected, 1 unrelated failure in `test_smoke_script_has_valid_bash_syntax`; Windows bash returned `Wsl/Service/E_ACCESSDENIED`. The default pytest temporary directory also raised `PermissionError` in this sandbox, so `--basetemp` was needed. Test artifacts were removed.

## Demo room, 1,500 USD

Total: 1,466.97 USD. Each alternative is `title — price (price_delta)`.

| Role | Pick | Alternatives |
|---|---|---|
| C | Edifier R1280DB Bluetooth Bookshelf Speakers — 189.99 | Edifier R1280DBs Active Bluetooth Bookshelf Speakers — 159.99 (-30.00); Klipsch R-41M Reference Bookshelf Speakers — 199.00 (+9.01); Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) — 220.00 (+30.01) |
| L | Edifier R1280DB Bluetooth Bookshelf Speakers — 189.99 | Edifier R1280DBs Active Bluetooth Bookshelf Speakers — 159.99 (-30.00); Klipsch R-41M Reference Bookshelf Speakers — 199.00 (+9.01); Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) — 220.00 (+30.01) |
| R | Edifier R1280DB Bluetooth Bookshelf Speakers — 189.99 | Edifier R1280DBs Active Bluetooth Bookshelf Speakers — 159.99 (-30.00); Klipsch R-41M Reference Bookshelf Speakers — 199.00 (+9.01); Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) — 220.00 (+30.01) |
| LFE | Klipsch R-120SW Subwoofer — 329.00 | Polk Audio PSW Series PSW505 12" Powered Subwoofer Single — 60.50 (-268.50); Klipsch R-12SW Subwoofer — 259.00 (-70.00); Klipsch Flexus Sub 100 10" Wireless Subwoofer — 349.00 (+20.00) |
| Ls | Polk Audio Signature Elite Es20 Bookshelf Speakers - Pair in Wenge at Nordstrom — 399.00 | Pair Of Edifier R1280db Bookshelf Speakers - Tested — 99.99 (-299.01); Klipsch Rb 51 Bookshelf Speakers, Black, Pair — 125.00 (-274.00); Klipsch R-50M 5.25" Bookshelf Speakers, 1-Pair — 424.99 (+25.99) |
| Rs | Polk Audio Signature Elite Es20 Bookshelf Speakers - Pair in Wenge at Nordstrom — 0.00 | none; swap through Ls |
| screen | Elite Screens 100 inch Manual Pull-down B Series Projection Screen M100H — 169.00 | Onn 120" Portable Indoor/Outdoor 16:9 Theater Projection Screen with Stand — 74.99 (-94.01); [Elite Screens] Yard Master 2 - Screen Material | CineWhite UHD-B (Front Projection) 75" (16:9) - Z-Type — 167.00 (-2.00); 100inch Projector Screen with Stand, Portable Movie Screen Indoor Outdoor, White — 171.68 (+2.68) |

The projector is omitted at this budget by the existing recommender, with its existing warning.

## Unfinished

- The full suite's Windows bash syntax test requires a working WSL/bash service outside this task's owned files.

## Design questions

- At very low budgets, should a same-model surround remain allowed when the different model meets the 85% quality threshold and role cap but cannot fit the remaining whole-list budget? The implementation keeps the affordable filled roles; the alternative is to omit a surround role or rebalance all roles.
- Should punctuation inside model names be normalized beyond a letter followed by a hyphen and digits? The implementation joins `R-41M` into `R41M`; the alternative is to treat the title tokens literally.
