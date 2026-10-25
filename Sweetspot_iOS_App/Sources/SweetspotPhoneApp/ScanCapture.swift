//import SwiftUI
//import RoomPlan
//import ARKit
//
//struct ScanCapture: UIViewRepresentable {
//    let session: ARSession
//    @Binding var shouldFinish: Bool
//    let onError: (String) -> Void
//    let onRoom: (CapturedRoom) -> Void
//
//    func makeCoordinator() -> RoomPlanCaptureCoordinator {
//        RoomPlanCaptureCoordinator(
//            onError: onError,
//            onRoom: onRoom
//        )
//    }
//
//    func makeUIView(context: Context) -> RoomCaptureView {
//        // RoomPlan requires a supplied ARSession to be running with a
//        // world-tracking configuration before it creates the capture view.
//        if session.currentFrame == nil {
//            let configuration = ARWorldTrackingConfiguration()
//            configuration.planeDetection = [.horizontal, .vertical]
//            session.run(configuration)
//        }
//
//        let view = RoomCaptureView(frame: .zero, arSession: session)
//        view.delegate = context.coordinator
//        context.coordinator.captureView = view
//
//        // Wait until SwiftUI has attached and sized the view before starting capture.
//        DispatchQueue.main.async {
//            context.coordinator.startWhenReady(
//                view,
//                attemptsRemaining: 20
//            )
//        }
//
//        return view
//    }
//
//    func updateUIView(_ uiView: RoomCaptureView, context: Context) {
//        context.coordinator.startWhenReady(
//            uiView,
//            attemptsRemaining: 5
//        )
//
//        if shouldFinish {
//            context.coordinator.finish()
//            shouldFinish = false
//        }
//    }
//}
//
//final class RoomPlanCaptureCoordinator: NSObject, RoomCaptureViewDelegate {
//    private let onError: (String) -> Void
//    private let onRoom: (CapturedRoom) -> Void
//    private var didStartCapture = false
//    weak var captureView: RoomCaptureView?
//
//    init(
//        onError: @escaping (String) -> Void,
//        onRoom: @escaping (CapturedRoom) -> Void
//    ) {
//        self.onError = onError
//        self.onRoom = onRoom
//        super.init()
//    }
//
//    required init?(coder: NSCoder) {
//        return nil
//    }
//
//    func encode(with coder: NSCoder) {}
//
//    func startWhenReady(
//        _ view: RoomCaptureView,
//        attemptsRemaining: Int
//    ) {
//        guard !didStartCapture else { return }
//
//        view.setNeedsLayout()
//        view.layoutIfNeeded()
//
//        guard view.window != nil,
//              view.bounds.width > 1,
//              view.bounds.height > 1 else {
//            guard attemptsRemaining > 0 else {
//                onError("The room scan view did not get a usable screen size.")
//                return
//            }
//
//            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
//                [weak self, weak view] in
//
//                guard let self, let view else { return }
//                self.startWhenReady(
//                    view,
//                    attemptsRemaining: attemptsRemaining - 1
//                )
//            }
//            return
//        }
//
//        didStartCapture = true
//
//        var configuration = RoomCaptureSession.Configuration()
//        configuration.isCoachingEnabled = true
//        view.captureSession.run(configuration: configuration)
//    }
//
//    func finish() {
//        captureView?.captureSession.stop(pauseARSession: false)
//    }
//
//    func captureView(
//        shouldPresent roomDataForProcessing: CapturedRoomData,
//        error: (any Error)?
//    ) -> Bool {
//        if let error {
//            onError("RoomPlan could not process the scan: \(error.localizedDescription)")
//            return false
//        }
//        return true
//    }
//
//    func captureView(
//        didPresent room: CapturedRoom,
//        error: (any Error)?
//    ) {
//        if let error {
//            onError("RoomPlan failed to finish the scan: \(error.localizedDescription)")
//        } else {
//            onRoom(room)
//        }
//    }
//}
import SwiftUI
import RoomPlan
import ARKit

struct ScanCapture: UIViewRepresentable {
    @Binding var shouldFinish: Bool
    let onError: (String) -> Void
    /// Delivers the finished room plus the ARSession RoomPlan used, so the
    /// AR layout screen can reuse the scan's world coordinate frame.
    let onRoom: (CapturedRoom, ARSession) -> Void

