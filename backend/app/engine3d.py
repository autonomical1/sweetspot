"""Headless runner and coordinate adapter for speakerplacer's schema 2 scenes."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
from collections import Counter
from pathlib import Path
from typing import Any

from .engine_speakerplacer import _engine_facing

PRESETS = ("2.1", "5.1", "7.1", "5.1.2", "5.1.4", "7.1.2", "7.1.4")
METRES_PER_FOOT = 0.3048
REPO_ROOT = Path(__file__).resolve().parents[2]
MATERIAL_MAP = {
    "drywall": "drywall", "glass": "glass", "brick": "concrete",
    "carpet": "carpet", "hardwood": "tile", "tile": "tile",
    "curtain": "curtain", "unknown": "drywall",
}
MOUNT_MAP = {
    "on_wall": "on_wall", "in_wall": "in_wall", "in_ceiling": "on_ceiling",
    "on_ceiling": "on_ceiling", "floor_standing": "floor", "stand_mounted": "stand",
}


class EngineError(RuntimeError):
    """A headless engine run failed or did not produce a schema 2 scene."""


def _plain(value: Any) -> dict:
    return value.model_dump() if hasattr(value, "model_dump") else value


def _validate_preset(preset: str) -> None:
    if preset not in PRESETS:
        raise ValueError(f"unsupported 3D preset {preset!r}; choose from {', '.join(PRESETS)}")


def _materials(room: dict) -> str:
    surfaces = room.get("surfaces", [])
    names: dict[str, str] = {}
    for kind, key in (("wall", "walls"), ("floor", "floor"), ("ceiling", "ceiling")):
        choices = [MATERIAL_MAP.get(s.get("material"), "drywall") for s in surfaces if s.get("kind") == kind]
        names[key] = Counter(choices).most_common(1)[0][0] if choices else "drywall"
    return ",".join(f"{key}={names[key]}" for key in ("walls", "floor", "ceiling"))


def _engine_xyz(point: list[float], length: float) -> list[float]:
    """Engine (x, north-positive y, up z) -> room (x, up y, south-positive z)."""
    return [float(point[0]), float(point[2]), length - float(point[1])]


def build_command(
    room: dict, listener: dict, *, preset: str = "5.1", standard: str = "dolby",
    seats: str | None = None, output_dir: str | Path, layout_path: str | Path,
    fast: bool = True,
) -> list[str]:
    """Build a headless CLI command without filesystem side effects."""
    _validate_preset(preset)
    room, listener = _plain(room), _plain(listener)
    dims = room["dimensions"]
    position = listener["position"]
    # The existing 2D adapter's u=x, v=length-z mapping determines CLI axes.
    facing, _ = _engine_facing({"listener": listener})
    command = [
        sys.executable, "-m", "speakerplacer",
        "--length", str(dims["width"]), "--width", str(dims["length"]),
        "--height", str(dims["height"]),
        "--listener", str(position[0]), str(float(dims["length"]) - float(position[2])),
        "--ear-height", str(position[1]), "--facing", facing,
        "--layout", "custom" if preset == "2.1" else preset, "--standard", standard,
        "--materials", _materials(room), "--no-show", "--no-view3d",
        "--save-layout", str(layout_path), "--output", str(output_dir),
    ]
    if preset == "2.1":
        command.extend(("--speakers", "front:2", "bass:1"))
        # The custom front pair has no center channel to clear the default
        # solid screen keepout. Plan the display after speaker placement.
        command.append("--no-display")
    if seats:
        command.extend(("--seats", seats))
    if fast:
        command.append("--fast")
    return command


def _stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, check=False)
        if process.poll() is None:
            process.kill()
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


_ACTIVE: dict[str, subprocess.Popen] = {}
_ACTIVE_LOCK = threading.Lock()


def cancel(cancel_key: str) -> bool:
    """Kill the engine run registered under cancel_key (a newer request replaced it). True if one was running."""
    with _ACTIVE_LOCK:
        process = _ACTIVE.pop(cancel_key, None)
    if process is None or process.poll() is not None:
        return False
    _stop_process_tree(process)
    return True


def run_scene(
    room: dict, listener: dict, *, preset: str, standard: str,
    timeout_s: float = 150, workdir: str | Path | None = None, cancel_key: str | None = None,
) -> dict:
    """Run speakerplacer in a disposable DATA_DIR/tmp subdirectory."""
    _validate_preset(preset)
    temp_root = (Path(os.getenv("DATA_DIR", "data")) / "tmp").resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="engine3d-", dir=temp_root) as temp:
        output_dir = Path(temp) / "output"
        layout_path = Path(temp) / "layout.json"
        command = build_command(room, listener, preset=preset, standard=standard,
                                output_dir=output_dir, layout_path=layout_path)
        env = {**os.environ, "MPLBACKEND": "Agg"}
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(command, cwd=workdir or REPO_ROOT, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, creationflags=creationflags,
                                   start_new_session=os.name != "nt")
        if cancel_key:
            with _ACTIVE_LOCK:
                _ACTIVE[cancel_key] = process
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _stop_process_tree(process)
            stdout, stderr = process.communicate()
            raise EngineError(f"engine timed out after {timeout_s}s; exit code {process.returncode}\n"
                              f"{_tail(stdout, stderr)}") from exc
        finally:
            if cancel_key:
                with _ACTIVE_LOCK:
                    if _ACTIVE.get(cancel_key) is process:
                        del _ACTIVE[cancel_key]
        if process.returncode != 0:
            raise EngineError(f"engine exit code {process.returncode}\n{_tail(stdout, stderr)}")
        try:
            scene = json.loads(layout_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise EngineError(f"engine exit code {process.returncode}; missing or invalid layout JSON\n"
                              f"{_tail(stdout, stderr)}") from exc
        if not isinstance(scene, dict) or scene.get("schema_version") != 2:
            raise EngineError(f"engine exit code {process.returncode}; expected schema_version 2\n"
                              f"{_tail(stdout, stderr)}")
        return scene


def _tail(stdout: str, stderr: str) -> str:
    return "\n".join((stdout + "\n" + stderr).splitlines()[-20:])


def _compliance(value: dict | None) -> dict | None:
    if not value:
        return None
    return {key: value[key] for key in
            ("status", "azimuth_deg", "azimuth_allowed", "elevation_deg", "elevation_allowed")
            if key in value}


def _default_display(room: dict) -> dict:
    """Use speakerplacer's normal display planner without its speaker keepout."""
    from speakerplacer import make_room
    from speakerplacer.display import DEFAULT_PROJECTOR_SPEC, DEFAULT_SCREEN_SPEC, solve_display_positions

    dims = room["dimensions"]
    facing, _ = _engine_facing(room)
    placement = solve_display_positions(
        make_room(float(dims["width"]), float(dims["length"])), facing,
        DEFAULT_SCREEN_SPEC, DEFAULT_PROJECTOR_SPEC,
        float(dims["height"]) * METRES_PER_FOOT,
    )
    center = placement["screen_center_m"]
    projector = placement["projector_position_m"]
    geometry = placement["screen_geometry"]
    return {"screen": {"center_ft": [value / METRES_PER_FOOT for value in center],
                       "geometry": {"width_m": geometry.width_m, "height_m": geometry.height_m}},
            "projector": {"position_ft": [value / METRES_PER_FOOT for value in projector]}}


