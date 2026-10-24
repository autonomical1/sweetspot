# DECISIONS (append-only; newest last)

Format: `- [YYYY-MM-DD HH:MM] decision - why - who (user|orchestrator)`  (add lines with: dispatch.ps1 decide -Text "..."; it stamps the time)
- [2026-10-24 13:23] Setup: gates=all, design=high, project dir=sweetspot, deadline 2026-10-25 11:30 - user chose at BEGIN - user
- [2026-10-24 13:27] Web 3D viewer: built by a teammate once their part is done; orchestration only delivers the API contract + fixture for it - user
- [2026-10-24 13:27] Engine is Python but its architecture/deliverables are undecided; orchestrator proposes a pure-function module contract (score/optimize) in docs/API.md for the engine owner to accept - user
- [2026-10-24 13:27] Storage: JSON files on disk + in-memory session map - simplest, demo room committable - user
- [2026-10-24 13:27] Pairing: QR + 6-char code, pair before scan, desktop shows QR and phone scans - matches PROJECT_CONTEXT s6 - user
- [2026-10-24 13:46] Priority layering: rectangular-room baseline (length/width/listener/facing) is MVP; RoomPlan scan is a high-priority layer on top via same contract - user
- [2026-10-24 13:46] Engine contract: Python package speakerplacer with optimize(room)/score(room,layout) over shared room JSON, rectangular room is the simplest valid input - user approved
- [2026-10-24 13:46] Gemini access method open: direct API vs backend-hosted gemini CLI on user's personal Pro account; keys: SerpApi in hand, Vultr account exists, domain easy - user
- [2026-10-24 13:52] Products: SerpApi Google Shopping JSON, module products.get_products(layout,budget) in repo root products/, adapter in backend with stub fallback - user said module lives on backend, signature undecided so orchestrator proposed - orchestrator
- [2026-10-24 13:52] Assumed (user did not object): REST only no WebSocket; Gemini via API behind classify_materials interface - orchestrator
- [2026-10-24 14:02] iOS->backend scan payload is an explicit DTO sweetspot.roomplan.v1 (not default Codable CapturedRoom) since Apple does not document simd/enum encoding; added GET photo-targets and optional listener to POST /rooms; scanned rooms keep RoomPlan world frame - orchestrator, pending user OK at Gate 2
