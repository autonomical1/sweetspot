# backend-2-1: add a 2.1 speaker configuration

## Goal
`POST /rooms/{id}/optimize` accepts `options.preset = "2.1"` (left, right, subwoofer) and returns a valid layout, metrics and shopping list for it, so the iPhone form can offer 2.1 / 5.1 / 7.1 with optional height channels.

## Design decisions encoded (user, 2026-10-25 02:50)
- Presets offered by the product: `2.1`, `5.1`, `7.1` plus height variants `5.1.2`, `5.1.4`, `7.1.2`, `7.1.4` (already supported). No `.6` variants, no 2.1.x height variants.
- 2.1 means exactly the roles `L`, `R`, `LFE` in the layout (no `C`, `Ls`, `Rs`). The listener, screen and projector logic stay as for other presets.
- The staged flow is unchanged: a quick layout first (`stage: quick`), then the refined 3D run (`refined`). For 2.1 both stages contain only L, R, LFE.

## Deliverables
1. `backend/app/engine3d.py`: add `"2.1"` to `PRESETS` and make the headless 3D run produce a 2.1 layout (check `python -m speakerplacer --help`: the engine CLI has `--layout custom` with `--speakers`; if no 2.1 preset exists, build the custom speaker list for L, R and a sub; read `speakerplacer/ENGINE.md`). The schema-2 -> layout mapper must emit only L, R, LFE.
2. `backend/app/rooms.py` / `refine.py` (whatever validates `preset`): accept `2.1`. The quick 2D layout for 2.1 is the existing quick layout reduced to L, R, LFE (positions unchanged), so the quick answer stays fast.
3. Products: `products/` picks for 2.1: a matched left/right pair, one subwoofer (powered), a stereo-capable receiver or amplifier (2 channels is enough), plus the existing display/projector logic. Add the role list for 2.1 where roles are chosen and make sure the budget shares redistribute over the roles that exist.
4. Tests (pytest, no network): `2.1` optimize returns exactly L, R, LFE with positions inside the room; invalid presets still 422; products for a 2.1 layout list only the needed roles and respect the budget; existing 5.1/7.1 tests unchanged.

## Done when
`python -m ruff check . && python -m pytest -q` pass. Report in HANDOFF.md any needed change to docs/API.md (the orchestrator edits it).

## Out of scope
The iOS app, the web app, `.6` height variants, speakerplacer internals (do not edit `speakerplacer/`), docs/API.md.

## Files you own
`backend/app/engine3d.py`, `backend/app/refine.py`, `backend/app/rooms.py`, `products/**`, `backend/tests/test_preset_2_1.py` and tests under `backend/tests/products/` you add.
