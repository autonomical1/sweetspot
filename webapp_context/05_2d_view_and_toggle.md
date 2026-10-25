# 05: App architecture (React + Vite), 2D view and the 2D/3D toggle

## Decision: React + Vite single-page app
The backend is FastAPI, so the web app is a client-side React app. Vite builds it into static files that the existing backend serves at **`/app/`** on the same origin as the API (no CORS, no Node process in production, the Docker image gains one build stage). No Next.js (its server features would go unused).

## Project layout
```
webapp/                      Vite + React + TypeScript
  vite.config.ts             see below
  package.json               pinned versions; scripts: dev, build, preview, test, lint
  index.html                 Vite entry
  src/main.tsx               mounts <App/>
  src/App.tsx                screen switch: start | pair | room (from the URL)
  src/screens/Start.tsx      demo / rectangular room / pair / open by id
  src/screens/Pair.tsx       pairing screen (QR + code + polling)
  src/screens/Room.tsx       viewer: top bar, view, panels
  src/components/Plan2D.tsx  SVG plan view (port of web/plot2d/plot.js)
  src/components/Scene3D.tsx @react-three/fiber canvas (04_3d_view.md)
  src/components/panels/*.tsx  Layout, Acoustics, Shop, Room tabs
  src/lib/api.ts             typed fetch client (timeouts, {detail} errors)
  src/lib/store.ts           zustand store (below)
  src/lib/format.ts          port of web/plot2d/format.js (formatFtIn, parseFtIn, objectSvgRotation, ...)
  src/lib/types.ts           TypeScript types for Room, Layout, Metrics, Products (from docs/API.md)
  src/**/*.test.ts           vitest unit tests
```
Keep `web/plot2d/` working; it stays as a dev page at `/app/plot2d/`.

## `vite.config.ts`
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";
export default defineConfig({
  plugins: [react()],
  base: "/app/",                       // assets load from /app/assets/...
  build: { outDir: "dist", emptyOutDir: true },
  server: { proxy: { "/rooms": api, "/sessions": api, "/health": api } },   // dev only
  test: { environment: "jsdom" },      // vitest
});
```

## Routing (keep it simple)
Use the query string on the single page `/app/`: `/app/` (start), `/app/?pair` (pairing), `/app/?room=<id>&view=3d` (viewer). Read and write it with `URLSearchParams` + `history.replaceState`/`pushState` (or `react-router` with `basename="/app"` if you prefer real paths; then the backend must serve `index.html` for unknown `/app/*` paths, so tell the backend person). Shared links are the full `https://.../app/?room=<id>&view=3d` URL.

## Rules
- API calls use root-relative paths (`/rooms/...`), never prefixed with `/app`, never an absolute host.
- Static assets go through Vite imports (so they get the `/app/` base); do not hardcode `/assets/...`.
- Everything is bundled; nothing loaded from a CDN at runtime.

## Libraries (pin exact versions in package.json; use current stable)
`react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`, `three`, `@react-three/fiber`, `@react-three/drei` (OrbitControls, Html labels, Line, Grid), `zustand`, `qrcode.react`, `vitest`, `jsdom`.

## State store (zustand): the key to a clean toggle
```
{ generation, room, layout, metrics, products, selection: {kind, id} | null, view: "2d" | "3d",
  busy: null | "optimize" | "products" | "load", error: string | null }
actions: loadRoom(id), setRoom(room), optimize(), setLayout(result), moveSpeaker(role, position),
         setMetrics(metrics), select(kind, id), setView(view), getProducts(budget), clearError()
```
- `setRoom` bumps `generation` and clears layout/metrics/products/selection; every async action captures `generation` and drops its result if it changed (stale-response guard, same idea as `web/plot2d/plot.js`).
- `moveSpeaker` updates the layout locally and schedules a throttled `POST /score` (<= 10/s, latest-wins, final call on drop).
- Plan2D and Scene3D both render purely from the store; the toggle is `setView`. The hidden view unmounts or pauses (`frameloop="demand"` in R3F), so unsaved drags and the selection survive switching.
- Mirror `view` and room id in the URL and `view` in `localStorage` (try/catch).

## 2D plan view
Port `web/plot2d/plot.js` into `Plan2D.tsx` (SVG): walls from polygons, 1 ft grid with 5 ft labels, objects as rotated rectangles (`rotate(objectSvgRotation(rotation_y))`), doors/windows on walls, listener with facing arrow, role-coloured speakers with aim lines, screen bar, translucent treatment patches, pointer-event drag, arrow-key nudge (1 in, Shift = 1 ft), ft-in tooltips; plus reflection paths for the selected speaker and two-way selection with the panels.

## Toggle UX
Segmented control `2D | 3D` in the top bar (shortcut `V`); instant; default 3D after pairing/demo, 2D when WebGL is unavailable.

## Local development
1. Backend: `pip install -r backend/requirements.txt` and `uvicorn backend.app.main:app --reload` (port 8000).
2. Web: `cd webapp && npm ci && npm run dev`, open http://localhost:5173/app/ (API calls are proxied to 8000).
3. Production-like check: `npm run build` (writes `webapp/dist/`), copy `webapp/dist/*` into `web/` locally (do not commit the build) and open http://127.0.0.1:8000/app/.

## Deployment (backend person does this once the app exists)
- `deploy/Dockerfile` gains a Node build stage: `npm ci && npm run build` in `webapp/`, then copies `webapp/dist/` into the image's `web/` folder (next to `web/plot2d/`), so FastAPI serves it at `/app/`.
- `.dockerignore` adds `webapp/node_modules` and `webapp/dist`.
- `deploy/Caddyfile` root redirect changes from `/app/plot2d/` to `/app/`.
- Do not commit `webapp/dist/` or `node_modules/` (already in `.gitignore`).
