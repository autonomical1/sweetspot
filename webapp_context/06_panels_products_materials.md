# 06: Panels, shopping list, materials, warnings

## Layout tab
- Big score: `metrics.score * 100`, one decimal, colour from red (<40) through amber to green (>75). Under it: "heuristic: speaker angles vs. ITU-R BS.775 and early reflections" (honest label).
- Speaker table: role chip (colour), position `x, z (height)` in ft-in, distance to listener in ft-in, angle from facing in degrees, and from `metrics.engine.placements`: model id, toe-in, predicted SPL. Clicking a row selects the speaker.
- Screen: wall, width x height in ft-in, diagonal in inches (16:9: `diag = width_in / 0.8716`).
- Warnings: `metrics.warnings` (collapse `INFO:` lines).

## Acoustics tab
- Reflections table: speaker, surface (kind + material, not the raw UUID), delay (ms, 1 decimal), level (dB, 1 decimal); sorted loudest first; rows with `level_db > -10` and `delay_ms < 15` flagged "strong". Click = select and draw the path.
- Treatment: count of patches and a sentence: "Put absorption panels at the N amber spots to tame the strongest early reflections."
- Room modes: `axial_modes_hz` as a small list or bar strip from 20 to 300 Hz, `schroeder_hz` as a vertical marker, sub position in ft-in. One-line explanation: "Below about {schroeder} Hz the room's modes dominate; the sub position was chosen to even them out."
- Model limits note (always visible, small): "2D/first-order model; materials estimated from photos; not a measurement."

## Shop tab
- Budget input ($, default `room.budget` or 1500) + **Get products**.
- Grouped by role (front L/R often the same product shown once with "x2"), each item: thumbnail (if any), title, price (`Intl.NumberFormat` with `currency`), source, seller, specs, dimensions in feet, and "View" link (`target="_blank" rel="noopener"`). Show `alternatives` (up to 3) as swap options with `price_delta`; for a pair listing the second role has price 0 and no alternatives, so swap through the first role. `pair_with` identifies the paired role. LIVE roles are `receiver`, `tv`, `mount`, `hdmi_cable`, and `speaker_wire`; bundled items may include `included_in`.
- Footer: total vs budget with a bar; "Prices from Google Shopping via SerpApi" once real data is live; stub data shows a "sample data" badge (items with `source == "stub"`).
- Errors: 404 = "Place the speakers first"; network/other = banner + retry.

## Room tab
- Dimensions in ft-in, floor area in sq ft, volume in cu ft, source badge, room warnings.
- Surfaces table: kind, material (with a small "from photo" marker when the material is not the default `drywall`, i.e. it was classified), absorption at 500/1000 Hz.
- Photo targets (`GET /rooms/{id}/photo-targets`): list of labels, so judges see what the phone captured.
- Materials classification is LIVE: show `materials/status` while running. On a fresh result, apply surfaces with confidence >= 0.5; identify cached results as cached and joined requests as shared in-flight work. On HTTP 429 show "Gemini is busy, retry in N s" using `retry_after_s` and `Retry-After`, and do not hammer the endpoint.

## Copy rules
- Short, plain sentences; feet and inches everywhere; numbers with units.
- Never show raw ids to users except in the Share/debug field.
- Error banners quote the server's `detail`.
