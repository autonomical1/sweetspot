# API / module contracts (orchestrator-owned; changes after plan approval need user OK)

Conventions: meters, y-up, right-handed (RoomPlan = three.js). Floor plane is x-z. "north" = -z, "east" = +x. Rectangular rooms: origin at the north-west floor corner, `width` along +x, `length` along +z, `height` along +y. All ids are strings. JSON keys are snake_case.

## 1. Room JSON (the shared contract)

Source of truth in code: `backend/app/schemas.py` (pydantic v2). Fixture: `fixtures/room_rect.json`.

```json
{
  "schema_version": 1,
  "room_id": "r_abc123",
  "session_id": "s_xyz789 | null",
  "source": "rectangle | roomplan",
  "dimensions": {"width": 12.0, "length": 15.0, "height": 2.7},
  "surfaces": [
    {"id": "wall_n", "kind": "wall | floor | ceiling | door | window | opening",
     "polygon": [[x,y,z], ...],
     "material": "drywall | glass | brick | carpet | hardwood | tile | curtain | unknown",
     "absorption": {"125": 0.05, "250": 0.06, "500": 0.08, "1000": 0.09, "2000": 0.09, "4000": 0.09}}
  ],
  "objects": [
    {"id": "obj_sofa", "category": "sofa | television | storage | table | other",
     "center": [x,y,z], "size": [w,h,d], "rotation_y": 0.0}
  ],
  "listener": {"position": [x, 1.1, z], "facing": [fx, fz]},
  "budget": 1500.0,
  "captured_room": null
}
```
- Rectangle builder creates 4 walls (`wall_n|s|e|w`), `floor`, `ceiling`, default drywall absorption, and no objects. `listener.facing` is a unit vector in x-z (north = [0,-1]).
- RoomPlan converter fills the same shape from a `CapturedRoom` JSON (stored verbatim in `captured_room`). Listener comes from the sofa transform (seat center, 1.1 m ear height) with fallback to room center facing the longest wall.
- `absorption` is always present on every surface (default table keyed by material in `backend/app/materials.py`).

## 2. Layout and metrics (engine output)

```json
{
  "layout": {
    "speakers": [{"role": "L|R|C|LFE|Ls|Rs", "position": [x,y,z], "aim": [x,y,z]}],
    "screen": {"wall_id": "wall_n", "center": [x,y,z], "width": 1.95, "height": 1.1}
  },
  "metrics": {
    "score": 0.0,
    "reflections": [{"speaker": "L", "surface_id": "wall_w", "delay_ms": 4.2, "level_db": -8.1, "point": [x,y,z]}],
    "treatment_patches": [{"surface_id": "wall_w", "center": [x,y,z], "size": [w,h]}],
    "sub_modes": {"schroeder_hz": 0.0, "axial_modes_hz": [], "sub_position": [x,y,z]},
    "warnings": []
  }
}
```
`screen` may be null. Minimum viable engine output is `layout.speakers` only; every other field may be empty.

## 3. Engine module (owner: engine teammate; package `speakerplacer/` at repo root)

```python
def optimize(room: dict, options: dict | None = None) -> dict   # returns {"layout":..., "metrics":...}
def score(room: dict, layout: dict) -> dict                      # returns {"metrics":...}, target < 100 ms
```
Pure functions, no I/O, no network. `room` is section 1. Must accept a plain rectangle room (4 walls + floor + ceiling) and ignore fields it does not use. CLI for testing: `python -m speakerplacer --room fixtures/room_rect.json [--layout layout.json] --json`; existing `--length/--width/--listener/--facing` flags may stay as shortcuts. Backend loads it with `importlib`; if import fails it falls back to `backend/app/stubs/engine_stub.py`.

## 4. Products module (owner: SerpApi teammate; package `products/` at repo root)

```python
def get_products(layout: dict, budget: float, *, serpapi_key: str | None = None) -> dict
# -> {"budget": 1500.0, "total": 1432.5,
#     "items": [{"role": "L|R|C|LFE|Ls|Rs|screen|projector", "title": str, "price": float,
#                "currency": "USD", "link": str, "thumbnail": str | None, "source": str}]}
```
Calls Google Shopping via SerpApi, front-weighted budget split (center + L/R largest, then sub, then surrounds), caches responses on disk under `data/cache/serpapi/` keyed by query. Falls back to `backend/app/stubs/products_stub.py` if import fails.

