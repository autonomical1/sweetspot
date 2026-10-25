# web-drag: drag-to-rescore, 2D | 3D toggle, staged-layout polling

## Goal
Make the layout interactive and live: drag a speaker in 3D or 2D and the score updates; switch between the 2D and 3D views; pick up the refined 3D layout automatically after the quick one.

## Design decisions encoded
- Dragging follows `webapp_context/04_3d_view.md` (3D: drag on a horizontal plane at the speaker's current height, orbit disabled during drag, clamp to the room with a 0.25 ft margin; height not draggable) and `05_2d_view_and_toggle.md` (2D: pointer drag on the SVG). The layout in the store is in **feet**; convert pointer positions to feet (3D scene is meters: use the adapter's inverse).
- Rescoring: `POST /rooms/{id}/score` with the edited layout, **throttled** (at most one in flight, latest wins, ~16 ms server time), with a stale-response guard (sequence number). While dragging, update the speaker position locally at once and the score when the response arrives. Roles in the widened API (`Lss Rss Lrs Rrs`, overheads, `LFE2`) are all draggable; the screen and projector are not.
- Toggle: segmented control **2D | 3D** in the top bar (shortcut `V`), default 3D after pairing/demo and 2D when WebGL is unavailable (feature-detect). View mode is also in the URL (`view=2d|3d`).
- Staged results (`docs/API.md` section 2a): after `optimize` answers with `stage: "quick"`, poll `GET /rooms/{id}/refine/status` (exact path and fields from `docs/API.md`; code against the doc, and stub minimally if the endpoint is absent, reporting it) every 3 s while the page is visible; when refined, `GET /rooms/{id}/layout`, replace the layout, keep the user's selection, and show a toast "3D layout refined". Stop polling on `refined`, `failed`, unmount, or room change. A user drag while refining cancels adoption of the refined layout (the user's edit wins; show "Keep my edit / Use refined layout").
- Listener nudge (P2): arrow keys move the listener 0.25 ft (shift = 1 ft) with the same throttled rescore.

## Deliverables
1. `src/interaction/` (drag controllers for 3D and 2D, throttle + sequence guard, coordinate converters) and wiring in `App.tsx`, `components/Topbar.tsx`, `store.ts`, `api/client.ts` (you own them in this wave: web-base is merged).
2. Tests (vitest): throttle/latest-wins/stale response, clamp, 2D<->feet conversion, 3D plane-drag math without WebGL, polling stop conditions, edit-vs-refined conflict, view-mode URL sync, WebGL-unavailable default.

## Done when
`cd webapp && npm test && npm run typecheck` pass; python checks still pass.

## Out of scope
Panels, pairing, backend, Dockerfile.

## Files you own
`webapp/src/interaction/**`, `webapp/src/App.tsx`, `webapp/src/components/Topbar.tsx`, `webapp/src/store.ts`, `webapp/src/api/client.ts` and their tests.
