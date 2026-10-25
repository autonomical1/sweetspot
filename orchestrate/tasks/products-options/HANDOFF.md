# products-options handoff

## Done

- Kept the initial variety and per-item alternatives work, and fixed all four retry findings.
- Center validation now uses C's `2 * share` upgrade cap. Single L/R and Ls/Rs upgrades change both roles together; front upgrades reselect C in the same family and account for its cost and quality in the same decision.
- Alternative selection now considers all eligible listings before choosing cheaper, pricier, and third options, then removes duplicate models among those choices.
- `model_key` joins punctuation inside model codes and split letter suffixes. Added regression tests for this, center caps, joint front and surround upgrades, and alternative selection. No old test assertions were changed.

## Validation

- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/products/test_options.py -q --basetemp orchestrate/tasks/products-options/.pytest-tmp`: 11 passed.
- `python -m pytest -q -k 'not test_smoke_script_has_valid_bash_syntax' --basetemp orchestrate/tasks/products-options/.pytest-tmp`: 287 passed, 10 deselected.
- Unfiltered full suite: the only remaining failure is `test_smoke_script_has_valid_bash_syntax`. Windows `bash.EXE` launches WSL and returns `Wsl/Service/E_ACCESSDENIED`; this is outside the owned files. The default pytest temporary directory also raises `PermissionError` in this sandbox, so `--basetemp` is required.

## Demo room, 1,500 USD

Total: 1,466.97 USD. Alternatives show title, price, and `price_delta`.

| Role | Pick | Alternatives |
|---|---|---|
| C | Edifier R1280DB Bluetooth Bookshelf Speakers — 189.99 | Edifier R1280DBs Active Bluetooth Bookshelf Speakers — 159.99 (-30.00); Klipsch R-41M Reference Bookshelf Speakers — 199.00 (+9.01); Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) — 220.00 (+30.01) |
| L | Edifier R1280DB Bluetooth Bookshelf Speakers — 189.99 | Edifier R1280DBs Active Bluetooth Bookshelf Speakers — 159.99 (-30.00); Klipsch R-41M Reference Bookshelf Speakers — 199.00 (+9.01); Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) — 220.00 (+30.01) |
| R | Edifier R1280DB Bluetooth Bookshelf Speakers — 189.99 | Edifier R1280DBs Active Bluetooth Bookshelf Speakers — 159.99 (-30.00); Klipsch R-41M Reference Bookshelf Speakers — 199.00 (+9.01); Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) — 220.00 (+30.01) |
| LFE | Klipsch R-120SW Subwoofer — 329.00 | Polk Audio PSW Series PSW505 12" Powered Subwoofer Single — 60.50 (-268.50); Klipsch R-12SW Subwoofer — 259.00 (-70.00) |
| Ls | Polk Audio Signature Elite Es20 Bookshelf Speakers - Pair in Wenge at Nordstrom — 399.00 | Pair Of Edifier R1280db Bookshelf Speakers - Tested — 99.99 (-299.01); Klipsch Rb 51 Bookshelf Speakers, Black, Pair — 125.00 (-274.00); Klipsch R-50M 5.25" Bookshelf Speakers, 1-Pair — 424.99 (+25.99) |
| Rs | Polk Audio Signature Elite Es20 Bookshelf Speakers - Pair in Wenge at Nordstrom — 0.00 | none; swap through Ls |
| screen | Elite Screens 100 inch Manual Pull-down B Series Projection Screen M100H — 169.00 | Onn 120" Portable Indoor/Outdoor 16:9 Theater Projection Screen with Stand — 74.99 (-94.01); [Elite Screens] Yard Master 2 - Screen Material \| CineWhite UHD-B (Front Projection) 75" (16:9) - Z-Type — 167.00 (-2.00); 100inch Projector Screen with Stand, Portable Movie Screen Indoor Outdoor, White — 171.68 (+2.68) |

The projector is omitted at this budget with the existing warning.

## Unfinished

- The WSL bash syntax test requires a working WSL service or another bash installation outside this task's owned files.

## Design questions

- At very low budgets, should a same-model surround remain allowed when the different model meets the 85% quality threshold and role cap but cannot fit the whole-list budget? Kept the affordable filled roles; the alternative is to omit a surround role or rebalance all roles.
- Should model punctuation normalization join short suffix words after a model number? Joined one- or two-letter suffixes such as `R1280 DB` and all listed punctuation variants; alternatives are literal tokenization or joining longer words too.
