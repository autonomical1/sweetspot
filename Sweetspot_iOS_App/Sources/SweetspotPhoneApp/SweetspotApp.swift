//import SwiftUI
//import RoomPlan
//import ARKit
//import RealityKit
//import VisionKit
//import UIKit
//
//@main
//struct SweetspotApp: App {
//    var body: some SwiftUI.Scene {
//        WindowGroup { HomeView() }
//    }
//}
//
//@MainActor
//final class Flow: ObservableObject {
//    @Published var error: String?
//    @Published var showingOfflinePreview = false
//    @Published var isWorking = false
//    @Published var roomID: String?
//    @Published var sessionID: String?
//    @Published var phase: AppPhase = .home
//    @Published var materials: [MaterialResult] = []
//    @Published var layout: Layout?
//    @Published var roomDimensions: Dimensions?
//    @Published var photoTargets: [PhotoTarget] = []
//    @Published var photoIndex = 0
//
//    let backend = BackendClient()
//
//    /// RoomPlan's ARSession, kept after a scan so the AR layout screen
//    /// shares the scan's world coordinate frame.
//    private(set) var scanSession: ARSession?
//
//    private(set) var captured: CapturedRoom?
//
//    private var scanFile: URL? {
//        FileManager.default.urls(
//            for: .documentDirectory,
//            in: .userDomainMask
//        ).first?.appendingPathComponent("latest-roomplan.json")
//    }
//
//    init() {
//        sessionID = UserDefaults.standard.string(forKey: "sweetspot.session_id")
//        roomID = UserDefaults.standard.string(forKey: "sweetspot.room_id")
//    }
//
//    func accept(_ room: CapturedRoom, session: ARSession) {
//        captured = room
//        scanSession = session
//        phase = .review
//
//        do {
//            guard let scanFile else { return }
//            try RoomPlanDTO(room).data().write(to: scanFile, options: .atomic)
//        } catch {
//            self.error = "Could not save scan: \(error.localizedDescription)"
//        }
//    }
//
//    /// Drops the live scan when the person switches to a room that wasn't
//    /// scanned, so the AR screen asks for alignment instead of assuming
//    /// the scan's coordinate frame. Also turns the scan's camera off.
//    private func forgetScan() {
//        scanSession?.pause()
//        scanSession = nil
//        captured = nil
//    }
//
//    func uploadScan() async {
//        guard let captured else { return }
//
//        do {
//            let response = try await backend.upload(
//                dto: RoomPlanDTO(captured).data(),
//                sessionID: sessionID
//            )
//
//            roomID = response.room_id
//            UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id")
//            roomDimensions = response.dimensions
//            phase = .photos
//
//            let targets = (try? await backend.targets(roomID: response.room_id)) ?? []
//            photoTargets = targets.isEmpty ? fallbackTargets() : targets
//        } catch {
//            self.error = error.localizedDescription
//        }
//    }
//
//    func useDemo() async {
//        forgetScan()
//        isWorking = true
//        defer { isWorking = false }
//
//        do {
//            let response = try await backend.demo(sessionID: sessionID)
//            roomID = response.room_id
//            UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id")
//            roomDimensions = response.dimensions
//                ?? Dimensions(width: 12, length: 15, height: 9)
//            showingOfflinePreview = false
//            phase = .results
//        } catch {
//            self.error = """
//            Backend unavailable (\(error.localizedDescription)). \
//            Showing a local preview; uploads and pairing need the backend.
//            """
//            startPreview(width: 12, length: 15, height: 9)
//        }
//    }
//
//    func pair(code: String) async {
//        isWorking = true
//        defer { isWorking = false }
//
//        do {
//            let response = try await backend.pair(code: code)
//            sessionID = response.session_id
//            UserDefaults.standard.set(response.session_id, forKey: "sweetspot.session_id")
//        } catch {
//            self.error = error.localizedDescription
//        }
//    }
//
//    func compute() async {
//        guard let roomID else { return }
//
//        if roomID == "local-preview" {
//            phase = .ar
//            return
//        }
//
//        do {
//            layout = try await backend.optimize(roomID: roomID).layout
//            phase = .ar
//        } catch {
//            self.error = error.localizedDescription
//        }
//    }
//
//    func makeRectangle(width: Double, length: Double, height: Double) async {
//        forgetScan()
//        isWorking = true
//        defer { isWorking = false }
//
//        do {
//            let response = try await backend.rectangle(
//                width: width,
//                length: length,
//                height: height,
//                sessionID: sessionID
//            )
//
//            roomID = response.room_id
//            roomDimensions = response.dimensions
//                ?? Dimensions(width: width, length: length, height: height)
//            showingOfflinePreview = false
//            phase = .results
//        } catch {
//            self.error = """
//            Backend unavailable (\(error.localizedDescription)). \
//            Showing a local preview for the entered room.
//            """
//            startPreview(width: width, length: length, height: height)
//        }
//    }
//
//    private func startPreview(width: Double, length: Double, height: Double) {
//        roomID = "local-preview"
//        roomDimensions = Dimensions(width: width, length: length, height: height)
//
//        layout = Layout(
//            speakers: [
//                SpeakerPlacement(role: "L", position: [3, 1, 3], aim: [6, 1, 7.5]),
//                SpeakerPlacement(role: "R", position: [9, 1, 3], aim: [6, 1, 7.5]),
//                SpeakerPlacement(role: "C", position: [6, 1.5, 2], aim: [6, 1.5, 7.5]),
//                SpeakerPlacement(role: "LFE", position: [6, 0.5, 3], aim: [6, 0.5, 7.5]),
//                SpeakerPlacement(role: "Ls", position: [2, 1, 11], aim: [6, 1, 7.5]),
//                SpeakerPlacement(role: "Rs", position: [10, 1, 11], aim: [6, 1, 7.5])
//            ],
//            screen: ScreenPlacement(
//                wall_id: "wall_n",
//                center: [6, 4.5, 0.2],
//                width: 6.4,
//                height: 3.6
//            )
//        )
//
//        showingOfflinePreview = true
//        phase = .results
//    }
//
//    func classify() async {
//        guard let roomID else { return }
//
//        do {
//            materials = try await backend.classify(roomID: roomID).surfaces
//            phase = .results
//        } catch {
//            self.error = error.localizedDescription
//            phase = .results
//        }
//    }
//
//    func uploadPhoto(surfaceID: String, image: UIImage) async {
//        guard let roomID, let jpeg = image.sweetspotJPEG() else {
//            error = "Could not prepare photo."
//            return
//        }
//
//        do {
//            try await backend.uploadPhoto(
//                roomID: roomID,
//                surfaceID: surfaceID,
//                jpeg: jpeg
//            )
//            photoIndex += 1
//        } catch {
//            self.error = error.localizedDescription
//        }
//    }
//
//    func uploadSavedScan() async {
//        guard let scanFile, let data = try? Data(contentsOf: scanFile) else {
//            error = "No saved scan is available on this iPhone."
//            return
//        }
//
//        do {
//            let response = try await backend.upload(dto: data, sessionID: sessionID)
//            roomID = response.room_id
//            UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id")
//            roomDimensions = response.dimensions
//
//            let targets = (try? await backend.targets(roomID: response.room_id)) ?? []
//            photoTargets = targets.isEmpty ? fallbackTargets() : targets
//            phase = .photos
//        } catch {
//            self.error = error.localizedDescription
//        }
//    }
//
//    private func fallbackTargets() -> [PhotoTarget] {
//        guard let captured else { return [] }
//
//        let walls = captured.walls.sorted {
//            $0.dimensions.x * $0.dimensions.y >
//            $1.dimensions.x * $1.dimensions.y
//        }
//
//        let labels = ["Largest wall", "Second wall", "Third wall", "Fourth wall"]
//
//        return walls.prefix(4).enumerated().map { index, wall in
//            PhotoTarget(
//                surface_id: wall.identifier.uuidString,
//                kind: "wall",
//                label: labels[index]
//            )
//        }
//    }
//}
//
//struct HomeView: View {
//    @StateObject private var flow = Flow()
//
//    var body: some View {
//        NavigationStack {
//            VStack(spacing: 18) {
//                Text("Sweetspot")
//                    .font(.largeTitle.bold())
//
//                Text(
//                    RoomCaptureSession.isSupported
//                        ? "LiDAR room scan available"
//                        : "No LiDAR detected. Use a fallback."
//                )
//                .foregroundStyle(.secondary)
//
//                if flow.isWorking {
//                    ProgressView("Contacting Sweetspot backend…")
//                }
//
//                if RoomCaptureSession.isSupported {
//                    Button("Start room scan") {
//                        flow.phase = .scan
//                    }
//                    .buttonStyle(.borderedProminent)
//                }
//
//                Button("Use demo room") {
//                    Task { await flow.useDemo() }
//                }
//                .buttonStyle(.borderedProminent)
//
//                Button("Upload saved scan") {
//                    Task { await flow.uploadSavedScan() }
//                }
//
//                NavigationLink(
//                    "Enter room dimensions",
//                    destination: RectangleEntry(flow: flow)
//                )
//
//                CodeEntry(flow: flow)
//
//                if let sessionID = flow.sessionID {
//                    Label("Connected · \(sessionID)", systemImage: "link")
//                }
//
//                if let error = flow.error {
//                    Text(error)
//                        .foregroundStyle(.red)
//                        .font(.footnote)
//                }
//            }
//            .padding()
//            .navigationDestination(
//                isPresented: Binding(
//                    get: { flow.phase != .home },
//                    set: { if !$0 { flow.phase = .home } }
//                )
//            ) {
//                switch flow.phase {
//                case .scan:
//                    ScanScreen(flow: flow)
//                case .review:
//                    ReviewScreen(flow: flow)
//                case .photos:
//                    PhotosStep(flow: flow)
//                case .results:
//                    ResultsScreen(flow: flow)
//                case .ar:
//                    ARLayoutScreen(flow: flow)
//                case .home:
//                    EmptyView()
//                }
//            }
//        }
//        .alert(
//            "Sweetspot",
//            isPresented: Binding(
//                get: { flow.error != nil },
//                set: { if !$0 { flow.error = nil } }
//            )
//        ) {
//            Button("OK", role: .cancel) { flow.error = nil }
//        } message: {
//            Text(flow.error ?? "")
//        }
//    }
//}
//
//struct CodeEntry: View {
//    @ObservedObject var flow: Flow
//    @State private var code = ""
//    @State private var showScanner = false
//
//    var body: some View {
//        VStack {
//            HStack {
//                TextField("Desktop code", text: $code)
//                    .textInputAutocapitalization(.characters)
//                    .textFieldStyle(.roundedBorder)
//
//                Button("Connect") {
//                    Task {
//                        await flow.pair(
//                            code: code.trimmingCharacters(in: .whitespaces)
//                        )
//                    }
//                }
//                .disabled(code.count < 6)
//            }
//
//            if DataScannerViewController.isSupported {
//                Button("Scan desktop QR") {
//                    showScanner = true
//                }
//                .sheet(isPresented: $showScanner) {
//                    ZStack {
//                        PairQRScanner { value in
//                            do {
//                                flow.sessionID = try sessionID(from: value)
//                                UserDefaults.standard.set(
//                                    flow.sessionID,
//                                    forKey: "sweetspot.session_id"
//                                )
//                                showScanner = false
//                            } catch {
//                                flow.error = error.localizedDescription
//                            }
//                        }
//                        .ignoresSafeArea()
//
//                        RoundedRectangle(cornerRadius: 18)
//                            .stroke(.green, lineWidth: 3)
//                            .frame(width: 290, height: 210)
//                            .overlay(alignment: .bottom) {
//                                Text("Center the desktop QR code in the box")
//                                    .font(.callout)
//                                    .padding(8)
//                                    .background(.black.opacity(0.7))
//                                    .foregroundStyle(.white)
//                                    .clipShape(Capsule())
//                                    .offset(y: 42)
//                            }
//                            .allowsHitTesting(false)
//                    }
//                    .ignoresSafeArea()
//                }
//            }
//        }
//    }
//}
//
//struct RectangleEntry: View {
//    @ObservedObject var flow: Flow
//    @State private var width = "12"
//    @State private var length = "15"
//    @State private var height = "9"
//
//    var body: some View {
//        Form {
//            Text("Enter measurements in feet")
//
//            TextField("Width (ft)", text: $width)
//                .keyboardType(.decimalPad)
//            TextField("Length (ft)", text: $length)
//                .keyboardType(.decimalPad)
//            TextField("Height (ft)", text: $height)
//                .keyboardType(.decimalPad)
//
//            Button("Create room") {
//                Task {
//                    await flow.makeRectangle(
//                        width: Double(width) ?? 12,
//                        length: Double(length) ?? 15,
//                        height: Double(height) ?? 9
//                    )
//                }
//            }
//        }
//        .navigationTitle("Room size")
//    }
//}
//
//struct ScanScreen: View {
//    @ObservedObject var flow: Flow
//    @State private var shouldFinish = false
//
//    var body: some View {
//        VStack {
//            Text(
//                "Stand near the center. Turn slowly and capture each wall, " +
//                "doors, windows and furniture. Do not take photos during scanning."
//            )
//            .padding()
//
//            ScanCapture(
//                shouldFinish: $shouldFinish,
//                onError: { flow.error = $0 },
//                onRoom: { room, session in
//                    flow.accept(room, session: session)
//                }
//            )
//            .frame(maxWidth: .infinity, maxHeight: .infinity)
//            .background(.black)
//            .overlay(alignment: .bottom) {
//                Button("Finish scan") {
//                    shouldFinish = true
//                }
//                .padding()
//                .background(.regularMaterial)
//                .clipShape(Capsule())
//                .padding(.bottom, 16)
//            }
//        }
//        .navigationTitle("Room scan")
//    }
//}
//
//struct ReviewScreen: View {
//    @ObservedObject var flow: Flow
//
//    var body: some View {
//        VStack(spacing: 16) {
//            Text("Scan saved on this iPhone. Upload to generate the room layout.")
//
//            Button("Upload scan") {
//                Task { await flow.uploadScan() }
//            }
//            .buttonStyle(.borderedProminent)
//
//            Button("Use demo room instead") {
//                Task { await flow.useDemo() }
//            }
//        }
//        .padding()
//        .navigationTitle("Review scan")
//    }
//}
//
//struct PhotosStep: View {
//    @ObservedObject var flow: Flow
//    @State private var showCamera = false
//
//    var body: some View {
//        List {
//            Section("Material photos") {
//                Text("Photos help identify wall and floor materials. They are used for classification.")
//
//                if flow.photoIndex < flow.photoTargets.count {
//                    let target = flow.photoTargets[flow.photoIndex]
//
//                    Text("\(target.label) · \(target.kind)")
//
//                    Button("Take photo") {
//                        showCamera = true
//                    }
//                    .sheet(isPresented: $showCamera) {
//                        CameraCapture { image in
//                            guard let image else { return }
//                            Task {
//                                await flow.uploadPhoto(
//                                    surfaceID: target.surface_id,
//                                    image: image
//                                )
//                            }
//                        }
//                        .ignoresSafeArea()
//                    }
//
//                    Text("Photo \(flow.photoIndex + 1) of \(flow.photoTargets.count)")
//                        .foregroundStyle(.secondary)
//                } else {
//                    Text("All available target photos uploaded.")
//                }
//
//                if let error = flow.error {
//                    Text(error).foregroundStyle(.red)
//                }
//            }
//
//            Button("Finish photos and classify") {
//                Task { await flow.classify() }
//            }
//
//            Button("Skip photos and continue") {
//                Task { await flow.classify() }
//            }
//        }
//        .navigationTitle("Surface photos")
//    }
//}
//
//struct ResultsScreen: View {
//    @ObservedObject var flow: Flow
//
//    var body: some View {
//        VStack(alignment: .leading, spacing: 12) {
//            Text("Room: \(flow.roomID ?? "not uploaded")")
//
//            if flow.showingOfflinePreview {
//                Text(
//                    "Offline sample preview — positions are illustrative, " +
//                    "not calculated by the backend."
//                )
//                .font(.footnote)
//                .foregroundStyle(.orange)
//            }
//
//            ForEach(flow.materials) { material in
//                Text("\(material.material) · \(Int(material.confidence * 100))%")
//            }
//
//            Button("Compute speaker layout") {
//                Task { await flow.compute() }
//            }
//            .buttonStyle(.borderedProminent)
//        }
//        .padding()
//        .navigationTitle("Results")
//    }
//}
//
//struct ARLayoutScreen: View {
//    @ObservedObject var flow: Flow
//    @State private var alignment = "Preparing AR"
//
//    var body: some View {
//        VStack(spacing: 0) {
//            if let layout = flow.layout {
//                ARLayoutView(
//                    scanSession: flow.scanSession,
//                    layout: layout,
//                    roomWidthFeet: flow.roomDimensions?.width,
//                    sharedScanFrame: flow.scanSession != nil,
//                    alignmentState: $alignment
//                )
//                .overlay(alignment: .top) {
//                    HStack {
//                        Text(alignment)
//
//                        if flow.scanSession == nil {
//                            Button("Align again") {
//                                alignment = "Align again"
//                            }
//                        }
//                    }
//                    .padding(8)
//                    .background(.regularMaterial)
//                    .clipShape(Capsule())
//                    .padding()
//                }
//
//                Text(
//                    "Speaker markers are positioned from the backend layout. " +
//                    "Coordinates are converted from feet to meters."
//                )
//                .font(.footnote)
//                .padding(8)
//            } else {
//                Text("No layout is available yet.")
//            }
//        }
//        .navigationTitle("AR layout")
//    }
//}
import SwiftUI
import RoomPlan
import ARKit
import RealityKit
import VisionKit
import UIKit

