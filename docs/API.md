# API / module contracts (orchestrator-owned; changes after plan approval need user OK)

Conventions: **feet** (decimal feet, so 7.5 = 7 ft 6 in), y-up, right-handed. Feet-and-inches strings (`7' 6"`) are display-only and are produced at the UI edge by `format_ft_in` (`backend/app/units.py`); JSON never carries them. RoomPlan/ARKit/three.js speak meters, so conversion happens at exactly two places: backend `roomplan.py` (m -> ft, x 3.28084) and the iOS AR layer (ft -> m, x 0.3048). The iOS scan DTO stays in raw meters. REST only: GET/POST/PATCH, no WebSocket anywhere. Testing: `docs/TESTING.md`. Floor plane is x-z. "north" = -z, "east" = +x. Rectangular rooms: origin at the north-west floor corner, `width` along +x, `length` along +z, `height` along +y. All ids are strings. JSON keys are snake_case.

## 1. Room JSON (the shared contract)

Source of truth in code: `backend/app/schemas.py` (pydantic v2). Fixture: `fixtures/room_rect.json`.

```json
{
  "schema_version": 1,
  "units": "ft",
  "room_id": "r_abc123",
  "session_id": "s_xyz789 | null",
  "source": "rectangle | roomplan",
  "dimensions": {"width": 12.0, "length": 15.0, "height": 9.0},   // bounding box of the outline
  "outline": [[0,0],[12,0],[12,15],[0,15]],                       // floor polygon [x,z] in feet, room frame; null/absent = rectangle from dimensions
  "surfaces": [
    {"id": "wall_n", "kind": "wall | floor | ceiling | door | window | opening",
     "polygon": [[x,y,z], ...],
     "material": "drywall | glass | brick | carpet | hardwood | tile | curtain | unknown",
     "absorption": {"125": 0.05, "250": 0.06, "500": 0.08, "1000": 0.09, "2000": 0.09, "4000": 0.09}}
  ],
  "objects": [
    {"id": "obj_sofa", "category": "sofa | television | storage | table | other",
     "center": [x,y,z], "size": [w,h,d], "rotation_y": 0.0}      // rotation_y in DEGREES about +y
  ],
  "listener": {"position": [x, 3.6, z], "facing": [fx, fz]},
  "budget": 1500.0,
  "warnings": [],                                       // e.g. "no sofa detected; listener at room centre"
  "frame": {"yaw_deg": 0.0, "offset": [0.0, 0.0, 0.0]},   // scanned rooms only, else null
  "captured_room": null
}
```
- **Outline (non-rectangular rooms, decided 2026-10-25).** `outline` is the floor polygon as >= 3 `[x, z]` points in feet in the room frame, in order, simple (no self-intersection), every edge >= 0.5 ft, all coordinates >= 0 (the bounding box starts at the origin). `dimensions` is always its bounding box (width = max x, length = max z), so older clients keep working. `null`/absent means the rectangle `[0,0],[w,0],[w,l],[0,l]`; every consumer uses one helper (`room_outline(room)`) so rectangles behave exactly as before. Each outline edge is a wall surface (`wall_0..wall_n-1` for polygon rooms built by the backend; scanned rooms keep the RoomPlan UUID ids), walls need not be axis-aligned, and scanned rooms still use `frame` so the dominant edges are axis-aligned. The listener, every speaker, every object centre and the screen centre must lie inside the outline (point-in-polygon with a 0.1 ft margin); the validators and the engine adapter enforce it. Scan conversion builds the outline from the floor polygon corners when present, else by chaining the wall segments into a closed loop within 0.5 ft tolerance, else falls back to the wall bounding rectangle with the warning `scan incomplete; using bounding box`.
- Rectangle builder creates 4 walls (`wall_n|s|e|w`), `floor`, `ceiling`, default drywall absorption, and no objects. `listener.facing` is a unit vector in x-z (north = [0,-1]).
- RoomPlan converter fills the same shape from the iOS export DTO `sweetspot.roomplan.v1` (spec: `phoneapp_context/01_roomplan_capture.md`, example: `phoneapp_context/sample_payloads/post_rooms_request.example.json`), stored verbatim in `captured_room`. Surface/object `transform` is 16 floats column-major (translation = elements 12-14), `dimensions` = [w,h,d]. For scanned rooms the converter **normalizes** the scan into the standard room frame (walls axis-aligned, wall bounding box from (0,0,0) to (width,height,length), floor at y=0, listener facing roughly north = -z) and records how to get back to the scan's world frame in `frame` (section 1a). It uses the RoomPlan UUID strings as surface ids, plus synthetic `floor` and `ceiling`. Listener comes from the sofa transform (seat center, 3.6 ft ear height) with fallback to the room centre (floor-polygon centroid when a floor exists) facing the midpoint of the farthest wall.
- `absorption` is always present on every surface (default table keyed by material in `backend/app/materials.py`).

