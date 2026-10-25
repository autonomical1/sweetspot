# 07: Testing and acceptance

Rule (docs/TESTING.md): standalone first. The web app must work against the backend running **locally with stubs or the real engine** before it touches the deployed server.

## Automated
- `cd webapp && npm test` (vitest): `lib/format.ts` (same table as `backend/app/units.py`: `7.5 -> 7' 6"`, `11.99 -> 12' 0"`, `-1.5 -> -1' 6"`, parse variants), `lib/store.ts` transitions (setRoom clears layout and bumps generation; stale-generation results ignored; toggle keeps selection and unsaved drags; score throttling latest-wins with fake timers), `lib/api.ts` error handling (`{detail}` surfaced, timeouts), 16:9 diagonal, reflection path points, rotation helpers (`objectSvgRotation(90) === -90`; R3F `rotation.y = degToRad(rotation_y)`).
- `npm run build` must succeed and every asset URL in `dist/index.html` must start with `/app/`.
- `backend/tests/test_web_app.py` (pytest, written by the backend person once the build is wired into deploy): with a built `web/index.html` present, `GET /app/` returns HTML, its `/app/assets/...` files return 200, no absolute `http(s)://` asset URLs, `/app/plot2d/` and `/health` still work; skipped when no build is present.
- The whole repo suite (`python -m pytest -q`) must stay green; `webapp/node_modules` and `webapp/dist` are never committed.

## Manual checklist (do on the deployed URL before the pitch, Chrome on the demo laptop and on the projector resolution)
- [ ] `/app/` loads in under 2 s; no console errors.
- [ ] Demo room: room appears, optimize overlay, six speakers + screen, score shown, in both 2D and 3D.
- [ ] Toggle 2D <-> 3D five times while a speaker is selected and after a drag: same selection, same positions.
- [ ] Drag in 2D and in 3D: score updates within ~0.2 s; speakers cannot leave the room.
- [ ] Reflections: click the strongest one; path drawn to the right wall; amber patches visible.
- [ ] Shop: budget 1500 -> list and total <= budget; budget 0 shows a validation message.
- [ ] Pairing: QR + code; phone pairs; page flips to the viewer automatically; expired code shows "New code".
- [ ] Scanned room (phone or `sample_payloads/room_scanned.json` via `POST /rooms` in /docs): walls, door, window, sofa, TV drawn in the right places; listener on the sofa facing the TV.
- [ ] Server down: banner, no blank page; back up: retry works.
- [ ] Share link `/app/?room=<id>&view=3d` opens the same room in 3D in a new tab.
- [ ] 1280 x 720 window: nothing cut off; text readable from 3 m.
- [ ] WebGL disabled (chrome://flags or a VM): 2D still works, toggle hidden.

## Acceptance (what "done" means for the pitch)
1. Pair -> scan -> viewer flips automatically -> optimized layout in 3D, without touching the laptop.
2. Demo room path works with no phone and no internet beyond the server.
3. 2D/3D toggle is instant and lossless.
4. Drag-to-rescore feels live.
5. Shopping list shows a total within budget.
6. No raw decimals, no raw UUIDs, no uncaught errors anywhere in the demo path.
