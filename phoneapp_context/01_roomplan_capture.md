# 01: RoomPlan capture

**[Apple docs]** = confirmed on Apple's pages on 2026-10-24. **VERIFY** = check on the device.

## Xcode project setup
- iOS App, SwiftUI lifecycle, **Deployment Target iOS 17.0** (`polygonCorners` is iOS 17.0+; the rest of RoomPlan is 16.0+).
- `Info.plist`: `NSCameraUsageDescription` (e.g. "Sweetspot uses the camera and LiDAR to scan your room"). Needed for RoomPlan, VisionKit QR scanning and photos.
- Imports: `RoomPlan`, `ARKit`, `RealityKit` (AR), `VisionKit` (QR), `simd`.
- Signing with the personal team is fine (free profile expires after 7 days). Device needs Developer Mode on (Settings > Privacy & Security > Developer Mode).
- On launch check `RoomCaptureSession.isSupported` (`static var isSupported: Bool` **[Apple docs]**). If false: no LiDAR, show only "Use demo room" / "Enter room size".

## RoomPlan API surface (as documented)
| Type | Facts **[Apple docs]** |
|---|---|
| `RoomCaptureView` | `@MainActor` UIKit view, iOS 16.0+. `init(frame: CGRect)` and **`init(frame: CGRect, arSession: ARSession)`**. `var captureSession: RoomCaptureSession!`. `var delegate: (any RoomCaptureViewDelegate)?`. Conforms to `NSCoding`. |
| `RoomCaptureViewDelegate` | `protocol RoomCaptureViewDelegate : NSCoding`. Methods: `captureView(shouldPresent: CapturedRoomData, error: (any Error)?) -> Bool` and `captureView(didPresent: CapturedRoom, error: (any Error)?)`. Both have default implementations. The delegate type must satisfy `NSCoding`, so use an `NSObject` subclass (and add `init?(coder:)`/`encode(with:)`) or a `UIViewController`. |
| `RoomCaptureSession` | `static var isSupported: Bool`; `var arSession: ARSession` (iOS 16.0+, "You may use this object to display your own AR experience"; set at init, **you cannot assign it**); `func run(configuration: RoomCaptureSession.Configuration)`; `func stop()` and **`func stop(pauseARSession: Bool)`**; `var delegate: (any RoomCaptureSessionDelegate)?`. |
| `RoomCaptureSession.Configuration` | `init()`; `var isCoachingEnabled: Bool`. |
| `RoomCaptureSessionDelegate` | `AnyObject` protocol, all methods have defaults: `didStartWith`, `didAdd room`, `didUpdate room`, `didRemove room`, `didChange room`, `didProvide instruction`, `didEndWith data: CapturedRoomData, error:`. Use `didUpdate` to show live counts. |
| `CapturedRoom` | iOS 16.0+. `Codable` (Encodable + Decodable). Properties: `identifier: UUID`, `story: Int`, `version: Int`, `walls`, `doors`, `windows`, `openings`, **`floors`** (all `[CapturedRoom.Surface]`), `objects: [CapturedRoom.Object]`, `sections: [CapturedRoom.Section]`. Also `export(to: URL, exportOptions: CapturedRoom.USDExportOptions) throws` (USDZ; we do not need it). |
| `CapturedRoom.Surface` | `identifier: UUID`, `category`, `dimensions: simd_float3` ("a bounding box that contains the surface"), `transform: simd_float4x4` ("position and orientation in the scene"), `confidence: CapturedRoom.Confidence`, `completedEdges: Set<Edge>`, `polygonCorners: [simd_float3]` (**iOS 17.0+**, "described in local plane coordinates"), `curve: Curve?`, `parentIdentifier: UUID?`, `story: Int`. |
| `Surface.Category` | `floor`, `door(isOpen: Bool)`, `opening`, `wall`, `window`. |
| `CapturedRoom.Object` | `identifier`, `parentIdentifier: UUID?`, `category`, `confidence`, `dimensions: simd_float3` ("bounding box sized to the object's extremities"), `transform: simd_float4x4`, `story`, `attributes: [any CapturedRoomAttribute]`. |
| `Object.Category` (16) | bathtub, bed, chair, dishwasher, fireplace, oven, refrigerator, sink, **sofa**, stairs, storage, stove, table, **television**, toilet, washerDryer. |

