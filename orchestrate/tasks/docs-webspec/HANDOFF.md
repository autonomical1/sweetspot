# Handoff

Updated the five owned web-app specification files for the staged engine, richer product results, and Gemini material-classification behavior.

- `webapp_context/01_product_and_flows.md`: documented immediate quick-layout display and refined-layout replacement; retained the six LIVE role colors and added a clearly labelled SUGGESTED palette for planned roles and theater accessories.
- `webapp_context/02_api_reference.md`: marked LIVE versus PLANNED optimize behavior, refinement status polling, layout stages and options, material status/classification responses, Gemini 429 handling, product alternatives and dimensions, and planned complete-theater product roles. The retry review correction now makes the current optimize call explicitly synchronous; the staged flow is PLANNED and fetches `GET /rooms/{id}/layout` after status polling because status has no layout.
- `webapp_context/03_data_and_coordinates.md`: separated LIVE 5.1 roles from planned 7.1/overhead/LFE2 roles, documented optional 3D speaker/layout fields, and specified speaker sizing precedence and real heights.
- `webapp_context/04_3d_view.md`: documented planned 3D roles, optional orientation/mount metadata, sizing precedence, real y-up heights, overhead placement, and planned layout metadata.
- `webapp_context/06_panels_products_materials.md`: documented product seller/spec/dimension/alternative fields, pair swap behavior, planned accessory roles, and live Gemini status/cache/join/rate-limit UI behavior.

Validation:

- `python -m ruff check .` passed.
- `python -m pytest -q` was rerun for this documentation-only retry: it reached 40 passing tests, then stalled without a summary and was interrupted. No code or tests were changed.
- `git diff --check` passed.

## Design questions

- none
