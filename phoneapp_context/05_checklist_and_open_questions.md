# 05: Checklist, screens, risks, open questions

## App state machine
`launch -> (supported?) -> home -> [pair] -> scan -> review -> upload -> photos -> materials -> layout/AR`

Home screen buttons: **Connect to desktop** (QR), **Start scan**, **Use demo room**, **Load saved scan**, **Enter room size** (no-LiDAR fallback). Persist `session_id`, `room_id` and the last scan file path so a relaunch can resume (relaunch breaks AR option A, see file 04).

## Screens
1. Home / device check.
2. QR scanner + code entry.
3. Scan (RoomCaptureView, Done button, live counts).
4. Review (summary, Rescan, Save/Share, Upload).
5. Photo steps (prompt, camera, upload tick).
6. Results (materials list, "Compute layout").
7. AR overlay (alignment status, Recompute, debug toggle).

## Test checklist (do in this order, on the real phone)
- [ ] Scan runs; `CapturedRoom` arrives in `didPresent`.
- [ ] DTO JSON saved to Documents and shared to the backend person. **(unblocks the converter)**
- [ ] DTO transforms look sane: translation (elements 12,13,14) values within a few meters; dimensions in meters.
- [ ] Upload succeeds against the deployed HTTPS backend; `room_id` stored.
- [ ] Demo room button works with no scan.
- [ ] QR scan yields the `session_id`; the laptop page switches to the viewer after upload.
- [ ] Typed code works.
- [ ] Each photo uploads (<300 KB); `materials` returns.
- [ ] Layout fetch returns and parses.
- [ ] AR: marker at a known wall corner lands on the corner (shared session). If not, option C works.
- [ ] Airplane-mode / backend-down path shows a readable error and the saved-scan path still works.

## Risks
| Risk | Mitigation |
|---|---|
| Live scan fails in the demo (dark/cluttered room) | Pre-scanned saved room + "Load saved scan" + demo room button |
| Default `Codable` JSON of RoomPlan types is odd or errors | Use the explicit DTO (file 01) |
| AR world frame mismatch | Shared ARSession (A), else manual two-corner alignment (C), else recorded clip |
| Backend slow/unreachable on venue Wi-Fi | Generous timeouts, retry, local saved scan, personal hotspot |
| Sofa not detected | Backend falls back to room center; add a manual "I sit here" step (see questions) |
| Camera conflicts (scan vs photos vs QR) | Strict order: finish and stop one camera user before the next |
| iOS build/signing eats time | Get a hello-world RoomPlan build on the device in the first 30 minutes |

## Open questions for the iOS developer / team
1. **Does the shared ARSession (option A) work?** Run the 15-minute test early and report.
2. **Listener position:** the backend derives it from the sofa. Should the app add an AR tap "Tap where you sit"? If yes, the upload gets an optional `listener: {position:[x,y,z], facing:[fx,fz]}` field (backend will add it to `POST /rooms`; tell the backend person).
3. `polygonCorners` axes and `confidence` case names: send a dumped example with the sample file.
4. iPhone model and iOS version actually on the team's device (docs say 16.0+, `polygonCorners` needs 17.0+).
5. Final domain for `Config.baseURL`.
6. Is the web page or the app responsible for triggering `optimize`? Default: the web page triggers it; the app polls `GET .../layout`.

## Message to send the backend person as soon as possible
"Attached: `room_<timestamp>.json` from a real scan in DTO format, plus a printout of one wall's `transform`, `dimensions` and `polygonCorners` and the `confidence` strings you saw."