@main
struct SweetspotApp: App {
    var body: some SwiftUI.Scene {
        WindowGroup { HomeView() }
    }
}

@MainActor
final class Flow: ObservableObject {
    @Published var error: String?
    @Published var showingOfflinePreview = false
    @Published var isWorking = false
    @Published var roomID: String?
    @Published var sessionID: String?
    @Published var phase: AppPhase = .home
    @Published var materials: [MaterialResult] = []
    @Published var layout: Layout?
    @Published var roomDimensions: Dimensions?
    @Published var roomFrame: RoomFrame?
    @Published var photoTargets: [PhotoTarget] = []
    @Published var photoIndex = 0

    let backend = BackendClient()

    /// RoomPlan's ARSession, kept after a scan so the AR layout screen
    /// shares the scan's world coordinate frame.
    private(set) var scanSession: ARSession?

    private(set) var captured: CapturedRoom?

    /// Every finished scan, with the room and session IDs from its uploads.
    let history = ScanHistory()

    /// The history entry for the scan that was just captured, if any.
    private(set) var currentScanID: UUID?

    var currentScan: SavedScan? {
        currentScanID.flatMap { history.scan(id: $0) }
    }

    init() {
        sessionID = UserDefaults.standard.string(forKey: "sweetspot.session_id")
        roomID = UserDefaults.standard.string(forKey: "sweetspot.room_id")
    }

