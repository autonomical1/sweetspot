## Completed

- Added horizontal angle and rotated 3D object exclusion checks to the engine contract for fixture and generated rooms.
- Tightened classification to require one result per expected surface, and reflection numbers to reject booleans, NaN, and infinity.
- Marked the real products fixture parameter `live` regardless of `SERPAPI_KEY`; covered both screen variants at all four budgets.
- Updated the mock materials test to send four actual JPEG photos when the materials module is available.
- Made DTO validation and CLI reporting tolerate malformed JSON shapes and bad paths without a traceback; added table-driven regression cases and individual warning/error cases.

## Verification

- `python -m pytest backend -q --basetemp backend/tests/contract/.pytest_tmp`: 101 passed, 15 skipped, 8 live deselected, 1 xfailed. The temporary directory was removed afterward.
- `python tools/validate_dto.py phoneapp_context/sample_payloads/post_rooms_request.example.json`: 0 errors, 0 warnings, exit 0.
- Plain `python -m pytest backend -q` still cannot set up `tmp_path` in this sandbox because pytest cannot scan `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm`. The workspace `--basetemp` run verifies those tests.

## Unfinished

- Real `speakerplacer`, `products`, and `backend.app.materials` are absent on this branch. Their tests skip with explicit reasons. The 8 real products cases are deselected by default because they carry `live`; under `-m live` they additionally require `SERPAPI_KEY`.

## Decisions

- Stub xfail: 10 x 10 ft room with listener at `[0.3, 3.6, 5]`. The stub clamps `L` to x=1, giving a 15.08 degree front angle and placing it on the listener's right side. The same geometry check remains live for the real engine.

## Design questions

- none
