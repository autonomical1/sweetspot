//import Foundation
//
//enum AppConfig {
//    // Replace with the deployed HTTPS origin. Debug-only local development may use a LAN URL
//    // together with an NSAppTransportSecurity local networking exception in the Xcode target.
//    static let baseURL = URL(string: "https://sweetspotav.tech")!
//}
//
//enum BackendError: LocalizedError {
//    case invalidResponse, http(Int, String), invalidQR
//    var errorDescription: String? {
//        switch self {
//        case .invalidResponse: return "The server returned an invalid response."
//        case .http(let status, let detail): return "Server error (\(status)): \(detail)"
//        case .invalidQR: return "That QR code is not a Sweetspot pairing link."
//        }
//    }
//}
//
//struct BackendClient {
//    let baseURL: URL
//    init(baseURL: URL = AppConfig.baseURL) { self.baseURL = baseURL }
//
//    func request<T: Decodable>(_ path: String, method: String = "GET", body: Data? = nil,
//                               timeout: TimeInterval = 30) async throws -> T {
//        var request = URLRequest(url: baseURL.appendingPathComponent(path))
//        request.httpMethod = method; request.timeoutInterval = timeout
//        request.httpBody = body
//        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
//        let (data, response) = try await URLSession.shared.data(for: request)
//        guard let http = response as? HTTPURLResponse else { throw BackendError.invalidResponse }
//        guard (200..<300).contains(http.statusCode) else {
//            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
//            throw BackendError.http(http.statusCode, detail ?? String(data: data, encoding: .utf8) ?? "Request failed")
//        }
//        return try JSONDecoder().decode(T.self, from: data)
//    }
//
//    private func json(_ object: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: object) }
//    func upload(dto: Data, sessionID: String?) async throws -> RoomResponse {
//        var envelope: [String: Any] = ["captured_room": try JSONSerialization.jsonObject(with: dto)]
//        if let sessionID { envelope["session_id"] = sessionID }
//        return try await request("rooms", method: "POST", body: json(envelope), timeout: 120)
//    }
//    func demo(sessionID: String?) async throws -> RoomResponse {
//        var body: [String: Any] = [:]; if let sessionID { body["session_id"] = sessionID }
//        return try await request("rooms/demo", method: "POST", body: json(body))
//    }
//    func rectangle(width: Double, length: Double, height: Double, sessionID: String?) async throws -> RoomResponse {
//        var body: [String: Any] = ["width": width, "length": length, "height": height]
//        if let sessionID { body["session_id"] = sessionID }
//        return try await request("rooms/rect", method: "POST", body: json(body))
//    }
//    func targets(roomID: String) async throws -> [PhotoTarget] {
//        try await request("rooms/\(roomID)/photo-targets")
//    }
//    func uploadPhoto(roomID: String, surfaceID: String, jpeg: Data) async throws {
//        let boundary = UUID().uuidString
//        var request = URLRequest(url: baseURL.appendingPathComponent("rooms/\(roomID)/photos"))
//        request.httpMethod = "POST"; request.timeoutInterval = 30
//        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
//        var body = Data()
//        func append(_ value: String) { body.append(Data(value.utf8)) }
//        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"surface_id\"\r\n\r\n\(surfaceID)\r\n")
//        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n")
//        body.append(jpeg); append("\r\n--\(boundary)--\r\n"); request.httpBody = body
//        let (_, response) = try await URLSession.shared.data(for: request)
//        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw BackendError.invalidResponse }
//    }
//    func classify(roomID: String) async throws -> MaterialsResponse {
//        try await request("rooms/\(roomID)/materials", method: "POST", body: json([:]), timeout: 120)
//    }
//    func optimize(roomID: String) async throws -> LayoutResponse {
//        try await request("rooms/\(roomID)/optimize", method: "POST", body: json([:]), timeout: 120)
//    }
//    func layout(roomID: String) async throws -> LayoutResponse { try await request("rooms/\(roomID)/layout") }
//}
//
//func sessionID(from qrText: String) throws -> String {
//    guard let url = URL(string: qrText), url.scheme == "https", url.pathComponents.count >= 2,
//          url.pathComponents.contains("pair") else { throw BackendError.invalidQR }
//    return url.lastPathComponent
//}
import Foundation
import os

