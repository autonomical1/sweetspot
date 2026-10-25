# ios-error-audit: no error or status message in the iPhone app should give away internals

## Goal
Read ALL the Swift in `Sweetspot_iOS_App/Sources/SweetspotPhoneApp/*.swift` and make every message a person can see (alerts, `flow.error`, banners, status lines, loader text, empty states, share/shop failures) short, plain and safe. Nothing user-visible may reveal: server URLs or hostnames, endpoint paths, HTTP status codes or raw response bodies, backend `detail` text verbatim, internal ids (room ids, session ids, surface UUIDs, scan ids), file paths, Swift/Foundation error descriptions (`localizedDescription` of decoding/URLSession errors, `DecodingError`, `NSError` domains and codes), stack/type names, model/provider names, rate-limit or quota internals, or debug strings. Raw detail may stay in a debug log only.

## What to do
1. Grep every place an error or status reaches the UI: `self.error =`, `flow.error`, `error.localizedDescription`, `Text(` with interpolated errors, `alert(`, `alignmentState = `, `processingError`, `BackendError` and its `errorDescription`, any `String(describing:)` shown to people. Also read how `BackendClient` turns HTTP failures and decoding failures into messages.
2. Add ONE central mapper (put it in `BackendClient.swift`, no new files so the Xcode project needs no change): `func userMessage(for error: Error) -> String` that maps to friendly text by category: offline / timed out -> "Can't reach Sweetspot. Check your connection and try again."; 404 room or session -> "That room isn't available any more. Start a new scan."; 410/expired -> "This pairing code has expired. Scan a new QR code."; 413 -> "That photo is too large."; 422/400 -> "That didn't look right. Please try again."; 429 or busy -> "We're busy right now. Trying again shortly." (keep any retry-seconds number only if it is already shown as a countdown); 5xx and everything else -> "Something went wrong. Please try again." Keep the HTTP status and `detail` in an `os.Logger` (`Logger(subsystem: "com.sweetspot.phone", category: "backend")`, `.error` level, privacy `.private`) so debugging is still possible from Xcode.
3. Replace each user-visible use with the mapper or a fixed friendly string. Keep existing behaviours: retry/countdown logic, which button appears, navigation. Do not change anything that is not a message.
4. Review fixed strings too: remove words like "backend", "API", "endpoint", "Gemini", "RoomPlan DTO", "session_id", "JSON", "decode", "URL", "timeout" (say "took too long"), coordinate/unit jargon in error text ("Coordinates are converted from feet to meters" style footers) unless it is genuinely useful instruction.
5. Do not touch copy that is not an error/status message.

## Constraints
Swift cannot be compiled here: mirror existing patterns, Grep every symbol you use, keep edits small and mechanical, add `import os` only where you use `Logger`. Do not rename or remove existing types/functions. No new files. `python -m ruff check .` and `python tools/smoke_tests.py` must pass.

## Done when
A final Grep shows no `localizedDescription`, `.description`, status codes or raw `detail` flowing into any `Text`, alert or `flow.error` assignment. HANDOFF.md lists every message changed (old -> new, file and line) and anything backend-side worth tightening (backend `detail` strings the app might still receive) WITHOUT editing backend files. Add a short manual test list for the iOS tester (airplane mode, expired QR, stopped server, bad photo).

## Out of scope
Backend, web, restyling, wording of normal (non-error) screens.

## Files you own
`Sweetspot_iOS_App/Sources/SweetspotPhoneApp/*.swift`, `orchestrate/tasks/ios-error-audit/HANDOFF.md`.
