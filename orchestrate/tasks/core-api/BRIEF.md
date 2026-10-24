# core-api: FastAPI backend core

## Goal
A runnable FastAPI app that serves the REST endpoints in docs/API.md section 6 (except photos, materials, and the scan conversion) using JSON-file storage, with engine and products behind adapters that fall back to deterministic stubs. With all stubs on, this app is the "mock server" the iOS and web teammates build against.

## Read first
docs/API.md (all), docs/TESTING.md sections 2, 3.1, 3.2, backend/app/schemas.py, backend/app/store.py (shared, do NOT edit), backend/tests/conftest.py (shared, do NOT edit), fixtures/room_rect.json.

## Design decisions this brief encodes (do not change)
- Units: decimal feet everywhere; `units.py` provides `m_to_ft`, `ft_to_m`, `format_ft_in(feet) -> "7' 6\""` (nearest inch, 11.6 in rolls to next foot, negatives get a leading `-`) and `parse_ft_in`.
- REST only, no WebSocket. No CORS. No auth.
- Sessions in memory (module-level dict) with an injectable clock (`sessions.now: Callable[[], float]`) so tests can fake time; 30 min expiry; code = 6 chars from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, looked up case-insensitively.
- Rooms/layouts/photos persist via `backend/app/store.py`. Ids from `store.new_id("r")` / `("s")`.
- Engine/products are optional external modules: `speakerplacer` and `products` (repo root packages that may not exist yet). Adapters load them with `importlib` when `ENGINE_BACKEND`/`PRODUCTS_BACKEND` is `auto` (default); on ImportError or `stub` use `backend/app/stubs/*`. If the real module raises at runtime, fall back to the stub and add a `"warnings"` entry (never a 500).

## Deliverables
1. `units.py` as above.
2. `sessions.py`: create, get (status `waiting|ready|expired`), link room, by-code lookup.
3. `rooms.py` (APIRouter): rect builder (4 walls `wall_n|s|e|w`, `floor`, `ceiling`, default drywall absorption on all six octave bands {"125":0.05,"250":0.06,"500":0.08,"1000":0.09,"2000":0.09,"4000":0.09}; polygons exactly as in fixtures/room_rect.json; default listener x=width/2, y=3.6, z=0.7*length, facing [0,-1]; reject dims <3 or >100 ft with 422) and endpoints: `POST /rooms/rect`, `POST /rooms/demo`, `GET /rooms/{id}`, `PATCH /rooms/{id}/listener` (400 if outside room box), `GET /rooms/{id}/photo-targets`, `POST /rooms/{id}/optimize`, `POST /rooms/{id}/score`, `GET /rooms/{id}/layout`, `GET /rooms/{id}/products?budget=`, and `POST /rooms`:
   - body is a full Room JSON -> validate and store it;
   - body has `captured_room` -> `try: from .roomplan import convert_dto` (a later task adds it; signature `convert_dto(captured_room: dict, *, room_id: str, session_id: str|None, budget: float|None, listener: dict|None) -> Room`); on ImportError return 501 with detail "scan conversion not available yet".
   - If `session_id` is given: unknown -> 404, expired -> 410, else mark session ready with the room_id.
   - `photo-targets`: generic over any Room: up to the 4 largest walls plus `floor` and `ceiling`; labels relative to the listener facing ("Front wall", "Back wall", "Left wall", "Right wall", "Floor", "Ceiling"); stable order and ids.
4. `engine.py` adapter: `run_optimize(room: Room, options: dict|None) -> dict` and `run_score(room: Room, layout: dict) -> dict` (returns `{"layout","metrics"}` / `{"metrics"}` per docs/API.md section 2/3); `optimize` saves via `store.save_layout`.
5. `products.py` adapter: `run_products(layout: dict, budget: float) -> dict` per docs/API.md section 4; `/products` uses the room's saved layout (404 if none) and `budget` query param (default room.budget; <=0 -> 422).
6. `stubs/engine_stub.py`: deterministic, geometry-sane 5.1 layout for any rectangular Room: L/R about 30 deg either side of the listener facing at the front, C on the facing axis, surrounds about 110 deg, LFE near a front corner; all positions inside the room box with >= 1 ft wall margin, speaker height 3.6 ft (surrounds 5 ft), `aim` at the listener; screen on the wall the listener faces (width 2*d*tan(18 deg) with d the listener-to-wall distance, 16:9, centre height 4.5 ft); metrics `{"score": 0.5, "reflections": [], "treatment_patches": [], "sub_modes": {}, "warnings": ["stub engine"]}`. `score` returns the same metrics shape and must be fast (<10 ms).
7. `stubs/products_stub.py`: deterministic fake items per role present in the layout (+ one screen/projector item) whose prices sum to <= budget.
8. `main.py`: `create_app()` and module-level `app`; includes sessions routes (`POST /sessions`, `GET /sessions/{id}`, `POST /sessions/by-code`), `/health`, the rooms router, and optionally `from .materials_router import router` inside try/except ImportError (another task adds it). No other imports of modules you do not own.
9. `fixtures/room_demo.json`: an 18 x 13 ft room (height 9) with objects `sofa` (centered at the listener, against the back wall), `television` (front wall), a window on one side wall; valid against schemas.Room; `POST /rooms/demo` returns it with a fresh `room_id`, saved through `store`.
10. Tests (pytest, TestClient, all stubs, DATA_DIR via the shared `data_dir` fixture): cover every bullet in docs/TESTING.md 3.1 and 3.2 that applies (units formatting table, session lifecycle with fake clock, rect validation, demo, persistence across new app instances, 404/410/422 cases, listener PATCH, optimize/score/layout/products flow, photo-targets, adapter fallback when the real module raises, `/openapi.json` contains the paths above). Tests must not use the network or sleeps.