enum AppConfig {
    // Replace this with the actual Vultr HTTPS origin when it is ready.
    static let baseURL = URL(string: "https://sweetspotav.tech")!
}

enum BackendError: LocalizedError {
    case invalidResponse
    case http(Int, String)
    case busy(String, Int)
    case invalidQR
    case expiredPairing

    var errorDescription: String? {
        switch self {
        case .invalidResponse, .http(_, _), .busy(_, _):
            return "Something went wrong. Please try again."
        case .invalidQR:
            return "That QR code is not a Sweetspot pairing link."
        case .expiredPairing:
            return "This pairing code has expired. Scan a new QR code."
        }
    }
}

private struct BackendErrorBody: Decodable {
    let detail: String?
    let retry_after_s: Int?
}

struct BackendClient {
    let baseURL: URL

    init(baseURL: URL = AppConfig.baseURL) {
        self.baseURL = baseURL
    }

    func userMessage(for error: Error) -> String {
        let logger = Logger(subsystem: "com.sweetspot.phone", category: "backend")
        switch error {
        case let backendError as BackendError:
            switch backendError {
            case .http(let status, let detail):
                logger.error("Backend request failed: status=\(status, privacy: .private), detail=\(detail, privacy: .private)")
                switch status {
                case 404: return "That room isn't available any more. Start a new scan."
                case 410: return "This pairing code has expired. Scan a new QR code."
                case 413: return "That photo is too large."
                case 400, 422: return "That didn't look right. Please try again."
                case 429: return "We're busy right now. Trying again shortly."
                case 500...599: return "Something went wrong. Please try again."
                default: return "Something went wrong. Please try again."
                }
            case .busy(let detail, let seconds):
                logger.error("Backend busy: retry_after_s=\(seconds, privacy: .private), detail=\(detail, privacy: .private)")
                return "We're busy right now. Trying again shortly."
            case .expiredPairing:
                logger.error("Pairing code expired")
                return "This pairing code has expired. Scan a new QR code."
            case .invalidQR:
                logger.error("Invalid pairing QR code")
                return "That QR code isn't a Sweetspot pairing code."
            case .invalidResponse:
                logger.error("Invalid backend response")
                return "Something went wrong. Please try again."
            }
        case let urlError as URLError:
            logger.error("Network request failed: code=\(urlError.code.rawValue, privacy: .private), error=\(urlError, privacy: .private)")
            switch urlError.code {
            case .notConnectedToInternet, .networkConnectionLost, .cannotConnectToHost,
                 .cannotFindHost, .dnsLookupFailed, .timedOut:
                return "Can't reach Sweetspot. Check your connection and try again."
            default:
                return "Something went wrong. Please try again."
            }
        default:
            logger.error("Backend request failed: error=\(String(describing: error), privacy: .private)")
            return "Something went wrong. Please try again."
        }
    }

    func request<T: Decodable>(
        _ path: String,
        method: String = "GET",
        body: Data? = nil,
        timeout: TimeInterval = 30,
        query: [URLQueryItem] = []
    ) async throws -> T {
        var components = URLComponents(
            url: baseURL.appendingPathComponent(path),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = query.isEmpty ? nil : query
        guard let url = components?.url else { throw BackendError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = timeout
        request.httpBody = body

        if body != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw BackendError.invalidResponse
        }

        guard (200..<300).contains(http.statusCode) else {
            let body = try? JSONDecoder().decode(BackendErrorBody.self, from: data)
            let detail = body?.detail
                ?? String(data: data, encoding: .utf8)
                ?? "Request failed"
            if http.statusCode == 429 {
                throw BackendError.busy(detail, max(1, body?.retry_after_s ?? 10))
            }
            throw BackendError.http(http.statusCode, detail)
        }

        return try JSONDecoder().decode(T.self, from: data)
    }

    private func json(_ object: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: object)
    }

