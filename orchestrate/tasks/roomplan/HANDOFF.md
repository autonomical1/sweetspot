# roomplan handoff

## Completed
- Added `backend/app/roomplan.py::convert_dto` with shared DTO validation loaded through `importlib.util.spec_from_file_location`, metre-to-foot conversion, dominant-wall normalization, north-oriented listener selection, and reversible room/world frames.
- Preserved scan IDs, object categories and orientation, request metadata, validator warnings, and the verbatim DTO. Created wall/door/window/opening polygons plus synthetic floor/ceiling with copied material absorption tables.
- Added `frame_to_world`, `world_to_room`, and `dir_to_world` (supports both 3D directions and two-component x-z facing vectors); helpers accept `Frame` models or dictionaries.
- Added the synthetic example's `captured_room` as `fixtures/roomplan_sample.json`.
- Added 48 offline tests covering every shared frame vector, six scan rotations crossed with three offsets, geometry/object round trips, normalized-room invariance, listener overrides/fallbacks, floor level, malformed DTOs, and HTTP upload/session/photo-target/optimization integration.
- Only the three owned deliverables and this handoff were changed. No commits, network requests, or dependency installations.

## Validation
- `python -m pytest backend/tests/test_roomplan.py -q --basetemp=.pytest_cache/roomplan-temp`: **48 passed**.
- `python -m pytest backend -q --basetemp=.pytest_cache/roomplan-temp`: **192 passed, 1 failed, 7 skipped, 8 deselected, 1 xfailed**. The sole failure is the obsolete expectation described below.
- The unmodified command `python -m pytest backend -q` initially hit 21 setup errors because Windows denied access to `C:/Users/neelm/AppData/Local/Temp/pytest-of-neelm`. Using an explicit workspace-local pytest temporary directory resolved that environment problem.
- `git diff --check` passed. Starlette emits an existing AnyIO deprecation warning.

## Unfinished / orchestrator action
- Update `backend/tests/test_rooms.py:57` in `test_full_room_and_expiry`: it still expects **501** for `{"captured_room": {"format": "sweetspot.roomplan.v1"}}`, assuming no converter exists. With the required converter installed, this malformed DTO correctly returns **422** with the shared validator's missing-key messages. This file is outside OWNS.txt, so it was not edited. The full suite cannot be green until this obsolete assertion is updated. No behavior workaround or test suppression was added.
- The fixture remains synthetic; replace it with an actual iOS export when available. Real-device AR alignment was not tested.
- `docs/TESTING.md` section 3.6 retains earlier listener rules (sofa-transform facing / longest wall) and mentions parent-wall output and huge-value warnings. The task brief instead requires seat-to-TV/centroid facing, farthest midpoint fallback, and rejection above 100 m; those explicit rules were implemented. `Surface` has no parent-wall field, so no field was invented (the raw DTO retains parent IDs).

## Decisions
- Followed API section 1a's right-handed frame math exactly; used the brief's width-weighted fourfold wall-angle mean without snapping individual walls, preserving world-coordinate round trips.
- Reject degenerate positive-volume room boxes and surfaces without a horizontal width direction with `ValueError` rather than divide by zero or emit invalid geometry.
- For equal farthest-wall distances, preserve DTO order; distance comparisons round to ten decimal places to prevent floating-point rotation noise from changing symmetric-room ties.

## Design questions
- What defines the largest sofa when several are detected? Used floor footprint (`width * depth`) with DTO-order ties; alternatives are bounding-box volume or width alone. [resolved: largest by floor footprint, as built]
- Which television should determine facing when several exist? Used the first in DTO order; alternatives include largest screen or nearest television. [resolved: largest TV by screen size; task roomplan-tv]
- What facing should be used when the inferred target coincides with the seat (for example, a sofa at the room centre without a TV)? Used the farthest wall midpoint and added a warning; alternatives are sofa orientation or requiring a listener override. [resolved: keep farthest wall midpoint plus a warning]
- Should the listener be offset from the sofa box centre? Used the specified sofa-centre x-z position and clamped 3.6 ft ear height; alternatives are a seat/front-edge offset or an explicit user-selected seat. [resolved: no offset: sofa centre, 3.6 ft ears]
- Should TV-less facing use another policy? Implemented the brief's sofa-to-room-centre direction, or the farthest wall midpoint without a sofa; alternatives are sofa orientation or a user-selected front wall. [resolved: keep farthest wall midpoint plus a warning]
- How should curved walls be represented later? Treated them as straight dimension/transform-derived spans and ignored polygon corners as instructed; alternatives are documented polygon geometry or explicit unsupported-scan rejection. [resolved: true polygon geometry; task polygon-walls (blocked, needs spec)]
