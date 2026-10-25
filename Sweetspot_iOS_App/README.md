# Sweetspot iPhone app

This folder contains an iOS app project and implementation. Open `SweetspotPhoneApp.xcodeproj` in Xcode.

## What is included

- `Sources/SweetspotPhoneApp/Models.swift`: RoomPlan DTO serialization and backend response types.
- `Sources/SweetspotPhoneApp/BackendClient.swift`: typed REST client for pairing by code, scan/demo/rectangle room creation, photo-target lookup, material classification and layout optimization.
- `Sources/SweetspotPhoneApp/ScanCapture.swift`: RoomPlan capture view using a retained ARSession.
- `Sources/SweetspotPhoneApp/CaptureViews.swift`: VisionKit QR scanner and system camera with 1024 px / quality 0.7 JPEG resizing.
- `Sources/SweetspotPhoneApp/ARLayoutView.swift`: RealityKit speaker and screen markers with two-point floor alignment for demo/manual rooms.
- `Sources/SweetspotPhoneApp/SweetspotApp.swift`: SwiftUI flow for device check, scan/review/upload, demo room, typed pairing, room dimensions, photos, setup form, processing, and AR layout.
- `SweetspotPhoneApp.xcodeproj`: iOS app target, iOS 17 deployment target, and camera purpose string.
- `Resources/`: request and response examples from the project contract.
- `01`–`05` markdown files: original detailed design and acceptance checklist, retained as source context.

## Create and run in Xcode

1. Replace `https://YOUR_DOMAIN.tech` in `BackendClient.swift` with the deployed HTTPS origin. Do not add an ATS exception for production.
2. Open the project, select the app target, choose the team's signing team, then run on a LiDAR iPhone. Enable Developer Mode if Xcode requests it. RoomPlan is unavailable in Simulator.
3. Pair by scanning the desktop QR or entering its six-character code. The phone carries the `session_id` through room creation; session and room IDs persist across relaunch.
4. Scan slowly around the room, finish, review and upload. The raw-meter DTO is saved to Documents as `latest-roomplan.json`; the home screen can upload it again.
5. Photograph each returned surface target, or skip photos; the app resizes JPEGs before multipart upload. Leaving photos starts materials classification in the background when photos exist.
6. On the setup form, choose a budget and speaker configuration, then tap "Build my layout". The processing screen waits for classification, optimizes the selected preset, and opens AR. A live RoomPlan scan reuses its ARSession; demo/manual rooms prompt for two floor-corner taps to align.

For a local backend, set the URL only in a Debug configuration and use a local-network ATS exception scoped to that Debug target. The backend's API contract is in `02_backend_integration.md` and root `docs/API.md` in the original archive. Do not ship a local HTTP configuration.

## Flow and data rules

`home → scan → review → upload → photos → setup form → processing → AR layout`.
Demo room and manually entered rectangle rooms go straight to the setup form. Pairing can be skipped. Session and room ids are held in memory for this app run. The scan file is the local recovery copy.

The RoomPlan DTO uses `sweetspot.roomplan.v1`, raw meter dimensions/transforms, column-major transforms, UUID surface identifiers, and the categories required by the backend. Do not convert the uploaded scan to feet. The backend response is decimal feet; the AR scene must multiply returned positions and sizes by `0.3048` before placing anchors. Keep y-up and do not flip axes.

## Validation status

The current Swift flow changes have not been compiled in this Windows workspace, which lacks the iOS SDK and Simulator. Compiling, signing/installing, confirming RoomPlan's shared session behavior, camera permissions, QR recognition, and physical AR alignment require the team's Mac/Xcode and LiDAR iPhone. Use the ordered device checklist in `05_checklist_and_open_questions.md` and record any SDK diagnostics before demo day.

The API endpoint and physical-device validation are the only environment-dependent items; source, project, workflows, fallbacks, and device checklist are in this folder.

## Contract reference

The project-level `docs/API.md` is authoritative if it disagrees with contextual notes. Relevant examples are in `Resources/`. REST only; backend room geometry and layout use feet, while scan DTO coordinates remain meters. Session expiry is 30 minutes. Backend errors contain a `detail` field.
