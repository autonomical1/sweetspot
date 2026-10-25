# web-panels: Layout, Acoustics, Shop and Room panels

## Goal
Replace the sidebar content with the four tabs from `webapp_context/06_panels_products_materials.md`: **Layout**, **Acoustics**, **Shop**, **Room**, driven by the store and the API client.

## Design decisions encoded
- Copy and behaviour follow `webapp_context/06_*.md` (read it in full); `docs/API.md` wins on data. All numbers in the UI: feet-inches via `formatFtIn`, money via `Intl.NumberFormat`, scores 0-100 with one decimal.
- Shop tab uses `GET /rooms/{id}/products` (DB first; expansion happens server-side; response may take a while on first call: show progress and a Retry on error). Group by role, pairs/bundles shown once with `included_in` handling, show `specs`, `dimensions` (feet-inches), `alternatives` (collapsed list with price delta vs recommended) and "sample data" for `source == "stub"`. Total vs budget bar; projector-first display (a TV appears only if the server returned one).
- Staged layout: when `layout.stage` is `quick` or `refining`, show a banner "Showing the quick layout, refining in 3D..."; when it becomes `refined`, the panels update from the store without a page reload. The polling of the refine status is added to the store later by `web-drag`; you only read state (`layout`, `stage`).
- The Gemini limits (`429` + `Retry-After`) are shown as "Waiting on Gemini, retry in N s" with a countdown; never as a generic error.
- Role colour chips use the map from `src/scene/adapter/roleColors.ts` (web-adapter). If it is not merged yet, use a local fallback map and note it in HANDOFF.md.
- Clicking a speaker row or a reflection row sets `selected` in the store.

## Deliverables
1. `src/components/panels/` with `LayoutPanel`, `AcousticsPanel`, `ShopPanel`, `RoomPanel`, and `Sidebar.tsx` (replaces the web-base one) with the tab bar; keyboard accessible tabs.
2. `src/api/extra.ts`: typed `getProducts(roomId, budget)`, `getPhotoTargets(roomId)`, `getMaterialsStatus()`; errors mapped like the base client.
3. Modest, readable CSS in `src/components/panels/panels.css` using the existing design tokens in `styles.css` (do not edit `styles.css`).
4. Tests (vitest + jsdom): each panel renders from `webapp_context/sample_payloads/*` and `fixtures/engine/*.json`, shop grouping and totals, 404 "Place the speakers first", Gemini 429 countdown, stage banner, unknown role, empty states.

## Done when
`cd webapp && npm test && npm run typecheck` pass; python checks still pass.

## Out of scope
Scene, 2D view, dragging, pairing, store/client edits (list needed fields in HANDOFF.md), backend.

## Files you own
`webapp/src/components/panels/**`, `webapp/src/components/Sidebar.tsx`, `webapp/src/api/extra.ts` and tests for them.
