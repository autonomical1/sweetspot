import SwiftUI
import RealityKit
import ARKit

struct ARLayoutView: UIViewRepresentable {
    /// RoomPlan's session from the scan, if there was one. Reusing it keeps
    /// the scan's world coordinate frame, so no manual alignment is needed.
    let scanSession: ARSession?
    let layout: Layout
    let products: [ProductItem]
    let roomWidthFeet: Double?
    let roomLengthFeet: Double?
    let roomHeightFeet: Double?
    let roomFrame: RoomFrame?
    let sharedScanFrame: Bool
    @Binding var alignmentState: String
    @Binding var trackingState: String

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
        view.session.delegate = context.coordinator

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
            context.coordinator.draw(layout: layout,
                transform: roomFrame.map { worldTransform(for: $0) } ?? matrix_identity_float4x4)
            if roomFrame == nil {
                alignmentState = "Room frame missing: AR placement may be wrong"
            } else {
                alignmentState = "Aligned to scan"
            }
        } else {
            context.coordinator.isAligningManually = true
            alignmentState = "Tap front-left corner"
        }

        return view
    }

    func updateUIView(_ uiView: ARView, context: Context) {
        context.coordinator.parent = self
        context.coordinator.startSessionWhenReady(
            uiView,
            attemptsRemaining: 5
        )

        if alignmentState == "Align manually" {
            context.coordinator.points.removeAll()
            uiView.scene.anchors.removeAll()
            context.coordinator.lastTransform = nil
            context.coordinator.drawnContent = nil
            context.coordinator.isAligningManually = true
            alignmentState = "Tap front-left corner"
        }

        if alignmentState == "Reset to scan alignment" {
            context.coordinator.points.removeAll()
            context.coordinator.isAligningManually = false
            context.coordinator.lastTransform = nil
            context.coordinator.drawnContent = nil
            alignmentState = "Aligned to scan"
        }

        if context.coordinator.isAligningManually {
            if let transform = context.coordinator.lastTransform,
               alignmentState == "Aligned manually" {
                context.coordinator.draw(layout: layout, transform: transform)
            }
        } else if sharedScanFrame {
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

    final class Coordinator: NSObject, ARSessionDelegate {
        var parent: ARLayoutView
        weak var view: ARView?
        var points: [SIMD3<Float>] = []
        var lastTransform: simd_float4x4?
        var isAligningManually = false
        private var drawnTransform: simd_float4x4?
        var drawnContent: String?
        private var didStartSession = false

        init(parent: ARLayoutView) {
            self.parent = parent
        }

        func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
            let status: String
            switch camera.trackingState {
            case .normal: status = "Tracking normal"
            case .notAvailable: status = "Tracking unavailable"
            case .limited(let reason):
                switch reason {
                case .initializing: status = "Tracking limited: initializing"
                case .excessiveMotion: status = "Tracking limited: moving too fast"
                case .insufficientFeatures: status = "Tracking limited: few visible details"
                case .relocalizing: status = "Tracking limited: re-locking"
                @unknown default: status = "Tracking limited"
                }
            }
            DispatchQueue.main.async { [weak self] in
                guard let self, self.parent.trackingState != status else { return }
                self.parent.trackingState = status
            }
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
            guard isAligningManually, let view,
                  let width = parent.roomWidthFeet, width > 0 else {
                return
            }

            let point = recognizer.location(in: view)

            guard let query = view.makeRaycastQuery(
                from: point,
                allowing: .estimatedPlane,
                alignment: .horizontal
            ),
            let result = view.session.raycast(query).first else {
                parent.alignmentState = "Point at the floor, then tap again"
                return
            }

            let translation = result.worldTransform.columns.3
            points.append(
                SIMD3(translation.x, translation.y, translation.z)
            )

            if points.count == 1 {
                parent.alignmentState = "Tap front-right corner"
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

            // A +yaw rotation about +y sends the room's +x axis to (cos, 0, -sin),
            // so the world z delta is negated (same convention as worldTransform).
            let worldAngle = atan2(
                -(secondWorldPoint.z - firstWorldPoint.z),
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
            parent.alignmentState = "Aligned manually"
            points.removeAll()

            _ = roomNorthEast // The second tap establishes the room's direction.
        }

        func draw(layout: Layout, transform: simd_float4x4) {
            guard let view else { return }
            lastTransform = transform

            let content = String(describing: layout) + String(describing: parent.products)
                + String(describing: [parent.roomWidthFeet, parent.roomLengthFeet, parent.roomHeightFeet])
            if let drawnTransform, drawnContent == content,
               (0..<4).allSatisfy({ drawnTransform[$0] == transform[$0] }) {
                return
            }
            drawnTransform = transform
            drawnContent = content

            view.scene.anchors.removeAll()
            let anchor = AnchorEntity(world: transform)

            if let width = parent.roomWidthFeet, let length = parent.roomLengthFeet,
               let height = parent.roomHeightFeet, width > 0, length > 0, height > 0 {
                let w = Float(width * 0.3048)
                let l = Float(length * 0.3048)
                let h = Float(height * 0.3048)
                let guide = SimpleMaterial(color: .cyan, isMetallic: false)
                func line(_ size: SIMD3<Float>, at position: SIMD3<Float>) {
                    let entity = ModelEntity(mesh: .generateBox(size: size), materials: [guide])
                    entity.position = position
                    anchor.addChild(entity)
                }
                for x in [Float(0), w] {
                    for z in [Float(0), l] {
                        line([0.012, h, 0.012], at: [x, h / 2, z])
                    }
                }
                for z in [Float(0), l] {
                    line([w, 0.012, 0.012], at: [w / 2, 0, z])
                }
                for x in [Float(0), w] {
                    line([0.012, 0.012, l], at: [x, 0, l / 2])
                }
            }

            if let projector = layout.projector, projector.position.count == 3 {
                // Same footprint as the web model (0.34 x 0.13 x 0.30 m), pointed at its aim point.
                let body = ModelEntity(
                    mesh: .generateBox(size: [0.34, 0.13, 0.30]),
                    materials: [SimpleMaterial(color: .white, roughness: 0.4, isMetallic: false)]
                )
                body.position = SIMD3<Float>(
                    Float(projector.position[0] * 0.3048),
                    Float(projector.position[1] * 0.3048),
                    Float(projector.position[2] * 0.3048)
                )
                if projector.aim.count == 3 {
                    let dx = Float(projector.aim[0] - projector.position[0])
                    let dz = Float(projector.aim[2] - projector.position[2])
                    if abs(dx) + abs(dz) > 0.0001 {
                        body.orientation = simd_quatf(angle: atan2(-dx, -dz), axis: SIMD3<Float>(0, 1, 0))
                    }
                }
                anchor.addChild(body)
            }

            for speaker in layout.speakers where speaker.position.count == 3 {
                let position = SIMD3<Float>(
                    Float(speaker.position[0] * 0.3048),
                    Float(speaker.position[1] * 0.3048),
                    Float(speaker.position[2] * 0.3048)
                )

                let dimensions = parent.products.first { $0.role == speaker.role }?.dimensions
                let validDimensions = dimensions.flatMap { value -> SIMD3<Float>? in
                    guard value.width > 0, value.height > 0, value.depth > 0 else { return nil }
                    return SIMD3(
                        Float(value.width * 0.3048),
                        Float(value.height * 0.3048),
                        Float(value.depth * 0.3048)
                    )
                }
                let markerMesh: MeshResource
                if let validDimensions {
                    markerMesh = .generateBox(size: validDimensions)
                } else {
                    markerMesh = .generateSphere(radius: 0.09)
                }
                let marker = ModelEntity(
                    mesh: markerMesh,
                    materials: [
                        SimpleMaterial(
                            color: ARTint.accent,
                            roughness: 0.35,
                            isMetallic: false
                        )
                    ]
                )
                marker.position = position
                if validDimensions != nil, speaker.aim.count == 3 {
                    let dx = Float(speaker.aim[0] - speaker.position[0])
                    let dz = Float(speaker.aim[2] - speaker.position[2])
                    if abs(dx) + abs(dz) > 0.0001 {
                        marker.orientation = simd_quatf(
                            angle: atan2(-dx, -dz),
                            axis: SIMD3<Float>(0, 1, 0)
                        )
                    }
                }
                anchor.addChild(marker)

                let stem = ModelEntity(
                    mesh: .generateBox(
                        size: [0.025, max(0.05, position.y), 0.025]
                    ),
                    materials: [
                        SimpleMaterial(color: ARTint.accentDim, isMetallic: false)
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
                            color: ARTint.accentLink.withAlphaComponent(0.45),
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

/// Marker colors for the AR scene, same values as the web theme (kept here so this file builds on its own).
private enum ARTint {
    static let accent = UIColor(red: 0x5c / 255, green: 0xdd / 255, blue: 0xc5 / 255, alpha: 1)
    static let accentLink = UIColor(red: 0x6c / 255, green: 0xdd / 255, blue: 0xc8 / 255, alpha: 1)
    static let accentDim = UIColor(red: 0x4b / 255, green: 0x74 / 255, blue: 0x6e / 255, alpha: 1)
}
