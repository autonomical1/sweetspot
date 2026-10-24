# TESTING.md: test plan (orchestrator-owned)

Rule: **every component must pass its own tests, standalone, with mocks and fixtures, before it is integrated with anything.** Integration is then a sequence of small pairwise steps, not one big bang. Default `pytest` never touches the network; live tests are opt-in (`-m live`).

Units reminder: everything in the backend contract is decimal feet. Feet-and-inches (`7' 6"`) is display only. The iOS scan DTO is raw meters; conversion happens only in `backend/app/roomplan.py` (m -> ft) and the iOS AR layer (ft -> m).

## 1. Levels

| Level | What | Who runs it | Network |
|---|---|---|---|
| L0 | Unit tests (pure functions) | owner of the code | none |
| L1 | Contract tests: does an implementation satisfy `docs/API.md` shapes and invariants | owner, against their module | none |
| L2 | Component standalone: the whole component runs with stubs/mocks/recorded data | owner | none |
| L3 | Pairwise integration: A with real B | pair of owners | local |
| L4 | End to end on the deployed stack with the real phone/browser | everyone | yes |
| L5 | Demo rehearsal and failure drills | everyone | yes |

**Standalone-ready gate** (a component may not enter L3 until all are true): L0 and L1 tests pass; L2 runs from a clean checkout in under 5 minutes with documented commands; fixtures it needs are committed; it has a stub/mock for each thing it depends on; it fails with a readable error, not a crash, when a dependency is down.

## 2. Test tooling and conventions
- `python -m pytest backend -q` is the orchestrator test command and must stay green on `master`. Markers: `live` (real Gemini/SerpApi/network, opt-in), `slow`.
- Shared fixtures in `fixtures/`: `room_rect.json` (15 x 12 x 9 ft room, listener 7.5, 3.6, 4.0 facing north), `room_demo.json`, `roomplan_sample.json` (real scan, from iOS), `serpapi_shopping_sample.json` (recorded response), `gemini_responses/*.json` (recorded and malformed), `phoneapp_context/sample_payloads/*` (API examples).
- Stub switches for every external dependency: `ENGINE_BACKEND=stub`, `PRODUCTS_BACKEND=stub`, `MATERIALS_BACKEND=mock`. With all three set the backend is a complete, deterministic **mock server**; the iOS and web developers use it from day one: `uvicorn backend.app.main:app --host 0.0.0.0`.
- Tests use `DATA_DIR` in a pytest `tmp_path`; a fake clock for session expiry; `httpx.MockTransport` for outbound HTTP; no sleeps.
- Contract tests live in `backend/tests/contract/` and take the implementation under test from env (`ENGINE_BACKEND=auto` runs the real `speakerplacer`), so the engine and products owners run the same tests the backend runs.

## 3. Per component

### 3.1 Contract, units, schemas (owner: backend)
- Every fixture validates against `schemas.py`; round-trip `Room -> json -> Room` is lossless.
- `units.py`: `m_to_ft(1.0)=3.28084`, `ft_to_m` inverse within 1e-9; `format_ft_in(7.5)=="7' 6\""`, `3.6 -> 3' 7"`, `0 -> 0' 0"`, rounding 11.6 in -> next foot, negative numbers; `parse_ft_in("7' 6\"")==7.5`.
- Rect builder: 4 walls + floor + ceiling, polygons inside `[0,width]x[0,height]x[0,length]`, wall normals consistent, default absorption on every surface, rejects non-positive or absurd sizes (<3 ft or >100 ft).

### 3.2 Backend core API (owner: backend)
Run with TestClient, all stubs. Cases:
- `/health`; `POST /sessions` returns a 6-char code and `pair_url`; `GET /sessions/{id}` status `waiting`; `POST /sessions/by-code` happy path, wrong code 404, case-insensitive; expiry after 30 min (fake clock) -> `expired`.
- `POST /rooms/rect` -> `GET /rooms/{id}` identical; with `session_id` the session becomes `ready` with `room_id`; unknown session id is rejected, a room without session works.
- `POST /rooms/demo` goes through the same store path and equals the fixture except ids.
- `PATCH /rooms/{id}/listener` moves the listener, 400 if outside the room.
- `optimize` persists the layout; `GET layout` returns it, 404 before; `score` returns metrics and takes <100 ms on the stub; the engine import failing falls back to the stub with a warning, not a 500.
- Products endpoint passes `budget` and the current layout; 404 if no layout yet; budget 0 or negative -> 422.
- Persistence: restart the app (new TestClient, same `DATA_DIR`) and rooms and layouts are still there; sessions are not (documented); a corrupt JSON file gives a clean 500 with `detail`, not a hang.
- Concurrency: 20 parallel `POST /rooms/rect` produce unique ids.
- OpenAPI schema renders (`/openapi.json`) and matches the endpoint table in `docs/API.md`.

