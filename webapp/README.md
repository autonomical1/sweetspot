# SweetSpot AV Room Planner

An interactive browser based AV room planner built with React, TypeScript, Vite, Three.js, and Zod. The default room is generated entirely from geometry; GLB models and screen images are optional.

## Run locally

```sh
npm install
npm run dev
```

Create a production build with `npm run build`. Run the schema, coordinate, and projection checks with `npm test`.

## Coordinate conventions

- All lengths are meters and the scene uses **Y-up**.
- The floor center is `[0, 0, 0]`. The floor extends from `-length / 2` to `+length / 2` along Z and `-width / 2` to `+width / 2` along X.
- Positive X points right, positive Y points up, and negative Z is the room's front wall / default device facing direction.
- Equipment `position` is its center. `dimensions` are `[width, height, depth]`.
- JSON `rotation` is `[X, Y, Z]` in degrees. Imported GLB files should use Y-up and face their front along local negative Z for the default device orientation.
- Projector `lensOffset` is the vertical distance in meters from the equipment center to its lens (negative means below center). The projection preview supports perpendicular projection only. Width is lens-to-screen distance divided by throw ratio; height is width divided by aspect ratio. Angled projection is reported as unsupported.

## JSON format

The format has a required version (`1`), room dimensions and colors, equipment, and optional named seating viewpoints. A full working setup is in [`examples/home-theater.json`](examples/home-theater.json). Load a file with **Load room file**. Its equipment is displayed read-only; **Export setup** downloads the loaded configuration.

```json
{
  "version": 1,
  "units": "m",
  "coordinateSystem": "Y-up",
  "room": { "width": 5.6, "length": 7.2, "height": 2.8 },
  "equipment": [{
    "id": "screen-main", "name": "Screen", "type": "screen",
    "dimensions": [3.1, 1.75, 0.08], "position": [0, 1.45, -3.48],
    "rotation": [0, 0, 0]
  }],
  "seats": [{ "id": "main", "name": "Main seat", "position": [0, 1.1, 1.1], "target": [0, 1.5, -3.48] }]
}
```

Equipment types are `speaker`, `projector`, `screen`, and `seat`. Each object can include an optional `description` used in its on-object popup. Projectors can define `lensOffset`, `throwRatio`, `aspectRatio`, and `targetScreenId`. Any equipment can define a `modelUrl`; screens can define `imageUrl`.

## GLB assets

Create or export a GLB from Blender, Meshy, or Tripo and reference it in the room JSON using `modelUrl`. The default room bundles speaker, projector, and fixed-screen GLBs in `public/models/`. The loader caches each model, clones it for device instances, centers its bounds, and scales it to the configured dimensions. Blender export should keep Y-up; model front orientation should face local negative Z. No external model service or credentials are required.

## MVP notes

Left-drag to orbit, right-drag to pan, and scroll to zoom. **Seat POV** hides the chair and moves the camera to the first configured viewpoint; left-drag to look around in first person. Returning to **Orbit** or **Top** restores the room view and shows the chair again. In orbit and top views, the floor, walls, and ceiling become translucent so the room remains visible; toggle walls or ceiling as needed. Select devices from the viewport or list for an on-object label and description. Objects cannot be edited in the viewer. Room dimensions, colors, and equipment are supplied in the validated JSON file.
