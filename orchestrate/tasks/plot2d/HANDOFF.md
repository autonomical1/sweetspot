# Plot2d handoff

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

- Colors: used dark teal with mint speakers, amber listener/warnings, and magenta screen; alternatives include a lighter theme or role-specific speaker colors.
- Drag feel: used direct pointer tracking with immediate clamping to the room bounds; alternatives include an offset-preserving grab or snapping to the 1 ft grid.
- Tooltip wording: used element name plus x, z, and height in feet and inches; alternatives include shorter x/z-only text or named coordinate axes.
