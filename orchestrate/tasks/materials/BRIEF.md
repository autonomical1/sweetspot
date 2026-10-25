# materials: absorption table, Gemini material classifier, photos + materials endpoints

## Goal
Given surface photos, classify each surface's material (Gemini, behind an interface with a mock) and update the room's materials and octave-band absorption. Must work and be fully tested with no network.

## Read first
docs/API.md sections 5, 6, 7, 8; docs/TESTING.md section 3.5; backend/app/schemas.py, backend/app/store.py, backend/app/rooms.py, backend/app/main.py (all already on master; do NOT edit them; main.py includes `backend/app/materials_router.py` automatically once it exists, via `router`); backend/tests/conftest.py (shared fixtures `data_dir`, `room_rect`); fixtures/room_demo.json (hardwood floor + glass window absorption values to match).

## Design decisions this brief encodes (do not change)
- Gemini via the **API** (`google-genai`), not the CLI. Behind one interface; a deterministic mock exists for tests and demos. Env: `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-3.8-flash`, was gemini-2.5-flash until it was retired; the user may change it, do not hardcode it anywhere else), `MATERIALS_BACKEND` = `gemini` (default) or `mock`.
- One Gemini request per classification call containing all photos (each image preceded by a text part `surface_id: <id>`), JSON-only response, 20 s timeout. Any failure (no key, timeout, SDK error, unparsable output) degrades to `unknown` with confidence 0.0, never an exception or a 500.
- Absorption is keyed by material and is the only place absorption values live for classification results. Drywall defaults must match the rest of the repo.
- A result is applied to the room only if `confidence >= MIN_CONFIDENCE` (0.5, a module constant); otherwise the surface keeps its current material and the response marks `"applied": false`.
- Photos are stored as resized JPEGs (long edge 1024 px, quality 70) via `store.save_photo`; originals are not kept.

## Deliverables
1. `backend/app/materials.py`
   - `MATERIALS = ["drywall","glass","brick","carpet","hardwood","tile","curtain","unknown"]`.
   - `ABSORPTION: dict[str, dict[str, float]]` over bands `"125","250","500","1000","2000","4000"`. Use exactly these approximate typical textbook values and say so in a comment ("approximate typical octave-band absorption coefficients, not from a single cited measurement"):
     - drywall 0.05, 0.06, 0.08, 0.09, 0.09, 0.09
     - hardwood 0.15, 0.11, 0.10, 0.07, 0.06, 0.07
     - glass 0.35, 0.25, 0.18, 0.12, 0.07, 0.04
     - brick 0.03, 0.03, 0.03, 0.04, 0.05, 0.07
     - carpet 0.02, 0.06, 0.14, 0.37, 0.60, 0.65
     - tile 0.01, 0.01, 0.01, 0.01, 0.02, 0.02
     - curtain 0.07, 0.31, 0.49, 0.75, 0.70, 0.60
     - unknown: same as drywall
     (drywall, hardwood and glass must equal what fixtures/room_demo.json uses; add a test that reads that fixture and asserts it.)
   - `PROMPT` constant asking for strict JSON `[{"surface_id": str, "material": <enum>, "confidence": 0..1}]`, listing the enum, one entry per given surface_id.
   - `parse_model_output(text: str, expected_ids: list[str]) -> list[dict]`: tolerant (strips markdown fences and surrounding prose, extracts the first JSON array/object, accepts `{"surfaces":[...]}`); unknown material strings become `unknown`; missing fields become `unknown`/0.0; confidence clamped to [0,1]; ids not in `expected_ids` dropped; every expected id appears exactly once in the output (missing ones become `unknown`, 0.0).
   - `prepare_image(data: bytes) -> bytes`: Pillow, convert to RGB, long edge <= 1024, JPEG q=70; raises `ValueError` on non-images.
   - `classify_materials(photos: list[dict], backend: str | None = None) -> list[dict]` per docs/API.md section 5 (photos are `{"surface_id","image_bytes","mime"}`); `backend=None` reads `MATERIALS_BACKEND`.
   - `MockClassifier`: deterministic by surface id: id containing `floor` gives hardwood (0.9), `window` gives glass (0.9), `ceiling` gives drywall (0.9), everything else drywall (0.8).
   - `GeminiClassifier`: imports `google.genai` lazily inside the call (so tests never need the SDK), builds the request as described, calls the model, passes the text to `parse_model_output`. Make the client injectable (constructor arg or function parameter) so tests use a fake client; tests never touch the network.
2. `backend/app/materials_router.py`: `router = APIRouter()` with
   - `POST /rooms/{room_id}/photos` multipart (`surface_id` form field, `file` upload): 404 unknown room; 422 if `surface_id` is not one of the room's surface ids; 400 if the file is not an image; stores via `store.save_photo(room_id, surface_id, prepare_image(bytes))`; returns `{"stored": true}`.
   - `POST /rooms/{room_id}/materials` body `{}` (ignore the body): loads stored photos (`store.list_photos`), classifies, applies results to room surfaces (set `material` and `absorption = ABSORPTION[material]` copy; `unknown` results never applied), saves the room, returns `{"surfaces": [{"surface_id","material","confidence","applied"}]}`. No stored photos gives 200 `{"surfaces": []}`. Calling twice gives the same room. Only classified surfaces change.
   - Define these route functions with plain `def` (FastAPI runs them in a threadpool) because photo reading and the Gemini call block.
3. Tests (`backend/tests/test_materials.py`, `test_materials_router.py`), no network, no sleeps, Pillow-generated test images:
   - Absorption table complete (all materials x 6 bands, each in (0,1)); drywall/hardwood/glass match fixtures/room_demo.json.
   - `parse_model_output`: valid array; wrapped in prose and fences; `{"surfaces": [...]}`; not JSON; empty; unknown material `marble`; missing fields; confidence 7 and -1; extra/missing ids; duplicate ids.
   - `prepare_image`: a 4000x3000 image becomes long edge 1024; a tiny image is not upscaled; random bytes raise `ValueError`.
   - `GeminiClassifier` with a fake client: success path; client raising; no API key; malformed text each degrade as specified. `MockClassifier` determinism. `classify_materials(backend="mock")` and the env switch.
   - Router (use `create_app()` and `/rooms/rect`): upload ok; unknown room 404; bad surface 422; non-image 400; materials with the mock updates exactly the classified surfaces' material and absorption (floor gets hardwood values), a low-confidence result is not applied, idempotent, no photos gives an empty list, other surfaces untouched, persisted after reload from `store`.

## Done when
`python -m pytest backend -q` passes on this branch; the app imports cleanly with `MATERIALS_BACKEND=mock` and with no `GEMINI_API_KEY`; no edits outside OWNS.txt.

## Out of scope
Real Gemini calls, the CLI route, spec extraction, rationale text, any frontend, deploy. If `google-genai` is not installed in the sandbox, the lazy import keeps the tests passing; say so in HANDOFF.md. Put unsettled choices (model name, prompt wording, threshold) under `## Design questions` in HANDOFF.md.
