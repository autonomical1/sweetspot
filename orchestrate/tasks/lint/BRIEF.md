# lint: make our Python code pass ruff, without changing behaviour

## Goal
`python -m ruff check .` exits 0 at the repo root, and `python -m pytest -q` still passes (249 tests). After this merges, the orchestrator makes `ruff check . && python -m pytest -q` the merge gate, so every later task is lint-gated.

## Read first
`ruff.toml` (repo root, orchestrator-owned, do not edit), `pytest.ini`, then `python -m ruff check . --statistics`. ruff 0.17.2 is pinned in backend/requirements.txt and installed by setup.

## Design decisions this brief encodes (do not change)
- Rules: E F W I B UP, line length 120, target py312. Teammate engine (`speakerplacer/`, `tests/test_speakerplacer.py`) is excluded: never touch it.
- FastAPI `File()/Form()/Query()/Body()/Depends()` defaults are allowed (configured in ruff.toml).
- No `ruff format` over the tree (noisy diffs mid-hackathon). Fix findings with minimal edits.
- Behaviour-preserving only: no API, schema, logic or test-assertion changes. If a fix would change behaviour, use a narrow `# noqa: <CODE>` with a short reason instead and list it in HANDOFF.md.

## Current findings (about 150)
E501 line too long (63), E701/E702 several statements on one line (43), B905 `zip()` without `strict=` (16), F403/F405 star import in backend/tests/contract/test_checks.py (12), I001 import order (11), F401 unused imports (3), UP017 (1). Most are in tools/validate_dto.py and backend/tests/contract/*.
- Start with `python -m ruff check . --fix` (safe fixes only; do NOT use `--unsafe-fixes` blindly).
- B905: add `strict=True` only where the two iterables must be the same length by construction AND the tests still pass; otherwise `strict=False` (keeps today's behaviour). When in doubt, `strict=False`.
- F403/F405: replace `from .checks import *` with explicit imports.
- E501/E701/E702: split lines or statements; keep the meaning identical.

## Deliverables
1. Lint fixes in the owned files only (see OWNS.txt).
2. HANDOFF.md: counts before/after, every `noqa` added with its reason, anything you could not fix.

## Done when
`python -m ruff check .` exits 0, `python -m pytest -q` passes, `git diff` touches only owned files and contains no behaviour changes.

## Out of scope
ruff.toml, requirements, config, speakerplacer, new tests, refactors, `ruff format`. New files another task is adding in parallel (tools/e2e.py, backend/tests/e2e/) are not yours. Put unsettled choices under `## Design questions` in HANDOFF.md.
