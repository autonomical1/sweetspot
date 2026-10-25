# Sweetspot iPhone app

This folder contains an iOS app project and implementation. Open `SweetspotPhoneApp.xcodeproj` in Xcode.

## What is included

- `Sources/SweetspotPhoneApp/Models.swift`: RoomPlan DTO serialization and backend response types.
- `Sources/SweetspotPhoneApp/BackendClient.swift`: typed REST client for scan/demo/rectangle room creation, photo-target lookup, material classification and layout optimization.
- `Sources/SweetspotPhoneApp/ScanCapture.swift`: RoomPlan capture view using a retained ARSession.
- `Sources/SweetspotPhoneApp/CaptureViews.swift`: VisionKit QR scanner and system camera with 1024 px / quality 0.7 JPEG resizing.
- `Sources/SweetspotPhoneApp/ARLayoutView.swift`: RealityKit speaker and screen markers with two-point floor alignment for demo/manual rooms.
- `Sources/SweetspotPhoneApp/SweetspotApp.swift`: SwiftUI flow for device check, QR pairing before each scan, scan/review/upload, demo room, room dimensions, photo target review, materials and layout results.
- `SweetspotPhoneApp.xcodeproj`: iOS app target, iOS 17 deployment target, and camera purpose string.
- `Resources/`: request and response examples from the project contract.
- `01`–`05` markdown files: original detailed design and acceptance checklist, retained as source context.

## Create and run in Xcode

1. Replace `https://YOUR_DOMAIN.tech` in `BackendClient.swift` with the deployed HTTPS origin. Do not add an ATS exception for production.
2. Open the project, select the app target, choose the team's signing team, then run on a LiDAR iPhone. Enable Developer Mode if Xcode requests it. RoomPlan is unavailable in Simulator.
3. Open the web pairing page, tap "Start room scan," and scan its QR before scanning the room. The phone keeps the `session_id` only until that scan uploads; each new room scan requires a new QR.
4. Scan slowly around the room, finish, review and upload. The raw-meter DTO is saved to Documents as `latest-roomplan.json`; the home screen can upload it again.
5. Photograph each returned surface target, or skip photos; the app resizes JPEGs before multipart upload and calls materials classification.
6. Compute layout. A live RoomPlan scan reuses its ARSession; demo/manual rooms prompt for two floor-corner taps to align. Verify the markers against the real room.

For a local backend, set the URL only in a Debug configuration and use a local-network ATS exception scoped to that Debug target. The backend's API contract is in `02_backend_integration.md` and root `docs/API.md` in the original archive. Do not ship a local HTTP configuration.

## Flow and data rules

`home → QR → scan → review → upload → photos → results → AR layout`.
Demo room and manually entered rectangle rooms skip scanning and pairing. The scan session id stays in memory until upload; the room id and scan history remain available for recovery.

The RoomPlan DTO uses `sweetspot.roomplan.v1`, raw meter dimensions/transforms, column-major transforms, UUID surface identifiers, and the categories required by the backend. Do not convert the uploaded scan to feet. The backend response is decimal feet; the AR scene must multiply returned positions and sizes by `0.3048` before placing anchors. Keep y-up and do not flip axes.

## Validation status

Swift syntax parsing and Xcode project file lint pass. This execution environment has only the Xcode command line tools, not the Xcode IDE/iOS SDK or Simulator (`xcodebuild` reports the active developer directory is Command Line Tools; `simctl` is unavailable). No LiDAR iPhone is attached to this workspace. As a result, compiling against Apple's iOS SDK, signing/installing, confirming RoomPlan's shared session behavior, camera permissions, QR recognition, and physical AR alignment still require the team's Mac/Xcode and LiDAR iPhone. Use the ordered device checklist in `05_checklist_and_open_questions.md` and record any SDK diagnostics before demo day.

The API endpoint and physical-device validation are the only environment-dependent items; source, project, workflows, fallbacks, and device checklist are in this folder.

## Contract reference

The project-level `docs/API.md` is authoritative if it disagrees with contextual notes. Relevant examples are in `Resources/`. REST only; backend room geometry and layout use feet, while scan DTO coordinates remain meters. Session expiry is 30 minutes. Backend errors contain a `detail` field.
