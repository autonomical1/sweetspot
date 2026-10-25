# ios-shop-push handoff

## Completed
- `SweetspotApp.swift`: `ResultsScreen` and `ARLayoutScreen` now use `navigationDestination(isPresented:)` to push the same `ProductsView(flow: flow)` from their Shop buttons. Both remain inside `HomeView`'s `NavigationStack`; the `local-preview` button guards remain.
- `CaptureViews.swift`: `ProductsView` uses the enclosing navigation stack, titles the pushed screen "Shop", and relies on the standard back button. Its per-item swap options remain a sheet. Product loading, selection, budget, totals, links, and retry logic were not changed.

## Verification
- `python -m ruff check .`: passed.
- `python -m pytest -q`: 239 passed, 9 deselected, 1 failed, 48 errors. The errors came from access denied to the existing Windows pytest temp directory; the failure was the WSL `bash.exe` launcher access denial.
- `python -m pytest -q --basetemp C:\Users\neelm\AppData\Local\Temp\ios-shop-push-pytest -k 'not smoke_script_has_valid_bash_syntax' --tb=short`: 287 passed, 10 deselected.
- Neither `swiftc` nor `swift` is installed, so `swiftc -parse`, Xcode compilation, simulator, and device behavior could not be checked. SwiftUI API to confirm in Xcode: `navigationDestination(isPresented:destination:)` attached to each view within the enclosing `NavigationStack`.

## Manual device checks
1. Compute a layout on Results and tap "Shop this setup"; confirm Shop is pushed with the "Shop" title and standard back button.
2. Open AR and tap "Shop this setup"; confirm the same pushed Shop screen and title.
3. Tap the standard back button from each entry path; confirm the prior Results or AR screen returns.
4. Tap a product with alternatives; confirm the swap sheet opens and dismisses after selection.
5. Swap an item, go back, then reopen Shop from Results or AR; confirm the selection persists until layout or budget changes.

## Unfinished
- Swift parsing, Xcode build, and physical-device checks require a macOS/iOS toolchain.

## Design questions
- none
