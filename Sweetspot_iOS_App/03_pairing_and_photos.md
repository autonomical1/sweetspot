# 03: Pairing and guided photos

## Pairing flow (desktop shows the QR, phone scans)
1. Web page calls `POST /sessions` and shows a QR for `https://<domain>/pair/<session_id>` plus a 6-character code, then polls `GET /sessions/{id}`.
2. App "Connect to desktop" opens a QR scanner. On a result, extract `session_id` (last path component) and keep it in app state. Sessions expire after 30 minutes.
3. Scan, upload etc. (files 01/02). The upload carries `session_id`; the web page flips to the viewer by itself.
4. If scanning fails or the camera is unavailable: text field for the 6-character code -> `POST /sessions/by-code`.
5. Allow "Skip pairing" (standalone use, `session_id` omitted). Skip is also the demo fallback.

Do not use universal links or custom URL schemes (needs entitlements and `apple-app-site-association`; not worth the time).

## QR scanning with VisionKit
**[Apple docs]** `DataScannerViewController` is iOS 16.0+, `@MainActor`, with `class var isSupported: Bool` and `class var isAvailable: Bool` (available = camera permission granted and no restrictions), `func startScanning() throws`, and an async `recognizedItems` stream as an alternative to the delegate. Init: `init(recognizedDataTypes:qualityLevel:recognizesMultipleItems:isHighFrameRateTrackingEnabled:isPinchToZoomEnabled:isGuidanceEnabled:isHighlightingEnabled:)`. Needs `NSCameraUsageDescription` and a camera-permission grant; check `isSupported` and `isAvailable` before presenting.

**VERIFY** (from memory): `recognizedDataTypes: [.barcode(symbologies: [.qr])]`, and `RecognizedItem.barcode(let b)` with `b.payloadStringValue`.

```swift
struct QRScanner: UIViewControllerRepresentable {
    let onCode: (String) -> Void
    func makeUIViewController(context: Context) -> DataScannerViewController {
        let vc = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])],
                                           qualityLevel: .balanced, recognizesMultipleItems: false,
                                           isHighFrameRateTrackingEnabled: false, isPinchToZoomEnabled: false,
                                           isGuidanceEnabled: true, isHighlightingEnabled: true)
        Task { @MainActor in
            try? vc.startScanning()
            for await items in vc.recognizedItems {
                for case .barcode(let b) in items { if let s = b.payloadStringValue { onCode(s); return } }
            }
        }
        return vc
    }
    func updateUIViewController(_ vc: DataScannerViewController, context: Context) {}
}
func sessionID(fromQR s: String) -> String? { URL(string: s)?.lastPathComponent }
```
Fallback if DataScanner is unavailable: `AVCaptureMetadataOutput` with `.qr`. Do not spend long on it; the typed code is the real fallback.

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
