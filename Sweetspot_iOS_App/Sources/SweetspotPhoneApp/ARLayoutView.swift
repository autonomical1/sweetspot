import SwiftUI
import RealityKit
import ARKit

struct ARLayoutView: UIViewRepresentable {
    let view: ARView
    let layout: Layout
    let roomWidthFeet: Double?
    let sharedScanFrame: Bool
    @Binding var alignmentState: String

    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }
    func makeUIView(context: Context) -> ARView {
        view.automaticallyConfigureSession = false
        if view.session.currentFrame == nil {
            let config = ARWorldTrackingConfiguration(); config.planeDetection = [.horizontal, .vertical]
            view.session.run(config)
        }
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.tapped(_:)))
        view.addGestureRecognizer(tap); context.coordinator.view = view
        if sharedScanFrame { context.coordinator.draw(layout: layout, transform: matrix_identity_float4x4) }
        else { alignmentState = "Tap north-west floor corner" }
        return view
    }
    func updateUIView(_ uiView: ARView, context: Context) {
        context.coordinator.parent = self
        if alignmentState == "Align again" { context.coordinator.points.removeAll(); uiView.scene.anchors.removeAll(); alignmentState = "Tap north-west floor corner" }
    }

    final class Coordinator: NSObject {
        var parent: ARLayoutView
        weak var view: ARView?
        var points: [SIMD3<Float>] = []
        init(parent: ARLayoutView) { self.parent = parent }

        @objc func tapped(_ recognizer: UITapGestureRecognizer) {
            guard !parent.sharedScanFrame, let view, let width = parent.roomWidthFeet else { return }
            let point = recognizer.location(in: view)
            guard let query = view.makeRaycastQuery(from: point, allowing: .estimatedPlane, alignment: .horizontal),
                  let result = view.session.raycast(query).first else { return }
            let c = result.worldTransform.columns.3
            points.append(SIMD3(c.x, c.y, c.z))
            if points.count == 1 { parent.alignmentState = "Tap north-east floor corner"; return }
            let p1 = points[0], p2 = points[1]
            let q1 = SIMD3<Float>(0, 0, 0), q2 = SIMD3<Float>(Float(width * 0.3048), 0, 0)
            let worldAngle = atan2(p2.z - p1.z, p2.x - p1.x)
            let roomAngle: Float = 0
            let yaw = worldAngle - roomAngle
            let rotation = simd_float4x4(simd_quatf(angle: yaw, axis: [0, 1, 0]))
            let rotatedQ1 = rotation * SIMD4(q1, 1)
            var transform = rotation
            transform.columns.3 = SIMD4(p1.x - rotatedQ1.x, p1.y - rotatedQ1.y, p1.z - rotatedQ1.z, 1)
            draw(layout: parent.layout, transform: transform)
            parent.alignmentState = "Aligned · tap Align again to reset"
            points.removeAll()
        }

        func draw(layout: Layout, transform: simd_float4x4) {
            guard let view else { return }
            view.scene.anchors.removeAll()
            let anchor = AnchorEntity(world: transform)
            for speaker in layout.speakers where speaker.position.count == 3 {
                let p = SIMD3<Float>(Float(speaker.position[0] * 0.3048), Float(speaker.position[1] * 0.3048), Float(speaker.position[2] * 0.3048))
                let marker = ModelEntity(mesh: .generateSphere(radius: 0.09), materials: [SimpleMaterial(color: .orange, roughness: 0.35, isMetallic: false)])
                marker.position = p; anchor.addChild(marker)
                let stem = ModelEntity(mesh: .generateBox(size: [0.025, max(0.05, p.y), 0.025]), materials: [SimpleMaterial(color: .yellow, isMetallic: false)])
                stem.position = SIMD3(p.x, p.y / 2, p.z); anchor.addChild(stem)
                let labelMesh = MeshResource.generateText(speaker.role, extrusionDepth: 0.002, font: .systemFont(ofSize: 0.12), containerFrame: .zero, alignment: .center, lineBreakMode: .byWordWrapping)
                let label = ModelEntity(mesh: labelMesh, materials: [SimpleMaterial(color: .white, isMetallic: false)])
                label.position = p + SIMD3(-0.07, 0.14, 0); anchor.addChild(label)
            }
            if let screen = layout.screen, screen.center.count == 3 {
                let plane = ModelEntity(mesh: .generatePlane(width: Float(screen.width * 0.3048), height: Float(screen.height * 0.3048)),
                    materials: [SimpleMaterial(color: UIColor.systemBlue.withAlphaComponent(0.45), isMetallic: false)])
                plane.position = SIMD3(Float(screen.center[0] * 0.3048), Float(screen.center[1] * 0.3048), Float(screen.center[2] * 0.3048))
                anchor.addChild(plane)
            }
            view.scene.addAnchor(anchor)
        }
    }
}
