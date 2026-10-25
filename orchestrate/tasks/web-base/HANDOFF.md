# web-base handoff

## Completed

- Retry 1: corrected `ProductAlternative` to match the documented alternative listing fields without requiring product role, currency, or nested alternatives. Added a response-shape test and type-checked the test files.
- Retry 1: a different room or demo load now clears the prior room, layout, metrics, and selection before requesting data; failed loads leave them cleared. The viewer effect no longer makes a duplicate request when that clear changes store state. Added tests for direct navigation and demo-load failures.
- Kept the raw Three.js scene and bundled GLB assets. Split the viewer UI into top bar, sidebar, viewport, start/viewer/pair screens, and 2D placeholder; extracted room shell, projection lines, and seat POV helpers.
- Configured Vite for `/app/`, output to `web/` without clearing `web/plot2d/`, and proxying backend routes. Added a local `.gitignore` for build and dependency artifacts. Used Vite's runner config loader because the default loader fails in this restricted Windows workspace.
- Added typed relative API calls for sessions, rooms, optimize, score, layout, and products, with FastAPI and wrapped-error handling plus `Retry-After` parsing.
- Added the Zustand room/layout/view/session store, demo-room action, shared `loadRoom(roomId)` action, loading/error states, and raw backend room dimensions in the sidebar. The existing example scene remains visible until the adapter task renders backend layouts.
- Added feet/meters and feet/inches helpers, unit and client tests, and updated the web app README.

## Verification

- `npm test`: 12 passed. `npm run build`: passed, including `tsc -b`. Focused TypeScript check of both client and store test files passed. Build output was ignored; `web/plot2d/` was untouched.
- `python -m ruff check .`: passed.
- Backend full run with `--basetemp webapp/.pytest-tmp`: 281 passed, 12 deselected, 3 failed. Two 5000-budget product cases took 2.01 s and 2.14 s against a 2 s limit. The smoke-script syntax test fails because Windows `bash.exe` invokes WSL and returns E_ACCESSDENIED in this sandbox. These are outside this task's owned files.

## Unfinished

- Backend room/layout to meter-based scene adapter, QR pairing implementation, and 2D view are assigned to later tasks.

## Design questions

- none
