# Plot2d handoff

## Retry 1 changes

- Bound optimize and products responses and errors to the room and layout generation at request start. Changing rooms discards stale results; changing layouts also discards stale products. The products panel clears when the room changes.
- Rendered treatment patches as translucent filled polygons along their walls, set the SVG room padding to exactly 0.5 ft per side, and displayed room warnings alongside metrics warnings.
- Applied object `rotation_y` as degrees with the SVG sign reversed for the x-right, z-down view. Added a pure helper and Node assertions for positive and negative angles.

## Retry 1 verification

- `python -m pytest backend -q --basetemp .plot2d-run/pytest` passed: 145 passed, 7 skipped, 8 deselected, 1 xfailed. The first attempt used `.test-tmp/run`, which another test removed during the suite, causing setup errors; the separate path resolved that.
- `plot.js` passed the Node module syntax check, and `git diff --check` found no whitespace errors.
- I could not verify the visual render, mouse or touch drag, keyboard interaction, or request races in a browser. The prior attempt found no browser surface available; this retry used code inspection and automated tests only.
- The untracked `.plot2d-run/` test output remains. A cleanup command was rejected by the environment policy; the orchestrator should remove it before committing.

## Done

- Added the static top-down SVG page at `/app/plot2d/` with demo, rectangle, open-by-id, optimize/reset, score, and product controls.
- Drew the grid, walls, openings, furniture, listener, speakers and aims, screen, and treatment patches from the documented room and layout shapes. Added speaker dragging, keyboard nudges, clamping, tooltips, throttled scoring, and visible API errors.
- Added DOM-free feet-and-inches and geometry helpers plus static-route and Node format tests.
- On first load, the page posts the demo room and optimizes it, so the stub-backed page can display six speakers and a screen immediately.

## Verification and unfinished

- `python -m pytest backend -q --basetemp .test-tmp/run` passed with workspace-local `TMP` and `TEMP`: 145 passed, 7 skipped, 8 deselected, 1 xfailed. The temporary directory was removed afterward. The normal command initially encountered a permission error in the machine's default pytest temp directory.
- `plot.js` passed `node --input-type=module --check`. TestClient verified the page and assets are served and `/health` stays JSON. The Node format test passed as part of pytest.
- I could not verify a visual render, mouse/touch drag, or keyboard interaction in a browser: the computer-use browser inventory was empty. A local `python -m uvicorn` server started, but no browser was available to open it. The server was stopped.
- The stub engine always returns score 0.5, so moving a speaker sends and displays a fresh scoring response, but its numeric score does not change until the real engine is used.

## Decisions

- Kept score requests serialized and limited to one send per 100 ms; pending movement sends the latest full layout after an in-flight response.
- Kept a missing `/rooms/{id}/layout` (404) as an ordinary room-without-layout case when opening a room.

## Design questions

- Treatment patch plan-view depth: used a 0.3 ft rectangle centered on the wall; alternatives include a thinner strip or a surface-specific depth. [resolved: per-surface plan-view depth; task plot2d-patch-depth]
- Colors: used dark teal with mint speakers, amber listener/warnings, and magenta screen; alternatives include a lighter theme or role-specific speaker colors. [resolved: keep the current colours]
- Drag feel: used direct pointer tracking with immediate clamping to the room bounds; alternatives include an offset-preserving grab or snapping to the 1 ft grid. [resolved: keep direct pointer tracking]
- Tooltip wording: used element name plus x, z, and height in feet and inches; alternatives include shorter x/z-only text or named coordinate axes. [resolved: keep the current tooltip wording]
