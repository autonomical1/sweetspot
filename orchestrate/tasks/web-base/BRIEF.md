# web-base: make the teammate's prototype the Sweetspot web app foundation

## Goal
Turn `frontend/` (the web teammate's standalone 3D room viewer, merged from branch `webapp`) into `webapp/`, the base the later web tasks build on: readable modules, `/app/` hosting, a typed API client, a store, feet/inches formatting, a demo-room path, and tests. No new product features beyond "load the demo room from the backend and show it in the existing 3D scene".

## Design decisions this brief encodes (user-approved 2026-10-25)
- Keep the teammate's raw three.js scene (`src/scene/*`) and GLB models. Do NOT rewrite it with React Three Fiber.
- Folder is `webapp/` (already renamed from `frontend/` by the orchestrator).
- The scene stays in **meters, Y-up** internally. All backend data is **feet** (docs/API.md). Conversion happens only in an adapter (a later task), but this task adds `src/lib/units.ts` (`FT_TO_M = 0.3048`, `ftToM`, `mToFt`) and `src/lib/format.ts` with `formatFtIn(ft)` returning e.g. `7' 6"` (port the logic and tests from `web/plot2d/format.js`).
- The teammate is tester + assets only. Do not expect upstream changes to `frontend/`.
- Built output goes to `web/` (served by the backend at `/app/`); deployment (Dockerfile) is NOT in this task.

## Deliverables
1. **Already done by the orchestrator (do not redo):** `frontend/` was renamed to `webapp/` on master, and `zustand`, `qrcode.react`, `jsdom`, `@testing-library/react` and `@testing-library/dom` are installed in `webapp/package.json` + lockfile; a `typecheck` script (`tsc -b`) exists; `orchestrate/config.json` setup runs `npm ci --prefix webapp` and the test command runs `npm test` + `npm run typecheck` in `webapp/`. Your worktree already has `webapp/node_modules`. Keep `public/models/*.glb`, `examples/`, `package-lock.json`.
2. `vite.config.ts`: `base: '/app/'`, `build.outDir` = `../web`, `build.emptyOutDir: false` (must NOT delete `web/plot2d/`), dev server proxy for `/rooms`, `/health`, `/products`, `/materials` to `http://127.0.0.1:8000`. Add a `.gitignore` for `node_modules` and `dist`. Do not commit build output into `web/`.
3. Split the minified one-line `src/App.tsx` and `src/scene/RoomCanvas.tsx` into readable, formatted modules (`components/Topbar`, `Sidebar`, `Viewport` or similar; `scene/` helpers for room shell, equipment, seat POV, projection lines). Behaviour must stay identical: orbit/top/seat views, walls and ceiling toggles, projection preview, load/export room JSON, selection callout. No dead code.
4. `src/api/client.ts`: typed fetch client with the types needed for `POST /rooms/demo`, `POST /rooms/{id}/optimize`, `POST /rooms/{id}/score`, `GET /rooms/{id}/layout`, `GET /rooms/{id}/products` exactly as in `docs/API.md` and `webapp_context/02_api_reference.md` (+ `sample_payloads/`). Include error handling with the `{error: {code, message}}` shape and honouring `Retry-After`. Relative URLs only (`/rooms/...`), no host names.
5. `src/store.ts`: a small store (zustand is allowed; add it to package.json if it is already in the lockfile cache, otherwise use `useSyncExternalStore`; no network installs are possible, so check `node_modules` first and report in HANDOFF.md) holding `room`, `layout`, `stage`, `selected`, `viewMode` ('3d' | '2d').
6. A **Use demo room** button in the top bar: calls the client (`/rooms/demo` then `/optimize`), stores the result, and shows a loading and an error state. Rendering the returned layout in the scene is the NEXT task (adapter); for now show the raw room size from the response in the sidebar and keep the example scene.
6b. **Screen routing for the later tasks** (so they never edit App.tsx): `App.tsx` switches by query string on `/app/` (`?pair` -> pairing, `?room=<id>&view=3d|2d` -> viewer, none -> start). Create `src/screens/Pair.tsx` as a placeholder component ("Pairing coming soon") and a **Pair your iPhone** button next to **Use demo room** that sets `?pair`; the `web-pairing` task replaces the placeholder with the QR screen. Leave an equivalent mount point for the 2D view (`views/View2D.tsx` placeholder) and the 2D | 3D segmented control in the top bar (3D only works for now).
6d. **Pairing contract (decided by the user 2026-10-25; implemented by the next task `web-pairing`, but shape your routing and store for it):** pairing is **QR only**, no typed 6-character code anywhere in the web UI. The laptop calls `POST /sessions` and draws the QR **in the browser** with `qrcode.react` from the `pair_url` field of the response, encoded verbatim (`https://<domain>/pair/<session_id>`, not the bare id; the iOS app takes the last path component and rejects text without `pair` in the path). No server-side QR/PNG endpoint. The page then polls `GET /sessions/{id}` every 1.5 s and, when ready, loads the room and switches to `?room=<id>&view=3d`. In this task: the **Pair your iPhone** button, the `?pair` route and a placeholder `Pair.tsx`, plus store fields `session` (`{id, pairUrl, expiresAt, status}`) and a `loadRoom(roomId)` action that the demo-room button and the pairing screen both use. Types for `POST /sessions` and `GET /sessions/{id}` belong in `src/api/client.ts` (per `sample_payloads/post_sessions.json`, `get_session_ready.json`).
6c. Dependencies: the orchestrator installs `zustand`, `qrcode.react`, `jsdom` and `@testing-library/react` into `webapp/package.json` + lockfile before this task runs (workers have no network). Use them; do not hand-edit the lockfile.
7. Tests (vitest): units + format, client error mapping (mock `fetch`), schema test kept. `npm test` and `npm run build` must pass (`tsc -b` clean).
8. `webapp/README.md` updated: new commands, `/app/` base, meters inside / feet outside, folder layout.

## Done when
- `cd webapp && npm test && npm run build` pass; `web/plot2d/` is untouched.
- `python -m ruff check . && python -m pytest backend -q` still pass.
- HANDOFF.md lists any missing dependency (no network), open design questions under `## Design questions`.

## Out of scope
Adapter from layout to scene, pairing, 2D view, panels, dragging, Dockerfile/deploy, any backend change, `web/plot2d/**`.

## Pointers
`docs/API.md` (contract, wins), `webapp_context/02_api_reference.md`, `03_data_and_coordinates.md`, `05_2d_view_and_toggle.md` (architecture, ignore its React-Three-Fiber/`webapp` stack notes where they conflict with this brief), `web/plot2d/format.js`.


## RETRY 1 (review VERDICT: ISSUES) - fix both, keep tests green
VERDICT: ISSUES
webapp/src/api/client.ts:81 â€” `alternatives` incorrectly requires full `Product` fields (`role`, `currency`, nested `alternatives`), rejecting the valid API alternative shape.
webapp/src/store.ts:51 â€” Loading a new room does not clear the previous `room` or `layout`; failed/direct navigation can display stale data for another room.
Also: on loading a different room clear the previous room, layout, metrics and selection before the request returns (no stale data on failure or direct navigation), and make the lternatives type match docs/API.md section 4 exactly (see webapp_context/sample_payloads for the real shape). Add tests for both.

