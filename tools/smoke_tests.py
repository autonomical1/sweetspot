"""Fast backend smoke subset used by the orchestrator's per-task check (about 10 s).

The full suite (python -m pytest -q, about 8 minutes) runs the real acoustics engine and is kept for
final verification and for tasks that change engine, refine or product-ranking code:
    python tools/smoke_tests.py --full
"""
from __future__ import annotations

import subprocess
import sys

SMOKE = [
    "backend/tests/test_sessions.py",
    "backend/tests/test_schemas_store.py",
    "backend/tests/test_units.py",
    "backend/tests/test_wall_groups.py",
    "backend/tests/test_materials_router.py",
    "backend/tests/test_gemini_limits.py",
    "backend/tests/test_materials.py",
    "backend/tests/test_web_build_files.py",
    "backend/tests/test_rooms.py",
    "backend/tests/test_preset_2_1.py",
    "backend/tests/test_adapters.py",
    "backend/tests/products/test_expand_cooldown.py",
    "backend/tests/contract/test_validate_dto.py",
    "backend/tests/contract/test_checks.py",
]


def main() -> int:
    if "--full" in sys.argv:
        command = [sys.executable, "-m", "pytest", "-q"]
    else:
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *SMOKE]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
