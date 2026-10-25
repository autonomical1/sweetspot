# web-view2d: 2D plan view in the web app

## Goal
Port the working SVG plan view from `web/plot2d/` into `webapp/` as the **2D** mode of the 2D | 3D toggle, reading the same store as the 3D view. Demo room works in 2D with no WebGL.

## Design decisions encoded
- The 2D view reuses the logic of `web/plot2d/` (`plot.js`, `format.js`): do not rewrite from scratch; convert to typed modules. `web/plot2d/` itself stays untouched and keeps working at `/app/plot2d/`.
- The view works in **feet in the room frame** (SVG x = east, y = south) and shows feet-inches via `formatFtIn` (`src/lib/format.ts` from web-base). No meters here.
- It renders from the store (`room`, `layout`, `metrics`, `selected`) and shows the same selection as 3D. Dragging is NOT in this task (web-drag adds drag for both views later); selection and hover only.
- Supports every role in `docs/API.md` (L R C LFE Ls Rs Lss Rss Lrs Rrs, overheads as small circles with a height label), the projector, the screen on its wall, seats, furniture boxes with `rotation_y` (use `objectSvgRotation`), treatment patches, and the reflection path for the selected speaker.
- Staged results: show a small "Refining 3D..." chip when `layout.stage === 'refining'`.

## Deliverables
1. `src/views/View2D.tsx` (replaces the placeholder from web-base) plus small modules under `src/views/` and pure helpers in `src/lib/plan.ts` (room-to-SVG transform, label placement).
2. Responsive SVG with a grid (1 ft minor, 5 ft major), compass (N = up), scale bar, listener arrow along `facing`.
3. Tests (vitest + jsdom + `@testing-library/react`): transform, `rotation_y = 90` orientation, role colour mapping parity with 3D (`roleColors` lives in web-adapter; until it is merged, define a local map and note it in HANDOFF.md), unknown role, empty layout, stage chip.
4. Keyboard: Escape deselects; Tab cycles speakers.

## Done when
`cd webapp && npm test && npm run typecheck` pass; python checks still pass.

## Out of scope
Dragging, panels, 3D, toggle wiring (web-drag), store/API client edits (ask in HANDOFF.md), `web/plot2d/**`.

## Files you own
`webapp/src/views/**`, `webapp/src/lib/plan.ts`, `webapp/src/lib/plan.test.ts`.
