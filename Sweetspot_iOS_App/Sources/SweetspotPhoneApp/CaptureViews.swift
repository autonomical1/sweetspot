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

struct ProductsView: View {
    @ObservedObject var flow: Flow
    @State private var selectedItem: ProductItem?
    @State private var showWarnings = false

    private let roles = ["C", "L", "R", "LFE", "Ls", "Rs", "screen", "projector"]

    private var orderedItems: [ProductItem] {
        flow.productItems.sorted {
            (roles.firstIndex(of: $0.role) ?? roles.count) <
            (roles.firstIndex(of: $1.role) ?? roles.count)
        }
    }

    var body: some View {
        Group {
            if flow.productsLoading && !flow.productsLoaded {
                VStack(spacing: 12) {
                    ProgressView()
                    Text("Finding products...")
                }
            } else if let error = flow.productsError {
                message(error)
            } else if flow.productsLoaded && flow.productItems.isEmpty {
                message("No products fit this budget. Try another budget and retry.")
            } else if flow.productsLoaded {
                List {
                    Section {
                        let total = chosenTotal(items: flow.productItems)
                        HStack {
                            Text("Total")
                            Spacer()
                            Text(total, format: .currency(code: "USD"))
                                .foregroundStyle(total <= flow.budget ? .green : .red)
                        }
                        Text("Budget: \(flow.budget, format: .currency(code: "USD"))")
                            .foregroundStyle(.secondary)
                    }
                    if !flow.productWarnings.isEmpty {
                        Section {
                            DisclosureGroup("Warnings (\(flow.productWarnings.count))", isExpanded: $showWarnings) {
                                ForEach(flow.productWarnings, id: \.self) { warning in
                                    Text(warning).font(.footnote)
                                }
                            }
                        }
                    }
                    Section("Recommended setup") {
                        ForEach(orderedItems) { item in
                            productRow(item)
                        }
                    }
                }
            } else {
                ProgressView("Finding products...")
            }
        }
        .navigationTitle("Shop")
        .sheet(item: $selectedItem) { item in
            if let current = flow.productItems.first(where: { $0.role == item.role }) {
                alternativesView(for: current)
            }
        }
        .task(id: flow.productsGeneration) { await flow.loadProducts() }
    }

    private func message(_ text: String) -> some View {
        VStack(spacing: 14) {
            Text(text).multilineTextAlignment(.center)
            Button("Retry") { Task { await flow.loadProducts(force: true) } }
                .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    private func productRow(_ item: ProductItem) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Button {
                if !(item.alternatives ?? []).isEmpty { selectedItem = item }
            } label: {
                VStack(alignment: .leading, spacing: 5) {
                    HStack(alignment: .top) {
                        Text(item.role)
                            .font(.caption.bold())
                            .padding(5)
                            .background(.blue.opacity(0.15), in: Capsule())
                        Text(item.title).lineLimit(2)
                        Spacer(minLength: 4)
                        if let pairedRole = item.pair_with, item.price == 0 {
                            Text("Included in pair with \(pairedRole)")
                                .font(.caption)
                                .multilineTextAlignment(.trailing)
                        } else {
                            Text(item.price, format: .currency(code: "USD"))
                        }
                    }
                    if let seller = item.seller { Text(seller).font(.caption).foregroundStyle(.secondary) }
                    if let dimensions = item.dimensions {
                        Text(inchesDescription(dimensions)).font(.caption).foregroundStyle(.secondary)
                    }
                    if !(item.alternatives ?? []).isEmpty {
                        Text("View swap options").font(.caption).foregroundStyle(.blue)
                    }
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            if let url = httpsURL(item.link) {
                Link("Open product", destination: url).font(.caption)
            }
        }
    }

    private func alternativesView(for item: ProductItem) -> some View {
        NavigationStack {
            List(item.alternatives ?? []) { alternative in
                let localPriceChange = alternative.price - item.price
                let allowed = chosenTotal(items: flow.productItems) + localPriceChange <= flow.budget
                Button {
                    flow.choose(alternative, for: item.role)
                    selectedItem = nil
                } label: {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(alternative.title).lineLimit(2)
                        if let seller = alternative.seller {
                            Text(seller).font(.caption).foregroundStyle(.secondary)
                        }
                        HStack {
                            Text(alternative.price, format: .currency(code: "USD"))
                            if let delta = alternative.price_delta {
                                Text("\(delta >= 0 ? "+" : "-")\(abs(delta), format: .currency(code: "USD")) vs recommended")
                                    .foregroundStyle(.secondary)
                            }
                        }
                        if let dimensions = alternative.dimensions {
                            Text(inchesDescription(dimensions)).font(.caption).foregroundStyle(.secondary)
                        }
                        if !allowed {
                            Text("Over budget").font(.caption).foregroundStyle(.red)
                        }
                    }
                }
                .disabled(!allowed)
            }
            .navigationTitle("Swap \(item.role)")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { selectedItem = nil }
                }
            }
        }
    }
}

private func httpsURL(_ text: String) -> URL? {
    guard let url = URL(string: text),
          url.scheme?.lowercased() == "https",
          url.host != nil else { return nil }
    return url
}
