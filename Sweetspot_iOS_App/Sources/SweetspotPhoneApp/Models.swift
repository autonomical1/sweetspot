//import Foundation
//import simd
//import RoomPlan
//
//struct RoomPlanDTO: Encodable {
//    let format = "sweetspot.roomplan.v1"
//    let room_identifier: String
//    let story: Int
//    let surfaces: [Surface]
//    let objects: [RoomObject]
//
//    struct Surface: Encodable {
//        let id, category: String
//        let is_open: Bool?
//        let dimensions: [Float]
//        let transform: [Float]
//        let polygon_corners: [[Float]]
//        let confidence: String
//        let parent_id: String?
//    }
//    struct RoomObject: Encodable {
//        let id, category: String
//        let dimensions: [Float]
//        let transform: [Float]
//        let confidence: String
//        let parent_id: String?
//    }
//
//    init(_ room: CapturedRoom) {
//        room_identifier = room.identifier.uuidString
//        story = room.story
//        surfaces = (room.walls + room.doors + room.windows + room.openings + room.floors).map { s in
//            let kind: String
//            let open: Bool?
//            switch s.category {
//            case .wall: kind = "wall"; open = nil
//            case .door(let value): kind = "door"; open = value
//            case .window: kind = "window"; open = nil
//            case .opening: kind = "opening"; open = nil
//            case .floor: kind = "floor"; open = nil
//            @unknown default: kind = "wall"; open = nil
//            }
//            return .init(id: s.identifier.uuidString, category: kind, is_open: open,
//                         dimensions: [s.dimensions.x, s.dimensions.y, s.dimensions.z],
//                         transform: Self.flatten(s.transform),
//                         polygon_corners: s.polygonCorners.map { [$0.x, $0.y, $0.z] },
//                         confidence: String(describing: s.confidence), parent_id: s.parentIdentifier?.uuidString)
//        }
//        objects = room.objects.map {
//            .init(id: $0.identifier.uuidString, category: String(describing: $0.category),
//                  dimensions: [$0.dimensions.x, $0.dimensions.y, $0.dimensions.z],
//                  transform: Self.flatten($0.transform), confidence: String(describing: $0.confidence),
//                  parent_id: $0.parentIdentifier?.uuidString)
//        }
//    }
//
//    private static func flatten(_ m: simd_float4x4) -> [Float] {
//        [m.columns.0, m.columns.1, m.columns.2, m.columns.3].flatMap { [$0.x, $0.y, $0.z, $0.w] }
//    }
//    func data() throws -> Data {
//        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
//        return try encoder.encode(self)
//    }
//}
//
//struct RoomResponse: Decodable {
//    let room_id: String
//    let session_id: String?
//    let dimensions: Dimensions?
//}
//struct Dimensions: Decodable { let width, length, height: Double }
//struct LinkResponse: Decodable { let status: String }

struct SessionResponse: Decodable { let session_id: String }
//struct PhotoTarget: Decodable, Identifiable { let surface_id, kind, label: String; var id: String { surface_id } }
//struct MaterialsResponse: Decodable { let surfaces: [MaterialResult] }
//struct MaterialResult: Decodable, Identifiable { let surface_id, material: String; let confidence: Double; var id: String { surface_id } }
//struct LayoutResponse: Decodable { let layout: Layout }
//struct Layout: Decodable { let speakers: [SpeakerPlacement]; let screen: ScreenPlacement? }
//struct SpeakerPlacement: Decodable, Identifiable { let role: String; let position: [Double]; let aim: [Double]; var id: String { role } }
//struct ScreenPlacement: Decodable { let wall_id: String; let center: [Double]; let width, height: Double }
//
//enum AppPhase { case home, scan, review, photos, results, ar }
import Foundation
import simd
import RoomPlan

struct RoomPlanDTO: Encodable {
    let format = "sweetspot.roomplan.v1"
    let room_identifier: String
    let story: Int
    let surfaces: [Surface]
    let objects: [RoomObject]

