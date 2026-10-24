# 04: AR overlay

Goal: after the backend computes a layout, the user walks around the room with the phone and sees markers where each speaker (and the screen, and treatment patches) should go. This is the riskiest and most demo-worthy feature; **time-box the alignment test to about 1 hour**, and build everything else first.

## The core problem: one shared world frame
Layout coordinates (meters, y-up) are in the same frame as the RoomPlan scan **only if** the AR session that shows the markers is the same session (or relocalized into it). Three ways, best first:

### A. Reuse the scan's ARSession (preferred, zero alignment)
**[Apple docs]** `RoomCaptureView` has `init(frame:arSession:)`, `RoomCaptureSession.arSession` exposes the session in use ("You may use this object to display your own AR experience"), and `stop(pauseARSession: Bool)` exists.
Plan:
1. Create one `ARView` (RealityKit) at app start, or an `ARSession` you hold, and pass its session to `RoomCaptureView(frame:arSession:)`.
2. Run the scan. When finishing, call `captureSession.stop(pauseARSession: false)`.
3. Show the `ARView` and add anchors at the layout positions: `AnchorEntity(world: SIMD3<Float>(x, y, z))` with a marker model (sphere/box plus text label by role).
4. **VERIFY (15-minute test):** after `stop(pauseARSession: false)`, does `arView.session` keep tracking, and does a marker placed at a known scanned point (e.g. a wall corner position from the DTO) appear on that corner? Note that AR session is not interrupted by switching to the photo step; if tracking was lost, option B or C.

Important: do not tear down or re-create the session between scan and AR. Keep the whole flow in one app run (no relaunch). Interruptions (phone call, backgrounding) can reset the world origin.

### B. Save and restore an ARWorldMap
`ARSession.getCurrentWorldMap` then `ARWorldTrackingConfiguration.initialWorldMap` to relocalize in a later run. **VERIFY** it works with RoomPlan's session/configuration. Only use if A fails; treat as stretch.

### C. Manual two-point alignment (fallback, also required for the demo room)
When the AR session is not the scan session (relaunch, demo room, rectangular room), let the user align:
1. The room has known reference corners from the backend, e.g. for a rectangle `(0,0,0)` NW floor corner and `(width,0,0)` NE floor corner.
2. App asks: "Tap the floor at the north-west corner", then "Tap the north-east corner" (use `ARView.raycast` against `.estimatedPlane`/existing plane, y fixed to floor).
3. From the two tapped world points `p1, p2` and the two known room points `q1, q2` compute yaw about y and translation:
```swift
func alignment(room q1: SIMD3<Float>, _ q2: SIMD3<Float>, world p1: SIMD3<Float>, _ p2: SIMD3<Float>) -> simd_float4x4 {
    let dq = SIMD2(q2.x - q1.x, q2.z - q1.z), dp = SIMD2(p2.x - p1.x, p2.z - p1.z)
    let yaw = atan2(dp.y, dp.x) - atan2(dq.y, dq.x)          // rotation about +y mapping room -> world (sign: VERIFY)
    var m = simd_float4x4(simd_quatf(angle: -yaw, axis: [0, 1, 0]))   // y-up right-handed: rotation about y flips sign of the x-z angle
    m.columns.3 = SIMD4(p1 - (m * SIMD4(q1, 1)).xyz, 1)       // translation so q1 maps to p1
    return m
}
```
(The sign of the yaw is easy to get backwards in a y-up frame; test with the two corners and flip if markers mirror.) Apply the resulting transform to a parent `AnchorEntity` that holds all markers, so every marker keeps room coordinates.
4. If this also fails: show the AR overlay as a pre-recorded screen capture and say so honestly in the pitch.

## What to draw
- One marker per `layout.speakers[]`: role label (L, R, C, LFE, Ls, Rs), a small speaker-shaped box or sphere at `position`, and an arrow/line toward `aim`.
- Screen: a translucent plane at `screen.center` with `width x height`, oriented to the wall (facing into the room). If orientation data is missing, face it toward the listener position.
- Listener position: a small marker at the seat (ear height 1.1 m).
- Optional treatment patches (`metrics.treatment_patches`): colored translucent rectangles at `center` sized `[w, h]` on the named surface.
- Optional: a floating label with the best score and top warnings.
- Floor markers are easier to find in AR than wall markers; add a vertical line from the floor to each speaker position.

## Behavior
- Poll `GET /rooms/{room_id}/layout` every 2 s until non-404, or call `POST .../optimize` yourself via a button.
- A **"Recompute"** button re-fetches and redraws; if the user drags a speaker on the web page the app can pick up the new layout on pull.
- Show an "Alignment" indicator when running option C ("Aligned / Align again").
- Provide a **debug toggle** that draws the scanned walls as wireframe boxes using the DTO transforms/dimensions. If markers are wrong, this tells you whether alignment or coordinates are at fault.

## Failure modes
- Markers offset or rotated: world frames differ. Use option C, or check you did not re-create the session.
- Markers mirrored: axis/yaw sign error in the alignment math, or a coordinate flip somewhere. Remember: no axis flips anywhere.
- Markers drift: tracking lost; ask the user to look around slowly (use `ARCamera.TrackingState` to warn).
