"""Opt-in end-to-end exercise of the costly 3D engine."""

import json
import time
from pathlib import Path

import pytest

from backend.app.engine3d import run_scene, to_layout


@pytest.mark.slow
@pytest.mark.live  # pytest.ini excludes live by default; slow alone is not excluded.
def test_real_5_1_run(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[2]
    room = json.loads((root / "fixtures/room_rect.json").read_text(encoding="utf-8"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    started = time.monotonic()
    scene = run_scene(room, room["listener"], preset="5.1", standard="dolby")
    assert time.monotonic() - started < 150
    layout = to_layout(scene, room)["layout"]
    assert {speaker["role"] for speaker in layout["speakers"]} == {"L", "R", "C", "LFE", "Ls", "Rs"}
