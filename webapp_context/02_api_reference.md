# 02: API reference for the web app

Authoritative contract: `docs/API.md`. Same origin, relative URLs, JSON bodies (`Content-Type: application/json`). Errors are an HTTP status plus `{"detail": "..."}` (`sample_payloads/error_404.json`); always show `detail` to the user. Real responses for every call below are in `sample_payloads/`.

| Call | When | Typical time | Sample |
|---|---|---|---|
| `POST /sessions` | Pairing screen opens / New code | < 50 ms | `post_sessions.json` |
| `GET /sessions/{id}` | Every 1.5 s on the pairing screen | < 20 ms | `get_session_ready.json` |
| `POST /rooms/demo` `{}` | Use demo room | < 50 ms | `room_demo.json` |
| `POST /rooms/rect` | Rectangular room form | < 50 ms | (same shape as `room_demo.json`) |
| `GET /rooms/{id}` | Open/shared room, after pairing | < 20 ms | `room_demo.json`, `room_scanned.json` |
| `POST /rooms/{id}/optimize` `{}` | Auto after load, Optimize button | **about 8 s** | `optimize_demo.json` |
| `GET /rooms/{id}/layout` | Opening a room that may already have a layout | < 20 ms (404 if none) | (same shape as optimize) |
| `POST /rooms/{id}/score` `{"layout": ...}` | While dragging (throttled), on drop | **about 16 ms** + network | `score_demo.json` |
| `PATCH /rooms/{id}/listener` `{"position","facing"}` | Listener nudge (P2) | < 20 ms | returns the room |
| `GET /rooms/{id}/products?budget=1500` | Shop tab | stub: < 50 ms; real SerpApi: seconds (cached after) | `products_demo_stub.json` |
| `GET /rooms/{id}/photo-targets` | Room tab (shows which surfaces the phone photographed) | < 20 ms | `photo_targets_demo.json` |

## Details per call
- **`POST /sessions`** -> `{session_id, code, expires_at, pair_url}`. Put `pair_url` in the QR; show `code`; count down to `expires_at` (ISO 8601 UTC).
- **`GET /sessions/{id}`** -> `{session_id, status: "waiting"|"ready"|"expired", room_id}`. 404 = unknown or server restarted (sessions live in memory): treat like expired.
- **`POST /rooms/rect`** body: `{"width": 12, "length": 15, "height": 9, "listener": [x, y, z]?, "facing": [fx, fz]?, "budget": 1500?, "session_id": "..."?}` (feet). Dimensions must be 3..100 ft (422 otherwise). Omit `listener` to get the default seat.
- **`POST /rooms/{id}/optimize`**: body `{}` (optionally `{"options": {"absorption": 0.3}}`). Returns `{layout, metrics}` and saves it as the room's current layout. Show the progress overlay; ignore the response if the user changed rooms meanwhile (generation counter, as in `web/plot2d/plot.js`).
- **`POST /rooms/{id}/score`**: body `{"layout": {"speakers": [...], "screen": {...}|null}}` -> `{metrics}`. Send the **whole** current layout. Throttle to <= 10 requests/s, latest-wins (drop responses older than the newest request), one final call on drop. If it fails, keep the last good metrics and show a non-blocking banner.
- **`PATCH /rooms/{id}/listener`**: 400 if the position is outside the room, 422 for malformed input. Facing is normalized by the server.
- **`GET /rooms/{id}/products?budget=`**: 404 if no layout yet (run optimize first); 422 if budget <= 0. Shape: `{budget, total, items: [{role, title, price, currency, link, thumbnail, source}]}`; roles `L R C LFE Ls Rs screen projector`. Until the SerpApi module is merged the backend returns stub items titled "Demo ..." (`source: "stub"`): show them with a "sample data" badge.

## Not for the web app
`POST /rooms` (scan upload), `POST /rooms/{id}/photos`, `POST /rooms/{id}/materials`, `POST /sessions/by-code` are phone-side. The web app only reads the results (room surfaces' `material`/`absorption`).

## Error and network rules
- Every call: timeout (10 s, optimize 30 s), visible error with `detail`, never an uncaught promise rejection.
- 501 on anything = feature not deployed yet; show "not available yet".
- Network down: banner "Can't reach the server", keep the current view, retry button.
- Do not poll anything except the session on the pairing screen.
