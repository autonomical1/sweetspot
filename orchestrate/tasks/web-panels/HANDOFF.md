# web-panels handoff

## Completed

- Replaced the legacy sidebar body with accessible Layout, Acoustics, Shop, and Room tabs while retaining its existing caller props.
- Added panel components, scoped panel styling, role chips, staged-layout notice, selectable speaker/reflection rows, room surface/photo-target details, and shop product grouping/cards/budget state.
- Added `src/api/extra.ts` direct typed exports for products, photo targets, and material status, with the same `ApiError` / retry semantics as the base client.
- Added Vitest coverage for the extra client, staged/unknown-role layout rendering, reflection selection rendering, and the no-layout shop state.

## Verification

- `cd webapp && npm test` — 17 tests passed.
- `cd webapp && npm run typecheck` — passed.
- `python -m pytest backend -q` — passed.

## Unfinished / integration notes

- The current store does not expose refined-layout polling or material-classification submission; panels read `layout.stage` and the shared room/layout/metrics state as requested. The later store work can update those fields and the panels will rerender.
- The viewer/scene currently selects legacy equipment IDs, whereas the panel selects speaker roles and reflection keys. Scene-side selection mapping may be needed for visual highlighting.
- `getMaterialsStatus` is available for store integration but is not displayed because no materials submission/progress state is owned by this task.

## Design questions

- Role colours: `src/scene/adapter/roleColors.ts` is not present in this worktree, so I used a small local fallback map in `panels/shared.tsx`; replace it with the adapter export when that module lands.