    func accept(_ room: CapturedRoom, session: ARSession) {
        captured = room
        scanSession = session
        phase = .review

        do {
            currentScanID = try history.add(room).id
        } catch {
            currentScanID = nil
            self.error = "Could not save scan: \(error.localizedDescription)"
        }
    }

    func nameCurrentScan(_ name: String) {
        guard let currentScanID else { return }
        history.rename(scanID: currentScanID, to: name)
    }

    /// Drops the live scan when the person switches to a room that wasn't
    /// scanned, so the AR screen asks for alignment instead of assuming
    /// the scan's coordinate frame. Also turns the scan's camera off.
    /// The scan itself stays in the history.
    private func forgetScan() {
        scanSession?.pause()
        scanSession = nil
        captured = nil
        currentScanID = nil
        roomFrame = nil
    }

    func uploadScan() async {
        guard let captured else { return }
        isWorking = true
        defer { isWorking = false }

        do {
            let response = try await uploadDTO(RoomPlanDTO(captured).data())
            adoptUploadedRoom(response, scanID: currentScanID)
            phase = .photos
            await loadPhotoTargets(roomID: response.room_id)
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Uploads a scan from the history. Each upload creates a new room on
    /// the backend, and its room and session IDs are added to the scan.
    func upload(_ saved: SavedScan) async {
        guard let data = history.data(for: saved) else {
            error = "This scan's file is missing on this iPhone."
            return
        }

        // Only the scan just captured shares the live AR session's frame.
        if saved.id != currentScanID { forgetScan() }

        isWorking = true
        defer { isWorking = false }

        do {
            let response = try await uploadDTO(data)
            adoptUploadedRoom(response, scanID: saved.id)
            phase = .photos
            await loadPhotoTargets(roomID: response.room_id)
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Reopens the room from a scan's latest upload, after checking that
    /// the backend still has it.
    func open(_ saved: SavedScan) async {
        guard let upload = saved.latestUpload else { return }

        isWorking = true
        defer { isWorking = false }

        do {
            let room: RoomResponse = try await backend.request(
                "rooms/\(upload.roomID)",
                timeout: 15
            )

            if saved.id != currentScanID { forgetScan() }

            roomID = room.room_id
            roomFrame = room.frame
            UserDefaults.standard.set(room.room_id, forKey: "sweetspot.room_id")
            roomDimensions = room.dimensions ?? upload.size.map {
                Dimensions(width: $0.width, length: $0.length, height: $0.height)
            }
            materials = []
            layout = nil
            photoIndex = 0
            showingOfflinePreview = false
            phase = .results
        } catch BackendError.http(404, _) {
            error = """
            Room \(upload.roomID) is no longer on the server. \
            Use "Upload again" to create a new room from this scan.
            """
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Uploads scan JSON. If the stored desktop pairing has expired
    /// (sessions last 30 minutes), clears it and uploads unpaired.
    private func uploadDTO(_ data: Data) async throws -> RoomResponse {
        do {
            return try await backend.upload(dto: data, sessionID: sessionID)
        } catch BackendError.http(let status, let detail)
            where sessionID != nil && (status == 410 || detail.contains("session")) {

            sessionID = nil
            UserDefaults.standard.removeObject(forKey: "sweetspot.session_id")

            let response = try await backend.upload(dto: data, sessionID: nil)
            error = """
            The desktop pairing had expired, so the scan was uploaded without it. \
            Pair again to see this room on the desktop.
            """
            return response
        }
    }

    private func adoptUploadedRoom(_ response: RoomResponse, scanID: UUID?) {
        roomID = response.room_id
        roomFrame = response.frame
        UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id")
        roomDimensions = response.dimensions
        materials = []
        layout = nil
        photoIndex = 0
        showingOfflinePreview = false

        if let scanID {
            history.recordUpload(
                scanID: scanID,
                roomID: response.room_id,
                sessionID: response.session_id ?? sessionID,
                dimensions: response.dimensions
            )
        }
    }

    private func loadPhotoTargets(roomID: String) async {
        let targets = (try? await backend.targets(roomID: roomID)) ?? []
        photoTargets = targets.isEmpty ? fallbackTargets() : targets
    }

    func useDemo() async {
        forgetScan()
        isWorking = true
        defer { isWorking = false }

        do {
            let response = try await backend.demo(sessionID: sessionID)
            roomID = response.room_id
            roomFrame = response.frame
            UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id")
            roomDimensions = response.dimensions
                ?? Dimensions(width: 12, length: 15, height: 9)
            showingOfflinePreview = false
            phase = .results
        } catch {
            self.error = """
            Backend unavailable (\(error.localizedDescription)). \
            Showing a local preview; uploads and pairing need the backend.
            """
            startPreview(width: 12, length: 15, height: 9)
        }
    }

    func pair(code: String) async {
        isWorking = true
        defer { isWorking = false }

        do {
            let response = try await backend.pair(code: code)
            sessionID = response.session_id
            UserDefaults.standard.set(response.session_id, forKey: "sweetspot.session_id")
        } catch {
            self.error = error.localizedDescription
        }
    }

    func compute() async {
        guard let roomID else { return }

        if roomID == "local-preview" {
            phase = .ar
            return
        }

        do {
            layout = try await backend.optimize(roomID: roomID).layout
            phase = .ar
        } catch {
            self.error = error.localizedDescription
        }
    }

    func makeRectangle(width: Double, length: Double, height: Double) async {
        forgetScan()
        isWorking = true
        defer { isWorking = false }

        do {
            let response = try await backend.rectangle(
                width: width,
                length: length,
                height: height,
                sessionID: sessionID
            )

            roomID = response.room_id
            roomFrame = response.frame
            roomDimensions = response.dimensions
                ?? Dimensions(width: width, length: length, height: height)
            showingOfflinePreview = false
            phase = .results
        } catch {
            self.error = """
            Backend unavailable (\(error.localizedDescription)). \
            Showing a local preview for the entered room.
            """
            startPreview(width: width, length: length, height: height)
        }
    }

    private func startPreview(width: Double, length: Double, height: Double) {
        roomID = "local-preview"
        roomFrame = nil
        roomDimensions = Dimensions(width: width, length: length, height: height)

        layout = Layout(
            speakers: [
                SpeakerPlacement(role: "L", position: [3, 1, 3], aim: [6, 1, 7.5]),
                SpeakerPlacement(role: "R", position: [9, 1, 3], aim: [6, 1, 7.5]),
                SpeakerPlacement(role: "C", position: [6, 1.5, 2], aim: [6, 1.5, 7.5]),
                SpeakerPlacement(role: "LFE", position: [6, 0.5, 3], aim: [6, 0.5, 7.5]),
                SpeakerPlacement(role: "Ls", position: [2, 1, 11], aim: [6, 1, 7.5]),
                SpeakerPlacement(role: "Rs", position: [10, 1, 11], aim: [6, 1, 7.5])
            ],
            screen: ScreenPlacement(
                wall_id: "wall_n",
                center: [6, 4.5, 0.2],
                width: 6.4,
                height: 3.6
            )
        )

        showingOfflinePreview = true
        phase = .results
    }

    func classify() async {
        guard let roomID else { return }

        do {
            materials = try await backend.classify(roomID: roomID).surfaces
            phase = .results
        } catch {
            self.error = error.localizedDescription
            phase = .results
        }
    }

    func uploadPhoto(surfaceID: String, image: UIImage) async {
        guard let roomID, let jpeg = image.sweetspotJPEG() else {
            error = "Could not prepare photo."
            return
        }

        do {
            try await backend.uploadPhoto(
                roomID: roomID,
                surfaceID: surfaceID,
                jpeg: jpeg
            )
            photoIndex += 1
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Uploads the newest scan in the history.
    func uploadSavedScan() async {
        guard let latest = history.scans.first else {
            error = "No saved scan is available on this iPhone."
            return
        }
        await upload(latest)
    }

    private func fallbackTargets() -> [PhotoTarget] {
        guard let captured else { return [] }

        let walls = captured.walls.sorted {
            $0.dimensions.x * $0.dimensions.y >
            $1.dimensions.x * $1.dimensions.y
        }

        let labels = ["Largest wall", "Second wall", "Third wall", "Fourth wall"]

        return walls.prefix(4).enumerated().map { index, wall in
            PhotoTarget(
                surface_id: wall.identifier.uuidString,
                kind: "wall",
                label: labels[index]
            )
        }
    }
}

struct HomeView: View {
    @StateObject private var flow = Flow()

    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                Text("Sweetspot")
                    .font(.largeTitle.bold())

                Text(
                    RoomCaptureSession.isSupported
                        ? "LiDAR room scan available"
                        : "No LiDAR detected. Use a fallback."
                )
                .foregroundStyle(.secondary)

                if flow.isWorking {
                    ProgressView("Contacting Sweetspot backend…")
                }

                if RoomCaptureSession.isSupported {
                    Button("Start room scan") {
                        flow.phase = .scan
                    }
                    .buttonStyle(.borderedProminent)
                }

                Button("Use demo room") {
                    Task { await flow.useDemo() }
                }
                .buttonStyle(.borderedProminent)

                RecentScansLinks(flow: flow, history: flow.history)

                NavigationLink(
                    "Enter room dimensions",
                    destination: RectangleEntry(flow: flow)
                )

                CodeEntry(flow: flow)

                if let sessionID = flow.sessionID {
                    Label("Connected · \(sessionID)", systemImage: "link")
                }

                if let error = flow.error {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.footnote)
                }
            }
            .padding()
            .navigationDestination(
                isPresented: Binding(
                    get: { flow.phase != .home },
                    set: { if !$0 { flow.phase = .home } }
                )
            ) {
                switch flow.phase {
                case .scan:
                    ScanScreen(flow: flow)
                case .review:
                    ReviewScreen(flow: flow)
                case .photos:
                    PhotosStep(flow: flow)
                case .results:
                    ResultsScreen(flow: flow)
                case .ar:
                    ARLayoutScreen(flow: flow)
                case .home:
                    EmptyView()
                }
            }
        }
        .alert(
            "Sweetspot",
            isPresented: Binding(
                get: { flow.error != nil },
                set: { if !$0 { flow.error = nil } }
            )
        ) {
            Button("OK", role: .cancel) { flow.error = nil }
        } message: {
            Text(flow.error ?? "")
        }
    }
}

struct CodeEntry: View {
    @ObservedObject var flow: Flow
    @State private var code = ""
    @State private var showScanner = false

    var body: some View {
        VStack {
            HStack {
                TextField("Desktop code", text: $code)
                    .textInputAutocapitalization(.characters)
                    .textFieldStyle(.roundedBorder)

                Button("Connect") {
                    Task {
                        await flow.pair(
                            code: code.trimmingCharacters(in: .whitespaces)
                        )
                    }
                }
                .disabled(code.count < 6)
            }

            if DataScannerViewController.isSupported {
                Button("Scan desktop QR") {
                    showScanner = true
                }
                .sheet(isPresented: $showScanner) {
                    ZStack {
                        PairQRScanner { value in
                            do {
                                flow.sessionID = try sessionID(from: value)
                                UserDefaults.standard.set(
                                    flow.sessionID,
                                    forKey: "sweetspot.session_id"
                                )
                                showScanner = false
                            } catch {
                                flow.error = error.localizedDescription
                            }
                        }
                        .ignoresSafeArea()

                        RoundedRectangle(cornerRadius: 18)
                            .stroke(.green, lineWidth: 3)
                            .frame(width: 290, height: 210)
                            .overlay(alignment: .bottom) {
                                Text("Center the desktop QR code in the box")
                                    .font(.callout)
                                    .padding(8)
                                    .background(.black.opacity(0.7))
                                    .foregroundStyle(.white)
                                    .clipShape(Capsule())
                                    .offset(y: 42)
                            }
                            .allowsHitTesting(false)
                    }
                    .ignoresSafeArea()
                }
            }
        }
    }
}

struct RectangleEntry: View {
    @ObservedObject var flow: Flow
    @State private var width = "12"
    @State private var length = "15"
    @State private var height = "9"

    var body: some View {
        Form {
            Text("Enter measurements in feet")

            TextField("Width (ft)", text: $width)
                .keyboardType(.decimalPad)
            TextField("Length (ft)", text: $length)
                .keyboardType(.decimalPad)
            TextField("Height (ft)", text: $height)
                .keyboardType(.decimalPad)

            Button("Create room") {
                Task {
                    await flow.makeRectangle(
                        width: Double(width) ?? 12,
                        length: Double(length) ?? 15,
                        height: Double(height) ?? 9
                    )
                }
            }
        }
        .navigationTitle("Room size")
    }
}

struct ScanScreen: View {
    @ObservedObject var flow: Flow
    @State private var shouldFinish = false

    var body: some View {
        VStack {
            Text(
                "Stand near the center. Turn slowly and capture each wall, " +
                "doors, windows and furniture. Do not take photos during scanning."
            )
            .padding()

            ScanCapture(
                shouldFinish: $shouldFinish,
                onError: { flow.error = $0 },
                onRoom: { room, session in
                    flow.accept(room, session: session)
                }
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(.black)
            .overlay(alignment: .bottom) {
                Button("Finish scan") {
                    shouldFinish = true
                }
                .padding()
                .background(.regularMaterial)
                .clipShape(Capsule())
                .padding(.bottom, 16)
            }
        }
        .navigationTitle("Room scan")
    }
}

struct ReviewScreen: View {
    @ObservedObject var flow: Flow
    @State private var name = ""

    var body: some View {
        Form {
            Section {
                Text("Scan saved on this iPhone. You can find it again under Recent scans.")

                if let summary = flow.currentScan?.summary {
                    LabeledContent("Found", value: summary.text)
                }

                TextField("Name, e.g. Living room (optional)", text: $name)
                    .submitLabel(.done)
                    .onSubmit { flow.nameCurrentScan(name) }
            }

            Section {
                Button("Upload scan") {
                    flow.nameCurrentScan(name)
                    Task { await flow.uploadScan() }
                }
                .disabled(flow.isWorking)

                if flow.isWorking {
                    ProgressView("Uploading…")
                }

                Button("Use demo room instead") {
                    flow.nameCurrentScan(name)
                    Task { await flow.useDemo() }
                }
            }
        }
        .navigationTitle("Review scan")
    }
}

struct PhotosStep: View {
    @ObservedObject var flow: Flow
    @State private var showCamera = false

    var body: some View {
        List {
            Section("Material photos") {
                Text("Photos help identify wall and floor materials. They are used for classification.")

                if flow.photoIndex < flow.photoTargets.count {
                    let target = flow.photoTargets[flow.photoIndex]

                    Text("\(target.label) · \(target.kind)")

                    Button("Take photo") {
                        showCamera = true
                    }
                    .sheet(isPresented: $showCamera) {
                        CameraCapture { image in
                            guard let image else { return }
                            Task {
                                await flow.uploadPhoto(
                                    surfaceID: target.surface_id,
                                    image: image
                                )
                            }
                        }
                        .ignoresSafeArea()
                    }

                    Text("Photo \(flow.photoIndex + 1) of \(flow.photoTargets.count)")
                        .foregroundStyle(.secondary)
                } else {
                    Text("All available target photos uploaded.")
                }

                if let error = flow.error {
                    Text(error).foregroundStyle(.red)
                }
            }

            Button("Finish photos and classify") {
                Task { await flow.classify() }
            }

            Button("Skip photos and continue") {
                Task { await flow.classify() }
            }
        }
        .navigationTitle("Surface photos")
    }
}

struct ResultsScreen: View {
    @ObservedObject var flow: Flow

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Room: \(flow.roomID ?? "not uploaded")")

            if flow.showingOfflinePreview {
                Text(
                    "Offline sample preview — positions are illustrative, " +
                    "not calculated by the backend."
                )
                .font(.footnote)
                .foregroundStyle(.orange)
            }

            ForEach(flow.materials) { material in
                Text("\(material.material) · \(Int(material.confidence * 100))%")
            }

            Button("Compute speaker layout") {
                Task { await flow.compute() }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
        .navigationTitle("Results")
    }
}

struct ARLayoutScreen: View {
    @ObservedObject var flow: Flow
    @State private var alignment = "Preparing AR"

    var body: some View {
        VStack(spacing: 0) {
            if let layout = flow.layout {
                ARLayoutView(
                    scanSession: flow.scanSession,
                    layout: layout,
                    roomWidthFeet: flow.roomDimensions?.width,
                    roomFrame: flow.roomFrame,
                    sharedScanFrame: flow.scanSession != nil,
                    alignmentState: $alignment
                )
                .overlay(alignment: .top) {
                    HStack {
                        Text(alignment)

                        if flow.scanSession == nil {
                            Button("Align again") {
                                alignment = "Align again"
                            }
                        }
                    }
                    .padding(8)
                    .background(.regularMaterial)
                    .clipShape(Capsule())
                    .padding()
                }

                Text(
                    "Speaker markers are positioned from the backend layout. " +
                    "Coordinates are converted from feet to meters."
                )
                .font(.footnote)
                .padding(8)
            } else {
                Text("No layout is available yet.")
            }
        }
        .navigationTitle("AR layout")
    }
}