### 3.3 Engine, `speakerplacer` (owner: engine teammate)
Standalone with no backend. L0/L1:
- Geometry: image-source for a known case (single wall, speaker and listener on a line: delay = (reflected path - direct path) / 1125 ft/s computed by hand in the test); mirror across each wall plane; reflection points lie on the wall and inside its polygon; points inside a door/window opening are rejected or flagged.
- Placement invariants on `room_rect.json`: six roles `L,R,C,LFE,Ls,Rs` present once each; all positions inside the room box with a wall margin; none inside an object box; L/R at 30 deg +-5 from the listener's facing, C at 0 +-2, surrounds 100-120 deg; left/right symmetric about the facing axis; deterministic (same input, same output); input dict is not mutated.
- Screen: width = 2 d tan(theta/2) for theta 36 deg with a hand-computed number; placed on the wall the listener faces.
- Sub modes: axial modes `1125/(2L)` for each dimension; Schroeder frequency formula sanity check.
- `score(room, layout)` agrees with the `metrics` returned by `optimize` for the same layout; runs in <100 ms on the fixture (timed, generous bound on slow machines).
- Degenerate rooms: tiny room, very long room, listener at a wall: returns a layout plus `warnings`, never raises.
- CLI: `python -m speakerplacer --room fixtures/room_rect.json --json` prints valid JSON matching the layout schema; the old `--length/--width` flags still work.
- Contract test file (`test_engine_contract.py`) is run by both the engine owner and the backend.

### 3.4 Products / SerpApi (owner: SerpApi teammate)
Standalone, no network by default:
- Parse the recorded Google Shopping response: title, price strings (`$1,299.00`, `$49`, missing price), link, thumbnail, source.
- `get_products(layout, budget)`: one or more items for each present role; `total <= budget` (strict); budget split front-weighted (C + L/R share > surrounds share); fewer roles than 6 works; budget too small returns the cheapest options plus a warning, not an exception.
- Cache: second identical call makes zero HTTP requests (MockTransport counts); cache file written under `data/cache/serpapi/`.
- Failure drills: HTTP 500, 429, timeout, empty `shopping_results`, malformed JSON -> falls back to cache then to the stub, with a readable `warnings` entry.
- `@live` smoke: one real query with `SERPAPI_KEY` returns >0 results (run once, results saved as fixture, never in the default run; mind the quota).

### 3.5 Materials / Gemini (owner: backend)
- Absorption table: every material x every band (125 to 4000 Hz) present and in (0, 1); source cited in file.
- Classifier against the mock: output matches `[{surface_id, material, confidence}]`; confidence in [0, 1].
- Robustness with recorded bad responses: not JSON, JSON with unknown material (`marble`), missing fields, extra prose around JSON, empty list, timeout -> each yields `unknown` and drywall absorption, never an exception.
- Image handling: oversize image (4000 px) is resized to long edge 1024; non-image bytes rejected with 400.
- `POST /rooms/{id}/materials` updates the room's surfaces: material and absorption change on exactly the classified surfaces; others untouched; calling twice is idempotent.
- `@live`: one real photo through the real Gemini API returns a valid enum value (opt-in).

### 3.6 RoomPlan converter (owner: backend; fed by iOS)
- Golden test on `post_rooms_request.example.json` and later the real `roomplan_sample.json`: counts of walls/doors/windows/floors/objects; each translation scaled m -> ft (x 3.28084, check a hand-computed value); wall corner polygons derived from `dimensions` and `transform` (4 corners, ft, a rotated wall checked by hand); door and window become kinds with a parent wall.
- Normalization: every wall direction within 2 deg of the x or z axis; the wall bounding box spans exactly (0..width, 0..length); floor at y=0; listener facing within 45 deg of north (-z) when a TV or sofa exists.
- Frame round trip: for every wall corner and object center, `R_y(yaw)*room_ft + offset` (API.md section 1a) reproduces the DTO world position (x 3.28084) within 0.01 ft; rotating the whole scan by any yaw and shifting it by any offset yields the same normalized room (within 0.01 ft) with a `frame` that absorbs the change.
- `frame_test_vectors.json` reproduced to 1e-4 by the backend helper.
- Listener: from the sofa (position at ear height 3.6 ft, facing from its transform); no sofa -> room centre facing the longest wall plus a warning; explicit `listener` in the request overrides.
- Ids: RoomPlan UUID strings preserved; synthetic `floor` and `ceiling` added when absent; photo targets cover walls, floor, ceiling and are stable across calls.
- Validation: malformed DTO (missing `transform`, 15 floats, NaN, wrong `format`) returns 422 with a clear `detail`; empty room rejected; huge values (cm instead of m) flagged in `warnings`.
- `tools/validate_dto.py file.json` validates a saved iOS export so the iOS developer can check a scan without the server.

