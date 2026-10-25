# web-base handoff

## Completed

- Kept the raw Three.js scene and bundled GLB assets. Split the viewer UI into top bar, sidebar, viewport, start/viewer/pair screens, and 2D placeholder; extracted room shell, projection lines, and seat POV helpers.
- Configured Vite for `/app/`, output to `web/` without clearing `web/plot2d/`, and proxying backend routes. Added a local `.gitignore` for build and dependency artifacts. Used Vite's runner config loader because the default loader fails in this restricted Windows workspace.
- Added typed relative API calls for sessions, rooms, optimize, score, layout, and products, with FastAPI and wrapped-error handling plus `Retry-After` parsing.
- Added the Zustand room/layout/view/session store, demo-room action, shared `loadRoom(roomId)` action, loading/error states, and raw backend room dimensions in the sidebar. The existing example scene remains visible until the adapter task renders backend layouts.
- Added feet/meters and feet/inches helpers, unit and client tests, and updated the web app README.

## Verification

- `npm test`: 9 passed.
- `npm run build` and `npm run typecheck`: passed. Build output was ignored; `web/plot2d/` was untouched.
- `python -m ruff check .`: passed.
- Backend full run with the default pytest temp folder could not use `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm` (permission denied). With `--basetemp webapp/.pytest-tmp`, excluding the WSL-only smoke-script syntax check: 267 passed, 1 timing-sensitive products test failed at 2.18 s against a 2 s limit. That exact test passed on immediate isolated rerun (3.09 s total suite time). The smoke-script test fails because Windows `bash.exe` invokes WSL and returns E_ACCESSDENIED in this sandbox. These are outside this task's owned files.

## Unfinished

- Backend room/layout to meter-based scene adapter, QR pairing implementation, and 2D view are assigned to later tasks.

## Design questions

- none
