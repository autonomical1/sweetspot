# Sweetspot web app: context for the web developer

Read this first, then the numbered files in order. `docs/API.md` (repo root) is the contract and wins over anything here; if they disagree, tell the backend person.

## What the web app is
The desktop half of Sweetspot. A user opens the site on a laptop, pairs their phone with a QR code, scans the room with the phone, and the laptop shows the room with the recommended 5.1 speaker and screen placement in a **2D plan view or a 3D view (toggle)**. They can drag speakers and see the score, reflections and suggested acoustic treatment update, nudge their seat, and get a shopping list for their budget. Without a phone, **Use demo room** or **Rectangular room** gives the same experience.

## What already exists (use it, do not rebuild it)
- **Backend** (FastAPI): every endpoint you need is live and tested (`02_api_reference.md`). Run it locally: `pip install -r backend/requirements.txt` then `uvicorn backend.app.main:app --reload`, and open http://127.0.0.1:8000/docs.
- **Engine**: `POST /rooms/{id}/optimize` runs the teammate's `speakerplacer` acoustic optimizer through an adapter. It takes **about 8 seconds**. `POST /rooms/{id}/score` takes **about 16 ms** and is what drag-to-rescore uses.
- **2D plot page** at `/app/plot2d/` (`web/plot2d/`): a working SVG plan view with drag, live score, products, ft-in formatting and stale-response guards. It is the starting point for the 2D view; reuse `format.js` and the drawing code.
- **Hosting**: the backend serves the `web/` folder at `/app/` from the same origin as the API, so `fetch("/rooms/...")` needs no CORS and no host name. Deployed behind Caddy with HTTPS (`DEPLOY.md`).

## You own / you do not
| You (web) | Not you |
|---|---|
| Pairing page (QR + 6-char code, polling) | Any backend endpoint or data format |
| 2D view, 3D view, the toggle | The acoustics, the engine, scoring |
| Drag/inspect UI, listener nudge, budget + shopping list | Product search logic (SerpApi module) |
| Materials and warnings display | Material classification (Gemini) |
| Loading/error states, demo mode | Deployment (backend person) |

## Build order (deadline 2026-10-25 11:30; feature freeze 09:30)
1. **P0** App shell at `web/index.html` (served at `/app/`), shared state store, API client, demo-room path, 2D view ported from `web/plot2d/` (`05_2d_view_and_toggle.md`).
2. **P0** Pairing page with QR + code + polling (`01_product_and_flows.md`).
3. **P1** 3D view with three.js and the 2D/3D toggle (`04_3d_view.md`).
4. **P1** Inspect panel: score, reflections, treatment patches, room modes, warnings; shopping list (`06_panels_products_materials.md`).
5. **P2** Listener nudge, shareable `/app/#room=<id>` links, polish.
Cut from the bottom if time runs out; the 2D view plus demo room is already a demo.

## Files
- `01_product_and_flows.md`: screens, user flows, the pitch demo path, states.
- `02_api_reference.md`: every endpoint the web app calls, with real responses, timings, error handling, polling and throttling rules.
- `03_data_and_coordinates.md`: room/layout/metrics shapes, units (feet, ft-in display), the room frame, rotation conventions, how to draw each surface/object.
- `04_3d_view.md`: three.js setup, mapping, picking and dragging, camera, performance.
- `05_2d_view_and_toggle.md`: app architecture, state store, reusing plot2d, the toggle.
- `06_panels_products_materials.md`: inspect panel, shopping list, materials, warnings, copy.
- `07_testing_and_acceptance.md`: tests, acceptance criteria, demo checklist.
- `sample_payloads/`: **real** responses captured from the current backend (demo room through the real engine, a scanned room, products from the stub, errors).

## Hard facts
- **Feet everywhere in JSON** (decimal: 7.5 = 7 ft 6 in). Show users feet and inches (`7' 6"`) via `formatFtIn` in `web/plot2d/format.js`. Never show raw decimals.
- **Room frame:** x = east (room width), z = south (room length), y = up; the room box starts at (0,0,0); **north = -z** is the listener's usual facing. Scanned rooms carry a `frame` field for AR; the web app ignores it and always draws the room frame.
- **`rotation_y` is in degrees**, right-handed about +y (+90 maps +x to -z). In three.js use `rotation.y = rotation_y * PI/180`; in an SVG plan with z pointing down use `rotate(-rotation_y)`.
- **REST only**: `fetch` with GET/POST/PATCH. No WebSocket. Poll only where stated.
- **Same origin**, relative URLs, no API host constant.
- **No build step required** (plain ES modules, vendored three.js). If you prefer a framework, see the open question in `05_2d_view_and_toggle.md` first.
