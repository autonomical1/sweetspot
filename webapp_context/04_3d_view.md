# 04: 3D view (three.js)

## Library
- `three` + `@react-three/fiber` (React renderer for three.js) + `@react-three/drei` (`OrbitControls`, `Html` labels, `Line`, `Grid`), installed from npm with pinned versions and bundled by Vite (no CDN at runtime).
- Lazy-load `Scene3D.tsx` with `React.lazy` so the 2D view starts fast and three.js loads only when 3D is shown.
- Use `<Canvas frameloop="demand">` and call `invalidate()` on store changes, so the scene renders only when something changes (auto-orbit switches to `"always"`).
- Everything below is written in three.js terms; with R3F each item is a component (`<mesh>`, `<lineSegments>`, drei `<Line>`), and pointer events (`onPointerDown/Move/Up`) replace the manual `Raycaster`.

## Scene mapping
- Units: **1 three.js unit = 1 foot**. Axes are identical to the room frame (x east, y up, z south). No axis flips.
- Floor: plane from the floor polygon (or the `dimensions` box), dark grey with a 1 ft grid (`GridHelper` sized to the room, 5 ft major lines).
- Walls: one mesh per `wall` surface built from its polygon (two triangles for a 4-corner quad; use `ShapeGeometry` in the wall's own plane for more corners), light material, `side: DoubleSide`. **Walls between the camera and the room become transparent** (cut-away view): every frame, set opacity 0.15 for walls whose outward normal faces the camera, 1.0 otherwise. Ceiling hidden by default (toggle).
- Doors/windows/openings: thin boxes or planes offset 0.02 ft into the room from their wall (avoid z-fighting); window translucent blue, door brown.
- Objects: boxes (`center`, `size`, `rotation.y = degToRad(rotation_y)`), muted colours, labels via a small HTML overlay or `CSS2DRenderer`.
- Speakers: LIVE roles are `L R C LFE Ls Rs`; PLANNED staged 3D roles are `Lss Rss Lrs Rrs`, overheads `Ltf Rtf Ltr Rtr Ltm Rtm`, and `LFE2`. Size each box from the speaker's optional `size` `{width,height,depth}` in feet; if absent, use the chosen product's `dimensions`; otherwise fall back to the current default (0.6 x 1.0 x 0.5 ft, LFE 1.2 ft cube). Use role colours (`01_product_and_flows.md`), orient with `yaw_deg`/`pitch_deg` when present (otherwise `lookAt(aim)`), and show a floating role label. Heights are real (`y` is up); overhead speakers sit at ceiling height. A thin vertical line to the floor helps depth perception.
- PLANNED layout metadata includes `preset`, `standard`, `stage`, `seats`, and `projector`; render these when present and ignore them when absent.
- Listener: white sphere at ear height plus a cone/arrow along `facing`.
- Screen: plane `width x height` at `screen.center`, oriented to its wall (normal pointing into the room; for `wall_n` that is +z).
- Treatment patches: amber planes (35% opacity) on their wall, offset 0.03 ft into the room.
- Reflections: for the selected speaker (or all, with a toggle), `Line` from speaker to `point` to listener; brightness by `level_db`; a small dot at `point`.
- Lighting: ambient + one directional; no shadows needed (performance).

## Camera and controls
- `PerspectiveCamera` (fov 50) + `OrbitControls`: target = room centre at 3 ft; min/max distance bounded to the room size; disable panning below the floor.
- Presets (buttons): **Perspective** (default, from behind-above the listener looking at the front wall), **Top** (straight down, matches the 2D view), **Listener** (from the seat at ear height facing `facing`).
- Pitch mode: slow auto-orbit (0.1 rad/s) until the user interacts; off with `prefers-reduced-motion`.

## Picking and dragging
- `Raycaster` on pointer move/down against speaker meshes (and listener).
- Drag a speaker on a horizontal plane at its current height (`Plane(new Vector3(0,1,0), -y)`), disable OrbitControls while dragging, clamp x/z to `[0.25, width-0.25]` x `[0.25, length-0.25]`. Height is not draggable in 3D (keep `y`).
- On drag: update the shared state store (`05`), which triggers the throttled `POST /score` and re-renders both views.
- Hover: outline/emissive highlight + tooltip with role and ft-in position.

## Performance and robustness
- One `WebGLRenderer` (antialias), pixel ratio capped at 2, render on demand (only when state or camera changes; while auto-orbiting, every frame).
- Dispose geometries/materials when the room changes.
- If WebGL is unavailable (check once with a throwaway canvas), hide the 3D toggle and show a note; the 2D view must remain fully functional.
- Resize with a `ResizeObserver` on the canvas container.
