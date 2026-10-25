# 02: API reference for the web app

Authoritative contract: `docs/API.md`. Same origin, relative URLs, JSON bodies (`Content-Type: application/json`). Errors are an HTTP status plus `{"detail": "..."}` (`sample_payloads/error_404.json`); always show `detail` to the user. Real responses for every call below are in `sample_payloads/`.

| Call | When | Typical time | Sample |
|---|---|---|---|
| `POST /sessions` | Pairing screen opens / New code | < 50 ms | `post_sessions.json` |
| `GET /sessions/{id}` | Every 1.5 s on the pairing screen | < 20 ms | `get_session_ready.json` |
| `POST /rooms/demo` `{}` | Use demo room | < 50 ms | `room_demo.json` |
| `POST /rooms/rect` | Rectangular room form | < 50 ms | (same shape as `room_demo.json`) |
| `GET /rooms/{id}` | Open/shared room, after pairing | < 20 ms | `room_demo.json`, `room_scanned.json` |
| `POST /rooms/{id}/optimize` `{"options"?: ...}` | Auto after load, Optimize button | answers with the quick layout (`stage: quick`), the 3D refinement runs in the background (LIVE) | `optimize_demo.json` |
| `GET /rooms/{id}/layout` | Opening a room that may already have a layout | < 20 ms (404 if none) | (same shape as optimize) |
| `GET /rooms/{id}/optimize/status` | LIVE: while a refined layout is running | < 20 ms | status object |
| `POST /rooms/{id}/score` `{"layout": ...}` | While dragging (throttled), on drop | **about 16 ms** + network | `score_demo.json` |
| `PATCH /rooms/{id}/listener` `{"position","facing"}` | Listener nudge (P2) | < 20 ms | returns the room |
| `GET /rooms/{id}/products?budget=1500` | Shop tab | stub: < 50 ms; real SerpApi: seconds (cached after) | `products_demo_stub.json` |
| `GET /rooms/{id}/photo-targets` | Room tab (shows which surfaces the phone photographed) | < 20 ms | `photo_targets_demo.json` |
| `GET /rooms/{id}/materials/status` | LIVE: Room tab while materials are classified | < 20 ms | status object |

## Details per call
- **`POST /sessions`** -> `{session_id, code, expires_at, pair_url}`. Put `pair_url` in the QR; show `code`; count down to `expires_at` (ISO 8601 UTC).
- **`GET /sessions/{id}`** -> `{session_id, status: "waiting"|"ready"|"expired", room_id}`. 404 = unknown or server restarted (sessions live in memory): treat like expired.
- **`POST /rooms/rect`** body: `{"width": 12, "length": 15, "height": 9, "listener": [x, y, z]?, "facing": [fx, fz]?, "budget": 1500?, "session_id": "..."?}` (feet). Dimensions must be 3..100 ft (422 otherwise). Omit `listener` to get the default seat.
- **`POST /rooms/{id}/optimize`**: LIVE body `{}` returns the quick layout at once (about 30 s on a cold server) and starts one background 3D run. Optional body `{"options": {"preset": "5.1|7.1|7.1.4", "standard": "dolby|itu|thx", "refine": true}}` controls the run. Then show the returned quick layout immediately, poll status every 3 s, and when the status is `done` fetch `GET /rooms/{id}/layout` to obtain the refined layout (the status response has no layout); swap it in without blocking the UI. `stage` goes `quick` -> `refining` -> `refined`; a repeat optimize on the same room returns the cached refined layout at once (`from_cache: true`). Ignore responses if the user changed rooms meanwhile (generation counter, as in `web/plot2d/plot.js`).
- **`GET /rooms/{id}/optimize/status`** (LIVE): returns `{"state":"idle|running|done|failed", "preset", "started_at", "elapsed_s", "error"}`. A failed refinement leaves the quick layout visible.
- **`POST /rooms/{id}/score`**: body `{"layout": {"speakers": [...], "screen": {...}|null}}` -> `{metrics}`. Send the **whole** current layout. Throttle to <= 10 requests/s, latest-wins (drop responses older than the newest request), one final call on drop. If it fails, keep the last good metrics and show a non-blocking banner.
- **`PATCH /rooms/{id}/listener`**: 400 if the position is outside the room, 422 for malformed input. Facing is normalized by the server.
- **`GET /rooms/{id}/products?budget=`**: 404 if no layout yet (run optimize first); 422 if budget <= 0. LIVE shape: `{budget, total, items: [{role, title, price, currency, link, thumbnail, source, seller?, specs?, dimensions?, pair_with?, alternatives?}]}`. Alternatives contain up to three swaps with `price_delta`; the second role of a pair has price 0 and no alternatives, so swap through the first role. LIVE roles are `receiver`, `tv`, `mount`, `hdmi_cable`, `speaker_wire`, and `included_in` for bundled items. Until real data is available, stub items may be shown with a "sample data" badge.
- **`POST /rooms/{id}/materials`** (LIVE): classify stored surface photos. Response is `{surfaces: [{surface_id, material, confidence, applied}], status?: "fresh"|"cached"|"joined"}`. An unchanged photo set within the cache window is `cached`; a concurrent request joins the in-flight classification as `joined`; otherwise it is `fresh`. HTTP 429 includes `Retry-After` and `{"detail": "Gemini is busy; retry in N s", "retry_after_s": N}`. Show that message and do not hammer; use the status endpoint for progress.

## Phone-side and web-triggered calls
`POST /rooms` (scan upload), `POST /rooms/{id}/photos`, and `POST /sessions/by-code` are phone-side. The web app may trigger the LIVE `POST /rooms/{id}/materials` classification after photos are stored, and reads the resulting room surfaces' `material`/`absorption`.

## Error and network rules
- Every call: timeout (10 s, optimize 30 s), visible error with `detail`, never an uncaught promise rejection.
- 501 on anything = feature not deployed yet; show "not available yet".
- Network down: banner "Can't reach the server", keep the current view, retry button.
- Poll the session on the pairing screen; for the LIVE refined optimizer, poll `optimize/status` every 3 s only while its state is `running`.
