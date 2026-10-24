# PROJECT_CONTEXT.md — Sweetspot (working name)

Monolithic seed context for a hackathon project. A later Claude instance will split this into deeper per-area context files (contract, engine, integrations, iOS, web). Everything here is either a **confirmed decision** (stated by the team), a **proposal** (suggested, not yet confirmed), or an **open question**. Do not treat proposals as settled.

- Date written: Saturday 2026-10-24. Hackathon is in progress. Submission deadline: UNKNOWN (ask the team).
- Team hardware/skills known: an Arduino Uno + I2C shield with assorted sensors (see "Hardware not used"). Unknown: who has a LiDAR iPhone and a Mac with Xcode (the spec assumes an iPhone 17 Pro).

---

## 1. One-line pitch

Scan your home theater with an iPhone, and Sweetspot computes where to put your 5.1 speakers and projector screen, shows you the layout in AR and in a 3D web viewer, and recommends real products within your budget.

Name status: "Sweetspot" is a proposal (audiophile term for the ideal listening position; the listener position is the anchor of the whole pipeline). Not confirmed by the team. Alternatives considered: FirstBounce, Soundstage, Reflect. Stagehand rejected (existing product name). Domain availability NOT checked (e.g. sweetspot.tech, getsweetspot.tech).

---

## 2. Confirmed decisions

1. **iPhone LiDAR app using Apple RoomPlan.** (Correction: the framework is RoomPlan, not "RoomScan".) It captures walls, doors, windows, openings, and labeled objects (sofa, television, storage, etc.) as parametric boxes/surfaces.
2. The app sends a constructed **JSON** of the RoomPlan data to a **backend**.
3. **Backend hosted on Vultr.** It runs a custom "physics engine" that outputs:
   - Optimal **5.1 speaker placements**, influenced by **first-order reflection** calculations (candidate acoustic treatment/damping locations, and levels at seating locations).
   - A **simple projector screen placement optimization**.
4. **SerpApi** finds product recommendations (real speakers with prices, filtered by a user budget).
5. **Gemini, Option B (guided photo step).** After the scan, the app prompts the user to photograph specific surfaces. No frame-grab/projection approach for now. Photos are tagged with a surface ID and sent to Gemini for material classification.
6. **.Tech domain** (MLH prize; any .tech domain qualifies).
7. **Outputs:**
   - iOS app: AR simulation the user walks through to find the positions on walls/floor where speakers should go.
   - Desktop web app: 3D room the user can click/drag around for more info on placements; also serves the SerpApi recommendations.
8. **ESP32 hardware validation loop is CUT.** No measurement microphone work.
9. 5.1 layout is the target format (L, R, C, LFE/sub, Ls, Rs).

---

## 3. Prize tracks (from organizer text) and chosen targets

