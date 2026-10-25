//import SwiftUI
//import RealityKit
//import ARKit
//
//struct ARLayoutView: UIViewRepresentable {
//    let view: ARView
//    let layout: Layout
//    let roomWidthFeet: Double?
//    let sharedScanFrame: Bool
//    @Binding var alignmentState: String
//
//    func makeCoordinator() -> Coordinator {
//        Coordinator(parent: self)
//    }
//
//    func makeUIView(context: Context) -> ARView {
//        view.automaticallyConfigureSession = false
//
//        let tap = UITapGestureRecognizer(
//            target: context.coordinator,
//            action: #selector(Coordinator.tapped(_:))
//        )
//        view.addGestureRecognizer(tap)
//        context.coordinator.view = view
//
//        DispatchQueue.main.async {
//            context.coordinator.startSessionWhenReady(
//                view,
//                attemptsRemaining: 20
//            )
//        }
//
//        if sharedScanFrame {
//            context.coordinator.draw(
//                layout: layout,
//                transform: matrix_identity_float4x4
//            )
//        } else {
//            alignmentState = "Tap north-west floor corner"
//        }
//
//        return view
//    }
//
//    func updateUIView(_ uiView: ARView, context: Context) {
//        context.coordinator.parent = self
//        context.coordinator.startSessionWhenReady(
//            uiView,
//            attemptsRemaining: 5
//        )
//
//        if alignmentState == "Align again" {
//            context.coordinator.points.removeAll()
//            uiView.scene.anchors.removeAll()
//            alignmentState = "Tap north-west floor corner"
//        }
//    }
//
//    final class Coordinator: NSObject {
//        var parent: ARLayoutView
//        weak var view: ARView?
//        var points: [SIMD3<Float>] = []
//        private var didStartSession = false
//
//        init(parent: ARLayoutView) {
//            self.parent = parent
//        }
//
//        func startSessionWhenReady(
//            _ view: ARView,
//            attemptsRemaining: Int
//        ) {
//            guard !didStartSession else { return }
//
//            view.setNeedsLayout()
//            view.layoutIfNeeded()
//
//            guard view.window != nil,
//                  view.bounds.width > 1,
//                  view.bounds.height > 1 else {
//                guard attemptsRemaining > 0 else { return }
//
//                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
//                    [weak self, weak view] in
//
//                    guard let self, let view else { return }
//                    self.startSessionWhenReady(
//                        view,
//                        attemptsRemaining: attemptsRemaining - 1
//                    )
//                }
//                return
//            }
//
//            didStartSession = true
//
//            guard view.session.currentFrame == nil else { return }
//
//            let configuration = ARWorldTrackingConfiguration()
//            configuration.planeDetection = [.horizontal, .vertical]
//            view.session.run(configuration)
//        }
//
//        @objc func tapped(_ recognizer: UITapGestureRecognizer) {
//            guard !parent.sharedScanFrame,
//                  let view,
//                  let width = parent.roomWidthFeet else {
//                return
//            }
//
//            let point = recognizer.location(in: view)
//
//            guard let query = view.makeRaycastQuery(
//                from: point,
//                allowing: .estimatedPlane,
//                alignment: .horizontal
//            ),
//            let result = view.session.raycast(query).first else {
//                return
//            }
//
//            let translation = result.worldTransform.columns.3
//            points.append(
//                SIMD3(translation.x, translation.y, translation.z)
//            )
//
//            if points.count == 1 {
//                parent.alignmentState = "Tap north-east floor corner"
//                return
//            }
//
//            let firstWorldPoint = points[0]
//            let secondWorldPoint = points[1]
//
//            let roomNorthWest = SIMD3<Float>(0, 0, 0)
//            let roomNorthEast = SIMD3<Float>(
//                Float(width * 0.3048),
//                0,
//                0
//            )
//
//            let worldAngle = atan2(
//                secondWorldPoint.z - firstWorldPoint.z,
//                secondWorldPoint.x - firstWorldPoint.x
//            )
//            let yaw = worldAngle
//
//            let rotation = simd_float4x4(
//                simd_quatf(angle: yaw, axis: [0, 1, 0])
//            )
//            let rotatedNorthWest = rotation * SIMD4(roomNorthWest, 1)
//
//            var transform = rotation
//            transform.columns.3 = SIMD4(
//                firstWorldPoint.x - rotatedNorthWest.x,
//                firstWorldPoint.y - rotatedNorthWest.y,
//                firstWorldPoint.z - rotatedNorthWest.z,
//                1
//            )
//
//            draw(layout: parent.layout, transform: transform)
//            parent.alignmentState = "Aligned"
//            points.removeAll()
//
//            _ = roomNorthEast // The second tap establishes the room's direction.
//        }
//
//        func draw(layout: Layout, transform: simd_float4x4) {
//            guard let view else { return }
//
//            view.scene.anchors.removeAll()
//            let anchor = AnchorEntity(world: transform)
//
//            for speaker in layout.speakers where speaker.position.count == 3 {
//                let position = SIMD3<Float>(
//                    Float(speaker.position[0] * 0.3048),
//                    Float(speaker.position[1] * 0.3048),
//                    Float(speaker.position[2] * 0.3048)
//                )
//
//                let marker = ModelEntity(
//                    mesh: .generateSphere(radius: 0.09),
//                    materials: [
//                        SimpleMaterial(
//                            color: .orange,
//                            roughness: 0.35,
//                            isMetallic: false
//                        )
//                    ]
//                )
//                marker.position = position
//                anchor.addChild(marker)
//
//                let stem = ModelEntity(
//                    mesh: .generateBox(
//                        size: [0.025, max(0.05, position.y), 0.025]
//                    ),
//                    materials: [
//                        SimpleMaterial(color: .yellow, isMetallic: false)
//                    ]
//                )
//                stem.position = SIMD3(
//                    position.x,
//                    position.y / 2,
//                    position.z
//                )
//                anchor.addChild(stem)
//
//                let labelMesh = MeshResource.generateText(
//                    speaker.role,
//                    extrusionDepth: 0.002,
//                    font: .systemFont(ofSize: 0.12),
//                    containerFrame: .zero,
//                    alignment: .center,
//                    lineBreakMode: .byWordWrapping
//                )
//                let label = ModelEntity(
//                    mesh: labelMesh,
//                    materials: [
//                        SimpleMaterial(color: .white, isMetallic: false)
//                    ]
//                )
//                label.position = position + SIMD3(-0.07, 0.14, 0)
//                anchor.addChild(label)
//            }
//
//            if let screen = layout.screen, screen.center.count == 3 {
//                let plane = ModelEntity(
//                    mesh: .generatePlane(
//                        width: Float(screen.width * 0.3048),
//                        height: Float(screen.height * 0.3048)
//                    ),
//                    materials: [
//                        SimpleMaterial(
//                            color: UIColor.systemBlue.withAlphaComponent(0.45),
//                            isMetallic: false
//                        )
//                    ]
//                )
//                plane.position = SIMD3(
//                    Float(screen.center[0] * 0.3048),
//                    Float(screen.center[1] * 0.3048),
//                    Float(screen.center[2] * 0.3048)
//                )
//                anchor.addChild(plane)
//            }
//
//            view.scene.addAnchor(anchor)
//        }
//    }
//}
import SwiftUI
import RealityKit
import ARKit

