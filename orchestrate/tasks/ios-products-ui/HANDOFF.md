# ios-products-ui handoff

## Completed
- `Models.swift`: added product response, item, dimensions and alternative decoders. New catalog fields decode as optional. Added `chosenTotal(items:)` and feet-to-rounded-inches formatting.
- `BackendClient.swift`: added a 90-second products GET with a URL query item, plus optional room budget in scan and rectangle creation.
- `SweetspotApp.swift`: added a persistent $100-step budget on Results, shop entry buttons on Results and AR, selected product state in Flow, local swaps (including paired roles), and selection reset after room, layout or budget changes.
- `CaptureViews.swift`: added shop loading, error/Retry, empty, warning, item and swap views. Links open only when they are valid HTTPS URLs. Swap options exceeding the remaining budget are disabled.
- Retry 1: swap labels now use the optional backend `price_delta` and say "vs recommended". The budget guard still uses the current selected price and current local total.
- Retry 1: product loads now use a generation and request token. Budget, room and layout resets invalidate in-flight requests; the open Shop view starts a replacement load for the new inputs, and stale successes or failures cannot change its state.
- `ARLayoutView.swift`: draws selected speaker boxes from feet-based dimensions, aimed toward each speaker aim point, and retains sphere fallback, role labels and the existing room-frame transform.
- `Resources/products.example.json`: example response with optional fields on three items and an L/R pair.

## Verification
- `python -m ruff check .`: passed.
- Retry 1: `python -m ruff check .` passed; `python -m pytest -q --basetemp C:\Users\neelm\AppData\Local\Temp\ios-products-ui-pytest-retry --tb=short` finished with 276 passed, 9 deselected, 1 failed. The sole failure is `test_smoke_script_has_valid_bash_syntax`: the Windows WSL `bash.exe` launcher returns access denied.
- `python -m pytest -q`: 233 passed, 40 errors from permission denied on the existing pytest temp directory, and one failure because the Windows WSL `bash` launcher returns access denied.
- `python -m pytest -q --basetemp C:\Users\neelm\AppData\Local\Temp\ios-products-ui-pytest -k 'not smoke_script_has_valid_bash_syntax' --tb=short`: 273 passed, 10 deselected.
- `git diff --check` and example JSON parse: passed.
- Neither `swiftc` nor `swift` is installed, so Swift parsing, iOS SDK compilation, signing, simulator and device behavior could not be verified. APIs to confirm in Xcode: RealityKit `MeshResource.generateBox(size:)` with `SIMD3<Float>`, SwiftUI `.sheet(item:)` on `ProductItem`, and the `Stepper` Double binding.

## Manual device checks
1. Set the Results budget, leave and reopen Results, then relaunch the app; confirm the value persists and room creation carries it.
2. Compute a layout and open Shop against `https://144-202-27-51.sslip.io`; confirm the loading text, products, warnings and Retry path.
3. Swap a product; confirm the total changes, over-budget swaps are disabled, and an L/R or Ls/Rs pair changes both rows while the second stays included at $0.
4. Open a product link and confirm Safari opens the HTTPS listing.
5. Return to AR; confirm selected speakers render as sensibly sized boxes facing their aim, while products without dimensions remain spheres. Reopen Shop and confirm the selection remains. Recompute or change budget and confirm it resets.

## Unfinished
- Xcode compilation and physical-device checks above.

## Design questions
- Shop presentation: used a sheet from Results and AR as the smallest reversible UI option; a pushed navigation screen is an alternative. [resolved: pushed navigation screen, not a sheet; task ios-shop-push]
