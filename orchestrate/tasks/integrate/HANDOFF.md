# Handoff

## What I did

- Added `tools/e2e.py`, a typed library/CLI flow covering health, pairing, demo room, photos/materials, optimize/save, score mutation, listener update, products, scan, rectangle, and 404 handling.
- Added in-process tests with `TestClient`, a deterministic failing fake client for runner behavior, and an opt-in live test controlled by `E2E_BASE_URL`.
- Added `DEMO.md` with the pre-demo checklist, timed script, pending web/products notes, and failure drills.
- The runner creates a tiny JPEG with Pillow, which is already a backend dependency and avoids requiring an image asset or extra package.
- Fixed the retry findings: metric-level warnings are surfaced, optimize requires exactly the six expected roles, and score moves the speaker identified as `L` regardless of list order. Added regression tests for all three.

## Verification

- `python -m ruff check tools/e2e.py backend/tests/e2e` passes.
- `python tools/e2e.py --help` passes.
- `python -m pytest backend/tests/e2e -q --basetemp .pytest-e2e-tmp`: 6 passed, 1 live test deselected.
- Full `python -m pytest -q --basetemp .pytest-full-tmp`: 254 passed, 9 deselected, 1 failed. The unrelated existing `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax` cannot launch Windows Bash (`E_ACCESSDENIED`).

## Unfinished

- None in the task scope. Live e2e remains opt-in and requires `E2E_BASE_URL`.

## Design questions

- none
