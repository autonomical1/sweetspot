# Sweetspot iPhone app: context for the iOS developer

Read this first, then the numbered files in order. Written by the backend/planning side. The backend contract is `docs/API.md` in the repo root; if the two disagree, `docs/API.md` wins and tell the backend person.

## What the app does
The user opens the Sweetspot web page on a laptop, which shows a QR code. The iPhone app scans the QR to **pair** (learns a `session_id`), runs an Apple **RoomPlan** LiDAR scan, walks the user through ~6 **guided photos** of surfaces (for material classification by Gemini), and **uploads** everything to the Vultr backend over HTTPS. The backend computes where the 5.1 speakers and projector screen should go. The app then shows those positions as an **AR overlay** the user walks around, while the laptop shows a 3D web viewer of the same layout.

## You own / you do not
| You (iOS) | Not you |
|---|---|
| RoomPlan scan + export to our JSON format | Acoustic math (engine teammate) |
| QR pairing + typed-code fallback | Material classification (backend calls Gemini) |
| Guided photo capture + upload | Product search (SerpApi, backend) |
| Upload the scan | Web 3D viewer (another teammate) |
| AR overlay of the returned layout | Converting your JSON into the backend Room format (`backend/app/roomplan.py`) |

## Build order (deadline 2026-10-25 11:30)
1. **P0, first hour:** run a RoomPlan scan on the real iPhone, build the export JSON (`01_roomplan_capture.md`), save it to a file, and **send that file to the backend person at once**. It becomes `fixtures/roomplan_sample.json` and the backend converter is written against it.
2. **P0:** `POST` it to the backend (`02_backend_integration.md`).
3. **P0:** "Use demo room" button (no scan). This is the demo safety net.
4. **P1:** QR pairing, then guided photos (`03_pairing_and_photos.md`).
5. **P2:** AR overlay (`04_ar_overlay.md`). Time-box the shared-world-frame test to about 1 hour; fallbacks are in that file.

## Files
- `01_roomplan_capture.md`: Xcode setup, RoomPlan APIs (checked against Apple docs), scan lifecycle, the export JSON format, coordinates.
- `02_backend_integration.md`: every endpoint the app calls, bodies, networking rules, Swift snippets.
- `03_pairing_and_photos.md`: QR pairing with VisionKit, typed-code fallback, guided photos.
- `04_ar_overlay.md`: showing the layout in AR, sharing the scan's world frame, fallbacks.
- `05_checklist_and_open_questions.md`: state machine, screens, test checklist, risks, open questions.
- `sample_payloads/`: example JSON for requests and responses.

## Hard facts
- **Needs a LiDAR iPhone.** RoomPlan does not run in the Simulator. Test on the device from the start.
- RoomPlan is **iOS 16.0+** (Apple docs). The `polygonCorners` property needs **iOS 17.0+**. Set the deployment target to **iOS 17.0**.
- Backend is **HTTPS only** (App Transport Security blocks `http://`). One base-URL constant.
- Units **meters**, **y-up**, **right-handed**. Do not flip or rescale anything.
- Do not photograph during a scan. Order: pair, scan, stop, upload scan, photos, upload photos, (optional) AR.

## How this was verified
RoomPlan and VisionKit API facts were checked on 2026-10-24 against Apple's documentation data (`developer.apple.com/tutorials/data/documentation/...json`). Statements tagged **[Apple docs]** come from there. Statements tagged **VERIFY** are from memory or inference; test them on the device or read the linked Apple page. Swift snippets are illustrative and may need small fixes to compile.

Apple pages used: [CapturedRoom](https://developer.apple.com/documentation/roomplan/capturedroom), [CapturedRoom.Surface](https://developer.apple.com/documentation/roomplan/capturedroom/surface), [CapturedRoom.Object](https://developer.apple.com/documentation/roomplan/capturedroom/object), [RoomCaptureView](https://developer.apple.com/documentation/roomplan/roomcaptureview), [RoomCaptureViewDelegate](https://developer.apple.com/documentation/roomplan/roomcaptureviewdelegate), [RoomCaptureSession](https://developer.apple.com/documentation/roomplan/roomcapturesession), [RoomCaptureSessionDelegate](https://developer.apple.com/documentation/roomplan/roomcapturesessiondelegate), [DataScannerViewController](https://developer.apple.com/documentation/visionkit/datascannerviewcontroller).
