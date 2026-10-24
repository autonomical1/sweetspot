# plot2d: top-down 2D plot page (dev tool + demo fallback)

## Goal
A single static page, served by the backend at `/app/plot2d/`, that draws a room from above (x horizontal, z vertical), the listener, furniture, the six speakers, the screen, and lets the user drag speakers and see the score update. It is the quickest way to SEE the backend's output and doubles as a fallback if the 3D viewer is not ready. No build step, no CDN, no external libraries (works offline, from the same origin as the API).

## Read first
docs/API.md (all: room JSON, layout/metrics shapes, endpoints), phoneapp_context/sample_payloads/layout.example.json, fixtures/room_demo.json, backend/app/main.py (already mounts `web/` at `/app` with `html=True`; do NOT edit it), web/README.md.

## Design decisions this brief encodes (do not change)
- Plain HTML + CSS + JavaScript (ES modules allowed), SVG for drawing. Files in `web/plot2d/`: `index.html`, `plot.js`, `format.js` (pure helpers), `style.css`. API base is relative to the origin (`fetch("/rooms/...")`), never a hardcoded host.
- All distances shown to the user as feet and inches (`7' 6"`, nearest inch, 11.6 in rolls to the next foot, negatives get a leading `-`), identical to `backend/app/units.py::format_ft_in`. JSON stays decimal feet. Never show raw decimals in the UI.
- REST only: GET/POST/PATCH with `fetch`. No WebSocket, no polling loops except an optional manual "Refresh".
- Coordinates: x = right, z = down on screen, y (height) shown only as text. North (-z) is up. Room box starts at the origin (0,0).

## Deliverables
1. `index.html` with this layout: header; left control panel; main SVG canvas; right info panel.
   - Control panel: buttons **Load demo room** (`POST /rooms/demo` with `{}`), **New rectangular room** (width, length, height inputs in feet; `POST /rooms/rect`), **Optimize** (`POST /rooms/{id}/optimize`), **Reset layout** (re-run optimize), budget input + **Get products** (`GET /rooms/{id}/products?budget=`), and a "Room id" text field plus **Open** (`GET /rooms/{id}`, and `GET /rooms/{id}/layout` if it exists) so any room from the phone or another session can be viewed.
   - SVG canvas: walls (thick lines from the wall surfaces' polygons projected to x/z), a 1-foot light grid with labels every 5 ft, objects as rotated rectangles with their category name, window/door surfaces as gaps or marks on the wall they sit on, the listener (circle + arrow in the `facing` direction, label "Listener"), speakers as colored circles labeled `L R C LFE Ls Rs` with a thin line to their `aim` projected point, the screen as a thick bar on its wall with its width in ft-in, and treatment patches (if present in `metrics.treatment_patches`) as translucent rectangles on their surface. Auto-fit scale to the room with 0.5 ft padding; responsive to window size.
   - Info panel: score, warnings (`metrics.warnings`, show "stub engine" clearly in amber), reflection table if `metrics.reflections` is non-empty (speaker, surface, delay in ms, level in dB), the speaker list with each position as `x, z (height)` in ft-in, and the products list (role, title, price, link opens in a new tab, total vs budget).
2. Interaction: drag any speaker with pointer events (mouse and touch); positions clamp to inside the room; on drag, send `POST /rooms/{id}/score` with the full current layout, throttled to at most 10 requests per second with latest-wins, and show the returned score; on drop send one final score. If a score request fails, keep the last good metrics and show a dismissible red banner with the error text. Hover shows a tooltip with the element name and its ft-in coordinates. Keyboard: arrow keys nudge the selected speaker by 1 inch (Shift = 1 ft).
3. State and errors: a status line showing the current `room_id`; every `fetch` error (network, 404, 422, 501) becomes a visible message with the server's `detail`; loading indicators for the slow calls (optimize, products). No uncaught promise rejections.
4. `format.js` exports pure functions `formatFtIn(feet)`, `parseFtIn(text)` (accepts `7' 6"`, `7.5`, `7ft 6in`, `7-6`), `clamp`, `rotatePoint`, `polygonToWallSegment(polygon)`; keep them DOM-free so they can be tested in Node.
5. Tests `backend/tests/test_plot2d.py` (pytest, TestClient on `create_app()`): `GET /app/plot2d/` returns 200 `text/html` and contains the ids `canvas`, `btn-demo`, `btn-optimize`, `score`, `status`; `GET /app/plot2d/plot.js`, `format.js`, `style.css` return 200; the HTML references only same-origin relative or root-relative resources (assert there is no `http://` or `https://` in `src`/`href` attributes); API routes still win (`GET /health` is JSON). If `node` is on PATH, also run a small Node check of `format.js` (`formatFtIn(7.5)==="7' 6\""`, `formatFtIn(3.6)==="3' 7\""`, `formatFtIn(0)==="0' 0\""`, `formatFtIn(11.99)==="12' 0\""`, `formatFtIn(-1.5)==="-1' 6\""`, `parseFtIn("7' 6\"")===7.5`) via `subprocess` and skip otherwise (`shutil.which`).

## Done when
`python -m pytest backend -q` passes on this branch; opening `/app/plot2d/` on a running backend (all stubs) shows the demo room, six speakers, the screen and a working drag; no edits outside OWNS.txt.

## Out of scope
3D, WebSocket, auth, QR/pairing UI, material or photo features, any build tooling or frameworks. Put unsettled choices (colors, drag feel, tooltip wording) under `## Design questions` in HANDOFF.md. Tell me in HANDOFF.md exactly what you could not verify in a browser.

---
## RETRY 1 (2026-10-24): fix list. Keep what works; change only what is listed; add tests where possible.

Your previous result is on this branch (checks pass). Fix:
1. **Stale optimize responses** (`plot.js` ~l.324): tie every request to the room it was started for (a request id or room generation counter). If the user has loaded/opened another room before the response arrives, discard the response.
2. **Stale products responses** (~l.329): same guard for `GET /rooms/{id}/products`; also clear the products panel when the room changes.
3. **Treatment patches** (~l.129): draw each `metrics.treatment_patches` entry as a translucent filled rectangle (about 35% opacity) lying along its wall, `size[0]` long in plan view, not an opaque thick line.
4. **Fit padding** (~l.182): exactly 0.5 ft on every side.
5. **Object rotation units** (~l.112): `rotation_y` is in **degrees** (docs/API.md section 1 and 1a, updated after your first run; re-read them), right-handed about +y, where +90 deg maps +x to -z. The canvas draws x to the right and z downward, so a positive `rotation_y` must appear counter-clockwise on screen: use SVG `rotate(-rotation_y)`. Remove the radians conversion. Add a `format.js` (or geometry) helper for the transform and a Node test case if `node` is available.

Also note: rooms now include `warnings` (list of strings) and `frame` (null for rect/demo rooms); show room `warnings` in the info panel next to the metrics warnings. Ignore `frame` (the plot always draws the room frame).