We care about `sofa` (listener position), `television` (front wall hint), `table`, `storage`, `chair`.

## Scan lifecycle
1. **Start:** create the view, set the delegate, run: `captureView.captureSession.run(configuration: config)` with `config.isCoachingEnabled = true`.
2. Tell the user: stand in the middle, turn slowly, cover every wall, door, window, the sofa and the TV, lights on, 30-60 s.
3. **Done:** `captureView.captureSession.stop()` (or `stop(pauseARSession: false)`, see AR note below).
4. Delegate `captureView(shouldPresent:error:)`: return `error == nil` so RoomPlan post-processes.
5. Delegate `captureView(didPresent:error:)`: this is the final `CapturedRoom`. Store it in the view model.
6. Show a summary ("4 walls, 1 door, 2 windows, sofa: yes, TV: yes"). Warn if there is no sofa. Offer Rescan.
7. Save the local backup (below), then upload (`02_backend_integration.md`).

### AR note (for `04_ar_overlay.md`)
`RoomCaptureView(frame:arSession:)` accepts an `ARSession` you create, and `RoomCaptureSession.arSession` exposes the one in use. If the AR overlay later runs on that same `ARSession`, the world frame is identical to the scan and layout coordinates need no alignment. Decide this on day one: create **one** `ARSession` (e.g. `let arView = ARView(frame: .zero)` and pass `arView.session`) and reuse it. Use `stop(pauseARSession: false)` so it keeps tracking. **VERIFY** that RoomPlan accepts a RealityKit `ARView`'s session and that tracking continues after `stop(pauseARSession: false)`.

## Export format: send our own explicit JSON (recommended)
Although `CapturedRoom` is `Codable`, **do not rely on its default JSON** as the wire format: Apple does not document how `simd_float4x4` or the enums are encoded, and encoding RoomPlan types has produced errors for some developers. Build a small DTO yourself. The backend converter is written against this exact shape:

