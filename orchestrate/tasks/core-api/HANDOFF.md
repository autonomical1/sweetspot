# Core API handoff

## Done
- Implemented unit conversion and feet/inches formatting, in-memory pairing sessions, rectangle and demo room creation, room persistence endpoints, photo targets, listener updates, and the optimize/score/layout/products flow.
- Added optional engine and products adapters with deterministic offline stubs and runtime failure fallback warnings.
- Added the 18 x 13 ft demo fixture and tests for units, sessions, rooms, persistence, concurrency, layouts, OpenAPI paths, and adapter fallback.
- Verified `python -m pytest backend -q --basetemp .pytest_core_api`: 12 passed. The explicit pytest temp path was needed because the Windows user temp directory was inaccessible in this sandbox; the generated temp directory was removed afterward.
- Retry: added shared listener validation, full polygon wall area, corrected demo geometry and absorption, engine result validation, and import handling that exposes errors from present optional modules.
- Added regression tests for each retry item. `python -m pytest backend -q --basetemp .pytest_core_api`: 17 passed. Removed the generated temp directory afterward.

## Unfinished
- Scan conversion returns 501 until the separately assigned `roomplan.py` task supplies `convert_dto`.
- Photos and materials routes remain with their separate task. `main.py` includes the materials router when available.
- The demo fixture uses the specified provisional hardwood and glass absorption values. Align them with `materials.ABSORPTION` during integration.

## Decisions
- `POST /rooms` preserves the `room_id` of a complete Room JSON document; rect, demo, and scan paths generate a new id.
- New rectangles use the brief's listener default (`width / 2`, `3.6`, `0.7 * length`). The shared `room_rect.json` listener x coordinate is 7.5 in a 12 ft wide room, so it differs from that default.
- Sessions are a module-level in-memory map as specified. A process restart clears them; creating another FastAPI app in the same process does not.
- Listener vectors are normalized; malformed/nonfinite/zero vectors get 422 and out of bounds positions get 400. Full Room uploads follow the same rule.
- Wall area uses the entire 3D polygon. The demo sofa sits against the back wall, the TV is flush with the front wall, and the listener is within the sofa footprint.
- Demo hardwood and glass use the six provisional absorption values specified in RETRY 1.
- Invalid real engine results fall back to the stub with an explicit warning. Import errors from present optional modules propagate.

## Design questions
- none
