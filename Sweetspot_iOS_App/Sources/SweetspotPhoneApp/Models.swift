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
//struct SessionResponse: Decodable { let session_id: String }
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
}

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
