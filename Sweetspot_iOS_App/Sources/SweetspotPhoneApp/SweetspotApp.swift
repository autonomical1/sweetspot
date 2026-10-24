import SwiftUI
import RoomPlan
import ARKit
import RealityKit

@main
struct SweetspotApp: App {
    var body: some Scene { WindowGroup { HomeView() } }
}

@MainActor final class Flow: ObservableObject {
    @Published var error: String?
    @Published var roomID: String?
    @Published var sessionID: String?
    @Published var phase: AppPhase = .home
    @Published var materials: [MaterialResult] = []
    @Published var layout: Layout?
    @Published var roomDimensions: Dimensions?
    @Published var photoTargets: [PhotoTarget] = []
    @Published var photoIndex = 0
    let backend = BackendClient()
    let arView = ARView(frame: .zero, cameraMode: .ar, automaticallyConfigureSession: false)
    private(set) var captured: CapturedRoom?
    private var scanFile: URL? { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first?.appendingPathComponent("latest-roomplan.json") }

    init() {
        sessionID = UserDefaults.standard.string(forKey: "sweetspot.session_id")
        roomID = UserDefaults.standard.string(forKey: "sweetspot.room_id")
    }

    func accept(_ room: CapturedRoom) {
        captured = room; phase = .review
        do { try RoomPlanDTO(room).data().write(to: scanFile!, options: .atomic) }
        catch { self.error = "Could not save scan: \(error.localizedDescription)" }
    }
    func uploadScan() async {
        guard let captured else { return }
        do {
            let response = try await backend.upload(dto: RoomPlanDTO(captured).data(), sessionID: sessionID)
            roomID = response.room_id; UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id")
            roomDimensions = response.dimensions; phase = .photos
            let serverTargets = (try? await backend.targets(roomID: response.room_id)) ?? []
            photoTargets = serverTargets.isEmpty ? fallbackTargets() : serverTargets
        } catch { self.error = error.localizedDescription }
    }
    func useDemo() async {
        do { let response = try await backend.demo(sessionID: sessionID); roomID = response.room_id; UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id"); roomDimensions = response.dimensions; phase = .results }
        catch { self.error = error.localizedDescription }
    }
    func pair(code: String) async {
        do { sessionID = try await backend.pair(code: code).session_id; UserDefaults.standard.set(sessionID, forKey: "sweetspot.session_id") }
        catch { self.error = error.localizedDescription }
    }
    func compute() async {
        guard let roomID else { return }
        do { layout = try await backend.optimize(roomID: roomID).layout; phase = .ar }
        catch { self.error = error.localizedDescription }
    }
    func classify() async {
        guard let roomID else { return }
        do { materials = try await backend.classify(roomID: roomID).surfaces; phase = .results }
        catch { self.error = error.localizedDescription; phase = .results }
    }
    func uploadPhoto(surfaceID: String, image: UIImage) async {
        guard let roomID, let jpeg = image.sweetspotJPEG() else { error = "Could not prepare photo."; return }
        do { try await backend.uploadPhoto(roomID: roomID, surfaceID: surfaceID, jpeg: jpeg); photoIndex += 1 }
        catch { self.error = error.localizedDescription }
    }
    func uploadSavedScan() async {
        guard let scanFile, let data = try? Data(contentsOf: scanFile) else { error = "No saved scan is available on this iPhone."; return }
        do {
            let response = try await backend.upload(dto: data, sessionID: sessionID)
            roomID = response.room_id; UserDefaults.standard.set(response.room_id, forKey: "sweetspot.room_id")
            roomDimensions = response.dimensions
            let serverTargets = (try? await backend.targets(roomID: response.room_id)) ?? []
            photoTargets = serverTargets.isEmpty ? fallbackTargets() : serverTargets
            phase = .photos
        } catch { self.error = error.localizedDescription }
    }
    private func fallbackTargets() -> [PhotoTarget] {
        guard let captured else { return [] }
        return captured.walls.sorted { $0.dimensions.x * $0.dimensions.y > $1.dimensions.x * $1.dimensions.y }
            .prefix(4).enumerated().map { index, wall in
                PhotoTarget(surface_id: wall.identifier.uuidString, kind: "wall", label: ["Largest wall", "Second wall", "Third wall", "Fourth wall"][index])
            }
    }
}

struct HomeView: View {
    @StateObject private var flow = Flow()
    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                Text("Sweetspot").font(.largeTitle.bold())
                Text(RoomCaptureSession.isSupported ? "LiDAR room scan available" : "No LiDAR detected. Use a fallback.").foregroundStyle(.secondary)
                if RoomCaptureSession.isSupported {
                    Button("Start room scan") { flow.phase = .scan }.buttonStyle(.borderedProminent)
                }
                Button("Use demo room") { Task { await flow.useDemo() } }.buttonStyle(.borderedProminent)
                Button("Upload saved scan") { Task { await flow.uploadSavedScan() } }
                NavigationLink("Enter room dimensions", destination: RectangleEntry(flow: flow))
                CodeEntry(flow: flow)
                if let sid = flow.sessionID { Label("Connected · \(sid)", systemImage: "link") }
                if let error = flow.error { Text(error).foregroundStyle(.red).font(.footnote) }
            }.padding()
            .navigationDestination(isPresented: Binding(get: { flow.phase != .home }, set: { if !$0 { flow.phase = .home } })) {
                switch flow.phase {
                case .scan: ScanScreen(flow: flow)
                case .review: ReviewScreen(flow: flow)
                case .photos: PhotosStep(flow: flow)
                case .results: ResultsScreen(flow: flow)
                case .ar: ARLayoutScreen(flow: flow)
                case .home: EmptyView()
                }
            }
        }
    }
}

