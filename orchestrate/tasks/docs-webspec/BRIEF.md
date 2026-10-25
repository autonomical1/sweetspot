# docs-webspec: update the web teammate's spec for the new engine, products and Gemini behaviour (docs only)

## Goal
`webapp_context/` is the spec the web teammate builds the React + Vite app from. Parts of it are stale: it lists exactly six speaker roles, hard-codes speaker box sizes, and knows nothing about staged 3D layouts, product alternatives, or the Gemini limits. Update it minimally and accurately. Docs only.

## Read first
webapp_context/01_product_and_flows.md, 02_api_reference.md, 03_data_and_coordinates.md, 04_3d_view.md, 06_panels_products_materials.md (the five files you may edit), docs/API.md (authoritative: sections 1, 2, 2a, 4, 6), fixtures/engine/layout_7.1.4.json (a real engine output), docs/ENGINE_INTEGRATION_AUDIT.md.

## What to change (mark LIVE vs PLANNED explicitly; the web app must not rely on PLANNED parts yet)
- 03 and 04: speaker roles. LIVE: `L R C LFE Ls Rs`. PLANNED (staged 3D engine, task engine3d-wire): also `Lss Rss Lrs Rrs`, overheads `Ltf Rtf Ltr Rtr Ltm Rtm`, `LFE2`; speakers get optional `size {width,height,depth}` (feet), `yaw_deg`, `pitch_deg`, `mount`, `compliance`, `receiver_delay_ms`; layout gets optional `preset`, `standard`, `stage`, `seats`, `projector`. Tell the viewer to size each speaker box from `size` when present, from the product `dimensions` when a product is chosen, else fall back to the current default box. Heights are real (y is up); overhead speakers sit at ceiling height.
- 02: add LIVE `GET /rooms/{id}/materials/status` and the Gemini behaviour on `POST /rooms/{id}/materials` (`status` fresh/cached/joined, 429 with `retry_after_s` and the `Retry-After` header: show "Gemini is busy, retry in N s" and do not hammer); add PLANNED `GET /rooms/{id}/optimize/status`, `options {preset, standard, refine}` on optimize, and `stage` on layouts (`quick` -> `refining` -> `refined`; poll the status every 3 s, show the quick layout immediately with a small "refining in 3D..." indicator, swap in the refined layout when it arrives, never block the UI).
- 06 (products): LIVE fields `seller`, `specs`, `dimensions` (feet), `pair_with`, `alternatives` (up to 3 swap options with `price_delta`; for a pair listing the second role has price 0 and no alternatives: swap through the first role); PLANNED new roles `receiver`, `tv`, `mount`, `hdmi_cable`, `speaker_wire`, `included_in`. Suggest a swap UI that matches the iPhone Shop screen.
- 01: role colours: keep the existing six; add a SUGGESTED palette for the new roles (keep it consistent with the existing style) clearly labelled as a suggestion; mention that the first-time flow should show the quick layout immediately.
- Keep all edits small and in the existing style; do not restructure files or change decisions already made (stack, routes, panels). Do not touch webapp_context/README.md or 05/07 (another task owns the README).

## Deliverables / done when
The five files updated; HANDOFF.md lists the changes by file and any contradiction you found between the spec and docs/API.md. `python -m ruff check . && python -m pytest -q` still passes (no code changes). No edits outside OWNS.txt.

## Out of scope
Code, docs/API.md, the web app itself.