    struct Surface: Encodable {
        let id: String
        let category: String
        let is_open: Bool?
        let dimensions: [Float]
        let transform: [Float]
        let polygon_corners: [[Float]]
        let confidence: String
        let parent_id: String?
    }

    struct RoomObject: Encodable {
        let id: String
        let category: String
        let dimensions: [Float]
        let transform: [Float]
        let confidence: String
        let parent_id: String?
    }

    init(_ room: CapturedRoom) {
        room_identifier = room.identifier.uuidString
        story = room.story

        let allSurfaces =
            room.walls +
            room.doors +
            room.windows +
            room.openings +
            room.floors

        surfaces = allSurfaces.map { surface in
            let category: String
            let isOpen: Bool?

            switch surface.category {
            case .wall:
                category = "wall"
                isOpen = nil
            case .door(let open):
                category = "door"
                isOpen = open
            case .window:
                category = "window"
                isOpen = nil
            case .opening:
                category = "opening"
                isOpen = nil
            case .floor:
                category = "floor"
                isOpen = nil
            @unknown default:
                category = "wall"
                isOpen = nil
            }

            return Surface(
                id: surface.identifier.uuidString,
                category: category,
                is_open: isOpen,
                dimensions: [
                    surface.dimensions.x,
                    surface.dimensions.y,
                    surface.dimensions.z
                ],
                transform: Self.flatten(surface.transform),
                polygon_corners: surface.polygonCorners.map {
                    [$0.x, $0.y, $0.z]
                },
                confidence: String(describing: surface.confidence),
                parent_id: surface.parentIdentifier?.uuidString
            )
        }

        let capturedObjects = room.objects
        objects = capturedObjects.map { object in
            RoomObject(
                id: object.identifier.uuidString,
                category: String(describing: object.category),
                dimensions: [
                    object.dimensions.x,
                    object.dimensions.y,
                    object.dimensions.z
                ],
                transform: Self.flatten(object.transform),
                confidence: String(describing: object.confidence),
                parent_id: object.parentIdentifier?.uuidString
            )
        }
    }

    private static func flatten(_ matrix: simd_float4x4) -> [Float] {
        [
            matrix.columns.0,
            matrix.columns.1,
            matrix.columns.2,
            matrix.columns.3
        ].flatMap { column in
            [column.x, column.y, column.z, column.w]
        }
    }

    func data() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(self)
    }
}

struct RoomResponse: Decodable {
    let room_id: String
    let session_id: String?
    let dimensions: Dimensions?
    let frame: RoomFrame?
}

struct RoomFrame: Decodable {
    let yaw_deg: Double
    let offset: [Double]
}

/// Maps room-frame metres into the scan session's ARKit world metres.
func worldTransform(for frame: RoomFrame) -> simd_float4x4 {
    let yaw = Float(frame.yaw_deg * .pi / 180)
    var transform = simd_float4x4(
        simd_quatf(angle: yaw, axis: SIMD3<Float>(0, 1, 0))
    )
    transform.columns.3 = SIMD4<Float>(
        Float(frame.offset[0] * 0.3048),
        Float(frame.offset[1] * 0.3048),
        Float(frame.offset[2] * 0.3048),
        1
    )
    return transform
}

