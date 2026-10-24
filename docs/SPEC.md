# SPEC

Scope of this orchestration: backend/integration + the shared data contract. iOS app, physics engine, SerpApi logic and web viewer are built by teammates and plug in through docs/API.md. Seed context: PROJECT_CONTEXT.md.

## Goal
Scan a room with an iPhone (RoomPlan); a Vultr-hosted backend turns the scan into 5.1 speaker and projector-screen placements plus a budgeted product list; results show in iOS AR and a desktop 3D web viewer.

## Users / demo audience
Hackathon judges (Best Overall, Best Pitch) and track judges (SerpApi, Gemini, Vultr, .tech). Demo = live pairing, scan or demo room, layout, shopping list.

## Must-have (MVP) features
1. Shared JSON contract + fixture room + demo-room loader (same pipeline as a live scan).
2. FastAPI backend on Vultr behind Caddy auto-TLS on a .tech domain:
   - `POST /sessions`, `GET /sessions/{id}` (pairing; QR + 6-char code, 30 min expiry)
   - `POST /rooms` (RoomPlan envelope + optional photos + session_id), `GET /rooms/{id}`
   - `POST /rooms/{id}/score`, `POST /rooms/{id}/optimize` (delegate to the engine module)
   - `GET /rooms/{id}/products?budget=` (delegate to the SerpApi module)
   - `POST /rooms/{id}/materials` (Gemini classification of surface photos -> absorption table)
3. Engine and products wired through thin adapters so teammates' modules drop in without backend changes.
4. Storage: JSON files on disk, in-memory session map.
5. Gemini material classification: fixed enum, structured JSON, hardcoded absorption lookup (cited source).
6. Deployed, reachable over HTTPS from the iPhone, with a demo-room fallback.

## Nice-to-have (cut first)
- Gemini spec extraction from product results; plain-language layout rationale.
- `/r/{room_id}` shareable link page.
- Rate limiting, auth beyond unguessable ids.

## Web app
Specified in `webapp_context/` (screens, API usage with real sample payloads, 2D/3D views with a lossless toggle, panels, tests). Built by the web teammate (or a worker) as no-build ES modules at `web/index.html`, served at `/app/`.

## Non-goals
ESP32/mic validation, Best Hardware Hack, USDZ-based web scene, universal links, accounts/login, database.

## Acceptance criteria (what the demo must show)
1. Open the .tech URL on a laptop, see QR; phone scans it; phone upload makes the page load the room.
2. `Load demo room` goes through the same `POST /rooms` path and works with no phone.
3. `/optimize` returns 5.1 + screen layout for the fixture and the live scan; `/score` returns in <100 ms.
4. Products endpoint returns budgeted picks per channel role.
5. At least one Gemini-classified material changes a surface's absorption in the result.
6. Everything served over valid HTTPS from Vultr.

## Tech stack and constraints
Python 3.11+, FastAPI, pydantic v2, numpy (engine), uvicorn, Docker Compose + Caddy on a Vultr VPS. Gemini via google-genai; SerpApi via HTTP. Coordinates: feet (decimal, y-up, right-handed; ft-in strings are display only); RoomPlan meters are converted in the backend converter and the iOS AR layer. REST only (GET/POST/PATCH), no WebSocket. Workers have no network: external APIs behind interfaces with recorded fixtures/mocks. Keys come from env (`.env`, never committed).

## Open questions
- Engine module signatures: owner must accept the proposal in docs/API.md.
- SerpApi module location/signature: teammate must accept.
- Final project name and .tech domain availability.
- Who deploys to Vultr first, and are keys (Gemini, SerpApi, Vultr) in hand?
