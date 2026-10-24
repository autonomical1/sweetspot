# 01: Product, screens and flows

## Audience
Hackathon judges watching a live pitch (big screen, a few minutes), and track judges clicking around afterwards. Optimize for: instantly readable from across a room, no dead ends, never a blank screen, and an obvious "wow" moment (speakers snapping into place in 3D, reflections lighting up on the walls).

## Screens

### A. Start (`/app/`)
- Title, one-sentence pitch ("Scan your room. We place your 5.1 speakers and screen.").
- Three entry points, large buttons:
  1. **Pair your iPhone**: goes to screen B.
  2. **Use demo room**: `POST /rooms/demo` with `{}`, then the viewer (screen C) and an automatic optimize.
  3. **Rectangular room**: inline form (width, length, height in ft-in or decimal feet; budget) -> `POST /rooms/rect`, then the viewer.
- Small "Open a room by id" field (for shared links and debugging).

### B. Pairing
1. On entry: `POST /sessions` -> show a large QR encoding `pair_url` (phone scans it) and the 6-character `code` in big monospace text underneath ("or type this code in the app"), plus a countdown to `expires_at` (30 min).
2. Poll `GET /sessions/{session_id}` **every 1.5 s** while this screen is visible (pause when the tab is hidden).
3. Status text follows the phone's progress implicitly: "Waiting for your phone..." while `status == "waiting"`.
4. When `status == "ready"`: fetch `GET /rooms/{room_id}` and go to the viewer, then run optimize automatically.
5. When `status == "expired"` or `GET` returns 404: stop polling, show "Code expired" and a **New code** button (new `POST /sessions`).
6. Escape hatch on this screen: "No phone? Use the demo room".
QR generation is client-side with `qrcode.react` (bundled by Next), no external service, no CDN at runtime.

### C. Viewer (the main screen)
Layout (desktop first, works down to 1280 x 720 for projectors):
- **Top bar:** room name/id, source badge (`demo`, `rectangle`, `scan`), **2D | 3D toggle**, **Optimize** (re-run), **Share** (copies the full `https://.../app/room/?id=<id>` URL), **Start over**.
- **Center:** the active view (2D plan or 3D).
- **Right panel (tabs):** *Layout* (score, speakers with ft-in positions, warnings), *Acoustics* (reflections, treatment patches, room modes), *Shop* (budget + products), *Room* (dimensions, surfaces with materials, photo-classified materials).
- **Status line:** last action, loading spinners, errors (dismissible red banner with the server's `detail`).

States:
- **Optimizing** (about 8 s): keep the room visible, show a progress overlay "Computing the best placement..." with an indeterminate bar; disable drag until done. Never block the whole page.
- **No layout yet** (room loaded, optimize not run or failed): show the room and listener, a primary "Place my speakers" button.
- **Error**: banner + keep the last good state.

### D. Shared room `/app/room/?id=<id>`
Same as the viewer, loaded from the hash: `GET /rooms/{id}` then `GET /rooms/{id}/layout` (404 = no layout yet -> state "No layout yet").

## Core interactions
- **Drag a speaker** (2D and 3D): position updates locally; `POST /rooms/{id}/score` throttled to at most 10 per second, latest-wins, plus one final call on drop; score and reflections update. Speakers stay inside the room (clamp to the box with 0.25 ft margin). Dragging does not save; **Optimize** resets to the engine's layout.
- **Select** a speaker or a reflection: highlight it in the view and in the panel (two-way). Selecting a reflection draws the path speaker -> wall point -> listener.
- **Nudge the listener** (P2): drag the listener marker; on drop `PATCH /rooms/{id}/listener` with `{position, facing}` then re-run optimize (ask first: "Re-optimize for the new seat?").
- **Budget**: number input with $ prefix, default `room.budget` or 1500; **Get products** -> `GET /rooms/{id}/products?budget=`.
- **Toggle 2D/3D** keeps the selection, the current layout (including unsaved drags) and the panel state.

## The pitch demo path (must be flawless)
1. Laptop on `/app/`, click **Pair your iPhone**; QR on the projector.
2. Phone scans QR, scans the room, uploads; laptop flips to the viewer by itself and starts optimizing.
3. Speakers appear (3D view, slow orbit), reflections glow on the side walls; open *Acoustics* and click the strongest reflection.
4. Drag the front-left speaker, the score drops, drag it back.
5. *Shop* tab: budget $1,500 -> list with a total.
6. Toggle to 2D for the "plan you can print".
Fallback at any step: **Use demo room** gives the same flow without the phone.

## Visual direction
Dark theme (projectors), one accent colour, generous type (base 16 px, panel numbers 20+ px). Role colours, used identically in 2D, 3D and the panel: L `#4F8EF7`, R `#E5534B`, C `#F2C744`, LFE `#9B6CF0`, Ls `#3BB58E`, Rs `#F28C38`; listener white; screen light grey; treatment patches amber at 35% opacity; reflections: line width and opacity by `level_db` (louder = thicker/brighter). Respect `prefers-reduced-motion` (no auto-orbit).