## 5. Materials (owner: backend)

```python
# backend/app/materials.py
MATERIALS = ["drywall","glass","brick","carpet","hardwood","tile","curtain","unknown"]
ABSORPTION: dict[str, dict[str, float]]   # material -> octave band -> alpha (source cited in file)
def classify_materials(photos: list[dict]) -> list[dict]
# photos: [{"surface_id": str, "image_bytes": bytes, "mime": "image/jpeg"}]
# returns [{"surface_id": str, "material": str, "confidence": float}]
```
Backend implementations behind one interface: Gemini API (default, `GEMINI_API_KEY`), mock (tests, `MATERIALS_BACKEND=mock`). Gemini is asked for structured JSON; invalid output falls back to `unknown` / drywall.

## 6. HTTP endpoints (REST only, no WebSocket; JSON unless noted)

| Method + path | Request | Response |
|---|---|---|
| `GET /health` | | `{"ok": true}` |
| `POST /sessions` | | `{"session_id","code","expires_at","pair_url"}` (`code` is 6 chars, `pair_url` = `https://<DOMAIN>/pair/{session_id}`) |
| `GET /sessions/{id}` | | `{"session_id","status":"waiting\|ready\|expired","room_id":null\|str}` |
| `POST /sessions/by-code` | `{"code"}` | `{"session_id"}` |
| `POST /rooms/rect` | `{"width","length","height?","listener?","facing?","budget?","session_id?"}` | Room JSON (section 1) |
| `POST /rooms` | Room JSON or `{"captured_room": {...}, "session_id?","budget?"}` (RoomPlan export) | Room JSON |
| `POST /rooms/demo` | `{"session_id?"}` | Room JSON from `fixtures/room_demo.json` through the same store path |
| `GET /rooms/{id}` | | Room JSON |
| `PATCH /rooms/{id}/listener` | `{"position","facing"}` | Room JSON |
| `POST /rooms/{id}/photos` | multipart: `surface_id`, `file` | `{"stored": true}` |
| `POST /rooms/{id}/materials` | `{}` (classifies stored photos) | `{"surfaces":[{"surface_id","material","confidence"}]}`; also updates room absorption |
| `POST /rooms/{id}/optimize` | `{"options?": {}}` | `{"layout","metrics"}` (saved as the room's current layout) |
| `POST /rooms/{id}/score` | `{"layout"}` | `{"metrics"}` |
| `GET /rooms/{id}/layout` | | latest `{"layout","metrics"}` or 404 |
| `GET /rooms/{id}/products?budget=1500` | | products result (section 4) for the current layout |

Errors: HTTP status + `{"detail": "..."}`. Unknown ids -> 404. Sessions expire after 30 min. `POST /rooms` with `session_id` marks that session `ready` and sets `room_id`. CORS: none needed (web app is served from the same origin by Caddy).

## 7. Storage

`data/rooms/{room_id}.json` (room), `data/rooms/{room_id}.layout.json`, `data/photos/{room_id}/{surface_id}.jpg`, sessions in an in-memory dict. `DATA_DIR` env overrides `data/`. Ids: `secrets.token_urlsafe(8)` prefixed `r_` / `s_`.

## 8. Env vars

`DATA_DIR`, `DOMAIN`, `GEMINI_API_KEY`, `SERPAPI_KEY`, `MATERIALS_BACKEND` (`gemini|mock`), `ENGINE_BACKEND` (`auto|stub`), `PRODUCTS_BACKEND` (`auto|stub`). Never committed; `.env.example` lists them.

## 9. Repo layout

```
backend/app/{main.py,schemas.py,store.py,sessions.py,rooms.py,materials.py,engine.py,products.py,roomplan.py,stubs/}
backend/tests/
fixtures/{room_rect.json,room_demo.json,roomplan_sample.json}
speakerplacer/   (engine teammate)    products/   (SerpApi teammate)
deploy/{Dockerfile,docker-compose.yml,Caddyfile}
```
