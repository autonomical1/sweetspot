# web-pairing: QR pairing screen

## Goal
Add the pairing screen to `webapp/` (the app created by `web-base`): the laptop shows a QR code only (no typed code), polls the session, and flips to the viewer by itself when the phone has uploaded a scan.

## Design decisions this brief encodes
- The QR encodes `pair_url` **verbatim** (`https://<domain>/pair/<session_id>`), not the bare session id: the iOS app parses the last path component and rejects QR text without `pair` in the path (BackendClient.swift). Do not call any server-side QR/PNG endpoint; none exists and none is wanted.
- QR is generated **client-side** with `qrcode.react` (bundled by Vite, no CDN, no external service). The orchestrator installs `qrcode.react` (and `zustand`) into `webapp/package.json` + lockfile BEFORE this task runs; workers have no network. If it is missing, stub a minimal text fallback and say so in HANDOFF.md.
- Routing by query string on the single page `/app/`: `/app/?pair` opens the pairing screen, `/app/?room=<id>&view=3d` opens the viewer (webapp_context/05). Use `URLSearchParams` + `history.pushState`, no router library.
- Poll **only** `GET /sessions/{id}` every 1.5 s while the pairing screen is open; stop polling on unmount, on ready, and when the tab is hidden. Nothing else is polled.
- Units/sizes are irrelevant here; no scene work.

## Deliverables
1. A **Pair your iPhone** entry on the start screen / top bar (next to **Use demo room**) that opens `?pair`.
2. `src/screens/Pair.tsx`: on entry `POST /sessions` -> large QR of `pair_url` and a countdown to `expires_at`. **QR only: do NOT show, render or mention the 6-character `code` anywhere in the UI (user decision 2026-10-25 01:17).** On expiry show **New QR code** (calls `POST /sessions` again). Handle API errors with a visible retry.
3. `src/api/sessions.ts` (or reuse the types `web-base` put in `src/api/client.ts`): typed `createSession()` and `getSession()` per `docs/API.md` and `webapp_context/02_api_reference.md`, with `sample_payloads/post_sessions.json` and `get_session_ready.json` as fixtures.
4. When the session is ready, read its `room_id`, load the room, set `?room=<id>&view=3d` and switch to the viewer. The viewer then starts `optimize` exactly like the demo-room button does (reuse that store action; do not duplicate it).
5. Tests (vitest, mock `fetch` and timers): session create, polling cadence, stop on ready/unmount/expiry, "New QR code", error retry, URL switching, and that the `code` string never appears in the rendered output.
6. Note for HANDOFF.md only (do not change them): the backend still returns `code` and the iOS app may still offer manual code entry; report whether `webapp_context/01` and `07` still mention the typed code so the orchestrator can update the docs.

## Done when
- `cd webapp && npm test && npm run build` pass; `python -m ruff check . && python -m pytest backend -q` still pass.
- HANDOFF.md lists missing dependencies and open design questions under `## Design questions`.

## Out of scope
Backend/session endpoints, iOS, 2D view, panels, the scene adapter, Dockerfile. Edit only files you own (OWNS.txt); any change to the store or client outside the pairing additions goes in HANDOFF.md as a request.

## Pointers
`webapp_context/01_product_and_flows.md` (section B Pairing), `02_api_reference.md`, `05_2d_view_and_toggle.md`, `docs/API.md` (wins), `sample_payloads/`.
