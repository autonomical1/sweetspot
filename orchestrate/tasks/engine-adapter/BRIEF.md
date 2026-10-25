# engine-adapter: plug the teammate's `speakerplacer` into the backend contract

## Goal
The teammate's 2D optimizer is now in the repo (`speakerplacer/`, 32 passing tests in `tests/test_speakerplacer.py`). It does not expose the backend contract (`optimize(room)`, `score(room, layout)`, docs/API.md sections 1-3). Write an adapter module that does, plus a small fast acoustics module that computes our metrics, so `POST /rooms/{id}/optimize` uses the real engine and every contract test passes against it.

## Read first
docs/API.md sections 1, 1a, 2, 3; docs/TESTING.md 3.3; `speakerplacer/README.md` and `speakerplacer/{__init__,room,optimize,speaker_types,candidates}.py` (read only); `backend/app/engine.py` (already imports `backend.app.engine_speakerplacer` when it exists and falls back to the stub on errors); `backend/app/stubs/engine_stub.py` (screen logic to reuse); `backend/tests/contract/` (checks.py, conftest.py: the "real" engine parameter is your module; test_engine_contract.py includes an analytic reflection test). Do NOT edit `speakerplacer/`, `tests/`, the stubs, engine.py, schemas, or the contract tests.

## Facts verified by the orchestrator
- `speakerplacer.optimize_layout(polygon_m, listener_m, layout, facing, absorption, ...)` takes a 2xN CCW polygon in **metres**, a 2D listener, `facing` in `north|south|east|west` where **north = +y**, and a list of `SpeakerType`. The best result is `result.best_pair["speakers"]`: dicts with `type, model_id, position_m, position_ft, wall_index, wall_t, normal, aim_direction, toe_in_deg, angle_deg, predicted_spl_db, headroom_db, warnings`, and `result.best_pair["score_db"]`, `result.warnings`.
- `[DEFAULT_SPEAKER_TYPES["front"], DEFAULT_SPEAKER_TYPES["surround"], dataclasses.replace(DEFAULT_SPEAKER_TYPES["bass"], count=1, symmetric=False)]` works (about 8 s for a 15 x 12 ft room). There is **no center model**: a `center` role is rejected by its model registry.
- numpy values must be converted to plain floats/lists before returning JSON.

## Design decisions this brief encodes (do not change)
- **5.1 mapping:** front pair -> `L`/`R`, surround pair -> `Ls`/`Rs`, one bass -> `LFE`. `L`/`Ls` are the ones on the listener's left: left vector in the room frame is `(fz, -fx)` for facing `(fx, fz)`.
- **Center (`C`) is placed geometrically by the adapter:** where the ray from the listener along its facing meets the wall, inset 0.16 ft into the room, height 3.6 ft. Add warning `"C placed geometrically (speakerplacer has no center model)"`.
- **Coordinates:** room frame feet (x east = width, z south = length, north = -z) to engine metres: `u = x * 0.3048`, `v = (length - z) * 0.3048`; polygon `(0,0), (W,0), (W,L), (0,L)` in (u,v) metres (CCW). Back: `x = u / 0.3048`, `z = length - v / 0.3048`. Engine north (+v) equals room north (-z). Facing: room `(fx, fz)` -> engine `(fx, -fz)`, snapped to the nearest cardinal; if the snap changes the angle by more than 10 deg add a warning. Listener 2D = (u, v) of the listener position.
- **Heights (y, feet):** L, R, C 3.6; Ls, Rs 5.0; LFE 1.0. `aim`: for L/R/Ls/Rs follow the engine's `aim_direction` (mapped back with the same axis flip) to the listener's distance at ear height; C and LFE aim at the listener ear point.
- **Absorption:** `options["absorption"]` if given, else the mean of the room's wall surfaces' `"500"` and `"1000"` band absorption, clamped to [0.01, 0.99].
- **Metrics come from our own acoustics module for both `optimize` and `score`** so they agree exactly and `score` is fast: `metrics = acoustics.evaluate(room, layout)`. The engine's own result goes into `metrics["engine"] = {"name": "speakerplacer", "score_db": ..., "placements": [{role, model_id, toe_in_deg, predicted_spl_db, headroom_db}]}`. `metrics["warnings"]` = engine warnings (strings) + adapter warnings.
- **Screen:** reuse the stub's screen (`engine_stub.optimize(room)["layout"]["screen"]`).
- **Objects:** after mapping back, if any speaker lies inside an object's 3D box (`center`, `size`, `rotation_y` in degrees, same convention as API.md 1a), slide it along its wall to the nearest point outside the box in plan view, keep it inside the room, and add a warning naming the object.
- **Failures:** if the engine raises (tiny rooms, odd inputs), return the stub's layout with our metrics and a warning `"speakerplacer failed: <ExceptionType>: <message>"`; never raise from `optimize`/`score`.
- **Caching:** memoize `optimize` on a canonical JSON dump of `(room geometry, listener, absorption)` (LRU, 32 entries) so repeated calls (tests, re-opening a room) are instant and deterministic. Return deep copies.

