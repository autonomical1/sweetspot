# ios-ar-frame handoff

## Changed
- `Models.swift`: added optional `RoomResponse.frame`, `RoomFrame`, and pure `worldTransform(for:)` (room-frame metres to scan-world metres). `checkRoomFrameVectors()` checks all five points and three directions from `frame_test_vectors.json` within `1e-4` in Debug builds.
- `SweetspotApp.swift`: `Flow.roomFrame` now follows the current room through fresh scan upload, saved-scan re-upload, and `GET /rooms/{id}` reopen. Demo, rectangle, and offline preview paths clear it. `ARLayoutScreen` passes it to the AR view.
- `ARLayoutView.swift`: shared-scan drawing uses the backend frame as `AnchorEntity(world:)` transform on initial display and every SwiftUI update, including a layout update after Recompute. Room-relative marker positions remain feet converted to metres. A missing frame shows `Room frame missing: AR placement may be wrong`; manual two-corner alignment remains on its existing path. Debug builds assert the vector check when opening shared-scan AR.

## Verification and unfinished work
- `python -m ruff check .`: passed.
- `python -m pytest -q`: 233 passed, 1 failed, 40 errors, 9 deselected. Errors arise from `PermissionError` on `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm`; the unrelated deploy-script test fails because Windows `bash.exe` (WSL launcher) returns access denied. No Python files changed.
- `swiftc` and `swift` are unavailable, so `swiftc -parse`, iOS SDK compilation, and device alignment could not be run.
- No new Swift API was introduced beyond the existing `AnchorEntity(world:)` initializer and standard `simd_float4x4`/`simd_quatf` operations. Xcode should still confirm the Swift type checking and RealityKit behavior.

## Manual device checks
1. Build in Xcode on a LiDAR iPhone in Debug; open a live RoomPlan scan, keep the app running, upload it, and compute a layout. Confirm no vector assertion fires.
2. Inspect the uploaded room response: `source` is `roomplan`, `frame` has three offset values, and its room id matches the current result.
3. Open AR and confirm the status reads `Aligned to scan`. Walk to a known wall or scanned corner and verify a speaker marker appears at its intended physical wall position, with the expected height and no mirrored side.
4. Return to results, Recompute, reopen AR, and confirm the same placement. Reopen the saved room through history and confirm its frame is read again from `GET /rooms/{id}`; if the live scan session was lost, use the existing manual alignment path.
5. Load a demo or manual rectangle room, tap north-west then north-east floor corners, and confirm its two-corner alignment still works. For a scanned response without `frame`, confirm the missing-frame warning is visible.

## Design questions
- none
