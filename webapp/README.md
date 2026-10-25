# SweetSpot web app

React, Vite and the teammate's raw Three.js viewer. The production build is served at `/app/` by the backend. It writes to `../web/` without clearing `web/plot2d/`.

## Commands

From `webapp/`:

```sh
npm ci
npm run dev
npm test
npm run typecheck
npm run build
```

The dev server proxies `/rooms`, `/sessions`, `/health`, `/products`, and `/materials` to the local backend at port 8000. Start it with `uvicorn backend.app.main:app --reload` from the repository root. The scripts use Vite's runner config loader because its default bundled loader fails on restricted Windows workspaces.

## Data and coordinates

The backend API speaks decimal **feet**, Y-up, with a room corner at the origin. `src/api/client.ts` defines the API types and fetch calls; `src/store.ts` holds the fetched room, layout and view state. `src/lib/units.ts` provides feet to meter conversion, and `src/lib/format.ts` formats feet and inches for display.

The existing Three.js scene and imported room configuration remain in **meters**, Y-up, centered on the floor. `src/scene/` holds rendering, model loading, projection and room-shell helpers. A later adapter will map backend room and layout coordinates into that scene. Until then, **Use demo room** fetches `/rooms/demo`, optimizes it, shows its returned dimensions in the sidebar, and keeps the example scene visible. It does not position returned speakers yet.

`src/screens/Viewer.tsx` keeps the original scene controls and room-file import/export. `src/components/` contains the top bar, sidebar and viewport UI. `src/screens/Pair.tsx` and `src/views/View2D.tsx` are mount points for the next tasks. Routing uses `/app/?pair` and `/app/?room=<id>&view=3d|2d`.

## Existing viewer controls

Orbit with left drag, pan with right drag, and zoom with the wheel. Top and Seat POV switch cameras; the latter hides the seat and supports drag-to-look. Toggle walls, ceiling and projection preview in the viewport and sidebar. Click an object or its row to show its label. **Load room file** validates the original meter-based JSON format; **Export setup** downloads it. A working sample is in `examples/home-theater.json`.
