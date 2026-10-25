import SwiftUI
import VisionKit
import PhotosUI
import UIKit

struct PairQRScanner: UIViewControllerRepresentable {
    let onCode: (String) -> Void
    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])], qualityLevel: .balanced,
            recognizesMultipleItems: false, isHighFrameRateTrackingEnabled: false, isPinchToZoomEnabled: false,
            isGuidanceEnabled: true, isHighlightingEnabled: true)
        context.coordinator.scanner = scanner; scanner.delegate = context.coordinator
        try? scanner.startScanning(); return scanner
    }
    func updateUIViewController(_ uiViewController: DataScannerViewController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(onCode: onCode) }
    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let onCode: (String) -> Void
        weak var scanner: DataScannerViewController?
        init(onCode: @escaping (String) -> Void) { self.onCode = onCode }
        func dataScanner(_ dataScanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            guard let item = addedItems.first, case .barcode(let barcode) = item, let value = barcode.payloadStringValue else { return }
            dataScanner.stopScanning(); onCode(value)
        }
    }
}

struct CameraCapture: UIViewControllerRepresentable {
    let onImage: (UIImage?) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(onImage: onImage) }
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController(); picker.sourceType = .camera; picker.delegate = context.coordinator
        picker.cameraCaptureMode = .photo; return picker
    }
    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}
    final class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let onImage: (UIImage?) -> Void
        init(onImage: @escaping (UIImage?) -> Void) { self.onImage = onImage }
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            onImage(info[.originalImage] as? UIImage); picker.dismiss(animated: true)
        }
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { onImage(nil); picker.dismiss(animated: true) }
    }
}

extension UIImage {
    func sweetspotJPEG() -> Data? {
        let longest = max(size.width, size.height)
        guard longest > 0 else { return jpegData(compressionQuality: 0.7) }
        let scale = min(1, 1024 / longest)
        let target = CGSize(width: size.width * scale, height: size.height * scale)
        let renderer = UIGraphicsImageRenderer(size: target)
        return renderer.jpegData(withCompressionQuality: 0.7) { _ in draw(in: CGRect(origin: .zero, size: target)) }
    }
}
