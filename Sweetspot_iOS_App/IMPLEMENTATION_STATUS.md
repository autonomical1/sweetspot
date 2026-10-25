# Implementation and validation handoff

## Implemented in this folder

- iOS 17 SwiftUI app target with camera purpose string.
- LiDAR capability check and RoomPlan capture view, explicit `sweetspot.roomplan.v1` DTO export, local scan backup and saved-scan upload.
- Desktop QR scanning through VisionKit and typed six-character pairing.
- Session and room id persistence.
- Demo room and manual rectangle room creation.
- Backend photo target retrieval, camera capture, 1024 px JPEG compression, multipart uploads, and materials request. Supports skipping photos.
- Layout optimization and RealityKit rendering for speaker markers, floor stems, labels and screen plane.
- Shared scan ARSession for scan-derived coordinates and two-corner manual alignment for demo/manual rooms.
- HTTPS-only configuration placeholder and setup instructions.

## Checks performed here

- Xcode project file parsed successfully with `plutil -lint`.
- All Swift source files passed Swift frontend syntax parsing.

## Checks that require the user's Apple hardware

The workspace has no Xcode IDE/iOS SDK or connected LiDAR iPhone. Do not treat source parsing as an iOS build or device test. On the team's Mac:

1. Open the `.xcodeproj`, select signing team and set the actual HTTPS backend origin.
2. Build and install on a supported LiDAR iPhone running iOS 17+.
3. Scan a room and verify the saved JSON's meter values, 16-float transforms, and polygon data against a known wall.
4. Verify pairing, scan upload, photo upload/material classification, layout response, and desktop viewer update against the deployed backend.
5. Test one speaker marker against the scanned world frame; test demo/manual room alignment using two measured corners.
6. Test no-LiDAR demo/manual fallback, expired session, denied camera permission, network failure, and saved scan retry.

Shared RoomPlan/RealityKit session behavior and AR alignment are specifically hardware/runtime checks; neither can be reliably certified by source review alone.
