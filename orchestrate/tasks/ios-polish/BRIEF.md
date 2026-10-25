# ios-polish: configuration help text, no "Gemini" in user messages, AR alignment aids

## Goal
Three user-requested changes to the iPhone app (user, 2026-10-25 03:10), done after `ios-flow` is merged because they edit the same files.

## 1. Short descriptions of the speaker configurations (on the form from ios-flow)
Under the configuration pickers show a one-line explanation that updates with the selection. Number system: **first number = speakers around you at ear level, second number = subwoofers, third number = ceiling (height) speakers.** Copy to use (keep it short, plain English):
- **2.1:** "2 speakers (left and right) plus 1 subwoofer. Great for music and small rooms."
- **5.1:** "5 speakers (left, centre, right and two surrounds) plus 1 subwoofer. The standard home theatre."
- **7.1:** "7 speakers (adds two more surrounds at the sides) plus 1 subwoofer. Bigger rooms."
- Height channels: "**+2** adds 2 ceiling speakers, **+4** adds 4. They make sound come from above, as in Dolby Atmos." Examples shown when relevant: "7.1.4 = 7 speakers at ear level, 1 subwoofer, 4 ceiling speakers."
- Also a small "What do these numbers mean?" tap target (sheet or inline text) that explains the three numbers.

## 2. Never show the word "Gemini" to users
Replace every user-visible string that mentions Gemini or the model provider, in the iOS app and in backend error `detail` text that the app displays:
- iOS (`SweetspotApp.swift`, `CaptureViews.swift`, any view): e.g. "Waiting on Gemini to classify your photos..." -> "Analyzing your photos... this can take up to 30 seconds"; "Gemini is busy. Trying again in N s" -> "Our photo analysis is busy. Trying again in N s"; loader stage "Classifying materials with Gemini..." -> "Analyzing your room photos...".
- Backend: user-facing `detail`/messages in `backend/app/gemini_limits.py`, `materials_router.py`, `materials.py` (for example "Gemini is busy, retry in 12 s") -> neutral wording ("photo analysis"). Keep internal log lines, variable names, env var names and API field names unchanged. Update the backend tests that assert on the old text.
- Check with Grep: no `Gemini` remains inside any string literal that can reach the screen (code comments and identifiers may keep it).

## 3. AR alignment aids ("the AR hovers and does not match the walls")
Diagnosis from the code (not tested on a device): the layout is placed with `worldTransform(for: roomFrame)` in the scan session's world; if the AR session lost or re-created its origin (long pause during upload/photos, relocalization failure) everything floats. The only calibration today is the "north-west / north-east floor corner" tap flow, which users cannot understand, and which is hidden when the scan session is reused.
Deliver in `ARLayoutView.swift` and the caller `ARLayoutScreen`:
1. **Room outline overlay:** draw the room's floor rectangle and four corner posts (height = room height) from the room dimensions in the same room frame, as thin lines, so the user can see at once whether the model coincides with the real walls. Add `roomLengthFeet` / `roomHeightFeet` to the view's inputs from `Flow.roomDimensions`.
2. **Tracking state:** show `ARCamera.trackingState` (normal / limited with reason) in the status line and a hint ("Move the phone slowly and look at the floor and walls to re-lock").
3. **Always-available manual alignment**, also when the scan session is shared: a button **Align manually** with plain instructions: "Stand in the room, point at the floor where the FRONT wall (the screen wall) meets the left corner and tap, then tap the right corner of the same wall." Replace the words north-west / north-east in all user text with "front-left corner" / "front-right corner"; the math stays (first tap = room origin side, second tap sets the +x direction). A **Reset to scan alignment** button restores the automatic transform.
4. **Floor snap:** when raycasting fails to find a horizontal plane, say so ("Point at the floor") instead of ignoring the tap.
5. Keep per-frame work minimal: do not remove and re-add all anchors on every SwiftUI update unless the layout or transform changed.

## 4. Remove the "Found" field (user request 2026-10-25)
Remove the `LabeledContent("Found", value: summary.text)` rows from the scan detail views (`ScanHistoryView.swift` ~line 117 and `SweetspotApp.swift` ~line 1437) so the user no longer sees a "Found" field. Delete `summary.text` plumbing only if it becomes unused; keep the stored scan summary data.

## Deliverables and constraints
Swift cannot be compiled here: mirror existing patterns, check every symbol with Grep, keep edits small. HANDOFF.md must list changed functions and a manual test script for the iOS tester (including: does the outline coincide with the walls? if not, which offset/rotation is it off by, so we can fix the frame instead of guessing).

## Done when
`python -m ruff check .` and `python tools/smoke_tests.py` pass (the full pytest suite is slow: do NOT run it; run only the touched tests, backend/tests/test_gemini_limits.py and backend/tests/test_materials*.py); a Grep for `Gemini` shows no user-visible strings.

## Out of scope
Backend logic changes, web app, QR pairing (held), the "Set my seat" step (queued).

## Files you own
`Sweetspot_iOS_App/Sources/SweetspotPhoneApp/*.swift`, `Sweetspot_iOS_App/*.md`, `backend/app/gemini_limits.py`, `backend/app/materials_router.py`, `backend/app/materials.py`, backend tests that assert on those messages (`backend/tests/test_gemini_limits.py`, `backend/tests/test_materials*.py`), `orchestrate/tasks/ios-polish/HANDOFF.md`.
