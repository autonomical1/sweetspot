"""Schema and adapter checks for the recorded 3D scenes."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import engine3d, products
from backend.app.stubs import engine_stub
from backend.tests.contract.checks import assert_valid_layout_result

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name,roles", [
    ("layout_5.1.json", {"L", "R", "C", "LFE", "Ls", "Rs"}),
    ("layout_7.1.4.json", {"L", "R", "C", "LFE", "Lss", "Rss", "Lrs", "Rrs",
                           "Ltf", "Rtf", "Ltr", "Rtr"}),
])
def test_recorded_refined_layout_contract(name, roles):
    room = json.loads((ROOT / "fixtures" / "room_rect.json").read_text(encoding="utf-8"))
    room["dimensions"] = {"width": 15, "length": 12, "height": 9}
    room["listener"] = {"position": [7.5, 3.6, 8], "facing": [0, -1]}
    scene = json.loads((ROOT / "fixtures" / "engine" / name).read_text(encoding="utf-8"))
    mapped = engine3d.to_layout(scene, room)
    assert {speaker["role"] for speaker in mapped["layout"]["speakers"]} == roles
    from backend.app.acoustics import evaluate

    result = {"layout": mapped["layout"], "metrics": evaluate(room, mapped["layout"])}
    assert_valid_layout_result(result, room, full_51=name == "layout_5.1.json")


def test_stub_preset_warning(room_rect):
    result = engine_stub.optimize(room_rect, {"preset": "7.1.4"})
    assert len(result["layout"]["speakers"]) == 6
    assert any("7.1.4" in warning for warning in result["metrics"]["warnings"])


def test_products_get_legacy_roles(monkeypatch):
    captured = []

    def get_products(layout, budget, *, serpapi_key=None):
        captured.extend(item["role"] for item in layout["speakers"])
        return {"budget": budget, "total": 0, "items": []}

    monkeypatch.setenv("PRODUCTS_BACKEND", "auto")
    monkeypatch.setattr(products.importlib, "import_module",
                        lambda name: SimpleNamespace(get_products=get_products))
    layout = {"speakers": [{"role": role} for role in
                           ("L", "R", "C", "LFE", "Lss", "Rss", "Lrs", "Rrs", "Ltf", "Rtf", "LFE2")]}
    products.run_products(layout, 1000)
    assert captured == ["L", "R", "C", "LFE", "Ls", "Rs"]


@pytest.mark.slow
@pytest.mark.live
def test_runner_matches_engine_cli(data_dir, tmp_path):
    room = json.loads((ROOT / "fixtures" / "room_rect.json").read_text(encoding="utf-8"))
    runner = engine3d.run_scene(room, room["listener"], preset="5.1", standard="dolby")
    output = tmp_path / "cli-output"
    target = tmp_path / "cli-layout.json"
    command = engine3d.build_command(room, room["listener"], preset="5.1", standard="dolby",
                                     output_dir=output, layout_path=target)
    subprocess.run(command, cwd=ROOT, env={**os.environ, "MPLBACKEND": "Agg"},
                   timeout=180, check=True, capture_output=True, text=True)
    cli = json.loads(target.read_text(encoding="utf-8"))
    assert runner["schema_version"] == cli["schema_version"] == 2
    positions = lambda scene: {s["channel"]: s["position_ft"] for s in scene["speakers"]}
    assert positions(runner).keys() == positions(cli).keys()
    for role, position in positions(runner).items():
        assert position == pytest.approx(positions(cli)[role], abs=1e-6)


@pytest.mark.slow
@pytest.mark.live
def test_engine_physics_validation(tmp_path):
    command = [engine3d.sys.executable, "-m", "speakerplacer", "--length", "8", "--width", "8",
               "--height", "8", "--listener", "4", "4", "--facing", "north", "--layout", "5.1",
               "--no-show", "--no-view3d", "--fast", "--validate", "--output", str(tmp_path / "validation")]
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, "MPLBACKEND": "Agg"},
                            timeout=180, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-1000:]
