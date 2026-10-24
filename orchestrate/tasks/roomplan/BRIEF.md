# roomplan: iOS scan DTO (world meters) -> normalized Room (room-frame feet) + frame

## Goal
Implement `backend/app/roomplan.py::convert_dto` so `POST /rooms` with a `captured_room` turns a raw RoomPlan scan into a standard Room: walls axis-aligned, wall bounding box from the origin, floor at y=0, feet, listener facing roughly north, plus a `frame` that maps the room back to the scan's ARKit world so AR markers land on the real walls. The hook already exists in `backend/app/rooms.py` (it imports `convert_dto` when this module exists; `ValueError` becomes 422).

## Read first
docs/API.md sections 1, **1a (frame math, authoritative)**, 6; docs/TESTING.md section 3.6; phoneapp_context/01_roomplan_capture.md (DTO format) and 04_ar_overlay.md (Step 0, what the phone does with `frame`); phoneapp_context/sample_payloads/post_rooms_request.example.json (synthetic sample) and frame_test_vectors.json; backend/app/schemas.py (`Room`, `Frame`, `warnings`); backend/app/rooms.py (`POST /rooms`, `validate_listener`, photo-targets); backend/app/materials.py (`ABSORPTION`); tools/validate_dto.py (`validate(data) -> (errors, warnings)`). Do NOT edit any of them.

## Design decisions this brief encodes (do not change)
- The DTO is raw **world meters** (16-float column-major transforms, translation = elements 12-14; local x = width direction, local y = up, `dimensions` = [w, h, d]). Output is **room-frame feet** (x 3.28084).
- Frame convention, exactly as API.md 1a: `world_ft = R_y(yaw) * room_ft + offset_ft`, with `R_y(t)`: `x' = cos t * x + sin t * z`, `y' = y`, `z' = -sin t * x + cos t * z` (right-handed, +90 deg maps +x to -z). Inverse: `room = R_y(-t) * (world - offset)`. Object `rotation_y` uses the same convention, in degrees.
- Conversion only in this module; the phone never normalizes. Rect/demo rooms keep `frame: null`.
- Ids: DTO UUID strings for walls/doors/windows/openings/objects; synthetic `floor` and `ceiling`.
- Validation reuses `tools/validate_dto.py::validate` (load it with `importlib.util.spec_from_file_location` from the repo root); its errors become `ValueError` (-> 422) with the messages joined; its warnings go into `room.warnings`.

## Algorithm (implement exactly; tests decide correctness)
1. Validate (above). Reject (ValueError) if any translation component exceeds 100 m in absolute value or there are fewer than 3 walls.
2. Wall/opening geometry in world meters: centre `t` = elements 12-14; width direction `u` = normalized horizontal part of column 0 `(m[0], m[2])`; `w, h = dimensions[0], dimensions[1]`; horizontal endpoints `t +- u*w/2`; bottom `t.y - h/2`, top `t.y + h/2`; polygon order: bottom-start, bottom-end, top-end, top-start.
3. Dominant wall angle: `phi_i = atan2(u_z, u_x)`; `m = atan2(sum w_i sin 4phi_i, sum w_i cos 4phi_i) / 4`. Rotating by `R_y(-yaw)` adds `yaw` to every `atan2(z, x)` angle, so `yaw0 = -m` makes walls axis-aligned.
4. Listener in world: if the request has `listener` (scan world meters: `position` [x,y,z], `facing` [fx,fz]) use it. Else the seat is the largest `sofa` object's centre; facing = horizontal direction from the seat to the `television` centre if a TV exists, else the sofa's facing is unknown so use the direction from the seat to the room centre (wall endpoint centroid). No sofa: seat = wall endpoint centroid, facing toward the TV if any, else toward the farthest wall midpoint; add warning `"no sofa detected; listener at room centre"`.
5. Pick `yaw = yaw0 + k*90 deg` (k in 0..3, result normalized to (-180, 180]) so the listener's facing rotated into the room frame (`R_y(-yaw)`) is closest to north `(0, -1)`.
6. Rotate every world point by `R_y(-yaw)`. `b` = (min x over wall endpoints, floor level, min z over wall endpoints) in the rotated coordinates, where floor level = min of wall bottoms and any `floor` surface centre y. Room metres = rotated - b; room feet = x 3.28084. `frame.offset` (feet) = `R_y(yaw) * b * 3.28084`; `frame.yaw_deg = yaw`.
7. `dimensions`: width = x extent, length = z extent of wall endpoints; height = max wall top (all feet, after normalization).
8. Surfaces: each wall/door/window/opening with its 4-corner polygon in room feet; `kind` from category; material `glass` for windows, `drywall` otherwise; `absorption` copied from `materials.ABSORPTION[material]`. Synthetic `floor` (y=0) and `ceiling` (y=height) as the bounding rectangle, material drywall. DTO floor surfaces only contribute to the floor level.
9. Objects: `center` = rotated, shifted, feet; `size` = dimensions x 3.28084; `rotation_y` (degrees) = world yaw of column 0 (`atan2(-m[2], m[0])`) minus `yaw`, normalized to (-180, 180]; `category` = DTO category string.
10. Listener: position = seat mapped to the room frame with y forced to 3.6 ft (clamped into the room box), facing = rotated facing normalized. Must pass `rooms.validate_listener`.
11. Room: `source="roomplan"`, `room_id`/`session_id`/`budget` from args, `captured_room` = the DTO verbatim, `frame`, `warnings` (validator warnings + converter warnings).
12. Also export helpers `frame_to_world(point_ft, frame) -> list[float]`, `dir_to_world(direction, frame)`, `world_to_room(point_ft, frame)` (feet in and out).

