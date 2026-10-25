import SwiftUI
import UIKit

/// Home screen entries: the Recent scans list and a shortcut to upload the newest scan.
struct RecentScansLinks: View {
    @ObservedObject var flow: Flow
    @ObservedObject var history: ScanHistory

    var body: some View {
        let title = history.scans.isEmpty
            ? "Recent scans"
            : "Recent scans (\(history.scans.count))"

        NavigationLink {
            ScanHistoryList(flow: flow, history: history)
        } label: {
            Label(title, systemImage: "clock.arrow.circlepath")
        }

        Button("Upload latest scan") {
            Task { await flow.uploadSavedScan() }
        }
        .disabled(history.scans.isEmpty || flow.isWorking)
    }
}

struct ScanHistoryList: View {
    @ObservedObject var flow: Flow
    @ObservedObject var history: ScanHistory

    var body: some View {
        List {
            ForEach(history.scans) { scan in
                NavigationLink {
                    SavedScanDetail(flow: flow, history: history, scanID: scan.id)
                } label: {
                    SavedScanRow(scan: scan)
                }
            }
            .onDelete { offsets in
                let ids = offsets.map { history.scans[$0].id }
                ids.forEach { history.delete(scanID: $0) }
            }
        }
        .overlay {
            if history.scans.isEmpty {
                ContentUnavailableView(
                    "No scans yet",
                    systemImage: "cube.transparent",
                    description: Text("Finish a room scan and it is saved here automatically.")
                )
            }
        }
        .navigationTitle("Recent scans")
    }
}

struct SavedScanRow: View {
    let scan: SavedScan

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(scan.displayName)
                .font(.headline)

            if scan.name != nil {
                Text(scan.createdAt.formatted(date: .abbreviated, time: .shortened))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            if let summary = scan.summary {
                Text(summary.text)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            if let upload = scan.latestUpload {
                Label("Room \(upload.roomID)", systemImage: "checkmark.icloud")
                    .font(.caption)
                    .foregroundStyle(.green)
            } else {
                Label("Not uploaded", systemImage: "icloud.slash")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

struct SavedScanDetail: View {
    @ObservedObject var flow: Flow
    @ObservedObject var history: ScanHistory
    let scanID: UUID

    @State private var name = ""
    @State private var confirmingDelete = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        if let scan = history.scan(id: scanID) {
            Form {
                Section("Name") {
                    TextField("e.g. Living room", text: $name)
                        .submitLabel(.done)
                        .onSubmit { history.rename(scanID: scanID, to: name) }
                }

                Section("Scan") {
                    LabeledContent(
                        "Captured",
                        value: scan.createdAt.formatted(date: .abbreviated, time: .shortened)
                    )

                    if !history.fileExists(for: scan) {
                        Text("The scan file is missing on this iPhone, so it can't be uploaded or shared.")
                            .foregroundStyle(.red)
                    }
                }

                Section("Backend") {
                    if let upload = scan.latestUpload {
                        idRow("Room ID", upload.roomID)

                        if let sessionID = upload.sessionID {
                            idRow("Session ID", sessionID)
                        } else {
                            LabeledContent("Session ID", value: "Not paired")
                        }

                        LabeledContent(
                            "Uploaded",
                            value: upload.uploadedAt.formatted(date: .abbreviated, time: .shortened)
                        )

                        if let size = upload.size {
                            LabeledContent("Room size", value: sizeText(size))
                        }
                    } else {
                        Text("Not uploaded yet.")
                            .foregroundStyle(.secondary)
                    }
                }

                if scan.uploads.count > 1 {
                    Section("Earlier uploads") {
                        ForEach(Array(scan.uploads.dropLast().reversed())) { upload in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(upload.roomID)
                                    .font(.body.monospaced())
                                    .textSelection(.enabled)
                                Text(upload.uploadedAt.formatted(date: .abbreviated, time: .shortened))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                Section {
                    if scan.latestUpload != nil {
                        Button("Open results") {
                            Task { await flow.open(scan) }
                        }
                    }

                    Button(uploadTitle(for: scan)) {
                        history.rename(scanID: scanID, to: name)
                        Task { await flow.upload(scan) }
                    }
                    .disabled(!history.fileExists(for: scan))

                    if flow.isWorking {
                        ProgressView("Contacting Sweetspot backend…")
                    }

                    if history.fileExists(for: scan) {
                        ShareLink(item: history.fileURL(for: scan)) {
                            Label("Share scan JSON", systemImage: "square.and.arrow.up")
                        }
                    }
                } footer: {
                    if scan.latestUpload != nil {
                        Text("Upload again creates a new room from this scan. The earlier room stays on the server.")
                    }
                }
                .disabled(flow.isWorking)

                Section {
                    Button("Delete scan", role: .destructive) {
                        confirmingDelete = true
                    }
                }
            }
            .navigationTitle(scan.displayName)
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { name = scan.name ?? "" }
            .onDisappear { history.rename(scanID: scanID, to: name) }
            .confirmationDialog(
                "Delete this scan?",
                isPresented: $confirmingDelete,
                titleVisibility: .visible
            ) {
                Button("Delete scan", role: .destructive) {
                    history.delete(scanID: scanID)
                    dismiss()
                }
            } message: {
                Text("This removes the scan from this iPhone. Rooms already on the server are not deleted.")
            }
        } else {
            ContentUnavailableView("Scan deleted", systemImage: "trash")
        }
    }

    private func idRow(_ title: String, _ value: String) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.body.monospaced())
                    .textSelection(.enabled)
            }

            Spacer()

            Button {
                UIPasteboard.general.string = value
            } label: {
                Image(systemName: "doc.on.doc")
            }
            .buttonStyle(.borderless)
            .accessibilityLabel("Copy \(title)")
        }
    }

    private func uploadTitle(for scan: SavedScan) -> String {
        scan.latestUpload == nil ? "Upload scan" : "Upload again"
    }

    private func sizeText(_ size: SavedRoomSize) -> String {
        "\(feet(size.width)) × \(feet(size.length)) × \(feet(size.height)) ft"
    }

    private func feet(_ value: Double) -> String {
        value.formatted(.number.precision(.fractionLength(1)))
    }
}

