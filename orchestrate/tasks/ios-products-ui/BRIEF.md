# ios-products-ui: shopping list screen with swap options, budget input, product-sized AR markers

## Goal
The iPhone app currently never calls the products endpoint. Add the product side of the app, built against the backend contract in docs/API.md section 4: after a layout is computed the user can set a budget, see the recommended setup (one product per speaker role, screen, projector) with prices, open product links, swap any item for one of its alternatives, and see the speakers in AR as boxes with the real product dimensions. There is no Xcode, iOS SDK or device in this sandbox: write careful, compile-minded Swift, keep the diff small, and say what you could not run.

## Read first
docs/API.md section 4 (the exact response, incl. `dimensions`, `pair_with`, `warnings`, and `alternatives` which another task is adding right now: decode every new field as OPTIONAL so the app works with and without it), Sweetspot_iOS_App/README.md and 05_checklist_and_open_questions.md, and the Swift sources in Sweetspot_iOS_App/Sources/SweetspotPhoneApp/ (Models.swift, BackendClient.swift, SweetspotApp.swift, ARLayoutView.swift, CaptureViews.swift). Note ios-ar-frame already landed: `RoomFrame`, `worldTransform(for:)` and `Flow.roomFrame` exist; keep them untouched. Example response: call shape in docs/API.md (no network here); also write one example file, see deliverables.

## Design decisions this brief encodes (user-approved scope; do not change)
- API (fixed, backend side): `GET /rooms/{room_id}/products?budget=N` returns `{budget, total, items:[{role, title, price, currency, link, thumbnail, source, seller?, specs?, dimensions?:{width,height,depth,source}, pair_with?, alternatives?:[{title, price, link, seller?, specs?, dimensions?, price_delta}]}], warnings?}`. Dimensions are FEET. Pair roles: the second role of a pair (R, Rs) has price 0, `pair_with` set, `alternatives: []`; swaps for a pair go through the first role (L, Ls) whose alternatives are pair listings.
- Budget: a field on the results screen next to "Compute layout": a stepper-style control, default 1500 USD, step 100, range 100...20000, remembered with `@AppStorage`. The budget is also sent when creating a room: add an optional `budget` parameter to `BackendClient.upload(dto:sessionID:budget:)` and `rectangle(...)` (the backend accepts `budget` on `POST /rooms` and `POST /rooms/rect`); `demo` takes none.
- Shop screen: opened by a "Shop this setup" button available after a layout exists (results screen and AR screen). It calls the products endpoint (timeout 90 s: the first request after a server deploy can take about 20 s; show a spinner and the text "Finding products...") and shows: total vs budget (green when under, red if over), the `warnings` (readable, collapsible), and one row per item in the order C, L, R, LFE, Ls, Rs, screen, projector: role chip, title (2 lines), seller, price with USD formatting; second pair roles show "Included in pair with L" instead of a price; dimensions as `W x H x D in` (feet converted to inches, rounded); a button that opens `link` in Safari (`Link` / `UIApplication.open`, https only, ignore bad URLs). Handle empty items and HTTP errors with a readable message and a Retry button.
- Swap options: tapping a row (not the link) opens its alternatives (title, seller, price, a `+$12` or `-$40` delta from `price_delta`, dimensions). Choosing one replaces the item locally and recomputes the total from the item prices; an alternative whose delta would push the local total over the budget is shown disabled with the reason. No network call for a swap. Rows with no alternatives show nothing extra. A pair swap replaces both roles (the second role stays price 0 and keeps `pair_with`).
- Keep the user's chosen setup in app state (`Flow`), so reopening the Shop screen or the AR screen shows the same selection until the layout or budget changes (changing either refetches and resets the selection).
- AR: when a chosen setup exists and an item has `dimensions`, draw that speaker's marker as a box of `width x height x depth` (feet * 0.3048 meters; width on x, height on y, depth on z), sitting on its position (bottom at the marker position's y minus half height is NOT required: center the box on the existing position), rotated about +y to face the speaker's `aim` point in the same frame; otherwise keep the current sphere. Do not change how the frame transform is applied (ios-ar-frame). Keep the speaker role label.
- No new Swift files and do NOT touch the Xcode project file: put the new views in CaptureViews.swift, new model types in Models.swift, the client method in BackendClient.swift, state/wiring in SweetspotApp.swift, the AR box change in ARLayoutView.swift.
- Do not change pairing, scan, photo, material or frame logic, the DTO export, or the backend Python.

## Deliverables
1. Models.swift: Decodable types for the products response with all new fields optional; a pure helper `chosenTotal(items:)` and a small formatter for feet -> inches strings.
2. BackendClient.swift: `products(roomID:budget:)` (GET, timeout 90) and the optional `budget` parameter as above.
3. SweetspotApp.swift: budget control, "Shop this setup" entry points, state in `Flow` (selection, last budget).
4. CaptureViews.swift: `ProductsView` (list, swap sheet, states: loading, error, empty, loaded).
5. ARLayoutView.swift: product-sized box markers with the existing sphere fallback.
6. Sweetspot_iOS_App/Resources/products.example.json: an example response matching section 4 (all optional fields present for at least three items, one pair).
7. HANDOFF.md: files and functions changed; what could not be verified (no compiler); numbered manual device checks (budget persists, shop screen loads against https://144-202-27-51.sslip.io, swap changes the total, link opens, AR boxes appear with sensible sizes); Swift APIs you were unsure about.
8. If `swiftc` or `swift` exists in this sandbox run `swiftc -parse` on the changed files and report it; if not, say so.

## Done when
The Swift reads cleanly and is internally consistent (every symbol defined, optionals handled, no force unwraps on network data), `python -m ruff check . && python -m pytest -q` still passes (no Python changes), no edits outside OWNS.txt.

## Out of scope
Backend/Python, project file, new files other than the example JSON, the "tap where you sit" listener, thumbnails (always null), photo/material flows, a purchase/checkout flow. Put unsettled choices under `## Design questions` in HANDOFF.md.
