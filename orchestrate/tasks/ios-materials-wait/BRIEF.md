# ios-materials-wait: show that we are waiting on Gemini, block repeat taps, handle "busy"

## Goal
On the photo/results flow the user taps "Finish photos and classify" (or "Skip photos and continue"); `Flow.classify()` calls `POST /rooms/{id}/materials`, which takes 5 to 20 s. Nothing in the UI shows that, the button stays enabled, and the user tapped it 5 times and caused 5 Gemini calls. The backend (task gemini-limits, being built in parallel) now joins duplicate requests, caches, and returns HTTP 429 when Gemini is busy. Make the app behave well. There is no Xcode/SDK/device here: write careful, compile-minded Swift, small diff, and say what you could not run. The work lands on branch `ios-phone_context` (the orchestrator merges your task branch there); do not touch git.

## Read first
docs/API.md section 6 (the paragraph "Gemini limits on `POST /rooms/{id}/materials`", the `GET /rooms/{id}/materials/status` row, and the 429 body `{"detail": "...", "retry_after_s": N}`), Sweetspot_iOS_App/Sources/SweetspotPhoneApp/SweetspotApp.swift (`Flow.classify()`, the photos screen buttons "Finish photos and classify" / "Skip photos and continue", photo upload buttons and their states), BackendClient.swift (`classify`, `request`, `BackendError.http`), Models.swift.

## Design decisions this brief encodes (do not change)
- While a classification is in flight: all buttons that start it are disabled, and the screen shows a progress view with the text "Waiting on Gemini to classify your photos... this can take up to 30 seconds" plus an elapsed-seconds counter (updates every second). Also disable the per-photo upload/skip buttons that can race it, except Back.
- A single in-flight guard in `Flow` (`isClassifying`) so even programmatic double calls do nothing; cleared in a `defer`, including on error and cancellation.
- Add a client method `materialsStatus(roomID:) async throws -> MaterialsStatus` (GET `rooms/{id}/materials/status`, optional fields) and use it when the photos screen appears: if the server says `running` (for example after an app relaunch or from another device), show the same waiting state and poll every 2 s until `idle`, then fetch the result by calling `classify` once (the server returns the cached result).
- HTTP 429 handling: decode `retry_after_s` from the error body (add it to `BackendError` handling without breaking existing cases; fall back to 10 s); show "Gemini is busy. Trying again in N s" with a visible countdown, keep buttons disabled during the countdown, then retry automatically ONCE; if it fails again show the plain error with a Retry button. Do not loop.
- Other errors keep today's behaviour (readable message). The optional `"status"` field of the response (`fresh|cached|joined`) is decoded as optional and may be shown as a small caption ("Used saved results") for `cached`.
- Timeouts: the classify request keeps its 120 s timeout.
- No new Swift files, do not touch the Xcode project file, no Python changes. Do not change unrelated flows, the shop screen, the AR code or the DTO export.

## Deliverables
1. Models.swift: `MaterialsStatus` (optional fields), optional `status` on `MaterialsResponse`.
2. BackendClient.swift: `materialsStatus(roomID:)`, 429 body decoding helper.
3. SweetspotApp.swift: `Flow` in-flight guard, countdown/elapsed state, polling on appear, the waiting UI and disabled buttons.
4. HANDOFF.md: what changed (file/function names), what you could not verify, numbered manual device checks (tap Finish 5 times: one request, progress text and counter shown; relaunch during a run; 429 countdown and single retry; skip photos path), Swift APIs you were unsure about.
5. If `swiftc`/`swift` exist run `swiftc -parse` on the changed files and report; else say so.

## Done when
The Swift is internally consistent (every symbol defined, optionals handled, no force unwraps on network data), `python -m ruff check . && python -m pytest -q` still passes, no edits outside OWNS.txt.

## Out of scope
Backend/Python, the Xcode project file, other screens. Put unsettled choices under `## Design questions` in HANDOFF.md.
