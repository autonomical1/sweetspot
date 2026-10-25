# Products theater handoff

## Completed

- Added passive speaker, bundle, receiver, and TV rules in `products/theater.py`. The recommender now returns receiver, six speaker roles, projector and screen or TV, HDMI cable, projector mount when one fits its cap, and optional speaker wire. Pair, front-stage, and 5.1 bundle listings pay once with `included_in` on covered roles.
- Added receiver, mount, cable, and 16:9 TV dimensions; normalized punctuation within model keys; filtered alternatives using the same family, variety, eligibility, bundle, and budget context as the pick. Alternatives refill after model deduplication.
- Added `tools/expand_catalog.py` with the 20 requested queries, dry-run, query selection, explicit DB path, and a mandatory key for fetching.
- Added regression tests for passive filtering, bundle roles and pricing, receiver channel parsing, display choice, all five products-options findings, catalog tool behavior, and 1500/3000/5000 USD demo results.

## Demo room seed picks

All prices are USD. These were generated without API keys; listing availability and prices are the recorded seed data.

### Budget 1500 — total 1484.60

| Role | Listing | Price |
|---|---|---:|
| C | Edifier R980T Bookshelf Speakers | 79.99 |
| L | Edifier R980T Bookshelf Speakers | 79.99 |
| R | Edifier R980T Bookshelf Speakers | 79.99 |
| LFE | Klipsch R-12SW Subwoofer | 259.00 |
| Ls | Edifier R980T Bookshelf Speakers | 79.99 |
| Rs | Edifier R980T Bookshelf Speakers | 79.99 |
| receiver | Yamaha RX-V4A 5.2-Channel Network A/V Receiver with MusicCast 5.2 Channels | 220.00 |
| projector | XGIMI MoGo 4 1920 x 1080 DLP Portable Projector with 450 Lumens | 479.00 |
| screen | Onn 120" Portable Indoor/Outdoor 16:9 Theater Projection Screen with Stand | 74.99 |
| hdmi_cable | Monoprice HDMI Cable,High Speed | 16.48 |
| speaker_wire | AmazonBasics Basics 100ft 16-Gauge Audio Stereo Speaker Wire Cable Theater + Banana Plugs - Electronics | 35.18 |

The mount is omitted with a warning: the cheapest seed projector ceiling mount is 120.28, above the 78.95 doubled mount share at this budget.

### Budget 3000 — total 2976.62

| Role | Listing | Price |
|---|---|---:|
| C | Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) | 220.00 |
| L | Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) | 220.00 |
| R | Klipsch RP-8000F II Reference Premiere Floorstanding Speaker - Each (Ebony) | 220.00 |
| LFE | Klipsch R-12SW Subwoofer | 259.00 |
| Ls | Klipsch R-50M Reference Bookshelf Speakers | 254.99 |
| Rs | Klipsch R-50M Reference Bookshelf Speakers | 254.99 |
| receiver | Denon AVR-S770H 7.2 Ch. 8K AV Receiver | 699.99 |
| projector | XGIMI MoGo 4 1920 x 1080 DLP Portable Projector with 450 Lumens | 479.00 |
| screen | Elite Screens 100 inch Manual Pull-down B Series Projection Screen M100H | 169.00 |
| mount | Premier Mounts PDS-PLUS-W Ceiling Mount for Projector | 147.99 |
| hdmi_cable | Monoprice HDMI Cable,High Speed | 16.48 |
| speaker_wire | AmazonBasics Basics 100ft 16-Gauge Audio Stereo Speaker Wire Cable Theater + Banana Plugs - Electronics | 35.18 |

### Budget 5000 — total 4072.98

| Role | Listing | Price |
|---|---|---:|
| C | Klipsch RP-600M II Reference Premiere Bookshelf Speakers | 449.99 |
| L | Klipsch RP-600M II Reference Premiere Bookshelf Speakers | 449.99 |
| R | Klipsch RP-600M II Reference Premiere Bookshelf Speakers | 449.99 |
| LFE | SVS PB-2000 Pro Subwoofer | 699.00 |
| Ls | Klipsch R-50M Reference Bookshelf Speakers | 254.99 |
| Rs | Klipsch R-50M Reference Bookshelf Speakers | 254.99 |
| receiver | Denon AVR-S770H 7.2 Ch. 8K AV Receiver | 699.99 |
| tv | Tcl 98T8C Google Television 98 Inch T8C Premium 4K | 762.38 |
| hdmi_cable | Monoprice HDMI Cable,High Speed | 16.48 |
| speaker_wire | AmazonBasics Basics 100ft 16-Gauge Audio Stereo Speaker Wire Cable Theater + Banana Plugs - Electronics | 35.18 |

## Catalog gaps and follow-up

- Fetch affordable, explicitly passive center channels and bookshelf speakers using the new tool. The seed rarely says whether a speaker is passive. In particular, its `Edifier R980T Bookshelf Speakers` row has no powered/active clue in either title or parsed specs, so the specified keyword filter cannot establish its actual power type.
- Fetch a projector ceiling mount under about 79 USD for a complete 1500 USD setup. The seed's cheapest eligible one is 120.28 USD.
- Fetch more affordable passive 5.1 packages and receiver choices. The seed's `Klipsch R-50M 5.1 Home Theater System` title does not explicitly mention a subwoofer, so the conservative title rule covers five speaker roles, not LFE.
- Extend `backend/tests/contract/checks.py` `PRODUCT_ROLES` with `receiver`, `tv`, `mount`, `hdmi_cable`, and `speaker_wire`; it currently accepts only the legacy speaker, screen, and projector roles. The owned product tests project to those legacy roles when calling that checker. `included_in` is an additional optional field on bundle items.

## Unfinished

- The shared `PRODUCT_ROLES` checker and catalog seed updates are outside this task's ownership. The 1500 USD seed response warns that no ceiling mount fits its cap.

## Decisions

- Listings with no evidence of active or passive operation remain eligible under the approved keyword filter. This is reversible once the catalog includes reliable power-type metadata.
- A flagged speaker-category listing can be reconsidered only when its title unambiguously describes a 5.1 bundle, because the teammate classifier otherwise labels bundles with a subwoofer as subwoofers.

## Verification

- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/products -q --basetemp backend/tests/products/.tmp_test`: 39 passed.
- Full pytest run: 298 passed, 9 deselected, 1 failed in `test_smoke_script_has_valid_bash_syntax`. This unrelated deploy test invokes Windows `bash.exe`, which returned WSL `E_ACCESSDENIED` in this sandbox. The deploy files and test are outside this task's ownership.
- Excluding only that deploy syntax test: 298 passed, 10 deselected.

## Design questions

- The seed's cheapest projector is 479 USD, just above the strict 2 × projector share (473.68 USD) at a 1500 USD budget. I used a 2.05 × cap for projector selection so that budget can include a display. Alternatives are to keep the strict cap and omit the projector at 1500 USD, adjust the share weights, or fetch a cheaper projector.
