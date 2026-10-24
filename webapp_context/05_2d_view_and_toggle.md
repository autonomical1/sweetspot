# 05: App architecture, 2D view and the 2D/3D toggle

## Where the app lives
- `web/index.html` is served at **`/app/`** (the backend mounts `web/` at `/app` with `html=True`). Put code in `web/app/` (modules) and third-party files in `web/vendor/` (pinned, with a `VERSIONS.md`).
- `web/plot2d/` stays as the standalone dev page; do not break it (its tests run in CI).
- After the app exists, the backend person changes the Caddy root redirect from `/app/plot2d/` to `/app/` (one line in `deploy/Caddyfile`). Tell them.

## Recommended structure (no build step)
```
web/index.html            app shell, import map for three.js
web/app/main.js           boot, routing (#pair, #room=<id>, start screen)
web/app/api.js            fetch wrappers: timeouts, {detail} errors, generation guard helper
web/app/store.js          single state store (see below) with subscribe()
web/app/views/plan2d.js   SVG plan view (ported from web/plot2d/plot.js)
web/app/views/scene3d.js  three.js view (04_3d_view.md)
web/app/panels/*.js       layout, acoustics, shop, room tabs
web/app/pairing.js        QR + code + polling
web/app/format.js         re-export of web/plot2d/format.js (or move it and update plot2d's import)
web/app/style.css
```

## State store (the key to a clean toggle)
One plain object, updated only through store functions, with `subscribe(fn)`:
```
{ generation, room, layout, metrics, products, selection: {kind, id}, view: "2d"|"3d",
  status: {busy: null|"optimize"|"products"|..., error: null|string}, dragging: bool }
```
- `setRoom(room)` bumps `generation`, clears layout/metrics/products/selection.
- `setLayout(result)`, `moveSpeaker(role, position)` (local, triggers throttled score), `setMetrics(metrics)`, `select(kind, id)`, `setView(view)`.
- Both views and all panels render from the store; neither view owns data. The toggle is just `setView`: the hidden view stops rendering (3D: stop the animation loop), the visible one renders the current state, so unsaved drags and the selection survive the switch.
- Persist `view` in `localStorage` (try/catch) and in the URL hash (`#room=<id>&view=3d`).

## 2D plan view
Port `web/plot2d/plot.js`: walls from polygons, 1 ft grid with 5 ft labels, objects as rotated rectangles (`rotate(-rotation_y)`), doors/windows marked on walls, listener with facing arrow, speakers as role-coloured circles with aim lines, screen bar, translucent treatment patches, drag with pointer events, arrow-key nudge (1 in, Shift = 1 ft), hover tooltips in ft-in. Add: reflection paths for the selected speaker, selection highlight, and the same role colours as 3D.

## Toggle UX
- Segmented control `2D | 3D` in the top bar; keyboard shortcut `V`.
- Switching animates nothing heavy; it must be instant.
- Default: 3D for the pitch path (after pairing/demo), 2D when WebGL is missing.

## Open question (decide early)
No-build vanilla ES modules (recommended: matches plot2d, nothing to install on the server, the backend serves the files as-is) **vs** React/Vite. If you choose Vite, build into `web/dist/` and the backend person will mount that instead; commit the built output or add a build step to the Docker image. Tell the backend person before you start.
