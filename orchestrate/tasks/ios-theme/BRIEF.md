# ios-theme: minimalist iOS UI matching the web app (SwiftUI only, no behaviour changes)

## Goal
Restyle the whole iPhone app so it looks like the Sweetspot web app (`webapp/src/styles.css`, `webapp/src/components/panels/panels.css`): dark, quiet, one teal accent, thin borders, small caps "eyebrow" labels, generous spacing. Minimalist: remove decorative chrome, heavy system List/Form grouping where a simple card works, and extra colours.

## Design tokens (from the web app, use exactly)
- Background `#10151b`; surface (bars, sheets) `#141a21`; card/panel `#161d25`; raised control `#1d252e`; input `#1c252e`.
- Borders `#2a333d` (1 pt) and stronger `#313b46`. Radius: 7 pt controls, 9 pt cards, 100 for pills.
- Text primary `#e9edf0`, secondary `#89959f`, tertiary/eyebrow `#75818c`.
- Accent teal `#5cddc5` (text on accent `#10231f`); accent for outlines/links `#6cddc8`; accent dim `#4b746e`.
- Status: warning amber `#f4bd61`, error `#f28b82`, success `#77d79a`.
- Typography: the web uses DM Sans (body), Manrope (headings, bold, tight tracking) and DM Mono (tiny uppercase eyebrow labels with +1.2 letter spacing). We cannot bundle fonts offline, so use system fonts: `.system(.body, design: .default)` weights 400/500/600/700 for body, `.system(design: .rounded)` bold with `tracking(-0.4)` for headings and the "S" brand mark, and `.system(design: .monospaced)` 9-10 pt uppercase with `tracking(1.2)` for eyebrow labels. Keep type sizes small and calm (body 15, secondary 13, eyebrow 10).
- Force dark appearance: `.preferredColorScheme(.dark)` at the app root, and a `.tint` of the accent.

## Deliverables
1. New file `Sweetspot_iOS_App/Sources/SweetspotPhoneApp/Theme.swift` with: `Color(hex:)` initializer, a `Theme` enum of the tokens above, `ViewModifier`s / styles: `SweetspotPrimaryButtonStyle` (filled teal), `SweetspotQuietButtonStyle` (raised surface, 1 pt border), `SweetspotCard` modifier (panel background, border, 9 pt radius), `EyebrowText` view (mono, uppercase, tertiary), `SweetspotScreen` background modifier (full-bleed `#10151b`, hides default List/Form backgrounds with `.scrollContentBackground(.hidden)`), and a small "S" brand mark view like the web top bar.
2. Register `Theme.swift` in `SweetspotPhoneApp.xcodeproj/project.pbxproj` by copying the four lines that mention `CaptureViews.swift` (PBXBuildFile, PBXFileReference, group child, Sources build phase) with NEW unique 24-hex IDs and the new name. Do not change anything else in the project file.
3. Apply the theme to EVERY screen in `SweetspotApp.swift`, `CaptureViews.swift`, `ScanHistoryView.swift`, `ARLayoutView.swift` overlays (status pill, buttons, hints) and `ScanCapture.swift` overlays: home, device check, QR pairing overlay, scan / review, upload progress, photos, setup form (replace the default Form look with cards and segmented controls in the accent), processing, results / shop list, history list, AR layout screen. Navigation bars: dark surface `#141a21`, no large titles unless already used.
4. Keep copy as is (other agents own wording) except fixing anything that becomes clipped.

## Done when
All Swift files still parse by inspection (no compiler here: check every symbol with Grep, keep edits mechanical, never rename existing types/functions/properties, do not change logic, state, networking or navigation), `python -m ruff check .` and `python tools/smoke_tests.py` pass. HANDOFF.md lists the new styles and one screen-by-screen checklist for the iOS tester (what to eyeball, any place you were unsure about a modifier's availability on iOS 17).

## Out of scope
Backend, web, behaviour, copy, app icon, bundled fonts (note in HANDOFF that DM Sans / Manrope / DM Mono TTFs can be added later to match exactly).

## Design decisions encoded here
System fonts instead of bundled web fonts; dark-only; one accent colour; cards instead of grouped Forms.

## Files you own
`Sweetspot_iOS_App/Sources/SweetspotPhoneApp/*.swift`, `Sweetspot_iOS_App/SweetspotPhoneApp.xcodeproj/project.pbxproj`, `orchestrate/tasks/ios-theme/HANDOFF.md`.
