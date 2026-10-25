# 03: Pairing and guided photos

## Pairing flow (desktop shows the QR, phone scans)
1. Web page calls `POST /sessions`, shows a QR for `https://<domain>/pair/<session_id>`, then polls `GET /sessions/{id}`.
2. Tap "Start room scan" on the phone. The QR scanner opens first; scan the desktop QR to keep the `session_id` in memory for this scan. Sessions expire after 30 minutes. A camera that supports QR scanning is required.
3. Complete the room scan and upload it. The upload carries `session_id`; the web page flips to the viewer by itself. After a successful upload, the app clears `session_id`, so the next room scan starts at the QR scanner again.
4. If the session expires, the app returns to the QR scanner with an expiry message. Scan the new QR shown on the web page, then scan and upload the room. Invalid QR links keep the scanner open.
5. "Use demo room" and "Enter room dimensions" remain phone-only shortcuts without pairing.

Do not use universal links or custom URL schemes (needs entitlements and `apple-app-site-association`; not worth the time).

## QR scanning with VisionKit
**[Apple docs]** `DataScannerViewController` is iOS 16.0+, `@MainActor`, with `class var isSupported: Bool` and `class var isAvailable: Bool` (available = camera permission granted and no restrictions), `func startScanning() throws`, and an async `recognizedItems` stream as an alternative to the delegate. Init: `init(recognizedDataTypes:qualityLevel:recognizesMultipleItems:isHighFrameRateTrackingEnabled:isPinchToZoomEnabled:isGuidanceEnabled:isHighlightingEnabled:)`. Needs `NSCameraUsageDescription` and a camera-permission grant; check `isSupported` and `isAvailable` before presenting.

**VERIFY** (from memory): `recognizedDataTypes: [.barcode(symbologies: [.qr])]`, and `RecognizedItem.barcode(let b)` with `b.payloadStringValue`.

The implementation uses `PairQRScanner` in `CaptureViews.swift` and validates the HTTPS `/pair/<session_id>` path with `sessionID(from:)` in `BackendClient.swift`. A rejected QR leaves scanning active.
If `DataScannerViewController.isSupported` is false, show a message that a QR-capable camera is required for a room scan.

## Guided photos
**Purpose:** Gemini classifies each surface's material from one photo. Quality of the photo matters more than quantity: about 6 photos, about 90 s total.

Sequence (after the scan is uploaded and `room_id` is known):
1. Fetch `GET /rooms/{room_id}/photo-targets` (labels and `surface_id`s; see file 02 for the hardcoded fallback).
2. For each target show a full-screen prompt with the label ("Photograph the wall behind the TV"), a short hint ("Fill the frame with the surface, avoid people and lights, hold steady"), a Take Photo button, and Skip.
3. Capture with the system camera: `UIImagePickerController` with `sourceType = .camera` is the fastest route (wrap in `UIViewControllerRepresentable`). Custom `AVCapturePhotoOutput` is not worth it.
4. Resize to long edge 1024 px, JPEG quality 0.7, upload with `uploadPhoto(...)` (file 02). Show a checkmark per photo; retry on failure; never block on a failed upload (continue and note it).
5. Leaving the photos step starts `POST /rooms/{room_id}/materials` in the background when at least one photo was uploaded. The setup form remains usable during classification. With no photos, the app skips classification.
6. The setup form asks for budget, base configuration (2.1, 5.1, 7.1), and optional height channels (.2 or .4 for 5.1/7.1). "Build my layout" waits for classification, sends the combined preset to optimize, then opens AR. A processing screen shows the active stage, elapsed time, Gemini retry countdown, and Retry / Back to form on failure.

Constraints:
- Do not take photos while the RoomPlan session is running. Finish and stop the scan first. (If you share one `ARSession` with the AR overlay, `UIImagePickerController` pauses it; after photos, re-check tracking before AR, see file 04.)
- Do not upload the photos before the room exists (`room_id` needed).
- Photos stay on the server only for classification; mention this in the UI ("Photos are used only to identify materials").
- Skipping photos is allowed. Backend falls back to drywall defaults.