def to_layout(scene: dict, room: dict) -> dict:
    """Map a schema 2 scene into the backend layout and engine metrics payload."""
    if scene.get("schema_version") != 2:
        raise ValueError("expected speakerplacer schema_version 2")
    room = _plain(room)
    dims = room["dimensions"]
    length = float(dims["length"])
    recorded_dimensions = scene.get("room_dimensions_ft")
    if recorded_dimensions and any(
        abs(float(actual) - float(dims[key])) > 0.1
        for actual, key in zip(recorded_dimensions, ("width", "length", "height"), strict=False)
    ):
        raise ValueError("engine scene dimensions do not match room dimensions")
    roles = {"Lss": "Ls", "Rss": "Rs"} if len([s for s in scene["speakers"]
                                                    if s["channel"] in ("Lrs", "Rrs")]) == 0 else {}
    speakers = []
    for source in scene["speakers"]:
        position = _engine_xyz(source["position_ft"], length)
        if any(value < -0.1 or value > float(dims[key]) + 0.1
               for value, key in zip(position, ("width", "height", "length"), strict=False)):
            raise ValueError(f"engine speaker {source['channel']} is outside room bounds")
        direction = source["aim_direction"]
        aim = [position[0] + 2 * float(direction[0]),
               position[1] + 2 * float(direction[2]),
               position[2] - 2 * float(direction[1])]
        item = {"role": roles.get(source["channel"], source["channel"]),
                "position": position, "aim": aim,
                "yaw_deg": source.get("yaw_deg"), "pitch_deg": source.get("pitch_deg"),
                "size": {key: float(source[f"{key}_m"]) / METRES_PER_FOOT
                         for key in ("width", "height", "depth")},
                "mount": MOUNT_MAP.get(source.get("mount_type"), source.get("mount_type")),
                "model_id": source.get("model_id"),
                "distance_ft": float(source["distance_m"]) / METRES_PER_FOOT,
                "receiver_delay_ms": source.get("receiver_delay_ms"),
                "receiver_trim_db": source.get("receiver_trim_db"),
                "compliance": _compliance(source.get("compliance"))}
        speakers.append(item)
    display = scene.get("display") or (
        _default_display(room) if _preset_from_channels(scene["speakers"]) == "2.1" else {})
    screen_source = display.get("screen")
    screen = None
    if screen_source:
        center = _engine_xyz(screen_source["center_ft"], length)
        # Use the facing the engine actually ran with; fall back to the room's listener only for older scenes.
        facing = scene.get("facing")
        if facing not in ("north", "south", "east", "west"):
            facing, _ = _engine_facing(room)
        wall = {"north": "wall_n", "south": "wall_s", "east": "wall_e", "west": "wall_w"}[facing]
        screen = {"wall_id": wall, "center": center,
                  "width": float(screen_source["geometry"]["width_m"]) / METRES_PER_FOOT,
                  "height": float(screen_source["geometry"]["height_m"]) / METRES_PER_FOOT}
    projector_source = display.get("projector")
    projector = None
    if projector_source:
        position = _engine_xyz(projector_source["position_ft"], length)
        scene_listener = scene.get("listener_m")
        if screen:
            target = screen["center"]
        elif scene_listener:
            target = _engine_xyz([float(v) / METRES_PER_FOOT for v in scene_listener], length)
        else:
            target = room["listener"]["position"]
        projector = {"position": position, "aim": target}
    seats = [{"row": seat["row"], "seat": seat["seat"],
              "position": _engine_xyz([seat["position_m"][0] / METRES_PER_FOOT,
                                       seat["position_m"][1] / METRES_PER_FOOT,
                                       seat["ear_height_m"] / METRES_PER_FOOT], length),
              "ear_height": seat["ear_height_m"] / METRES_PER_FOOT}
             for seat in scene.get("seats", [])]
    preset = scene.get("layout")
    if not preset or preset == "custom":
        preset = _preset_from_channels(scene["speakers"])
    acoustic = scene.get("room_acoustics") or {}
    engine = {"compliance": scene.get("compliance", []),
              "receiver_calibration": scene.get("receiver_calibration", {}),
              "rt60": acoustic,
              "first_reflections": scene.get("first_reflections", []),
              "crossover": scene.get("crossover", {}),
              "sub_strategy_comparison": scene.get("sub_strategy_comparison", []),
              "warnings": scene.get("warnings", [])}
    return {"layout": {"speakers": speakers, "screen": screen, "preset": preset,
                       "standard": scene.get("standard"), "seats": seats,
                       "projector": projector}, "engine": engine}


def _preset_from_channels(speakers: list[dict]) -> str:
    channels = {speaker["channel"] for speaker in speakers}
    base = "7.1" if "Lrs" in channels else "2.1" if channels == {"L", "R", "LFE"} else "5.1"
    overheads = sum(channel in channels for channel in ("Ltf", "Rtf", "Ltr", "Rtr", "Ltm", "Rtm"))
    return f"{base}.{overheads}" if overheads else base
