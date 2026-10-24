import SwiftUI
import RoomPlan
import ARKit

struct ScanCapture: UIViewRepresentable {
    let session: ARSession
    @Binding var shouldFinish: Bool
    let onRoom: (CapturedRoom) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(onRoom: onRoom) }
    func makeUIView(context: Context) -> RoomCaptureView {
        let view = RoomCaptureView(frame: .zero, arSession: session)
        view.delegate = context.coordinator
        var config = RoomCaptureSession.Configuration(); config.isCoachingEnabled = true
        view.captureSession.run(configuration: config)
        context.coordinator.captureView = view
        return view
    }
    func updateUIView(_ uiView: RoomCaptureView, context: Context) {
        if shouldFinish { context.coordinator.finish(); shouldFinish = false }
    }
    final class Coordinator: NSObject, RoomCaptureViewDelegate {
        var onRoom: (CapturedRoom) -> Void
        weak var captureView: RoomCaptureView?
        init(onRoom: @escaping (CapturedRoom) -> Void) { self.onRoom = onRoom }
        required init?(coder: NSCoder) { nil }
        func encode(with coder: NSCoder) {}
        func finish() { captureView?.captureSession.stop(pauseARSession: false) }
        func captureView(shouldPresent roomDataForProcessing: CapturedRoomData, error: (any Error)?) -> Bool { error == nil }
        func captureView(didPresent room: CapturedRoom, error: (any Error)?) { if error == nil { onRoom(room) } }
    }
}
