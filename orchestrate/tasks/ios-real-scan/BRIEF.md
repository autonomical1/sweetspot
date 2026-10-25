# ios-real-scan: prove the backend handles real iPhone scans, including a sparse partial one (and that AR will land in the right place)

## Goal
The iOS app now scans a room with RoomPlan and posts it to `POST /rooms` (merged from branch ios-phone_context into Sweetspot_iOS_App/). The first real upload reached the live server and was converted, but it was only an INCOMPLETE test scan made to see whether the upload worked (the user has not captured a full room yet), and we have otherwise tested the converter only on a synthetic sample. Make the backend provably correct on the real scan: valid room, sensible listener, speaker layout inside the room, and layout coordinates that map back into the scan's ARKit world frame exactly as docs/API.md section 1a says (the phone draws speakers using that mapping).

## Read first
docs/API.md sections 1 and 1a (room frame vs scan world frame; the world mapping formula), backend/app/roomplan.py (the converter; you own it), backend/tests/test_roomplan.py, phoneapp_context/sample_payloads/frame_test_vectors.json, Sweetspot_iOS_App/02_backend_integration.md and 01_roomplan_capture.md, fixtures/partial_scan_upload_test.json (a real but PARTIAL `captured_room` DTO from the user's phone, meters; 4 wall segments, 1 door, 1 floor, no objects; it does not describe a complete room, so a strange room shape or listener is not by itself a converter bug).

## Facts already measured on this partial scan (server result)
Converted room: width 8.98 ft, length 26.14 ft, height 9.15 ft; `frame.yaw_deg` 169.66, offset [-1.85, -3.73, 15.57] ft; warnings `no sofa`, `no television`, `no sofa detected; listener at room centre`; but the listener came out at [5.64, 3.6, 22.44] with facing [0.31, -0.95], which is NOT the room centre (centre would be about [4.49, 3.6, 13.07]) and sits near the far end of a long narrow room. The scan is narrow (floor about 2.5 m x 8 m) with several wall segments, one of which is a 0.4 m stub, and the room is not closed. Because the scan is incomplete, judge the listener position by the documented fallback rule (not by what the room "should" look like): if the converter does not follow the rule below on this input, fix it; if it does, leave it and just document it.

## Design decisions this brief encodes (do not change)
- API shapes, units (feet in the room frame, meters only in the scan DTO) and the section 1a formula are fixed. Do not change the contract; if you find it wrong, say so in HANDOFF.md.
- The room frame stays: walls axis-aligned, wall bounding box from the origin, floor at y=0, listener facing roughly north. Fix bugs in the converter, do not redesign it.
- With no sofa, the listener fallback must be what the API says and what the warning says: the room centre (centre of the floor polygon projected into the room frame when a floor surface exists, otherwise the centre of the wall bounding box), at 3.6 ft ear height, clamped inside the room, facing the longest wall or the TV when there is one. Update the warning text only if it would otherwise be false.
- Do not hard-code anything for this one scan; the fix must work for any scan. Partial or sparse scans must never crash the converter or produce an out-of-room listener or layout; a warning is welcome when the scan looks incomplete (for example fewer than 4 wall segments forming a closed loop, or no objects).

## Deliverables
1. Investigate why the listener is off-centre on fixtures/partial_scan_upload_test.json and fix it in backend/app/roomplan.py (own it). Also check the other surface/door/stub handling for the same kind of mistake (e.g. wall stubs inflating the bounding box or the rotation choice picking a wrong yaw); fix real bugs, list suspicious-but-fine behaviour in HANDOFF.md.
2. New tests in backend/tests/test_roomplan_real_scan.py (the only test file you add; do not edit other tests unless an assertion encodes the bug, then say so):
   - converting the fixture through `POST /rooms` (FastAPI TestClient, DATA_DIR in tmp) gives a valid Room (`schemas`), `source == "roomplan"`, positive dimensions, `frame` present, listener inside the room box and within 1.5 ft of the room centre when there are no objects, `facing` unit length;
   - frame round trip: for the fixture's `frame`, mapping the listener and every wall polygon vertex of the converted room back to world metres (section 1a) lands within 0.05 m of the corresponding scan-space point (wall `polygon_corners` / transform-derived corners as the converter uses them);
   - `POST /rooms/{id}/optimize` returns six speakers inside the room box (0..width, 0..height, 0..length) and, mapped to world metres with the section 1a formula, every speaker lies inside the axis-aligned bounds of the scan's walls and floor in world space (tolerance 0.3 m) at ear-to-ceiling heights;
   - the same checks on fixtures/roomplan_sample.json so the old sample stays covered;
   - `frame_test_vectors.json` vectors reproduced by a small helper in the test (the backend side of "both must reproduce").
3. If the optimizer places speakers outside the scan in world space for this room, report it precisely in HANDOFF.md with numbers (do not edit backend/app/engine_speakerplacer.py; it is not yours).
4. HANDOFF.md: what was wrong, what you changed, before/after listener on the fixture, and any contract doubt.

## Done when
`python -m ruff check . && python -m pytest -q` passes; no edits outside OWNS.txt.

## Out of scope
The Swift app, docs, deploy, products, materials, the engine adapter. Put unsettled choices under `## Design questions` in HANDOFF.md.