| Track | Prize | Plan |
|---|---|---|
| Best Overall (Cinderella's Castle) | 14" MacBook Pro each | Primary. Judged on design, complexity, impact, unique vision. |
| Best Pitch (A Bard's Tale) | 1st DJI speakers, 2nd mechanical keyboards, 3rd JBL speakers | Voted by attendees; pitching is the day after. Demo clarity matters. |
| SerpApi: Best Use | ARZOPA portable monitors | Targeted. SerpApi must play a meaningful role (shopping results, budget). |
| MLH Best Use of Gemini API | MLH swag kits | Targeted (material classification, spec extraction, explanations). |
| MLH Best Use of Vultr | M5Stack Tab5 | Targeted (backend hosting; sign up for free credits). |
| MLH Best .Tech Domain | Desktop mic + free .tech domain up to 10 yrs | Targeted. |
| MLH SpaceXSI (Cursor + Grok Bot) | Cursor mechanical keyboard each | Optional add-on: requires using Cursor as core coding agent AND Grok Bot automation, describing both in the project description, and opting in to the raffle. Verify the team will actually do this before claiming it. |
| Best Hardware Hack (Brick House) | Nvidia 5080 each | NOT targeted. An iPhone app plus cloud backend is not hardware, and the Uno sensors do not measure sound (see section 9). |
| Meta, Capital One Nessie, Toyota, NMC2, Tiger Data, Snowflake, Solana, Best Novice, Most Entertaining | various | Not a fit. Tiger Data/Snowflake only if a measurement-logging feature is forced in; skip. |

Track descriptions are in the organizer text; re-read it before submitting to confirm exact qualification requirements.

---

## 4. Architecture (proposal unless noted)

```
iPhone app  --HTTPS-->  Vultr VPS (Docker Compose)
 RoomPlan JSON            |- Caddy (auto-TLS, serves web app on the .tech domain)
 + material photos        |- FastAPI: /sessions /rooms /score /optimize /products
 (+ session_id)           |- physics engine (numpy)
                          '- Gemini + SerpApi calls
                                   |
              .--------------------'--------------------.
        iOS AR overlay                          Web 3D viewer (three.js)
   (walk to marker positions)             (drag, inspect, buy list)
```

- **HTTPS is required from the start.** iOS App Transport Security blocks plain HTTP by default. Caddy with the .tech domain pointed at the Vultr IP gives automatic TLS.
- Build the web 3D scene from the parametric JSON (boxes and planes), not USDZ.
- Proposed team split: (1) iOS, (2) engine, (3) web, (4) infra + integrations (Vultr/Caddy/domain, SerpApi, Gemini, budget).

---

## 5. Data contract (proposal)

**Write the JSON schema and one fixture room before other code.** All parts develop against the fixture until the real scan path works.

- Raw export: `CapturedRoom` is `Codable`; wrap its output in a project envelope, e.g. `{ room_id, session_id, listener, materials, budget, captured_room }`.
- Coordinates: RoomPlan uses **meters, y-up, right-handed**, with a 4x4 transform per surface/object. three.js is also y-up right-handed, so no axis flips. Axis mismatches are the likeliest source of "speaker inside the wall" bugs.
- **Listener position**: derive from the `sofa` object's transform: seat center at ~1.1 m ear height, facing direction from the transform. Web app lets the user nudge it. If no sofa is detected, fall back to a manual/default seat.
- Surfaces carry stable IDs (used to tag Gemini photos and to reference reflection points).
- **Demo safety**: keep a pre-scanned room saved as JSON plus a "load demo room" path that goes through the same pipeline. RoomPlan struggles in dark/cluttered spaces and a failed live scan during the pitch is the main demo risk.

---

## 6. Pairing / QR flow (proposal; team asked for an explanation and did not object)

Direction: the **desktop shows the QR, the phone scans it** (the reverse is awkward because laptops don't scan QR codes easily).

1. Web app calls `POST /sessions` and receives a random `session_id` (e.g. `secrets.token_urlsafe(8)`); expire unused sessions after ~30 min.
2. Page renders a QR encoding `https://<domain>/pair/{session_id}` and polls `GET /sessions/{id}` (or uses a WebSocket).
3. iOS app: "Connect to desktop" scans the QR (VisionKit `DataScannerViewController`, iOS 16+, or `AVCaptureMetadataOutput` with `.qr`) and extracts `session_id`.
4. User does the RoomPlan scan and the guided photos.
5. App calls `POST /rooms` with the room JSON, photos, and `session_id`; the backend links `room_id` to the session.
6. The waiting web page sees the room and loads the 3D viewer.

Also: show a 6-character code under the QR as a typed fallback. Skip universal links (needs `apple-app-site-association` and entitlements; not worth hackathon time). Keep a shareable `https://<domain>/r/{room_id}` link with an unguessable `room_id`.

Open: pairing before the scan (recommended, upload target known at scan end) vs after.

---

## 7. Physics engine (proposal; "physics engine" is the team's own in-progress component)

**First-order reflections (image-source method):**
1. For each wall plane, mirror the speaker across it to get an image source.
2. Line from image source to listener; intersect with the wall plane.
3. Accept only if the hit point lies inside the wall polygon and not inside a door/window/opening (windows still matter as glass-reflective surfaces; treat per material).
4. Delay = path difference / c, relative to the direct sound. Reflections within roughly 15-20 ms of the direct sound are the ones that most affect imaging.
5. Report reflection-to-direct ratio in dB. Direct level ~ 1/r; a reflection falls with its longer path times sqrt(1 - alpha), where alpha is the surface absorption coefficient. Flag wall patches above roughly -10 dB as candidate treatment spots (render as colored wall patches).
6. Speed of sound: c ~ 343 m/s at 20 C (c ~ 331.3 + 0.606*T). A fixed 343 is fine; temperature correction is negligible for placement.

**5.1 placement search:** grid search over candidate positions, scored against ITU-R BS.775: L/R at +/-30 deg, C at 0 deg, surrounds roughly +/-100-120 deg from the listener's facing direction. Penalties: early-reflection strength, distance to boundaries (SBIR), symmetry. Discard candidates inside doors, windows, object boxes, or unmountable surfaces (e.g. windows) before scoring.

**Subwoofer:** compute axial room modes (f = c / 2L per dimension) and the Schroeder frequency; choose the sub position minimizing response variance across seats. Rectangular-room approximation; state it as such.

**Projector screen:** width = 2 * d * tan(theta/2), theta = 36 deg (THX) or 30 deg (SMPTE). Example: d = 3 m, 36 deg gives ~1.95 m wide (~88" 16:9 diagonal). Place on the wall facing the sofa with the fewest windows/doors. A projector's throw ratio (from product specs) feeds back into mount-distance, so recommendations influence layout.

**API split:** `/score` (layout -> metrics, target <100 ms) and `/optimize` (search built on `/score`). Lets the web viewer re-score live while the user drags a speaker; fall back to re-score-on-drop if too slow.

**Known model limits (state these in the pitch, don't let judges find them):**
- RoomPlan reports no materials, so absorption values are estimates (Gemini's material guess + a hardcoded lookup table).
- First-order model ignores diffraction, furniture scattering, and higher-order reflections.
- Rectangular-room mode math is an approximation for non-rectangular rooms.

---

## 8. Integrations

**Gemini (Option B, confirmed):**
- After the scan the app steps through photo prompts ("photograph the front wall", "the floor", etc.), roughly six photos, ~90 s of user effort. Each photo is tagged with the `surface_id` from the `CapturedRoom`.
- Prompt for structured JSON: `{ surface_id, material, confidence }` with `material` from a fixed enum, e.g. `drywall | glass | brick | carpet | hardwood | tile | curtain`.
- Map material to octave-band absorption coefficients (125 Hz to 4 kHz) from a hardcoded table sourced from published acoustics tables (the table itself is TODO; cite the source).
- Proposed extra jobs: (a) extract specs (throw ratio, lumens, speaker sensitivity, impedance) from SerpApi product titles/snippets or the SerpApi Extract API on product pages, since Google Shopping results lack reliable specs; (b) plain-language rationale for the layout, e.g. "Surround L moved 0.4 m forward because the window behind it produced a 4 ms reflection."

**SerpApi (confirmed use; details are proposals):**
- Google Shopping queries per channel role (center, L/R, surrounds, sub, projector/screen), filtered to the user's budget.
- Budget split heuristic, front-weighted: center and L/R get the largest share, then sub, then surrounds. Label it a heuristic in the pitch.

**Vultr:** one VPS, Docker Compose (Caddy + FastAPI). Claim free credits.

**Domain:** a .tech domain pointed at the Vultr IP.

---

## 9. Hardware not used (and why)

Team has an Arduino Uno + I2C shield with: light sensor, temp/barometer, limit switch, air quality sensor, I2C color sensor, IR reflective sensor. Assessment: none measures sound, so there is no honest validation of the acoustic predictions.
- Temp/barometer only corrects speed of sound (about 1.8% shift between 20 and 30 C; negligible for placement).
- Light sensor could flag screen glare at the seat (relevant only to projector/display advice).
- Limit switch, color, air quality, IR reflective: no meaningful use.
- The Uno has no I2S (an ESP32 + INMP441 mic idea was dropped). The decision to cut validation is final; do not re-add it unless the team does.
- Consequence: do not submit to Best Hardware Hack.

---

## 10. AR overlay (iOS output)

- The AR session must share the world frame with the scan. Easiest: keep the same `ARSession` running after the scan. Next: save an `ARWorldMap` and relocalize. Fallback: "tap two room corners to align."
- Test alignment early (15-minute test). RealityKit markers show speaker positions and reflection points.
- `RoomCaptureSession` exposing an underlying `ARSession` (iOS 17+) was stated from memory; verify against Apple's docs.

---

## 11. Decision tree

- LiDAR iPhone + Xcode on the team? Yes: native RoomPlan. No: web form for room dimensions plus USDZ upload as fallback.
- Backend working end-to-end by the midpoint? Yes: add AR overlay, then SerpApi, then Gemini. No: cut AR and show a top-down 2D plot.
- Web viewer working by the midpoint? Yes: add AR. No: cut AR, demo the web app only.
- AR alignment works with the shared session? Yes: walk-to-marker overlay. No: two-corner alignment; if that fails, show AR as a pre-recorded clip and say so.
- Engine fast enough for live drag re-scoring? Yes: ship it. No: re-score on drop.

## 12. Build order (proposal)

1. Hardcoded rectangular room: image-source math + 2D plot (proves the core).
2. RoomPlan export feeding the same backend.
3. Placement optimizer, sub-mode analysis, screen sizing.
4. Web 3D viewer with `/score` on drag.
5. SerpApi shopping list tied to a budget input.
6. Gemini material classification (Option B photos), then spec extraction and explanations.
7. AR overlay.
8. Pairing/QR polish, demo room, pitch rehearsal.

---

## 13. Open questions

- Submission deadline and pitch time slot?
- Who has a LiDAR iPhone and Xcode?
- Final project name and domain availability?
- Will the team actually use Cursor + Grok Bot (needed for the SpaceXSI raffle claim)?
- Pair before or after the scan?
- Absorption lookup table: source and values still to be compiled.
- Exact RoomPlan/ARSession APIs and VisionKit QR setup: verify against Apple docs (several were recalled from memory).

## 14. Pitch notes

- Lead with the user experience: scan a room, see where the speakers go, walk to the marks, buy the parts.
- State the model limits (section 7) up front.
- Track hooks: SerpApi drives a real budgeted shopping list; Gemini classifies materials and extracts specs; Vultr hosts the engine; the .tech domain is the live demo URL.