    func upload(dto: Data, sessionID: String?, budget: Double? = nil) async throws -> RoomResponse {
        var envelope: [String: Any] = [
            "captured_room": try JSONSerialization.jsonObject(with: dto)
        ]

        if let sessionID {
            envelope["session_id"] = sessionID
        }
        if let budget { envelope["budget"] = budget }

        return try await request(
            "rooms",
            method: "POST",
            body: json(envelope),
            timeout: 120
        )
    }

    func demo(sessionID: String?) async throws -> RoomResponse {
        var body: [String: Any] = [:]
        if let sessionID { body["session_id"] = sessionID }

        // Short timeout so an offline backend quickly falls back to the local preview.
        return try await request(
            "rooms/demo",
            method: "POST",
            body: json(body),
            timeout: 8
        )
    }

    /// Tells the backend this phone scanned the session's QR, so the web page can show it as linked.
    func link(sessionID: String) async throws {
        let _: LinkResponse = try await request(
            "sessions/\(sessionID)/link",
            method: "POST",
            timeout: 8
        )
    }

    func rectangle(
        width: Double,
        length: Double,
        height: Double,
        sessionID: String?,
        budget: Double? = nil
    ) async throws -> RoomResponse {
        var body: [String: Any] = [
            "width": width,
            "length": length,
            "height": height
        ]

        if let sessionID {
            body["session_id"] = sessionID
        }
        if let budget { body["budget"] = budget }

        return try await request(
            "rooms/rect",
            method: "POST",
            body: json(body),
            timeout: 8
        )
    }

    func targets(roomID: String) async throws -> [PhotoTarget] {
        try await request("rooms/\(roomID)/photo-targets")
    }

    func uploadPhoto(roomID: String, surfaceID: String, jpeg: Data) async throws {
        let boundary = UUID().uuidString
        var request = URLRequest(
            url: baseURL.appendingPathComponent("rooms/\(roomID)/photos")
        )

        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue(
            "multipart/form-data; boundary=\(boundary)",
            forHTTPHeaderField: "Content-Type"
        )

        var body = Data()

        func append(_ value: String) {
            body.append(Data(value.utf8))
        }

        append(
            "--\(boundary)\r\n" +
            "Content-Disposition: form-data; name=\"surface_id\"\r\n\r\n" +
            "\(surfaceID)\r\n"
        )
        append(
            "--\(boundary)\r\n" +
            "Content-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\n" +
            "Content-Type: image/jpeg\r\n\r\n"
        )

        body.append(jpeg)
        append("\r\n--\(boundary)--\r\n")
        request.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw BackendError.invalidResponse
        }
        guard http.statusCode == 200 else {
            let body = try? JSONDecoder().decode(BackendErrorBody.self, from: data)
            let detail = body?.detail ?? String(data: data, encoding: .utf8) ?? "Request failed"
            if http.statusCode == 429 {
                throw BackendError.busy(detail, max(1, body?.retry_after_s ?? 10))
            }
            throw BackendError.http(http.statusCode, detail)
        }
    }

    func classify(roomID: String) async throws -> MaterialsResponse {
        try await request(
            "rooms/\(roomID)/materials",
            method: "POST",
            body: json([:]),
            timeout: 120
        )
    }

    func materialsStatus(roomID: String) async throws -> MaterialsStatus {
        try await request("rooms/\(roomID)/materials/status")
    }

    func optimize(roomID: String, preset: String) async throws -> LayoutResponse {
        try await request(
            "rooms/\(roomID)/optimize",
            method: "POST",
            body: json(["options": ["preset": preset]]),
            timeout: 120
        )
    }

    func layout(roomID: String) async throws -> LayoutResponse {
        try await request("rooms/\(roomID)/layout")
    }

    func products(roomID: String, budget: Double) async throws -> ProductsResponse {
        try await request(
            "rooms/\(roomID)/products",
            timeout: 90,
            query: [URLQueryItem(name: "budget", value: String(Int(budget)))]
        )
    }
}

func sessionID(from qrText: String) throws -> String {
    guard
        let url = URL(string: qrText),
        url.scheme == "https",
        url.host != nil,
        url.pathComponents.count == 3,
        url.pathComponents[1] == "pair",
        url.pathComponents[2].hasPrefix("s_")
    else {
        throw BackendError.invalidQR
    }

    return url.lastPathComponent
}
