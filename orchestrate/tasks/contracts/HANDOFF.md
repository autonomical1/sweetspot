## Completed

- Added reusable validators in `backend/tests/contract/checks.py` for rooms, layouts/metrics, products, and material classifications.
- Added offline parametrized engine/products/materials contract tests and validator mutation tests.
- Added the hand-authored SerpApi shopping fixture and the Gemini response corpus plus expected outcomes.
- Added stdlib-only `tools/validate_dto.py` with importable `validate()` and multi-file CLI summaries.
- Added DTO mutation/CLI tests and documented the fixture/test behavior in code.

## Verification

- `python -m pytest backend/tests/contract -q`: 32 passed, 19 skipped.
- `python tools/validate_dto.py phoneapp_context/sample_payloads/post_rooms_request.example.json`: 0 errors, 0 warnings, exit 0.
- `python -m pytest backend -q`: contract tests and existing non-temp tests reached 40 passed, 19 skipped; 11 existing backend tests errored during pytest `tmp_path` setup because the sandbox denied scanning `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm`. No contract assertion failed.

## Unfinished

- Real `speakerplacer`, `products`, and `backend.app.materials` implementations were not present, so their tests are skipped as designed. The real products cases are additionally opt-in for `-m live`/`SERPAPI_KEY`.

## Design questions

- none

## Notes for orchestrator

- No stubs, API contracts, or files outside `OWNS.txt` were edited.
- The sample layout contains surface UUIDs from a scanned room, so its golden metrics check intentionally validates shape without pairing it to `fixtures/room_rect.json` surface ids.
