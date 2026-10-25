# ios-shop-push: Shop screen as a pushed navigation screen (not a sheet)

## Goal
User-resolved design fork: the Shop screen must be a pushed navigation screen, not a sheet. Change `ProductsView` presentation in the iPhone app from `.sheet` to a navigation push, from both entry points (Results screen and AR screen). There is no Xcode/SDK/device in this sandbox: write careful, compile-minded Swift, keep the diff small, and say what you could not run. The work lands on the branch `ios-phone_context` (the orchestrator merges your task branch there); do not touch git.

## Read first
Sweetspot_iOS_App/Sources/SweetspotPhoneApp/SweetspotApp.swift (search `showingShop`, `ProductsView`, `.sheet`, the NavigationStack/NavigationView structure, `ARLayoutScreen`), CaptureViews.swift (`ProductsView`, the swap sheet), orchestrate/tasks/ios-products-ui/HANDOFF.md.

## Design decisions this brief encodes (do not change)
- Shop is pushed with `navigationDestination(isPresented:)` (or `NavigationLink` if the existing stack is a `NavigationView`; match what the app already uses; if there is NO navigation container around the AR screen, wrap minimally and report). Back button is the standard one; title "Shop".
- The per-item swap options remain a sheet (small modal list) inside the pushed screen; do not change swap logic, totals, the budget control, link opening, the loading/error/retry states, or the stale-request token logic.
- Both entry points ("Shop this setup" on Results and on the AR screen) must push the same screen with the same shared state (`Flow`): reopening shows the same selection until the layout or budget changes.
- Keep the offline-preview guard (no Shop button for `local-preview`).
- No new Swift files, do not touch the Xcode project file, no Python changes.

## Deliverables
1. The presentation change in SweetspotApp.swift and CaptureViews.swift only as needed.
2. HANDOFF.md: what changed (file/function names), what you could not verify (no compiler), numbered manual device checks (push from Results, push from AR, back, swap sheet still opens, state preserved), Swift APIs you were unsure about.
3. If `swiftc`/`swift` exist run `swiftc -parse` on the changed files and report; else say so.

## Done when
The Swift is internally consistent (every symbol defined, optionals handled), `python -m ruff check . && python -m pytest -q` still passes, no edits outside OWNS.txt.

## Out of scope
Everything else in the app, backend, products logic. Put unsettled choices under `## Design questions` in HANDOFF.md.
