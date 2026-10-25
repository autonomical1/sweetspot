# web-adapter: draw the backend layout in the existing 3D scene

## Goal
Turn the backend's room + layout (feet, room frame) into the teammate's three.js scene (meters, Y-up) so **Use demo room** shows the real room, furniture, speakers (all roles), screen, projector, seats, treatment patches and reflections, instead of the hard-coded example.

## Design decisions encoded (user-approved 2026-10-25)
- Keep the teammate's raw three.js scene and GLB models (no React Three Fiber). The scene stays in **meters**; this task is the only place that converts feet to meters (`ftToM` from `src/lib/units.ts`).
- Axes: room frame x = east (width), y = up, z = south (length), north = -z, room box spans 0..width and 0..length. The teammate's scene is floor-centred (floor centre at the origin). The adapter subtracts half of width/length so frames align; document this in `src/scene/adapter/README.md` (short).
- Existing GLBs: `bookshelf_speaker.glb` for all speaker roles, `fixed_frame_screen_16_9.glb` for the screen, `projector.glb` for the projector. Roles without a model use a coloured box. Speaker colours by role family: fronts, centre, LFE, surrounds, overheads (legend in the existing sidebar space is owned by web-panels; you only expose the colour map in `src/scene/adapter/roleColors.ts`).
- Contract is `docs/API.md` (wins) and `webapp_context/03_data_and_coordinates.md`. engine3d-wire widens it: roles `L R C LFE Ls Rs Lss Rss Lrs Rrs Ltf Rtf Ltr Rtr Ltm Rtm LFE2`, optional `preset`, `seats`, `projector`, `stage`, and per-item `size` when present. Handle unknown roles and missing optional fields without throwing (box fallback + console warning once).

## Deliverables
1. `src/scene/adapter/` (pure functions, no three.js imports in the mapping layer): `layoutToScene(room, layout, metrics) -> SceneModel` where `SceneModel` = `{room:{width,length,height}, surfaces[], objects[], speakers[], screen?, projector?, seats[], patches[], reflections[]}` in **meters**, plus `roleColors.ts`.
2. Rendering changes in `src/scene/*` (you own this folder): build the scene from `SceneModel`; speakers oriented by `aim` (lookAt), floating role labels, a thin line to the floor; screen as a plane on its wall facing into the room; projector at its position pointing at `aim`; furniture boxes from `objects[]` with `rotation_y` degrees about +y; treatment patches as translucent amber planes offset 0.01 m into the room; reflections as lines speaker -> point -> listener (for the selected speaker, or all when `showReflections`); wall polygons from `surfaces[]` (use the polygon, never the id), doors/windows drawn on top.
3. Selection: clicking a speaker/screen/projector sets `selected` in the store to its role/id; the selected object is highlighted. Rebuild only what changed when the layout updates (no full teardown per frame).
4. Seat POV and top view use the first `layout.seats[0].position` or `listener.position` and `listener.facing` (fx, fz).
5. Tests (vitest, no WebGL needed): feet-to-meters and centring, `rotation_y` sign (object at 90 degrees: local +x maps to world -z), role colour/size fallbacks, unknown role, missing `projector`/`seats`/`size`, using `fixtures` copied into `webapp/src/__fixtures__/` from `webapp_context/sample_payloads/` and `fixtures/engine/layout_5.1.json`, `layout_7.1.4.json`.

## Done when
`cd webapp && npm test && npm run typecheck` pass; `python -m ruff check . && python -m pytest -q` still pass; `Use demo room` draws all speakers of the returned layout in the right places (verify by test, not by eye).

## Out of scope
Dragging, panels, 2D view, pairing, store/API client changes (request any needed field in HANDOFF.md), backend, Dockerfile.

## Files you own
`webapp/src/scene/**`, `webapp/src/__fixtures__/**`, and tests under them.