struct ARLayoutView: UIViewRepresentable {
    /// RoomPlan's session from the scan, if there was one. Reusing it keeps
    /// the scan's world coordinate frame, so no manual alignment is needed.
    let scanSession: ARSession?
    let layout: Layout
    let roomWidthFeet: Double?
    let roomFrame: RoomFrame?
    let sharedScanFrame: Bool
    @Binding var alignmentState: String

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeUIView(context: Context) -> ARView {
        // A fresh view each time this screen appears. The scan view has been
        // torn down by now, so this is the only view drawing the session.
        // (Reusing one shared ARView also stacked a new tap recognizer on it
        // every visit.)
        let view = ARView(
            frame: .zero,
            cameraMode: .ar,
            automaticallyConfigureSession: false
        )

        if let scanSession {
            view.session = scanSession
        }

        let tap = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.tapped(_:))
        )
        view.addGestureRecognizer(tap)
        context.coordinator.view = view

        DispatchQueue.main.async {
            context.coordinator.startSessionWhenReady(
                view,
                attemptsRemaining: 20
            )
        }

        if sharedScanFrame {
            #if DEBUG
            assert(checkRoomFrameVectors())
            #endif
            context.coordinator.draw(
                layout: layout,
                transform: roomFrame.map { worldTransform(for: $0) } ?? matrix_identity_float4x4
            )
            if roomFrame == nil {
                alignmentState = "Room frame missing: AR placement may be wrong"
            } else {
                alignmentState = "Aligned to scan"
            }
        } else {
            alignmentState = "Tap north-west floor corner"
        }

        return view
    }

    func updateUIView(_ uiView: ARView, context: Context) {
        context.coordinator.parent = self
        context.coordinator.startSessionWhenReady(
            uiView,
            attemptsRemaining: 5
        )

        if alignmentState == "Align again" {
            context.coordinator.points.removeAll()
            uiView.scene.anchors.removeAll()
            alignmentState = "Tap north-west floor corner"
        }

        if sharedScanFrame {
            context.coordinator.draw(
                layout: layout,
                transform: roomFrame.map { worldTransform(for: $0) } ?? matrix_identity_float4x4
            )
            if roomFrame == nil {
                alignmentState = "Room frame missing: AR placement may be wrong"
            } else if alignmentState != "Aligned to scan" {
                alignmentState = "Aligned to scan"
            }
        }
    }

    static func dismantleUIView(_ uiView: ARView, coordinator: Coordinator) {
        // Turn the camera off when leaving this screen. Flow still holds the
        // session, so coming back resumes it and ARKit relocalizes into the
        // same coordinate frame.
        uiView.session.pause()
    }

    final class Coordinator: NSObject {
        var parent: ARLayoutView
        weak var view: ARView?
        var points: [SIMD3<Float>] = []
        private var didStartSession = false

        init(parent: ARLayoutView) {
            self.parent = parent
        }

        func startSessionWhenReady(
            _ view: ARView,
            attemptsRemaining: Int
        ) {
            guard !didStartSession else { return }

            view.setNeedsLayout()
            view.layoutIfNeeded()

            guard view.window != nil,
                  view.bounds.width > 1,
                  view.bounds.height > 1 else {
                guard attemptsRemaining > 0 else { return }

                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    [weak self, weak view] in

                    guard let self, let view else { return }
                    self.startSessionWhenReady(
                        view,
                        attemptsRemaining: attemptsRemaining - 1
                    )
                }
                return
            }

            didStartSession = true

            let configuration = ARWorldTrackingConfiguration()
            configuration.planeDetection = [.horizontal, .vertical]
            // No reset options: a reused scan session keeps its world origin,
            // and a paused one resumes and relocalizes instead of starting over.
            view.session.run(configuration)
        }

        @objc func tapped(_ recognizer: UITapGestureRecognizer) {
            guard !parent.sharedScanFrame,
                  let view,
                  let width = parent.roomWidthFeet else {
                return
            }

            let point = recognizer.location(in: view)

            guard let query = view.makeRaycastQuery(
                from: point,
                allowing: .estimatedPlane,
                alignment: .horizontal
            ),
            let result = view.session.raycast(query).first else {
                return
            }

            let translation = result.worldTransform.columns.3
            points.append(
                SIMD3(translation.x, translation.y, translation.z)
            )

            if points.count == 1 {
                parent.alignmentState = "Tap north-east floor corner"
                return
            }

            let firstWorldPoint = points[0]
            let secondWorldPoint = points[1]

            let roomNorthWest = SIMD3<Float>(0, 0, 0)
            let roomNorthEast = SIMD3<Float>(
                Float(width * 0.3048),
                0,
                0
            )

            let worldAngle = atan2(
                secondWorldPoint.z - firstWorldPoint.z,
                secondWorldPoint.x - firstWorldPoint.x
            )
            let yaw = worldAngle

            let rotation = simd_float4x4(
                simd_quatf(angle: yaw, axis: [0, 1, 0])
            )
            let rotatedNorthWest = rotation * SIMD4(roomNorthWest, 1)

            var transform = rotation
            transform.columns.3 = SIMD4(
                firstWorldPoint.x - rotatedNorthWest.x,
                firstWorldPoint.y - rotatedNorthWest.y,
                firstWorldPoint.z - rotatedNorthWest.z,
                1
            )

            draw(layout: parent.layout, transform: transform)
            parent.alignmentState = "Aligned"
            points.removeAll()

            _ = roomNorthEast // The second tap establishes the room's direction.
        }

        func draw(layout: Layout, transform: simd_float4x4) {
            guard let view else { return }

            view.scene.anchors.removeAll()
            let anchor = AnchorEntity(world: transform)

            for speaker in layout.speakers where speaker.position.count == 3 {
                let position = SIMD3<Float>(
                    Float(speaker.position[0] * 0.3048),
                    Float(speaker.position[1] * 0.3048),
                    Float(speaker.position[2] * 0.3048)
                )

                let marker = ModelEntity(
                    mesh: .generateSphere(radius: 0.09),
                    materials: [
                        SimpleMaterial(
                            color: .orange,
                            roughness: 0.35,
                            isMetallic: false
                        )
                    ]
                )
                marker.position = position
                anchor.addChild(marker)

                let stem = ModelEntity(
                    mesh: .generateBox(
                        size: [0.025, max(0.05, position.y), 0.025]
                    ),
                    materials: [
                        SimpleMaterial(color: .yellow, isMetallic: false)
                    ]
                )
                stem.position = SIMD3(
                    position.x,
                    position.y / 2,
                    position.z
                )
                anchor.addChild(stem)

                let labelMesh = MeshResource.generateText(
                    speaker.role,
                    extrusionDepth: 0.002,
                    font: .systemFont(ofSize: 0.12),
                    containerFrame: .zero,
                    alignment: .center,
                    lineBreakMode: .byWordWrapping
                )
                let label = ModelEntity(
                    mesh: labelMesh,
                    materials: [
                        SimpleMaterial(color: .white, isMetallic: false)
                    ]
                )
                label.position = position + SIMD3(-0.07, 0.14, 0)
                anchor.addChild(label)
            }

            if let screen = layout.screen, screen.center.count == 3 {
                let plane = ModelEntity(
                    mesh: .generatePlane(
                        width: Float(screen.width * 0.3048),
                        height: Float(screen.height * 0.3048)
                    ),
                    materials: [
                        SimpleMaterial(
                            color: UIColor.systemBlue.withAlphaComponent(0.45),
                            isMetallic: false
                        )
                    ]
                )
                plane.position = SIMD3(
                    Float(screen.center[0] * 0.3048),
                    Float(screen.center[1] * 0.3048),
                    Float(screen.center[2] * 0.3048)
                )
                anchor.addChild(plane)
            }

            view.scene.addAnchor(anchor)
        }
    }
}