    func makeCoordinator() -> RoomPlanCaptureCoordinator {
        RoomPlanCaptureCoordinator(
            onError: onError,
            onRoom: onRoom
        )
    }

    func makeUIView(context: Context) -> RoomCaptureView {
        // Let RoomCaptureView create and own its ARSession. It draws the camera
        // feed and the live outline boxes through that session; passing in a
        // session that belongs to a different (off-screen) ARView left the feed
        // black. RoomPlan also configures the session itself when capture
        // starts, so there's no need to run a world-tracking config first.
        let view = RoomCaptureView(frame: .zero)
        view.delegate = context.coordinator
        context.coordinator.captureView = view

        // Wait until SwiftUI has attached and sized the view before starting capture.
        DispatchQueue.main.async {
            context.coordinator.startWhenReady(
                view,
                attemptsRemaining: 20
            )
        }

        return view
    }

    func updateUIView(_ uiView: RoomCaptureView, context: Context) {
        context.coordinator.startWhenReady(
            uiView,
            attemptsRemaining: 5
        )

        if shouldFinish {
            context.coordinator.finish()
            // Reset the binding after this update pass; changing state
            // during a view update is undefined behavior in SwiftUI.
            DispatchQueue.main.async {
                shouldFinish = false
            }
        }
    }

    static func dismantleUIView(
        _ uiView: RoomCaptureView,
        coordinator: RoomPlanCaptureCoordinator
    ) {
        // If the person backs out mid-scan, turn the camera off and
        // don't deliver a half-finished room.
        coordinator.cancelIfScanning(uiView)
    }
}

final class RoomPlanCaptureCoordinator: NSObject, RoomCaptureViewDelegate {
    private let onError: (String) -> Void
    private let onRoom: (CapturedRoom, ARSession) -> Void
    private var didStartCapture = false
    private var didStopCapture = false
    private var arSession: ARSession?
    weak var captureView: RoomCaptureView?

    init(
        onError: @escaping (String) -> Void,
        onRoom: @escaping (CapturedRoom, ARSession) -> Void
    ) {
        self.onError = onError
        self.onRoom = onRoom
        super.init()
    }

    required init?(coder: NSCoder) {
        return nil
    }

    func encode(with coder: NSCoder) {}

    func startWhenReady(
        _ view: RoomCaptureView,
        attemptsRemaining: Int
    ) {
        guard !didStartCapture else { return }

        view.setNeedsLayout()
        view.layoutIfNeeded()

        guard view.window != nil,
              view.bounds.width > 1,
              view.bounds.height > 1 else {
            guard attemptsRemaining > 0 else {
                onError("Couldn't start the scan. Please try again.")
                return
            }

            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                [weak self, weak view] in

                guard let self, let view else { return }
                self.startWhenReady(
                    view,
                    attemptsRemaining: attemptsRemaining - 1
                )
            }
            return
        }

        didStartCapture = true
        arSession = view.captureSession.arSession

        var configuration = RoomCaptureSession.Configuration()
        configuration.isCoachingEnabled = true
        view.captureSession.run(configuration: configuration)
    }

    func finish() {
        guard didStartCapture, !didStopCapture else { return }
        didStopCapture = true

        // Keep the ARSession running so the AR layout screen can reuse
        // the scan's world coordinate frame.
        captureView?.captureSession.stop(pauseARSession: false)
    }

    func cancelIfScanning(_ view: RoomCaptureView) {
        guard didStartCapture, !didStopCapture else { return }
        didStopCapture = true

        // Detach first so stopping doesn't trigger processing callbacks
        // that would navigate to the review screen.
        view.delegate = nil
        view.captureSession.stop()
    }

    func captureView(
        shouldPresent roomDataForProcessing: CapturedRoomData,
        error: (any Error)?
    ) -> Bool {
        if let error {
            onError("Couldn't process the scan. Please try again.")
            return false
        }
        return true
    }

    func captureView(
        didPresent room: CapturedRoom,
        error: (any Error)?
    ) {
        if let error {
            onError("Couldn't finish the scan. Please try again.")
            return
        }

        guard let arSession else {
            onError("Couldn't finish the scan. Please try again.")
            return
        }

        onRoom(room, arSession)
    }
}
