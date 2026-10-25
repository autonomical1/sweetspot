# ios-ar-frame: make the iPhone AR overlay use the backend's room-to-world frame

## Goal
For a scanned room the backend returns the layout in the ROOM frame (feet, walls axis-aligned, origin at the wall bounding box) and the room's `frame = {yaw_deg, offset}` (offset in feet) that maps room coordinates into the scan's ARKit world frame. The iOS app currently ignores `frame`: in the shared-scan AR mode it draws speakers and the screen at `position * 0.3048` with an identity transform, so speakers appear in the wrong place for any real scan. Fix that in the Swift app. There is no Xcode, no iOS SDK and no device in this sandbox, so write careful, compile-minded Swift and say clearly what you could not run.

## Read first
docs/API.md section 1a (the mapping, copied below), Sweetspot_iOS_App/README.md and 04_ar_overlay.md, Sweetspot_iOS_App/Sources/SweetspotPhoneApp/{Models.swift, ARLayoutView.swift, SweetspotApp.swift, BackendClient.swift}, phoneapp_context/sample_payloads/frame_test_vectors.json, backend/app/roomplan.py (how the backend defines the frame).

The mapping (section 1a), `t = radians(yaw_deg)`:
```
world_ft.x =  cos(t)*x + sin(t)*z + offset.x
world_ft.y =  y                   + offset.y
world_ft.z = -sin(t)*x + cos(t)*z + offset.z
world_m    =  world_ft * 0.3048
```
This is a right-handed rotation about +y by `t` (`simd_quatf(angle: t, axis: [0, 1, 0])`; +90 degrees maps +x to -z) followed by the offset. Directions (`aim`, `facing`) rotate only.

## Design decisions this brief encodes (do not change)
- The backend and its API are fixed; do not request contract changes. The app must read `frame` from the `POST /rooms` response (and from `GET /rooms/{id}` if the app re-fetches), keep it with the room id for the session, and apply it only when the AR view uses the shared scan session (`sharedScanFrame == true`). Demo and manual rectangle rooms have `frame: null`; they keep the existing two-corner manual alignment (the alignment world transform) and must not regress.
- Implement the math as one small pure function in Models.swift, e.g. `func worldTransform(for frame: RoomFrame) -> simd_float4x4` (rotation about +y by yaw, translation `offset * 0.3048` meters), plus `struct RoomFrame: Decodable { let yaw_deg: Double; let offset: [Double] }` and `frame: RoomFrame?` on `RoomResponse` (optional so older responses still decode). Pass that transform as the anchor transform (`AnchorEntity(world:)`) instead of `matrix_identity_float4x4`, keeping positions in room-frame feet * 0.3048 exactly as the existing draw code does.
- If `frame` is missing for a scanned room, show a visible status message ("Room frame missing: AR placement may be wrong") instead of silently drawing at identity.
- Add a debug-only self check (a function you can call from a `#if DEBUG` button or `assert`) that evaluates the function against the vectors in frame_test_vectors.json (embed the numbers in Swift; keep tolerances 1e-4). Also keep a pure-Python mirror out of scope: the backend task covers Python.
- No new third-party dependencies. Do not add new Swift files (the Xcode project file is not yours); keep all new code in the files you own.
- Do not change networking, pairing, photo or material flows, or the DTO export. Do not "clean up" unrelated code.

## Deliverables
1. Models.swift: `RoomFrame`, `RoomResponse.frame`, `worldTransform(for:)`, the vectors self-check.
2. SweetspotApp.swift: keep the room frame from the upload response with the room state (also when the saved scan is re-uploaded), and pass it to the AR view.
3. ARLayoutView.swift: apply the transform in shared-scan mode (including when the layout is redrawn after Recompute), keep the two-corner mode unchanged, show the missing-frame message.
4. HANDOFF.md: exactly what changed (file and function names), what you could NOT verify (no compiler or device) and the manual device checks to run, in order, to confirm a speaker marker lands on its real wall position; list any Swift API you were unsure about.
5. If `swiftc` or `swift` exists in this sandbox, run `swiftc -parse` on the changed files and report the result; if not, say so.

## Done when
The Swift code reads cleanly, is internally consistent (every symbol used is defined, optional handling is correct), `python -m ruff check . && python -m pytest -q` still passes (you change no Python), and no edits outside OWNS.txt.

## Out of scope
Python/backend code, the Xcode project file, adding files, new screens, a products screen, the "tap where you sit" listener feature, image/photo behaviour. Put unsettled choices under `## Design questions` in HANDOFF.md.