struct CodeEntry: View {
    @ObservedObject var flow: Flow
    @State private var code = ""
    @State private var showScanner = false
    var body: some View {
        VStack {
            HStack { TextField("Desktop code", text: $code).textInputAutocapitalization(.characters).textFieldStyle(.roundedBorder)
                Button("Connect") { Task { await flow.pair(code: code.trimmingCharacters(in: .whitespaces)) } }.disabled(code.count < 6) }
            if DataScannerViewController.isSupported && DataScannerViewController.isAvailable {
                Button("Scan desktop QR") { showScanner = true }
                    .sheet(isPresented: $showScanner) { PairQRScanner { value in
                        do { flow.sessionID = try sessionID(from: value); UserDefaults.standard.set(flow.sessionID, forKey: "sweetspot.session_id"); showScanner = false }
                        catch { flow.error = error.localizedDescription }
                    }.ignoresSafeArea() }
            }
        }
    }
}

struct RectangleEntry: View {
    @ObservedObject var flow: Flow
    @State private var width = "12"; @State private var length = "15"; @State private var height = "9"
    var body: some View {
        Form {
            Text("Enter measurements in feet")
            TextField("Width (ft)", text: $width).keyboardType(.decimalPad)
            TextField("Length (ft)", text: $length).keyboardType(.decimalPad)
            TextField("Height (ft)", text: $height).keyboardType(.decimalPad)
            Button("Create room") { Task {
                do { let r = try await flow.backend.rectangle(width: Double(width) ?? 12, length: Double(length) ?? 15, height: Double(height) ?? 9, sessionID: flow.sessionID); flow.roomID = r.room_id; flow.roomDimensions = r.dimensions; flow.phase = .results }
                catch { flow.error = error.localizedDescription }
            } }
        }.navigationTitle("Room size")
    }
}

struct ScanScreen: View {
    @ObservedObject var flow: Flow
    @State private var shouldFinish = false
    var body: some View {
        VStack {
            Text("Stand near the center. Turn slowly and capture each wall, doors, windows and furniture. Do not take photos during scanning.").padding()
            ScanCapture(session: flow.arView.session, shouldFinish: $shouldFinish) { flow.accept($0) }
                .overlay(alignment: .bottom) { Button("Finish scan") { shouldFinish = true }.padding().background(.regularMaterial).clipShape(Capsule()) }
        }.navigationTitle("Room scan")
    }
}

struct ReviewScreen: View {
    @ObservedObject var flow: Flow
    var body: some View {
        VStack(spacing: 16) {
            Text("Scan saved on this iPhone. Upload to generate the room layout.")
            Button("Upload scan") { Task { await flow.uploadScan() } }.buttonStyle(.borderedProminent)
            Button("Use demo room instead") { Task { await flow.useDemo() } }
        }.padding().navigationTitle("Review scan")
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
                    Button("Take photo") { showCamera = true }
                        .sheet(isPresented: $showCamera) { CameraCapture { image in
                            guard let image else { return }
                            Task { await flow.uploadPhoto(surfaceID: target.surface_id, image: image) }
                        }.ignoresSafeArea() }
                    Text("Photo \(flow.photoIndex + 1) of \(flow.photoTargets.count)").foregroundStyle(.secondary)
                } else { Text("All available target photos uploaded.") }
                if let error = flow.error { Text(error).foregroundStyle(.red) }
            }
            Button("Finish photos and classify") { Task { await flow.classify() } }
            Button("Skip photos and continue") { Task { await flow.classify() } }
        }.navigationTitle("Surface photos")
    }
}

struct ResultsScreen: View {
    @ObservedObject var flow: Flow
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Room: \(flow.roomID ?? "not uploaded")")
            ForEach(flow.materials) { Text("\($0.material) · \(Int($0.confidence * 100))%") }
            Button("Compute speaker layout") { Task { await flow.compute() } }.buttonStyle(.borderedProminent)
        }.padding().navigationTitle("Results")
    }
}

struct ARLayoutScreen: View {
    @ObservedObject var flow: Flow
    @State private var alignment = "Preparing AR"
    var body: some View {
        VStack(spacing: 0) {
            if let layout = flow.layout {
                ARLayoutView(view: flow.arView, layout: layout, roomWidthFeet: flow.roomDimensions?.width,
                             sharedScanFrame: flow.captured != nil, alignmentState: $alignment)
                    .overlay(alignment: .top) { HStack { Text(alignment); if flow.captured == nil { Button("Align again") { alignment = "Align again" } } }.padding(8).background(.regularMaterial).clipShape(Capsule()).padding() }
                Text("Speaker markers are positioned from the backend layout. Coordinates are converted from feet to meters.").font(.footnote).padding(8)
            } else { Text("No layout is available yet.") }
        }.navigationTitle("AR layout")
    }
}
