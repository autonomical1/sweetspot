# 02: Backend integration

Authoritative contract: `docs/API.md`. This file lists only what the iPhone app calls. Backend: FastAPI on Vultr behind Caddy, **REST only, no WebSocket**. JSON bodies unless noted, snake_case keys.

## Networking rules
- **HTTPS only**; one constant `Config.baseURL = URL(string: "https://<domain>.tech")!`. Do not add ATS exceptions in the demo build.
- `URLSession` + `async/await`. Timeouts: 30 s normal, 120 s for scan upload, `optimize` and `materials`.
- The scan upload body is built with `JSONSerialization` (see below) so the DTO is not touched by key-conversion. For your own small request structs use `.convertToSnakeCase` / `.convertFromSnakeCase`.
- Errors: HTTP status plus `{"detail": "..."}`. 404 unknown id. `status: "expired"` or 410 on a session means re-pair.
- No auth in the MVP; `room_id` and `session_id` are unguessable random strings. Do not post them in public channels.

## Endpoints used by the app

### Pairing
- The **web page** creates the session (`POST /sessions`) and shows a QR encoding `https://<domain>/pair/<session_id>`.
- "Start room scan" opens the phone's QR scanner before RoomPlan. The app parses the QR URL and keeps the last path component as `session_id` in memory for this scan. A 410 or session error on upload returns to the QR scanner with an expiry message. The backend's `POST /sessions/by-code` endpoint remains available to other clients; the iOS app does not call it.

### Upload the scan
`POST /rooms`
```json
{ "captured_room": { ...the DTO from 01_roomplan_capture.md... },
  "session_id": "s_abc123",
  "budget": 1500.0 }
```
`session_id` and `budget` optional in the API. The iOS room-scan flow sends its QR session, then clears it after a successful upload. Response: backend Room JSON (`docs/API.md` section 1) with `room_id`. **Store `room_id`.** Uploading with `session_id` is what makes the laptop jump to the 3D viewer.

### Photos
1. `GET /rooms/{room_id}/photo-targets` -> `[{"surface_id","kind","label"}, ...]` (about 6 entries; **proposed endpoint, backend is adding it**; until live, hardcode: the 4 largest walls by `dimensions.x * dimensions.y` using their DTO `id`, plus `"floor"` and `"ceiling"`).
2. For each: show the label ("Front wall, behind the TV"), capture, then `POST /rooms/{room_id}/photos` as `multipart/form-data` with fields `surface_id` (text) and `file` (JPEG). Response `{"stored": true}`.
3. Resize before upload: long edge **1024 px**, JPEG quality **0.7** (under about 300 KB).
4. Then `POST /rooms/{room_id}/materials` body `{}` -> `{"surfaces":[{"surface_id","material","confidence"}]}`. Calls Gemini server-side, 5 to 20 s; show a spinner, do not block the AR step on it. Materials: `drywall|glass|brick|carpet|hardwood|tile|curtain|unknown`.

### Layout (for AR)
- `POST /rooms/{room_id}/optimize` body `{}` -> `{"layout","metrics"}` (web page usually triggers it; app may too).
- `GET /rooms/{room_id}/layout` -> latest result, 404 until computed. Poll every 2 s with a cap.
```json
{"layout": {
   "speakers": [{"role":"L","position":[x,y,z],"aim":[x,y,z]}],   // roles L R C LFE Ls Rs
   "screen": {"wall_id":"<uuid>","center":[x,y,z],"width":6.4,"height":3.6}   // feet; may be null
 },
 "metrics": {"score":0.0,"reflections":[],"treatment_patches":[{"surface_id","center":[x,y,z],"size":[w,h]}],"warnings":[]}}
```
**Positions are decimal feet**, y-up (convert x 0.3048 to meters for ARKit). For scanned rooms they are in the scan's world frame (scaled to feet, not recentered).

### Demo and manual rooms
- `POST /rooms/demo` `{"session_id":"s_..."}` (optional) -> Room JSON, no scan. Needs a visible **"Use demo room"** button. Demo coordinates are in the demo room's own frame, so AR uses a manual alignment (`04_ar_overlay.md`).
- `POST /rooms/rect` (all values in feet) `{"width":12,"length":15,"height":9.0,"listener":[7.5,3.6,4],"facing":[0,-1],"session_id":"s_..."}` for a no-LiDAR "enter room size" screen.

## Swift snippets
```swift
func postJSON(_ path: String, _ body: [String: Any], timeout: TimeInterval = 30) async throws -> Data {
    var req = URLRequest(url: Config.baseURL.appendingPathComponent(path))
    req.httpMethod = "POST"; req.timeoutInterval = timeout
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    req.httpBody = try JSONSerialization.data(withJSONObject: body)
    let (data, resp) = try await URLSession.shared.data(for: req)
    guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
        throw URLError(.badServerResponse)
    }
    return data
}
// scan: try await postJSON("rooms", ["captured_room": exportDTO(room), "session_id": sid], timeout: 120)

func uploadPhoto(roomID: String, surfaceID: String, jpeg: Data) async throws {
    let boundary = UUID().uuidString
    var req = URLRequest(url: Config.baseURL.appendingPathComponent("rooms/\(roomID)/photos"))
    req.httpMethod = "POST"
    req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
    var body = Data()
    func add(_ s: String) { body.append(Data(s.utf8)) }
    add("--\(boundary)\r\nContent-Disposition: form-data; name=\"surface_id\"\r\n\r\n\(surfaceID)\r\n")
    add("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n")
    body.append(jpeg); add("\r\n--\(boundary)--\r\n")
    req.httpBody = body
    let (_, resp) = try await URLSession.shared.data(for: req)
    guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
}
```

## Rules the backend relies on
1. Send the DTO exactly as specified; never edit transforms or dimensions.
2. For scanned rooms, backend surface ids are the RoomPlan UUID strings (plus synthetic `"floor"` and `"ceiling"`). Tag photos with those strings.
3. Keep the QR `session_id` for one room scan and clear it after upload.
4. The scan DTO is raw meters (values like 300 or 3000 mean a stray cm/mm conversion); everything the backend returns is feet.

## Developing before the backend is deployed
Run the backend locally (`uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`) and point a **Debug build only** at `http://<mac-lan-ip>:8000` with a temporary ATS exception (`NSAllowsLocalNetworking`); remove it before the demo build. Or mock responses with the files in `sample_payloads/`.
