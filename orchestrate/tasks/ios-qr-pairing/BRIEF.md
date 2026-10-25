# ios-qr-pairing: remove the typed code from the iOS app; pair per scan by QR

## Goal
Pairing in the iPhone app becomes **QR only and per scan**. The web app opens with a QR code (`pair_url` = `https://<domain>/pair/<session_id>`). The phone scans that QR **first**, which gives it the `session_id` to link this scan to; the user then completes the scan steps on the phone; when the scan is uploaded, the web app presents the result (it is polling `GET /sessions/{id}`). The next scan starts with a new QR.

## Design decisions this brief encodes (user, 2026-10-25 01:30)
- The 6-character code is **removed from the iOS UI**: delete the `CodeEntry` view, its "Desktop code" text field and Connect button, `Flow.pair(code:)` and `BackendClient.pair(code:)` (the backend endpoint `POST /sessions/by-code` stays; do not touch the backend).
- Pairing is **per scan**, not a persistent link: no `UserDefaults` persistence of `sweetspot.session_id` (remove the load at init and the saves). The session id lives only in `Flow` memory for the current scan.
- **Start room scan** now begins with the QR scanner (reuse `PairQRScanner` and `sessionID(from:)`; keep the green frame and the "Center the desktop QR code in the box" hint). Only after a valid pairing QR is read does the app go to the scan phase (`flow.phase = .scan`). Invalid QR (not a `/pair/` link) shows the existing "That QR code is not a Sweetspot pairing link." error and stays on the scanner. If `DataScannerViewController.isSupported` is false, show a clear message that a camera that supports QR scanning is required; there is NO typed fallback.
- After the scan is uploaded successfully (the `upload(dto:sessionID:...)` call returns), clear `flow.sessionID` so the next scan requires a new QR. Keep the existing handling of an expired/unknown session (410 or "session" in the error): clear it and send the user back to the QR scanner with the message "That pairing code expired. Scan the new QR code on the web page."
- Keep the "Connected" indicator, but make it a plain "Linked to desktop" label (do not show the raw session id) while a session is set, visible during the scan steps.
- `Use demo room` and `Enter room dimensions` keep working **without** a session (they are phone-only shortcuts, unchanged) - see Design questions.

## Deliverables
1. Edits in `Sweetspot_iOS_App/Sources/SweetspotPhoneApp/` (`SweetspotApp.swift`, `BackendClient.swift`, `CaptureViews.swift` only if the scanner view needs a tweak). Remove dead commented-out blocks you touch only if they reference the removed code; do not mass-delete other comments.
2. Update `Sweetspot_iOS_App/03_pairing_and_photos.md` (pairing flow: QR first and per scan, no typed code) and any README/checklist line that mentions typing the code (`Sweetspot_iOS_App/README.md`, `05_checklist_and_open_questions.md`, `02_backend_integration.md`).
3. A Swift file nobody can compile here: keep edits small, mirror existing patterns, check every brace and every referenced symbol with Grep. List each changed function in HANDOFF.md so the iOS tester knows what to rebuild and test.
4. HANDOFF.md must include a manual test script: (a) open web `/app/?pair`, (b) tap Start room scan, scan QR, (c) scan the room, (d) upload, (e) web flips to the viewer, (f) tap Start room scan again -> QR scanner appears again.

## Done when
- No reference to `CodeEntry`, `pair(code:`, `by-code`, or `Desktop code` remains in the iOS sources (docs may mention the backend endpoint exists).
- `python -m ruff check . && python -m pytest -q` still pass (no backend change).
- Design questions listed in HANDOFF.md.

## Out of scope
Backend, web app, Xcode project settings, new screens beyond the QR step, polling from the phone.

## Pointers
`docs/API.md` (sessions), `webapp_context/02_api_reference.md`, `Sweetspot_iOS_App/03_pairing_and_photos.md`, `BackendClient.swift` (`sessionID(from:)`, `upload`), `SweetspotApp.swift` (`Flow`, `CodeEntry`, Home view, upload retry around the 410 handling).