#if DEBUG
/// Values from phoneapp_context/sample_payloads/frame_test_vectors.json.
func checkRoomFrameVectors() -> Bool {
    let points: [(Double, [Double], SIMD3<Float>, SIMD3<Float>)] = [
        (0, [0, 0, 0], SIMD3(2, 3, 5), SIMD3(0.6096, 0.9144, 1.524)),
        (30, [10, 0, -4], SIMD3(2, 3, 5), SIMD3(4.337929, 0.9144, -0.204177)),
        (-90, [1.5, 0, 2.5], SIMD3(4, 3.6, 1), SIMD3(0.1524, 1.09728, 1.9812)),
        (180, [20, 0, 15], SIMD3(6, 1, 2), SIMD3(4.2672, 0.3048, 3.9624)),
        (37.5, [-3.2, 0.4, 8.8], SIMD3(11.25, 5, 0.5), SIMD3(1.837824, 1.64592, 0.715704))
    ]
    for (yaw, offset, roomFeet, expected) in points {
        let transform = worldTransform(for: RoomFrame(yaw_deg: yaw, offset: offset))
        let actual = transform * SIMD4<Float>(roomFeet * 0.3048, 1)
        if simd_length(SIMD3<Float>(actual.x, actual.y, actual.z) - expected) >= 1e-4 {
            return false
        }
    }

    let directions: [(Double, SIMD3<Float>, SIMD3<Float>)] = [
        (30, SIMD3(0, 0, -1), SIMD3(-0.5, 0, -0.866025)),
        (90, SIMD3(1, 0, 0), SIMD3(0, 0, -1)),
        (-45, SIMD3(0, 0, -1), SIMD3(0.707107, 0, -0.707107))
    ]
    for (yaw, roomDirection, expected) in directions {
        let transform = worldTransform(for: RoomFrame(yaw_deg: yaw, offset: [0, 0, 0]))
        let actual = transform * SIMD4<Float>(roomDirection, 0)
        if simd_length(SIMD3<Float>(actual.x, actual.y, actual.z) - expected) >= 1e-4 {
            return false
        }
    }
    return true
}
#endif

struct Dimensions: Decodable {
    let width: Double
    let length: Double
    let height: Double
}

struct SessionResponse: Decodable {
    let session_id: String
}

struct PhotoTarget: Decodable, Identifiable {
    let surface_id: String
    let kind: String
    let label: String

    var id: String { surface_id }
}

struct MaterialsResponse: Decodable {
    let surfaces: [MaterialResult]
    let status: String?
}

struct MaterialsStatus: Decodable {
    let state: String?
    let started_at: String?
    let elapsed_s: Double?
    let photos: Int?
}

struct MaterialResult: Decodable, Identifiable {
    let surface_id: String
    let material: String
    let confidence: Double

    var id: String { surface_id }
}

struct LayoutResponse: Decodable {
    let layout: Layout
}

struct Layout: Decodable {
    let speakers: [SpeakerPlacement]
    let screen: ScreenPlacement?
}

struct SpeakerPlacement: Decodable, Identifiable {
    let role: String
    let position: [Double]
    let aim: [Double]

    var id: String { role }
}

struct ScreenPlacement: Decodable {
    let wall_id: String
    let center: [Double]
    let width: Double
    let height: Double
}

enum AppPhase {
    case home
    case scan
    case review
    case photos
    case results
    case ar
}

struct ProductDimensions: Decodable {
    let width: Double
    let height: Double
    let depth: Double
    let source: String?
}

struct ProductAlternative: Decodable, Identifiable {
    let title: String
    let price: Double
    let link: String
    let seller: String?
    let thumbnail: String?
    let source: String?
    let specs: [String: String]?
    let dimensions: ProductDimensions?
    let price_delta: Double?

    var id: String { "\(title)|\(link)" }
}

struct ProductItem: Decodable, Identifiable {
    let role: String
    var title: String
    var price: Double
    let currency: String
    var link: String
    let thumbnail: String?
    var source: String
    var seller: String?
    var specs: [String: String]?
    var dimensions: ProductDimensions?
    let pair_with: String?
    var alternatives: [ProductAlternative]?

    var id: String { role }
}

struct ProductsResponse: Decodable {
    let budget: Double
    let total: Double
    let items: [ProductItem]
    let warnings: [String]?
}

func chosenTotal(items: [ProductItem]) -> Double {
    items.reduce(0) { $0 + $1.price }
}

func inchesDescription(_ dimensions: ProductDimensions) -> String {
    let values = [dimensions.width, dimensions.height, dimensions.depth]
        .map { String(Int(($0 * 12).rounded())) }
    return "\(values.joined(separator: " x ")) in"
}