## Done when
`python -m pytest backend -q` passes on this branch; `uvicorn backend.app.main:app` starts; every endpoint above responds per docs/API.md; no edits outside OWNS.txt.

## Out of scope
Photos, materials, Gemini, the real scan conversion, deployment, static web hosting, WebSockets, auth. Do not create `roomplan.py`, `materials*.py`, or edit shared files (store.py, schemas.py, conftest.py, requirements.txt, API.md). If a dependency is missing or the contract is wrong, say so in HANDOFF.md under `## Design questions`.

---
## RETRY 1 (2026-10-24): fix list. Keep everything that already works; change only what is listed. Tests must stay green and gain regression tests for each item.

Your previous result is on this branch. The Codex review (VERDICT: ISSUES) and the orchestrator's code inspection found:

1. **Listener/facing validation (rooms.py `build_rect`, `POST /rooms`, `PATCH listener`).** Put one shared helper in rooms.py, e.g. `validate_listener(position, facing, dims) -> (position, facing)`, and use it in all three places (for `POST /rooms` apply it to the `listener` of a full Room JSON). Rules: `position` must be exactly 3 finite floats with `0<=x<=width`, `0<=y<=height`, `0<=z<=length`; `facing` must be exactly 2 finite floats, not both zero; **normalize facing to a unit vector** before storing (decision: lenient normalize, not reject). Empty lists are invalid (422), not "use the default"; only `None` means default. Violations: 422 for malformed shape/NaN/zero facing, 400 for a position outside the room (keep the existing PATCH behaviour). Add tests: `[1,2]`, `[nan,1,1]`, outside box, `[0,0]`, `[3,4]` becomes `[0.6,0.8]`, and a malformed listener in a full-Room `POST /rooms`.
2. **`_wall_area` (rooms.py ~l.144).** Replace the two-edge-length product with the true planar polygon area in 3D (shoelace via the norm of the summed cross products), so skewed or non-rectangular wall polygons rank correctly. Test: a trapezoid wall vs a rectangle where the two-edge shortcut picks wrong.
3. **`fixtures/room_demo.json` sofa.** Sofa must be against the back wall: back edge on `z=13`. Set sofa `center` to `[9, 1.5, 12.0]` with `size [7,3,2]`, put the TV flush on the front wall (`center z = 0.15`, size depth `0.3`), and set the listener to `position [9, 3.6, 11.5]`, facing `[0,-1]`. Add a test asserting the sofa's back edge equals the room length and the listener is inside the sofa's footprint.
4. **Demo fixture materials/absorption.** Answer to your design question: use typical published octave-band values for the demo fixture, not `unknown`. Floor (`hardwood`): `{"125":0.15,"250":0.11,"500":0.10,"1000":0.07,"2000":0.06,"4000":0.07}`. Window (`glass`): `{"125":0.35,"250":0.25,"500":0.18,"1000":0.12,"2000":0.07,"4000":0.04}`. Drywall stays as is. These are approximate textbook values; the materials task will own the authoritative table, so add a code comment saying the fixture values are provisional and must match `materials.ABSORPTION` later. Test: every surface's absorption has the six band keys, and hardwood/glass differ from drywall.
5. **Real engine output not validated (engine.py).** If the real `speakerplacer` returns without raising but its result does not validate (use `schemas.LayoutResult` for `optimize`; for `score` require a dict with a `metrics` dict), treat it as a failure: fall back to the stub and append `"engine fallback: invalid result"` to `metrics.warnings`. Test with a fake backend module that returns garbage.
6. **Guarded import hides real errors (main.py).** `try: from .materials_router import router ... except ImportError` would silently drop the materials routes if that module exists but fails on a missing dependency. Replace with `importlib.util.find_spec("backend.app.materials_router")`: if the spec is None, skip; otherwise import normally and let real errors raise. Same pattern for the `roomplan` import in rooms.py (use `find_spec`; only a missing module yields 501). Test: with the module absent, the app starts and `POST /rooms` with `captured_room` returns 501.

Also add to HANDOFF.md under `## Decisions`: the choices above. Do not touch shared files (store.py, schemas.py, conftest.py, requirements.txt, API.md, pytest.ini).
