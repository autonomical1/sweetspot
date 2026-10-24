# 05: App architecture (Next.js static export), 2D view and the 2D/3D toggle

## Decision: React + Next.js, **static export**
The backend is FastAPI, so Next's server features (SSR, route handlers, server actions, `next/image` optimization, middleware) are not used. The app is a client-side React app built by Next into static files (`output: 'export'`) and served by the existing backend at **`/app/`** on the same origin as the API (no CORS, no Node process in production, the Docker image gains one build stage).

## Project layout
```
webapp/                      Next.js app (App Router, TypeScript)
  next.config.mjs            see below
  package.json               pinned versions, scripts: dev, build, test, lint
  app/layout.tsx             shell, fonts, dark theme
  app/page.tsx               start screen (demo / rectangular room / pair / open by id)
  app/pair/page.tsx          pairing screen (QR + code + polling)
  app/room/page.tsx          viewer; room id from the query string (?id=r_...&view=3d)
  components/Plan2D.tsx      SVG plan view (port of web/plot2d/plot.js)
  components/Scene3D.tsx     @react-three/fiber canvas (04_3d_view.md)
  components/panels/*.tsx    Layout, Acoustics, Shop, Room tabs
  lib/api.ts                 typed fetch client (timeouts, {detail} errors)
  lib/store.ts               zustand store (below)
  lib/format.ts              port of web/plot2d/format.js (formatFtIn, parseFtIn, objectSvgRotation, ...)
  lib/types.ts               TypeScript types for Room, Layout, Metrics, Products (from docs/API.md)
  tests/                     vitest unit tests
```
Keep `web/plot2d/` working; it stays as a dev page at `/app/plot2d/`.

## `next.config.mjs`
```js
const isDev = process.env.NODE_ENV === "development";
export default {
  output: "export",          // static files in webapp/out
  basePath: "/app",          // served by FastAPI/Caddy under /app
  trailingSlash: true,       // /app/room/ -> room/index.html, works with static hosting
  images: { unoptimized: true },
  // Dev only: proxy API calls from `next dev` (port 3000) to the local backend (port 8000).
  ...(isDev ? { async rewrites() { return ["rooms", "sessions", "health"].flatMap(p => [
    { source: `/${p}`, destination: `http://127.0.0.1:8000/${p}`, basePath: false },
    { source: `/${p}/:path*`, destination: `http://127.0.0.1:8000/${p}/:path*`, basePath: false }]); } } : {}),
};
```
VERIFY with your Next version: rewrites are not supported in the static export build, which is why they are added only in development. If `next dev` refuses rewrites together with `output: "export"`, also make `output` conditional (`...(isDev ? {} : { output: "export" })`).

Rules that follow from static export:
- Every page is a client component (`"use client"`) or renders client components; fetch data in the browser (`useEffect`/SWR), never in server components.
- No dynamic route segments for room ids (`/room/[id]` would need `generateStaticParams`): use the query string `?id=` with `useSearchParams` inside a `<Suspense>` boundary.
- API calls use root-relative paths (`/rooms/...`), never prefixed with the basePath, never an absolute host.
- Use `<Link>` and `useRouter` for in-app navigation (they handle basePath).

## Libraries (pin exact versions in package.json; examples, use current stable)
`next`, `react`, `react-dom`, `typescript`, `three`, `@react-three/fiber`, `@react-three/drei` (OrbitControls, Html labels, Line), `zustand`, `qrcode.react`, `vitest`. Nothing loaded from a CDN at runtime; everything is bundled.

## State store (zustand) - the key to a clean toggle
```
{ generation, room, layout, metrics, products, selection: {kind, id} | null, view: "2d" | "3d",
  busy: null | "optimize" | "products" | "load", error: string | null }
actions: loadRoom(id), setRoom(room), optimize(), setLayout(result), moveSpeaker(role, position),
         setMetrics(metrics), select(kind, id), setView(view), getProducts(budget), clearError()
```
- `setRoom` bumps `generation` and clears layout/metrics/products/selection; every async action captures `generation` and drops its result if it changed (stale-response guard, same idea as `web/plot2d/plot.js`).
- `moveSpeaker` updates the layout locally and schedules a throttled `POST /score` (<= 10/s, latest-wins, final call on drop).
- Plan2D and Scene3D both render purely from the store; the toggle is `setView`. The hidden view unmounts or pauses (`frameloop="demand"` in R3F), so unsaved drags and the selection survive switching.
- Mirror `view` and room id in the URL (`/app/room/?id=...&view=3d`) and `view` in `localStorage` (try/catch).

## 2D plan view
Port `web/plot2d/plot.js` into `Plan2D.tsx` (SVG): walls from polygons, 1 ft grid with 5 ft labels, objects as rotated rectangles (`rotate(objectSvgRotation(rotation_y))`), doors/windows on walls, listener with facing arrow, role-coloured speakers with aim lines, screen bar, translucent treatment patches, pointer-event drag, arrow-key nudge (1 in, Shift = 1 ft), ft-in tooltips; plus reflection paths for the selected speaker and two-way selection with the panels.

## Toggle UX
Segmented control `2D | 3D` in the top bar (shortcut `V`); instant; default 3D after pairing/demo, 2D when WebGL is unavailable.

## Local development
1. Backend: `pip install -r backend/requirements.txt` and `uvicorn backend.app.main:app --reload` (port 8000).
2. Web: `cd webapp && npm ci && npm run dev` and open http://localhost:3000/app/ (API calls are proxied to 8000).
3. Production-like check: `npm run build` (writes `webapp/out/`), copy `webapp/out/*` into `web/` locally (do not commit the build) and open http://127.0.0.1:8000/app/.

## Deployment (backend person does this once the app exists)
- `deploy/Dockerfile` gains a Node build stage: `npm ci && npm run build` in `webapp/`, then copies `webapp/out/` into the image's `web/` folder (next to `web/plot2d/`), so FastAPI serves it at `/app/`.
- `.dockerignore` adds `webapp/node_modules`, `webapp/.next`, `webapp/out`.
- `deploy/Caddyfile` root redirect changes from `/app/plot2d/` to `/app/`.
- Do not commit `webapp/out/`, `.next/` or `node_modules/` (add them to `.gitignore`).
