# 03: Data shapes, units and coordinates

Look at `sample_payloads/room_demo.json`, `room_scanned.json` and `optimize_demo.json` side by side with this file.

## Units
- JSON: **decimal feet**. Display: feet and inches via `formatFtIn` (`web/plot2d/format.js`): nearest inch, `7.5 -> 7' 6"`, `11.99 -> 12' 0"`. Inputs accept `7' 6"`, `7.5`, `7ft 6in`, `7-6` via `parseFtIn`.
- Times: `delay_ms`. Levels: `level_db` (dB relative to the direct sound; negative = quieter). Frequencies: Hz. Money: `price` + `currency`.

## Room frame
- x = east (room width), y = up, z = south (room length). The room box spans `0..width`, `0..height`, `0..length`. **North = -z.**
- Rectangular and demo rooms are only in this frame (`frame: null`). Scanned rooms are normalized into it by the backend (walls axis-aligned, corner at the origin) and carry `frame` for the phone's AR; **the web app ignores `frame`**.
- Listener: `listener.position` [x, y, z] (y = ear height, 3.6 ft) and `listener.facing` [fx, fz] (unit vector in x-z; north = [0, -1]).

## Room JSON (what to draw)
- `dimensions`: `{width, length, height}`.
- `surfaces[]`: `{id, kind, polygon: [[x,y,z], ...], material, absorption: {"125": ..., "4000": ...}}`.
  - `kind`: `wall`, `floor`, `ceiling`, `door`, `window`, `opening`. Walls in rectangular rooms have ids `wall_n|s|e|w`; scanned rooms use UUIDs. Never rely on ids for geometry: use the polygon.
  - Doors/windows/openings are separate polygons lying on (or within 0.2 ft of) a wall plane. Draw them on top of the wall (window: translucent blue; door: brown outline; opening: gap).
  - `material` comes from the phone's photos via Gemini (`drywall, glass, brick, carpet, hardwood, tile, curtain, unknown`). Show it in the Room tab; optionally tint walls by material.
- `objects[]`: furniture boxes `{id, category, center: [x,y,z], size: [w,h,d], rotation_y (degrees)}`. Categories include `sofa`, `television`, `table`, `storage`, `chair`, `bed`... Draw as simple boxes with a label; sofa and TV deserve recognizable colours.
- `warnings[]`: strings from the scan conversion (e.g. "no sofa detected; listener at room centre"). Show in the Room tab.
- `source`: `rectangle` (rect and demo) or `roomplan` (scan). `budget`: default budget for the Shop tab.

## Layout and metrics (optimize/score)
- `layout.speakers[]`: `{role, position: [x,y,z], aim: [x,y,z]}` for `L R C LFE Ls Rs`. `aim` is a point the speaker points at (draw a short arrow/line toward it).
- `layout.screen`: `{wall_id, center: [x,y,z], width, height}` or null. Draw as a flat rectangle on that wall facing into the room.
- `metrics.score`: 0..1 heuristic (show as 0-100 with one decimal, colour scale). It is the same number from optimize and score, so drag changes are comparable.
- `metrics.reflections[]`: `{speaker, surface_id, delay_ms, level_db, point: [x,y,z]}`, first-order only, <= 20 ms, sorted loudest first. Draw the path `speaker.position -> point -> listener.position`.
- `metrics.treatment_patches[]`: `{surface_id, center: [x,y,z], size: [w, h]}` (feet) on walls/windows: where acoustic panels would help most. Draw as amber translucent rectangles on the wall.
- `metrics.sub_modes`: `{schroeder_hz, axial_modes_hz: [...], sub_position}`; show as a small list/chart in the Acoustics tab.
- `metrics.warnings[]`: strings from the engine/adapter (e.g. "C placed geometrically (speakerplacer has no center model)", "C slid to avoid object obj_television"). Show them; lines starting with `INFO:` can be collapsed.
- `metrics.engine`: `{name: "speakerplacer", score_db, placements: [{role, model_id, toe_in_deg, predicted_spl_db, headroom_db}]}`. Show `model_id`, `toe_in_deg` and `predicted_spl_db` per speaker in the Layout tab ("placeholder speaker models" note).

## Rotation conventions (get these right once)
- Object `rotation_y` (degrees): world = center + R_y(rotation_y) * local, right-handed about +y, +90 deg maps local +x to world -z.
- three.js: identical convention: `mesh.rotation.y = THREE.MathUtils.degToRad(rotation_y)`.
- SVG plan (x right, z down): `rotate(${-rotation_y})` around the object centre; `objectSvgRotation(rotation_y)` in `web/plot2d/format.js` already returns this. Test with an object at rotation 90: its local +x edge must point up/north.
- Listener facing angle for display: `atan2(-fz, fx)` gives 90 deg for north in a math convention; simpler to draw an arrow from the listener along (fx, fz).
