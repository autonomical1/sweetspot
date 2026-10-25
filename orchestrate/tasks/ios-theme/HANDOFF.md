# iOS theme handoff

## Done

- Added `Theme.swift` with the specified web colors, `Color(hex:)`, primary and quiet button styles, a card modifier, a full-screen dark modifier, eyebrow text, and the S brand mark. Registered it in the Xcode project with new IDs.
- Applied dark appearance and accent tint at the app root. Set segmented selection to teal. Restyled the home/device state, pairing QR guide, scan and review actions, room-size and setup cards, photos, processing, history, shop, and AR overlay controls. Kept flow, navigation, network calls, and copy intact.
- `ScanCapture.swift` and `ARLayoutView.swift` contain the UIKit camera/AR renderers; their SwiftUI overlays live in `SweetspotApp.swift` and were styled there. The AR speaker, stem, and screen indicators now use theme teal tones.

## Verification

- `python -m ruff check .`: passed.
- `python tools/smoke_tests.py`: 117 passed, using a fresh local pytest temp directory because the default pytest temp directory was inaccessible; the local directory was removed afterward.
- `git diff --check`: passed. Xcode/Swift compiler unavailable here; inspect on an iOS 17 device.

## iOS tester checklist

- Home/device check: dark full-bleed background, S brand mark, teal scan action, quiet demo and recent scan actions, readable unsupported-device state and linked banner.
- QR pairing: thin teal guide, dark hint and Close control; ensure camera remains visible.
- Scan/review/upload: dark navigation bar, legible camera hint and Finish button, scan name field, upload progress and demo action.
- Photos: dark rows, photo target and progress text, camera presentation, primary finish and quiet skip actions.
- Room size/setup: card fields and budget stepper, teal segmented selections, height-channel disabled state, help sheet, primary build action.
- Processing: centered progress, error/retry state and readable countdown.
- History: plain dark scan list, status colors, saved scan detail fields, upload/share/delete controls.
- AR layout: readable status card and alignment links over the camera, dark instruction card, shop action.
- Shop: dark totals, warning disclosure, product roles and links, alternatives sheet and over-budget state.

## Unfinished / notes

- Device visual QA and Swift compilation remain for the iOS tester. `scrollContentBackground(.hidden)` and `toolbarBackground` are available on iOS 17, but should be checked with the project deployment target in Xcode.
- DM Sans, Manrope and DM Mono TTFs can be added later for an exact web-font match; this task uses the requested system font substitutes.

## Design questions

- none
