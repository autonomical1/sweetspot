# Handoff

Implemented the iOS error/status safety audit in the owned Swift sources.

## What changed

- BackendClient.swift (around lines 120-165): added userMessage(for:) with offline/timeout, 404, 410, 413, 400/422, busy/429, 5xx, and fallback categories. HTTP status/detail, retry seconds, URL-session errors, and unknown errors are logged through Logger(subsystem: "com.sweetspot.phone", category: "backend") with private values. BackendError.errorDescription is now safe, and multipart photo uploads preserve HTTP status/detail for mapping.
- SweetspotApp.swift (around lines 670-1080 and 1235): replaced localized error text and backend-unavailable banners with the mapper or fixed copy:
  - Could not save scan: <error> -> Couldn't save the scan. Please try again.
  - raw upload/open/products/processing/photo/pairing errors -> the central mapper
  - room id in the missing-room message -> That room isn't available any more. Upload the scan again.
  - Compute a server layout to shop this setup. -> Build your layout before shopping.
  - raw product warnings -> Some recommendations may be unavailable.
  - Contacting Sweetspot backend… -> Connecting to Sweetspot…
  - Could not prepare photo. -> Couldn't prepare that photo. Please try again.
- ScanCapture.swift (around lines 239-303): screen-size/RoomPlan/AR-session failure details -> short generic scan failure messages.
- ARLayoutView.swift (around lines 60 and 107): Room frame missing: AR placement may be wrong -> Alignment unavailable.
- ScanHistoryView.swift (around lines 80-185): removed room/session IDs and earlier-upload IDs from UI; Backend section -> Upload; room label -> Uploaded; backend progress copy -> Connecting to Sweetspot…; server-specific footer -> Upload again creates a fresh room from this scan. The earlier result stays available.

## Backend-side tightening

- Backend detail strings and status-specific response bodies may still contain implementation wording. The iOS mapper now keeps those values in private logs and never presents them. No backend files were edited.

## Manual iOS test list

- Airplane mode while uploading, opening, optimizing, classifying, and shopping: verify the friendly connection message.
- Expired QR/pairing: verify the expired-code message and existing retry/navigation behavior.
- Stopped/unreachable service: verify the connection or generic retry message and local preview fallback.
- Bad or oversized photo: verify the friendly photo message; verify no response body or HTTP status appears.
- Open a previously uploaded saved scan: verify no room/session IDs are displayed and a missing room gets the friendly unavailable-room message.

## Verification

- python -m ruff check .: passed.
- python tools/smoke_tests.py: 91 passed; 26 errors caused by the sandbox denying access to C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm while pytest created tmp_path fixtures. No Swift compiler is available in this environment.

## Unfinished

- None within the owned files.

## Design questions

- none
