# DECISIONS (append-only; newest last)

Format: `- [YYYY-MM-DD HH:MM] decision - why - who (user|orchestrator)`  (add lines with: dispatch.ps1 decide -Text "..."; it stamps the time)
- [2026-10-24 13:23] Setup: gates=all, design=high, project dir=sweetspot, deadline 2026-10-25 11:30 - user chose at BEGIN - user
- [2026-10-24 13:27] Web 3D viewer: built by a teammate once their part is done; orchestration only delivers the API contract + fixture for it - user
- [2026-10-24 13:27] Engine is Python but its architecture/deliverables are undecided; orchestrator proposes a pure-function module contract (score/optimize) in docs/API.md for the engine owner to accept - user
- [2026-10-24 13:27] Storage: JSON files on disk + in-memory session map - simplest, demo room committable - user
- [2026-10-24 13:27] Pairing: QR + 6-char code, pair before scan, desktop shows QR and phone scans - matches PROJECT_CONTEXT s6 - user
