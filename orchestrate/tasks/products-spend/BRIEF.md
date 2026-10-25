# products-spend: use the budget (the recommender underspends)

## Goal
`products.get_products` must spend most of the budget on better products, front roles first, instead of picking the cheapest acceptable item per role. Measured on the live demo room (6 speakers + screen + projector): budget 1500 USD returns a total of only 521 USD (the same 134 USD Edifier bookshelf for C, L and Ls; a 60 USD subwoofer; a 169 USD screen; a 100 USD projector), and the leftover ~980 USD buys nothing. Budget 4000 returns 733.

## Read first
products/recommend.py (`_best`, `_choice`, `_choice_value`, the second pass in `get_products`), products/value.py (`quality`, `value`, the 0.35 price penalty), backend/tests/products/test_recommend.py, docs/API.md section 4 (budget rules: front-weighted shares C3 L2 R2 LFE2 Ls1 Rs1 screen1 projector1, best price-to-performance within each share, second pass upgrades with the leftover, `total <= budget` always).

## Design decisions this brief encodes (user-approved; do not change)
- Keep price-to-performance as the idea, but make the price penalty small: define one named constant `PRICE_PENALTY = 0.15` (was 0.35) in products/value.py and use it everywhere the 0.35 appears. Quality must dominate unless a higher-priced item is barely better.
- The second pass is a greedy upgrade loop, not a single sweep: repeat while leftover budget remains and an upgrade exists. Each round, among all roles (pair groups upgrade as one unit) consider the best-quality candidate that is strictly better in quality than the current pick and whose extra cost fits the leftover; apply the upgrade with the best `quality gain per extra dollar` (ties: earlier in the order C, L, R, LFE, Ls, Rs, screen, projector). Stop when no upgrade fits or no upgrade improves quality. Never exceed the budget; never drop a role that was filled.
- No role may take more than twice its original share in upgrades, so one role (e.g. the projector) cannot eat the budget while the speakers stay cheap: cap per role = `2 * share` (pair group: `2 * combined share`). Roles that cannot be filled within their cap keep their first-pass pick.
- Junk protection stays exactly as is (new condition, link, outlier filter, category_ok). Do not change the filters, the role-to-category mapping, expansion, dimensions, pair semantics or the item/response shape.
- Result target on the seed catalog (demo room with screen): budget 1500 -> total between 1100 and 1500; budget 4000 -> total at least 2400; budget 500 -> still valid with `total <= 500` (roles that cannot fit get warnings as today); the C item must not be cheaper than the average of L and R pick prices when a better-quality C candidate fits.

## Deliverables
1. Changes in products/value.py and products/recommend.py (only what the above needs).
2. Tests in backend/tests/products/ (extend test_recommend.py or add test_spend.py): the three seed-catalog totals above (copy the seed db into a tmp DATA_DIR as the existing seed test does; no network, no API keys); greedy loop upgrades several roles and stops at `total <= budget`; the per-role `2 * share` cap holds; the cheap-junk-vs-good value pick still prefers the good item; all existing tests stay green (update thresholds only where they encode the old 0.35 behaviour, and say so in HANDOFF.md).
3. HANDOFF.md: before/after totals for the demo room at 500, 1500 and 4000 USD with the chosen items (role, title, price).

## Done when
`python -m ruff check . && python -m pytest -q` passes; no edits outside OWNS.txt.

## Out of scope
Everything not listed above: teammate files (products/catalog.py, products/search.py, the db), backend/app/**, docs, deploy, dimensions, expansion. Put unsettled choices (cap factor, penalty, tie-breaks) under `## Design questions` in HANDOFF.md.
