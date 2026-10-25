# ios-flow: scan -> photos -> form -> automatic processing (no "Compute" button)

## Goal
The user should only scan, take photos, fill in one form and wait. No "Compute speaker layout" button. Flow (user, 2026-10-25 02:52): **scan -> photos -> form (budget + speaker configuration) -> loader while the backend works -> AR/layout**.

## Design decisions encoded
- After the photos step ("Finish photos and classify" / "Skip photos") the app shows a **form screen** with: (a) budget (existing stepper or number field, default from the room/`flow.budget`), (b) base configuration picker **2.1 / 5.1 / 7.1**, (c) height channels picker **None / .2 / .4** (disabled with a note for 2.1). The combined value is the backend `preset`: `2.1`, `5.1`, `7.1`, `5.1.2`, `5.1.4`, `7.1.2`, `7.1.4`. Default 5.1, none. A single primary button **Build my layout**.
- Gemini classification starts **as soon as the user leaves the photos step** (in the background while they fill the form), not on the form button. **Build my layout** waits for classification to finish (or skips it when no photos were taken), then calls optimize with the preset, then goes straight to the AR/layout screen. The user never sees an intermediate Results screen or a Compute button; remove the button and the `ResultsScreen` navigation from the flow (keep the `Flow.compute()` method but make it take the preset and reuse the `isComputing` guard).
- **Loader screen** (full screen, no repeat taps possible): stage text that follows reality: "Classifying materials with Gemini..." (show the existing 429 countdown / "Waiting on Gemini" text from `Flow`), "Placing your speakers..." (optimize), "Finding products..." only if the product prefetch is started; elapsed seconds counter; a friendly note that the first layout can take up to a minute. Errors show a message with **Retry** (re-runs only the failed stage) and **Back to form**.
- `POST /rooms/{id}/optimize` body becomes `{"options": {"preset": "<preset>"}}` (`BackendClient.optimize(roomID:preset:)`). `2.1` is added on the server by task `backend-2-1`; until it is deployed the picker still offers it, the call may return 422 and the loader shows the server message with Back to form.
- Demo room and "Enter room dimensions" (phone-only shortcuts, no photos) also end at the same form screen instead of the Results screen.
- Offline preview (`local-preview`) keeps working: the form is shown, **Build my layout** goes to the preview layout.
- Keep: screen stays awake during the scan, the Gemini waiting UI, the repeat-tap guards, the budget behaviour (`flow.setBudget`), recent scans.

## Deliverables
1. SwiftUI changes in `Sweetspot_iOS_App/Sources/SweetspotPhoneApp/` (`SweetspotApp.swift`, `BackendClient.swift`, new files allowed: `SetupFormView.swift`, `ProcessingView.swift`). New `Phase` cases as needed (`.form`, `.processing`).
2. `Flow` additions: `selectedBase`, `selectedHeight`, `preset` computed property, `classificationTask` started when leaving photos, `buildLayout()` orchestrating classify -> optimize -> AR with stage state `@Published var processingStage` and elapsed seconds.
3. Update `Sweetspot_iOS_App/03_pairing_and_photos.md` and README flow descriptions; list changed functions and a manual test script in HANDOFF.md.
4. Swift cannot be compiled here: mirror existing patterns, check every brace and every referenced symbol with Grep, avoid new dependencies.

## Done when
No view in the main flow shows a "Compute speaker layout" button; `python -m ruff check . && python -m pytest -q` still pass (no backend change).

## Out of scope
The QR pairing change (held in branch `task/ios-qr-pairing`; expect merge conflicts in `SweetspotApp.swift` that the orchestrator resolves), AR rendering, backend.

## Files you own
`Sweetspot_iOS_App/Sources/SweetspotPhoneApp/SweetspotApp.swift`, `BackendClient.swift`, `SetupFormView.swift`, `ProcessingView.swift`, `Sweetspot_iOS_App/03_pairing_and_photos.md`, `Sweetspot_iOS_App/README.md`, `orchestrate/tasks/ios-flow/HANDOFF.md`.