```json
{
  "format": "sweetspot.roomplan.v1",
  "room_identifier": "UUID string",
  "story": 0,
  "surfaces": [
    {"id": "UUID", "category": "wall|door|window|opening|floor", "is_open": null,
     "dimensions": [width, height, depth],
     "transform": [16 floats, column-major: column0(4), column1(4), column2(4), column3(4)],
     "polygon_corners": [[x,y,z], ...] ,
     "confidence": "low|medium|high",
     "parent_id": "UUID or null"}
  ],
  "objects": [
    {"id": "UUID", "category": "sofa|television|table|storage|chair|bed|...16 names lowercase camelCase",
     "dimensions": [w,h,d], "transform": [16 floats column-major],
     "confidence": "low|medium|high", "parent_id": "UUID or null"}
  ]
}
```
Rules:
- `transform`: flatten `matrix.columns.0 ... columns.3`, each as x,y,z,w. The **translation is the last column**: elements 12, 13, 14. These are world meters.
- `category`: lowercase name of the enum case (`wall`, `door`, `sofa`, `washerDryer` stays camelCase). For doors set `is_open` from the associated value, otherwise `null`.
- `confidence`: `String(describing: surface.confidence)`; the case names are not on the pages I checked (**VERIFY**), so just send whatever the string is.
- `polygon_corners`: `surface.polygonCorners` as arrays of 3 floats, iOS 17+ only. Meaning is "local plane coordinates" (**VERIFY** axes: dump one wall's `transform`, `dimensions` and `polygonCorners` and send them with the sample file; the backend does not depend on it, it builds corners from `dimensions` and `transform`).
- Include `floors` as surfaces with category `floor`.
- Optionally also include `"raw": <JSONEncoder output of CapturedRoom>` if that encoding succeeds on your device; the backend ignores it for now. Skip it if it errors.

```swift
func exportDTO(_ room: CapturedRoom) -> [String: Any] {
    func flat(_ m: simd_float4x4) -> [Float] {
        [m.columns.0, m.columns.1, m.columns.2, m.columns.3].flatMap { [$0.x, $0.y, $0.z, $0.w] }
    }
    func surf(_ s: CapturedRoom.Surface) -> [String: Any] {
        var cat = "wall"; var isOpen: Any = NSNull()
        switch s.category {
        case .wall: cat = "wall"
        case .window: cat = "window"
        case .opening: cat = "opening"
        case .floor: cat = "floor"
        case .door(let open): cat = "door"; isOpen = open
        @unknown default: cat = "wall"
        }
        return ["id": s.identifier.uuidString, "category": cat, "is_open": isOpen,
                "dimensions": [s.dimensions.x, s.dimensions.y, s.dimensions.z],
                "transform": flat(s.transform),
                "polygon_corners": s.polygonCorners.map { [$0.x, $0.y, $0.z] },
                "confidence": String(describing: s.confidence),
                "parent_id": s.parentIdentifier?.uuidString as Any? ?? NSNull()]
    }
    func obj(_ o: CapturedRoom.Object) -> [String: Any] {
        ["id": o.identifier.uuidString, "category": String(describing: o.category),
         "dimensions": [o.dimensions.x, o.dimensions.y, o.dimensions.z],
         "transform": flat(o.transform),
         "confidence": String(describing: o.confidence),
         "parent_id": o.parentIdentifier?.uuidString as Any? ?? NSNull()]
    }
    return ["format": "sweetspot.roomplan.v1", "room_identifier": room.identifier.uuidString, "story": room.story,
            "surfaces": (room.walls + room.doors + room.windows + room.openings + room.floors).map(surf),
            "objects": room.objects.map(obj)]
}
// body for the file: JSONSerialization.data(withJSONObject: exportDTO(room), options: [.prettyPrinted, .sortedKeys])
```
(`polygonCorners` needs iOS 17; wrap in `if #available(iOS 17, *)` if you keep a lower target.)

## Coordinates
- World frame is the ARSession's: **y up (gravity-aligned)**, right-handed, meters, origin where the session started. Matches three.js. **Do not flip axes anywhere.**
- Surface/object `transform` positions the plane/box **center** in world space; `dimensions` are the extents along the item's local axes. Which local axis is a wall's normal is **VERIFY**; the backend uses `dimensions` plus `transform` only, so just send them unmodified.
- For scanned rooms the backend **keeps this world frame** (it does not recenter), so returned speaker positions are valid ARKit world coordinates if the AR session shares the scan's session.

## Local backup (protects the demo)
Right after the scan, write the DTO JSON to `Documents/room_<timestamp>.json` and expose a share button (`ShareLink`). It is how the sample reaches the backend person, and it is the pre-scanned demo-room fallback. Add **"Load saved scan"**: read a saved file and upload it as if freshly scanned.

## Known RoomPlan limits (also pitch material)
- Dark, mirror/glass-heavy or cluttered rooms scan poorly; very large rooms degrade.
- RoomPlan reports **no materials** (hence the photos for Gemini).
- Furniture is detected as boxes; custom furniture may be mislabeled. Always let the user confirm/move the seat (open question in `05`).

## SwiftUI wrapper sketch (illustrative)
```swift
struct ScanView: UIViewRepresentable {
    let arSession: ARSession            // one shared session for scan + AR (see AR note)
    let onResult: (CapturedRoom) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(onResult: onResult) }
    func makeUIView(context: Context) -> RoomCaptureView {
        let v = RoomCaptureView(frame: .zero, arSession: arSession)
        v.delegate = context.coordinator
        var cfg = RoomCaptureSession.Configuration(); cfg.isCoachingEnabled = true
        v.captureSession.run(configuration: cfg)
        return v
    }
    func updateUIView(_ uiView: RoomCaptureView, context: Context) {}

    final class Coordinator: NSObject, RoomCaptureViewDelegate {
        let onResult: (CapturedRoom) -> Void
        init(onResult: @escaping (CapturedRoom) -> Void) { self.onResult = onResult; super.init() }
        required init?(coder: NSCoder) { fatalError("not used") }   // NSCoding requirement
        func encode(with coder: NSCoder) {}
        func captureView(shouldPresent roomDataForProcessing: CapturedRoomData, error: (any Error)?) -> Bool { error == nil }
        func captureView(didPresent processedResult: CapturedRoom, error: (any Error)?) {
            if error == nil { onResult(processedResult) }
        }
    }
}
// Stop button: view.captureSession.stop(pauseARSession: false)
```