## 1a. Room frame vs scan world frame (`frame`)

All room, layout and metrics coordinates are in the **room frame** (feet; box from the origin; walls axis-aligned). Rectangular and demo rooms have `frame: null`: they exist only in the room frame. Scanned rooms carry `frame = {yaw_deg, offset}` (offset in feet) mapping the room frame to the ARKit/RoomPlan world frame of the scan session:

```
t = radians(yaw_deg)
world_ft.x =  cos(t)*x + sin(t)*z + offset.x
world_ft.y =  y                   + offset.y
world_ft.z = -sin(t)*x + cos(t)*z + offset.z
world_m    =  world_ft * 0.3048
```
That is a right-handed rotation about +y (`simd_quatf(angle: t, axis: [0,1,0])`; +90 deg maps +x to -z) followed by the offset. Directions (`aim`, `facing`) rotate only. The converter applies the inverse (`room = R_y(-t) * (world - offset)`). Shared test vectors: `phoneapp_context/sample_payloads/frame_test_vectors.json`; backend and iOS tests must both reproduce them. Object `rotation_y` uses the same rotation convention, in degrees.

## 2. Layout and metrics (engine output)

```json
{
  "layout": {
    "speakers": [{"role": "L|R|C|LFE|Ls|Rs", "position": [x,y,z], "aim": [x,y,z]}],
    "screen": {"wall_id": "wall_n", "center": [x,y,z], "width": 6.4, "height": 3.6}
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

**Integration note (2026-10-24):** the teammate package exposes `optimize_layout(polygon_m, listener_m, layout, facing, ...)` (2D, metres, north = +y, roles front/surround/bass, no center model) rather than the functions below. `backend/app/engine_speakerplacer.py` adapts it to this contract (center placed geometrically, one LFE, metrics from `backend/app/acoustics.py`); the backend and the contract tests use that adapter.

```python
def optimize(room: dict, options: dict | None = None) -> dict   # returns {"layout":..., "metrics":...}
def score(room: dict, layout: dict) -> dict                      # returns {"metrics":...}, target < 100 ms
```
Pure functions, no I/O, no network. All lengths in feet; speed of sound 1125 ft/s. `room` is section 1. Must accept a plain rectangle room (4 walls + floor + ceiling) and ignore fields it does not use. CLI for testing: `python -m speakerplacer --room fixtures/room_rect.json [--layout layout.json] --json`; existing `--length/--width/--listener/--facing` flags may stay as shortcuts. Backend loads it with `importlib`; if import fails it falls back to `backend/app/stubs/engine_stub.py`.

## 4. Products module (owner: SerpApi teammate; package `products/` at repo root)

```python
def get_products(layout: dict, budget: float, *, serpapi_key: str | None = None) -> dict
# -> {"budget": 1500.0, "total": 1432.5,
#     "items": [{"role": "L|R|C|LFE|Ls|Rs|screen|projector", "title": str, "price": float,
#                "currency": "USD", "link": str, "thumbnail": str | None, "source": str,
#                # optional (real catalog; the stub may omit them):
#                "seller": str | None,
#                "specs": {name: str},          # parsed listing specs, e.g. {"power_w": "100W", "form_factor": "bookshelf"}
#                "dimensions": {"width": ft, "height": ft, "depth": ft,
#                               "source": "listing|default"} | None,   # for AR sizing; feet like everything else
#                "pair_with": "L|R|Ls|Rs" | None,                       # set on both roles covered by one (Pair) listing
#                "alternatives": [{"title","price","link","seller","thumbnail": null,"source",
#                                  "specs","dimensions","price_delta": float}]}],  # up to 3 swap candidates per item
#     "warnings": [str]}   # optional: omitted roles, expansion skipped/timed out, stale data
```
Files: `products/catalog.py` and `products/search.py` (teammate code: SerpApi fetcher, spec parser, SQLite search, Gemini catalog expansion; edit only with their agreement), `products/av_prices.db` (seed price database, committed), `products/__init__.py` exports `get_products` (backend-owned recommender in new modules under `products/`).
Behaviour (decided 2026-10-24, see DECISIONS.md):
- Database first. Working copy at `AV_DB`, default `$DATA_DIR/av_prices.db`, seeded by copying `products/av_prices.db` when missing (the repo copy is never written).
- Listings considered: newest fetch per query, `category_ok = 1`, condition `new`, non-empty link, price not below 25% of the median price of the same query's listings.
- Roles -> categories: L R C Ls Rs -> `speaker` (fronts prefer floorstanding/bookshelf, surrounds bookshelf), LFE -> `subwoofer`; `layout.screen` set -> `screen` (`projection_screen`, diagonal near the layout screen size) and `projector`; no screen -> `projector` only.
- Budget: front-weighted shares C 3, L 2, R 2, LFE 2, Ls 1, Rs 1, screen 1, projector 1; per role pick the best price-to-performance listing within its share, then a second pass upgrades with the leftover. `total <= budget` always; a role that cannot be filled is omitted with a warning.
- Alternatives (decided 2026-10-24): every item carries `alternatives`, up to 3 other listings for the same role (a different model, same filters), ordered by price ascending, with `price_delta` = alternative price minus the pick's price (negative = cheaper). Only alternatives that keep the whole list within budget if swapped in (`total - pick + alternative <= budget`) are listed; include at least one cheaper and one pricier when they exist. The second role of a pair listing (R, Rs; price 0) has `alternatives: []`: swap the pair through the first role (L, Ls), whose alternatives are pair listings that cover both roles.
- Variety (decided 2026-10-24): the front stage L, R and C is one matched model family (C uses the same brand and series as L/R when such a listing exists, otherwise its own best pick). The surround pair (Ls, Rs) must be a different model from the fronts when an eligible different model exists with quality within 15% of the best eligible one; otherwise the same model is allowed. LFE, screen and projector pick independently.
- **Complete home theater (decided 2026-10-25).** Besides the speaker roles the result includes, in this order after the speakers: `receiver`, then the display (`projector` + `screen`, or a single `tv`), then `mount` (projector ceiling mount, only with a projector) and `hdmi_cable`. `speaker_wire` is included only when a decent listing exists. Roles: `L|R|C|LFE|Ls|Rs|receiver|projector|screen|tv|mount|hdmi_cable|speaker_wire`.
- Speaker roles (L R C Ls Rs) accept PASSIVE speakers only: exclude listings whose title or specs say bluetooth, wireless, wi-fi, airplay, usb, powered, active, computer, desktop, gaming, portable, smart, party, karaoke, soundbar, alexa, sonos. `LFE` accepts powered subwoofers.
- Bundles: a listing may cover several roles (pair = L+R or Ls+Rs, "pair + center" = L+R+C, "5.1 home theater system" = L R C Ls Rs and the subwoofer). Every covered role gets an item with the same title/link; the first covered role in the order C, L, R, LFE, Ls, Rs carries the price, the others have price 0 and `included_in: "<that role>"`. `pair_with` stays for plain pairs. Bundle alternatives swap the whole bundle through the first covered role.
- Receiver: `receiver` item from category `av_receiver`; exclude listings whose title says manual, cover, remote, case, "for parts", "non working", or price below 150 USD; amplified channels (leading number of the `channels` label such as `5.2` -> 5, or `channel_count - 2`) must be >= the number of non-LFE speaker roles; when the display is a 4K projector (resolution >= 2160) the receiver must not be a known 1080p-only model (neutral when unknown). Share 3.
- Display: default is projector + screen. A `tv` replaces both only if a TV (category `display`, diagonal >= 0.9 x the layout screen diagonal, passes the usual filters) costs no more than the combined projector + screen share of the budget; otherwise projector + screen. TVs are never alternatives of projector items. The layout's `screen` placement is unchanged either way (the `tv` item carries `dimensions`).
- Shares (relative): receiver 3, projector 3, C 3, L 2, R 2, LFE 2, Ls 1, Rs 1, screen 1, mount 0.5, hdmi_cable 0.5, tv = projector + screen. Roles that cannot be filled within their cap are omitted with a warning, as before.
- Pairs: one listing whose title says pair covers L+R (or Ls+Rs): first role carries the price, second role gets price 0, same title/link, both `pair_with` each other.
- Expansion: when a role's constraints match fewer than 3 listings and both `GEMINI_API_KEY` and `SERPAPI_KEY` are set, run the teammate expansion (Gemini finds products, SerpApi fetches, stored in the working DB), at most once per category per request and within `PRODUCTS_EXPAND_DEADLINE_S` (default 20 s) total; past the deadline it continues in the background and the response uses what the DB has, with a warning. No keys -> DB only, with a warning.
- Never raises for data problems; `backend/app/products.py` still falls back to `backend/app/stubs/products_stub.py` on import failure or exception.

## 5. Materials (owner: backend)

```python
# backend/app/materials.py
MATERIALS = ["drywall","glass","brick","carpet","hardwood","tile","curtain","unknown"]
ABSORPTION: dict[str, dict[str, float]]   # material -> octave band -> alpha (approximate typical textbook values; no single cited source)
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
| `POST /rooms` | Room JSON or `{"captured_room": {DTO}, "session_id?","budget?","listener?"}` (iOS export; optional `listener` = `{position,facing}` in **scan world meters**, overrides sofa detection; the converter maps it into the room frame) | Room JSON (scanned: normalized, with `frame` and `warnings`) |
| `POST /rooms/polygon` | `{"points": [[x,z],...] (ft, >=3), "height?", "listener?", "facing?", "budget?", "session_id?"}` | Room JSON with `outline` (400 `detail` for self-intersecting, too-short edges or < 3 points) |
| `POST /rooms/demo` | `{"session_id?"}` | Room JSON from `fixtures/room_demo.json` through the same store path |
| `GET /rooms/{id}` | | Room JSON |
| `PATCH /rooms/{id}/listener` | `{"position","facing"}` | Room JSON |
| `GET /rooms/{id}/photo-targets` | | `[{"surface_id","kind","label"}]` (about 6 surfaces to photograph) |
| `POST /rooms/{id}/photos` | multipart: `surface_id`, `file` | `{"stored": true}` |
| `POST /rooms/{id}/materials` | `{}` (classifies stored photos) | `{"surfaces":[{"surface_id","material","confidence","applied"}]}` (`applied` is false when confidence < 0.5 and the surface kept its previous material); also updates room absorption |
| `POST /rooms/{id}/optimize` | `{"options?": {}}` | `{"layout","metrics"}` (saved as the room's current layout) |
| `POST /rooms/{id}/score` | `{"layout"}` | `{"metrics"}` |
| `GET /rooms/{id}/layout` | | latest `{"layout","metrics"}` or 404 |
| `GET /rooms/{id}/products?budget=1500` | | products result (section 4) for the current layout |

Errors: HTTP status + `{"detail": "..."}`. Unknown ids -> 404. Sessions expire after 30 min. `POST /rooms` with `session_id` marks that session `ready` and sets `room_id`. CORS: none needed (web app is served from the same origin by Caddy).

## 7. Storage

`data/rooms/{room_id}.json` (room), `data/rooms/{room_id}.layout.json`, `data/photos/{room_id}/{surface_id}.jpg`, sessions in an in-memory dict. `DATA_DIR` env overrides `data/`. Ids: `secrets.token_urlsafe(8)` prefixed `r_` / `s_`.

## 8. Env vars

`DATA_DIR`, `DOMAIN`, `GEMINI_API_KEY`, `SERPAPI_KEY`, `MATERIALS_BACKEND` (`gemini|mock`), `ENGINE_BACKEND` (`auto|stub`), `PRODUCTS_BACKEND` (`auto|stub`), `AV_DB` (products working DB path), `PRODUCTS_EXPAND_DEADLINE_S` (default 20). Never committed; `.env.example` lists them.

## 9. Repo layout

```
backend/app/{main.py,schemas.py,store.py,sessions.py,rooms.py,materials.py,engine.py,products.py,roomplan.py,stubs/}
backend/tests/
fixtures/{room_rect.json,room_demo.json,roomplan_sample.json}
speakerplacer/   (engine teammate)    products/   (SerpApi teammate)
deploy/{Dockerfile,docker-compose.yml,Caddyfile}
```
