import Foundation
import RoomPlan

/// Room size the backend reported for an upload, in feet.
struct SavedRoomSize: Codable, Equatable {
    let width: Double
    let length: Double
    let height: Double
}

/// One upload of a saved scan. Each upload creates a new room on the backend.
struct ScanUpload: Codable, Equatable, Identifiable {
    let roomID: String
    let sessionID: String?
    let uploadedAt: Date
    let size: SavedRoomSize?

    var id: String { roomID }
}

/// What RoomPlan found, kept so the list can describe a scan without reopening it.
struct ScanSummary: Codable, Equatable {
    let walls: Int
    let doors: Int
    let windows: Int
    let openings: Int
    let objects: Int
    let hasSofa: Bool
    let hasTelevision: Bool

    init(_ room: CapturedRoom) {
        walls = room.walls.count
        doors = room.doors.count
        windows = room.windows.count
        openings = room.openings.count
        objects = room.objects.count
        hasSofa = room.objects.contains { object in
            if case .sofa = object.category { return true }
            return false
        }
        hasTelevision = room.objects.contains { object in
            if case .television = object.category { return true }
            return false
        }
    }

    var text: String {
        var parts = [
            Self.count(walls, "wall", "walls"),
            Self.count(doors, "door", "doors"),
            Self.count(windows, "window", "windows")
        ]
        if hasSofa { parts.append("sofa") }
        if hasTelevision { parts.append("TV") }
        return parts.joined(separator: ", ")
    }

    private static func count(_ value: Int, _ singular: String, _ plural: String) -> String {
        "\(value) \(value == 1 ? singular : plural)"
    }
}

struct SavedScan: Codable, Equatable, Identifiable {
    let id: UUID
    let createdAt: Date
    /// File name of the scan's DTO JSON inside the Scans folder.
    let fileName: String
    var name: String?
    /// Nil only for a scan imported from the older single-file save.
    var summary: ScanSummary?
    /// Oldest first.
    var uploads: [ScanUpload]

    var latestUpload: ScanUpload? { uploads.last }

    var displayName: String {
        if let name, !name.isEmpty { return name }
        return "Scan, " + createdAt.formatted(date: .abbreviated, time: .shortened)
    }
}

/// Keeps every finished scan on this iPhone, newest first.
///
/// Layout in Documents/Scans/:
///   index.json    the list of SavedScan records (IDs, names, uploads)
///   <uuid>.json   each scan in the sweetspot.roomplan.v1 DTO format
@MainActor
final class ScanHistory: ObservableObject {
    @Published private(set) var scans: [SavedScan] = []

    private let folder: URL
    private var indexURL: URL { folder.appendingPathComponent("index.json") }

    init() {
        let documents = FileManager.default.urls(
            for: .documentDirectory,
            in: .userDomainMask
        )[0]
        folder = documents.appendingPathComponent("Scans", isDirectory: true)

        try? FileManager.default.createDirectory(
            at: folder,
            withIntermediateDirectories: true
        )

        load()
        importLegacyScanIfNeeded(documents: documents)
    }

    // MARK: Reading

    func scan(id: UUID) -> SavedScan? {
        scans.first { $0.id == id }
    }

    func fileURL(for scan: SavedScan) -> URL {
        folder.appendingPathComponent(scan.fileName)
    }

    func fileExists(for scan: SavedScan) -> Bool {
        FileManager.default.fileExists(atPath: fileURL(for: scan).path)
    }

    func data(for scan: SavedScan) -> Data? {
        try? Data(contentsOf: fileURL(for: scan))
    }

    // MARK: Changes

    @discardableResult
    func add(_ room: CapturedRoom) throws -> SavedScan {
        let id = UUID()
        let fileName = "\(id.uuidString).json"

        try RoomPlanDTO(room).data().write(
            to: folder.appendingPathComponent(fileName),
            options: .atomic
        )

        let scan = SavedScan(
            id: id,
            createdAt: Date(),
            fileName: fileName,
            name: nil,
            summary: ScanSummary(room),
            uploads: []
        )
        scans.insert(scan, at: 0)
        persist()
        return scan
    }

    func recordUpload(
        scanID: UUID,
        roomID: String,
        sessionID: String?,
        dimensions: Dimensions?
    ) {
        let size = dimensions.map {
            SavedRoomSize(width: $0.width, length: $0.length, height: $0.height)
        }

        update(scanID) { scan in
            scan.uploads.append(
                ScanUpload(
                    roomID: roomID,
                    sessionID: sessionID,
                    uploadedAt: Date(),
                    size: size
                )
            )
        }
    }

    func rename(scanID: UUID, to name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        update(scanID) { scan in
            scan.name = trimmed.isEmpty ? nil : trimmed
        }
    }

    func delete(scanID: UUID) {
        guard let index = scans.firstIndex(where: { $0.id == scanID }) else { return }
        try? FileManager.default.removeItem(at: fileURL(for: scans[index]))
        scans.remove(at: index)
        persist()
    }

    // MARK: Storage

    private func update(_ id: UUID, _ change: (inout SavedScan) -> Void) {
        guard let index = scans.firstIndex(where: { $0.id == id }) else { return }
        var scan = scans[index]
        change(&scan)
        guard scan != scans[index] else { return }
        scans[index] = scan
        persist()
    }

    private func load() {
        guard let data = try? Data(contentsOf: indexURL) else { return }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        do {
            scans = try decoder.decode([SavedScan].self, from: data)
        } catch {
            // Keep the unreadable index aside instead of overwriting it.
            let backup = folder.appendingPathComponent("index-unreadable.json")
            try? FileManager.default.removeItem(at: backup)
            try? FileManager.default.moveItem(at: indexURL, to: backup)
            print("ScanHistory: index could not be read, moved aside: \(error)")
        }
    }

    private func persist() {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]

        do {
            try encoder.encode(scans).write(to: indexURL, options: .atomic)
        } catch {
            print("ScanHistory: could not save index: \(error)")
        }
    }

    /// Earlier builds kept only Documents/latest-roomplan.json. Bring it into
    /// the history once, the first time the history is created.
    private func importLegacyScanIfNeeded(documents: URL) {
        let legacy = documents.appendingPathComponent("latest-roomplan.json")
        let manager = FileManager.default

        guard !manager.fileExists(atPath: indexURL.path),
              manager.fileExists(atPath: legacy.path) else {
            return
        }

        let id = UUID()
        let fileName = "\(id.uuidString).json"

        do {
            try manager.copyItem(
                at: legacy,
                to: folder.appendingPathComponent(fileName)
            )
        } catch {
            return
        }

        let modified = (try? manager.attributesOfItem(atPath: legacy.path))?[.modificationDate] as? Date

        scans.insert(
            SavedScan(
                id: id,
                createdAt: modified ?? Date(),
                fileName: fileName,
                name: "Earlier scan",
                summary: nil,
                uploads: []
            ),
            at: 0
        )
        persist()
    }
}

