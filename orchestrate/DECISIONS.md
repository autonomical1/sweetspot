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
- [2026-10-24 14:17] No WebSocket anywhere, GET/POST/PATCH only; web polls sessions - user
- [2026-10-24 14:17] Contract units are decimal feet (ft-in display only at UI edge); iOS DTO stays raw meters; converts at backend roomplan.py (m->ft) and iOS AR layer (ft->m) - user asked feet/inches, mechanics chosen by orchestrator to keep phone code simple
- [2026-10-24 14:17] Testing: every component standalone-ready (own tests + stubs) before pairwise integration; docs/TESTING.md is the plan; added contracts task - user
- [2026-10-24 14:31] Gate 2 approved. Models: gpt-6-sol or gpt-5.6-luna by default, gpt-6-astra only for hardest (roomplan converter); no gpt-6.1-sol - user
- [2026-10-24 14:31] Scaffold (store.py, conftest, pytest.ini, init files) committed after 4 passing tests; photo-targets generic in core-api, scan conversion hook via guarded import of roomplan.convert_dto - orchestrator
- [2026-10-24 14:35] Gate 3 approved; core-api dispatched with gpt-6-sol medium - user
- [2026-10-24 14:43] core-api check PASS, review ISSUES (5 findings); proposing one retry with findings appended to brief, awaiting user OK at Gate 4 - orchestrator
- [2026-10-24 14:45] core-api retry 1: facing normalized to unit vector (not rejected); demo fixture uses typical hardwood/glass absorption (provisional until materials table); engine result validated else stub fallback; optional-router imports via find_spec; user approved inspect then retry
- [2026-10-24 14:50] core-api retry 1: check PASS, review ISSUES again with 2 minor edge-case findings (listener y default vs height<3.6ft; products stub rounding vs tiny budget); interrupting user per protocol - orchestrator
- [2026-10-24 14:59] core-api: orchestrator patched 2 minor review findings (listener y clamp, products stub floor rounding) with regression tests, check PASS (19 tests); merging with explicit override of ISSUES verdict - user chose option 1
