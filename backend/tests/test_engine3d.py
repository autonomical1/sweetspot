"""Fast contract checks for the headless 3D engine adapter."""

import json
import math
import sys
from pathlib import Path

import pytest

from backend.app import engine3d

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def room():
    value = json.loads((ROOT / "fixtures/room_rect.json").read_text(encoding="utf-8"))
    return value


def recorded_room(room):
    # The recordings use engine floor x=0..15, y=0..12. See HANDOFF.md.
    room["dimensions"] = {"width": 15.0, "length": 12.0, "height": 9.0}
    room["listener"] = {"position": [7.5, 3.6, 8.0], "facing": [0, -1]}
    return room


@pytest.mark.parametrize("preset", ["5.1", "7.1.4"])
def test_build_command(room, preset, tmp_path):
    room["surfaces"][0]["material"] = "brick"
    room["surfaces"][1]["material"] = "carpet"
    room["surfaces"][2]["material"] = "brick"
    room["surfaces"][4]["material"] = "hardwood"
    command = engine3d.build_command(room, room["listener"], preset=preset,
                                     output_dir=tmp_path, layout_path=tmp_path / "scene.json")
    def arg(flag):
        return command[command.index(flag) + 1]
    assert command[:3] == [sys.executable, "-m", "speakerplacer"]
    assert arg("--length") == "12.0"
    assert arg("--width") == "15.0"
    assert arg("--height") == "9.0"
    assert command[command.index("--listener") + 1:command.index("--listener") + 3] == ["7.5", "11.0"]
    assert arg("--facing") == "north"
    assert arg("--layout") == preset
    assert arg("--materials") == "walls=concrete,floor=tile,ceiling=drywall"
    room["surfaces"][4]["material"] = "carpet"
    carpet_command = engine3d.build_command(room, room["listener"], preset=preset,
                                            output_dir=tmp_path, layout_path=tmp_path / "scene.json")
    assert carpet_command[carpet_command.index("--materials") + 1] == (
        "walls=concrete,floor=carpet,ceiling=drywall")
    for flag in ("--fast", "--no-show", "--no-view3d", "--save-layout", "--output"):
        assert flag in command
    with pytest.raises(ValueError, match="unsupported 3D preset"):
        engine3d.build_command(room, room["listener"], preset="9.9",
                               output_dir=tmp_path, layout_path=tmp_path / "scene.json")


@pytest.mark.parametrize("fixture,roles", [
    ("layout_5.1.json", {"L", "C", "R", "LFE", "Ls", "Rs"}),
    ("layout_7.1.4.json", {"L", "C", "R", "LFE", "Lss", "Rss", "Lrs", "Rrs",
                           "Ltf", "Rtf", "Ltr", "Rtr"}),
])
def test_to_layout_recorded(room, fixture, roles):
    room = recorded_room(room)
    scene = json.loads((ROOT / "fixtures/engine" / fixture).read_text(encoding="utf-8"))
    result = engine3d.to_layout(scene, room)
    layout = result["layout"]
    speakers = {speaker["role"]: speaker for speaker in layout["speakers"]}
    assert set(speakers) == roles
    for speaker in speakers.values():
        x, y, z = speaker["position"]
        assert 0 <= x <= 15 and 0 <= y <= 9 and 0 <= z <= 12
        assert all(value > 0 for value in speaker["size"].values())
        assert speaker["model_id"]
        assert speaker["mount"] in {"on_wall", "in_wall", "on_ceiling", "floor", "stand"}
        assert speaker["distance_ft"] > 0
        assert speaker["compliance"]["status"]
    assert speakers["C"]["position"][0] == pytest.approx(7.57, abs=0.1)
    assert speakers["C"]["position"][2] == pytest.approx(0)
    assert all(speakers[role]["position"][2] == pytest.approx(0) for role in ("L", "C", "R"))
    assert speakers["Ls" if "Ls" in speakers else "Lss"]["position"][0] == pytest.approx(0)
    if "Ltf" in speakers:
        assert all(speakers[role]["position"][1] == pytest.approx(9)
                   for role in ("Ltf", "Rtf", "Ltr", "Rtr"))
    listener = [7.5, 3.6, 8.0]
    for role in ("L", "C", "R"):
        speaker = speakers[role]
        assert math.dist(speaker["aim"], listener) < math.dist(speaker["position"], listener)
    assert layout["screen"]["wall_id"] == "wall_n"
    assert layout["screen"]["width"] > 6
    assert layout["projector"]["position"]
    assert layout["seats"][0]["ear_height"] == pytest.approx(3.6)
    assert layout["preset"] in ("5.1", "7.1.4")
    assert result["engine"]["rt60"]
    scene["schema_version"] = 3
    with pytest.raises(ValueError, match="schema_version"):
        engine3d.to_layout(scene, room)
    scene["schema_version"] = 2
    room["dimensions"]["width"] = 12
    with pytest.raises(ValueError, match="dimensions"):
        engine3d.to_layout(scene, room)


def test_run_scene_and_cleanup(room, tmp_path, monkeypatch):
    source = ROOT / "fixtures/engine/layout_5.1.json"
    script = "import shutil,sys; shutil.copyfile(sys.argv[1],sys.argv[2])"
    def command(*args, **kwargs):
        return [sys.executable, "-c", script, str(source), str(kwargs["layout_path"])]
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(engine3d, "build_command", command)
    scene = engine3d.run_scene(room, room["listener"], preset="5.1", standard="dolby")
    assert scene["schema_version"] == 2
    assert list((tmp_path / "tmp").iterdir()) == []


def test_run_scene_timeout_kills_child(room, tmp_path, monkeypatch):
    pid_file = tmp_path / "pid.txt"
    script = "import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(engine3d, "build_command",
                        lambda *args, **kwargs: [sys.executable, "-c", script, str(pid_file)])
    with pytest.raises(engine3d.EngineError, match="timed out"):
        engine3d.run_scene(room, room["listener"], preset="5.1", standard="dolby", timeout_s=1)
    assert pid_file.exists()
    assert list((tmp_path / "tmp").iterdir()) == []


def test_run_scene_error_tail(room, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(engine3d, "build_command",
                        lambda *args, **kwargs: [sys.executable, "-c",
                                                  "import sys; sys.stderr.write('engine failed\\n'); sys.exit(3)"])
    with pytest.raises(engine3d.EngineError, match="exit code 3") as error:
        engine3d.run_scene(room, room["listener"], preset="5.1", standard="dolby")
    assert "engine failed" in str(error.value)
    assert list((tmp_path / "tmp").iterdir()) == []
