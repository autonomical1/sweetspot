# web-view2d handoff

## Completed

- Replaced the 2D placeholder with a responsive SVG room plan driven by the shared Zustand store.
- Added feet-based grid, room walls, furniture rotation, listener direction, speaker roles (including overhead labels), unknown-role fallback, screen/projector, treatment/reflection indicators, compass, scale bar, stage chip, selection, Escape and Tab keyboard behavior.
- Added pure plan helpers and tests, plus jsdom view tests.
- `cd webapp && npm run typecheck` and `npm test` pass (18 tests).

## Unfinished

- The store's current selection ids are used as speaker roles in this view; the existing 3D/config selection uses equipment ids. Shared adapter wiring is out of scope for this task.
- Running the required TypeScript check updated the unowned generated file `webapp/tsconfig.app.tsbuildinfo`; I did not restore it because worker ownership rules prohibit editing that file.

## Design questions

- role colour map: used a local stable map in `View2D.tsx`; alternatives are importing the promised `web-adapter` map once it merges, or moving the map to a shared module.
- Screen orientation: the API screen model has a `wall_id`; the minimal reversible view draws a horizontal screen centered at its supplied coordinate. Deriving its exact angle from the corresponding wall should be added when shared plan geometry is consolidated.