### 3.7 iOS app (owner: iOS teammate)
Standalone without the backend using a **mock mode** (a flag that serves the files in `phoneapp_context/sample_payloads/`).
- XCTest unit tests: frame conversion reproduces every case in `phoneapp_context/sample_payloads/frame_test_vectors.json` to 1e-4 (points and directions); `flat(matrix)` column-major order and translation at elements 12-14; DTO builder on hand-made values (RoomPlan types cannot be constructed directly, so put the conversion behind plain structs); ft -> m (x 0.3048) and ft-in formatting identical to the backend table above; QR parsing (`https://x.tech/pair/s_abc` -> `s_abc`, junk -> nil, wrong host rejected); multipart body builder byte-for-byte for a tiny JPEG; JPEG resize keeps long edge 1024 and size <300 KB; URLProtocol-mocked client: success, 404, 500, timeout, expired session.
- `tools/validate_dto.py` on every exported scan file before sending it to the backend person.
- Device checklist is in `phoneapp_context/05_checklist_and_open_questions.md`. Plus: airplane mode mid-upload shows an error and the saved scan can be re-sent; scan with no sofa works; app killed mid-photo resumes; second scan replaces the first.
- AR: debug wireframe of the scanned walls overlays the real room within a few inches; marker at a known corner lands on the corner (inch-level error is acceptable, a foot is not).

### 3.8 Web viewer (owner: web teammate)
Standalone against the backend running with all stubs (the mock server) or a saved JSON of each response.
- Renders the fixture room: wall/floor planes, listener, six speakers, screen; units shown as feet and inches (`7' 6"`), never raw decimals.
- Drag a speaker -> throttled `POST /score` (max about 10 per second, latest wins), metrics update; `POST /score` failure keeps the last good state and shows a banner.
- Pairing page: shows QR and code from `POST /sessions`, polls `GET /sessions/{id}` every 1 to 2 s, switches to the viewer when `ready`, stops polling when expired and offers a refresh. No WebSocket anywhere.
- Products panel renders prices, links, total vs budget; empty and error states.
- Works from the same origin as the API (no CORS): load via the backend or Caddy, not `file://`.

### 3.9 Deploy (owner: backend)
- `docker compose config` valid; image builds from clean checkout; container starts with env from `.env`; `data/` is a volume.
- `deploy/smoke.sh <base_url>`: `/health`, `POST /sessions`, `POST /rooms/demo`, `optimize`, `products`, `materials` (mock), TLS certificate valid and not expiring, response times printed. Run it against `localhost`, then the Vultr domain, then from the phone's cellular network (a different network path than the laptop).
- Cold restart: reboot the VPS or `docker compose restart`; rooms persist, the site is back in under a minute, Caddy re-uses its certificate.

## 4. Integration steps (only after each side is standalone-ready)
1. **I1 backend + real engine:** `ENGINE_BACKEND=auto` runs the engine contract tests through HTTP.
2. **I2 backend + real products:** `PRODUCTS_BACKEND=auto`, offline with recorded data, then one live call.
3. **I3 backend + Gemini:** one real photo via the real API behind `/materials`.
4. **I4 backend + web viewer:** pair with a browser, fixture room, drag/score loop.
5. **I5 backend + iOS:** LAN first (debug build), then the deployed HTTPS URL; demo room, saved scan, live scan, photos.
6. **I6 AR overlay:** shared-session test, then two-corner fallback.
7. **L4 end to end:** `tools/e2e.py <base_url>` scripts the whole API path with the demo room and the sample scan; then the full manual run: laptop QR -> phone scan -> web viewer -> AR -> shopping list.
8. **L5 rehearsal x3 with a timer**, and the failure drills: Gemini key removed, SerpApi quota exhausted, Wi-Fi off (phone on hotspot), live scan fails (switch to the saved scan), backend restarted mid-demo, browser refresh mid-demo.

## 5. Schedule (deadline 2026-10-25 11:30)
| By | Gate |
|---|---|
| 18:00 | Contract frozen; mock server (all stubs) running; iOS and web can develop against it |
| 21:00 | Every component standalone-ready (section 1 gate) |
| 21:00 to 01:00 | I1 to I5 pairwise integration |
| 01:00 to 03:00 | I6 AR attempt, L4 end to end; decide AR keep/cut by 03:00 |
| 03:00 to 07:00 | Sleep |
| 07:00 to 09:30 | Fixes only, L5 rehearsals x3 |
| 09:30 | Feature freeze; submission text, demo video backup |
| 10:30 | Submit; 11:30 hard deadline |

## 6. Who runs what
| Component | Owner | Command |
|---|---|---|
| Backend, converter, materials, contract tests | backend (Neel + Codex) | `python -m pytest backend -q` |
| Engine | engine teammate | `python -m pytest speakerplacer -q` and `ENGINE_BACKEND=auto python -m pytest backend/tests/contract -q` |
| Products | SerpApi teammate | `python -m pytest products -q` and `PRODUCTS_BACKEND=auto python -m pytest backend/tests/contract -q` |
| iOS | iOS teammate | Xcode unit tests + `python tools/validate_dto.py <file>` + device checklist |
| Web | web teammate | their own tests + mock server |
| Smoke / E2E | backend | `bash deploy/smoke.sh <url>`, `python tools/e2e.py <url>` |