## Deliverables
1. `backend/app/acoustics.py`, pure Python + numpy, < 100 ms per call:
   - `evaluate(room: dict, layout: dict) -> dict` returning `{"score", "reflections", "treatment_patches", "sub_modes", "warnings"}` per API.md section 2.
   - **First-order reflections (image-source):** for each non-LFE speaker and each of the 6 boundary planes (x=0, x=width, z=0, z=length, y=0, y=height), mirror the speaker, intersect the image-to-ear segment with the plane, keep it if the hit point lies within the room bounds on that plane. `delay_ms = (reflected - direct) / 1125 * 1000`; `level_db = 20*log10(direct / reflected) + 10*log10(1 - alpha)` with `alpha` the `"1000"` absorption of the surface hit (a window/door/opening polygon containing the point wins over its wall; walls/floor/ceiling are found by polygon geometry, not by id, because scanned rooms use UUIDs). Report `{speaker, surface_id, delay_ms, level_db, point}`; keep only `delay_ms <= 20`; sort by `level_db` descending. Ear point = listener position.
   - **Treatment patches:** each wall/window reflection with `level_db > -10` becomes `{surface_id, center: point, size: [2.0, 2.0]}` (feet); merge patches on the same surface whose centres are within 1 ft.
   - **Sub modes:** first three axial modes per dimension `n * 1125 / (2 * dim_ft)`; `schroeder_hz = 2000 * sqrt(T60 / V)` (metric; Sabine `T60 = 0.161 V / A` with A from surface areas x `"500"` absorption); `sub_position` = LFE position (or null).
   - **Score (0..1), documented heuristic:** `0.7 * angle_score + 0.3 * reflection_score`, where `angle_score` is the mean over present roles of `max(0, 1 - |error_deg| / 30)` against targets L/R 30, C 0, Ls/Rs 110 (relative to the listener facing, horizontal plane), and `reflection_score = 1 - min(1, n_strong / 12)` with `n_strong` = reflections with `level_db > -10` and `delay_ms < 15`. Round to 4 decimals.
2. `backend/app/engine_speakerplacer.py` with `optimize(room: dict, options: dict | None = None) -> dict` and `score(room: dict, layout: dict) -> dict` implementing everything above.
3. Tests:
   - `backend/tests/test_acoustics.py`: the analytic case (18 x 13 x 9 room, listener (9, 3.6, 6.5) facing north, L at (3, 3.6, 6.5): reflection off `wall_w` with `delay_ms` 5.333 +- 0.01 and `level_db` = -6.02 + 10 log10(1 - 0.09) +- 0.01); floor and ceiling reflections present; window absorption wins over its wall; patches merge; score monotonic (moving L from 30 to 45 deg lowers the score); `evaluate` runs in < 100 ms; output JSON-serializable.
   - `backend/tests/test_engine_speakerplacer.py`: on `fixtures/room_rect.json` and `fixtures/room_demo.json`: six roles, L on the left, C straight ahead, LFE at 1 ft, all inside the room, nothing inside the sofa/TV boxes, `score(room, layout)["metrics"]["score"] == optimize(...)["metrics"]["score"]`, second `optimize` call served from the cache (< 0.1 s), engine failure (monkeypatch `speakerplacer.optimize_layout` to raise) returns the stub layout with the warning, facing snap warning for a 45 deg facing, JSON-serializable output. Keep the number of real `optimize` runs low (they take seconds); use the cache.
   - The contract suite `backend/tests/contract/test_engine_contract.py` must pass for the `real` parameter too (it now resolves to your module), including `test_real_engine_reflection_case`.

## Done when
`python -m pytest -q` (whole repo: backend and tests/) passes; `POST /rooms/demo` then `POST /rooms/{id}/optimize` returns a speakerplacer layout with `metrics.engine.name == "speakerplacer"`; no edits outside OWNS.txt.

## Out of scope
Changing the teammate's package, a center model for it, 3D acoustics, higher-order reflections, performance work on the engine itself. Put unsettled choices (score weights, patch size, LFE height, center inset) under `## Design questions` in HANDOFF.md.

---
## RETRY 1 (2026-10-25): fix list. Your previous code is on this branch and the whole suite passed (244), but the run timed out before HANDOFF.md was written. Keep what works; change only what is listed; add a regression test for each; write HANDOFF.md FIRST (update it at the end). Run the full suite at most twice (it takes about 70 s); iterate with `-k` on your own test files.

The Codex review (VERDICT: ISSUES) found:
1. **Engine-failure fallback** (`engine_speakerplacer.py` ~l.265) returns `_safe_fallback_layout(room)`; the brief requires the stub's layout (`backend.app.stubs.engine_stub.optimize(room)["layout"]`) with our metrics and the `"speakerplacer failed: ..."` warning. Keep `_safe_fallback_layout` only if the stub itself raises.
2. **Object avoidance leaves the wall** (~l.111): a moved speaker must stay on its wall: slide it along the wall line (constant inset from the wall) to the nearest position outside the object's footprint, within the room, keeping >= 0.5 ft from wall ends. If no such position exists on that wall, keep it in place and add a warning instead. Test with the demo room's sofa against the back wall and an LFE forced onto that wall.
3. **Treatment patches for floor/ceiling** (`acoustics.py` ~l.111): only wall and window reflections produce patches.
4. **Sabine double counting** (~l.123): when computing A, subtract each window/door/opening area from the wall it lies on (or count only the opening's area there), so A uses each piece of boundary once. Test: adding a window changes A by `area * (alpha_glass - alpha_wall)`, not by `area * alpha_glass`.