## Deliverables
1. `backend/app/roomplan.py` with `convert_dto(captured_room: dict, *, room_id: str, session_id: str | None, budget: float | None, listener: dict | None) -> Room` and the helpers.
2. `fixtures/roomplan_sample.json`: the `captured_room` object from `phoneapp_context/sample_payloads/post_rooms_request.example.json` (to be replaced by a real scan from the iOS developer; tests must not depend on its exact numbers beyond what the synthetic tests also check).
3. `backend/tests/test_roomplan.py`, no network:
   - Helpers reproduce every case of `frame_test_vectors.json` (points and directions) to 1e-4; `world_to_room` inverts `frame_to_world`.
   - Synthetic generator in the test: an axis-aligned 18 x 13 x 9 ft room (4 walls, a door, a window, sofa near the back wall, TV on the front wall) expressed in metres, then rotated by yaw in {0, 17, 45, 90, -120, 179} deg and shifted by several offsets (including negative and > 10 m). For each: converted dimensions match 18 x 13 x 9 (or 13 x 18) within 0.01 ft; every wall direction within 0.5 deg of an axis; bounding box starts at 0; floor y = 0; listener faces within 45 deg of north and sits on the sofa; `frame_to_world` of every wall corner and object centre reproduces the DTO world position (x 3.28084) within 0.01 ft; results for all yaws/offsets are the same normalized room within 0.01 ft.
   - Listener override in world metres maps correctly; no sofa -> centre + warning; no TV -> deterministic facing.
   - Errors -> `ValueError`: wrong `format`, 2 walls, translation 300 (cm), NaN, 15-float transform.
   - Endpoint (TestClient on `create_app()`): `POST /rooms` with the sample request -> 200, `source == "roomplan"`, `frame` present, ids preserved; session linking works; `GET /rooms/{id}/photo-targets` returns the 4 walls + floor + ceiling; `POST /rooms/{id}/optimize` (stub engine) returns six speakers inside the box; malformed DTO -> 422 with the validator message.

## Done when
`python -m pytest backend -q` passes; `POST /rooms` with the sample returns a normalized room whose frame round-trips; no edits outside OWNS.txt.

## Out of scope
Changing schemas/rooms/materials/validator, non-rectangular engine support, polygonCorners (ignore them: their axes are undocumented), curved walls (treat as straight), multi-room scans. List unsettled choices (seat offset from sofa centre, TV-less facing rule, curved-wall handling) under `## Design questions` in HANDOFF.md.
