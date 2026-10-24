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
