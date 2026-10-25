# web-drag handoff

## Completed

- Continued the existing uncommitted work. Added 2D SVG pointer dragging for every speaker role, clamping in feet (including polygon outlines), local position updates, final rescore on drop, a serialized latest-wins score queue, and 3D plane intersection and scene-to-feet coordinate helpers.
- Added the 2D | 3D top-bar control, V shortcut, URL view sync, a cached WebGL availability check, and the 2D fallback.
- Added staged-layout status polling while the tab is visible, refined-layout adoption with selection preserved, and a choice between an in-progress user edit and the refined result. Concurrent polls are suppressed and stale score replies are discarded. Arrow keys nudge the listener through the PATCH endpoint and rescore.
- Added interaction and store tests. `cd webapp && npm test` passes (47 tests), `npm run typecheck` passes, and `git diff --check` is clean.

## Unfinished

- **3D dragging is not wired.** `webapp/src/scene/BackendSceneCanvas.tsx` owns the Three.js camera, raycaster, speaker meshes, and OrbitControls, but is outside OWNS.txt. The owned `interaction/coordinates.ts` has the horizontal-plane ray math and scene-to-feet conversion ready. The scene owner must add pointerdown/move/up to raycast speaker groups, disable orbit during a drag, call `useAppStore.getState().moveSpeaker(role, sceneMetersToFeet(hit, room))`, then `finishDrag()` on release.
- Python check: `python -m pytest backend -q` finished with 228 passed, 1 failed, 73 errors. Most errors are `PermissionError` because pytest cannot read `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm` in this sandbox. The lone failure is `test_smoke_script_has_valid_bash_syntax`, outside this task. No backend files were edited.

## Contract discrepancy

- `docs/API.md` section 2a says optimization status is `idle|running|failed`; the current backend also returns `queued|done|superseded`. The client accepts those actual states, using `done` to fetch the refined layout. Please update the contract or backend after coordination.

## Design questions

- How should 3D dragging be connected across file ownership? I kept the existing Three.js scene and supplied reusable coordinate math; alternatives are to give this task ownership of `BackendSceneCanvas.tsx` or have its owner wire the controller there.
