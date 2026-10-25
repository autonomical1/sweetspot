"""Interactive Matplotlib 3D view of the optimized wall-mounted layout."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import sys
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from matplotlib.ticker import FuncFormatter
from matplotlib.widgets import Button, CheckButtons
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from .room import validate_polygon


FT = 0.3048
TYPE_COLORS = {"front": "orangered", "surround": "royalblue", "bass": "darkviolet"}
FACING = {
    "north": np.array([0., 1.]), "south": np.array([0., -1.]),
    "east": np.array([1., 0.]), "west": np.array([-1., 0.]),
}
TOGGLES = (
    ("ceiling", "Ceiling"), ("nearest_wall", "Nearest wall"),
    ("all_walls", "All walls"), ("keepouts", "Keep-outs"), ("labels", "Labels"),
    ("aim_arrows", "Aim arrows"), ("listener_lines", "Listener lines"),
    ("coverage", "Coverage cones"), ("candidates", "Candidate dots"),
    ("reflections", "Reflections"), ("treatment", "Treatment panels"),
    ("sphere", "Equidistance sphere"), ("ear_plane", "Ear plane"), ("framing", "Studs / joists"),
    ("floor_alternatives", "Floor alternatives"), ("overhead_speakers", "Overhead speakers"),
    ("screen_display", "Screen"), ("projector_display", "Projector"),
    ("projector_beam", "Projector beam"), ("view_wedges", "View wedges"), ("sightlines", "Sightlines"),
)


@dataclass(frozen=True)
class BoxPose:
    """Rigid cuboid in metres; vertices 0:4 are back, 4:8 are driver face."""
    vertices_m: np.ndarray
    front_normal: np.ndarray
    right_axis: np.ndarray
    up_axis: np.ndarray
    mount_position_m: np.ndarray
    wall_normal: np.ndarray

    @property
    def front_center_m(self) -> np.ndarray:
        return np.mean(self.vertices_m[4:8], axis=0)

    def faces(self) -> list[np.ndarray]:
        v = self.vertices_m
        return [v[[0, 1, 2, 3]], v[[4, 7, 6, 5]], v[[0, 1, 5, 4]],
                v[[1, 2, 6, 5]], v[[2, 3, 7, 6]], v[[3, 0, 4, 7]]]


def wall_frame(room_polygon_m: np.ndarray, wall_index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return wall start, tangent, and inward normal for a CCW room."""
    room = validate_polygon(room_polygon_m)
    if not 0 <= wall_index < room.shape[1]:
        raise ValueError("wall_index is outside the room polygon")
    start = room[:, wall_index]
    edge = room[:, (wall_index + 1) % room.shape[1]] - start
    tangent = edge / np.linalg.norm(edge)
    inward = np.array([-tangent[1], tangent[0]])
    return start, tangent, inward


def front_wall_index(room_polygon_m: np.ndarray, facing: str) -> int:
    """Find the wall whose outward normal points along the listener's facing."""
    if facing not in FACING:
        raise ValueError("facing must be north, south, east, or west")
    room = validate_polygon(room_polygon_m)
    return max(range(room.shape[1]),
               key=lambda index: float(-wall_frame(room, index)[2] @ FACING[facing]))


def box_pose(
    room_polygon_m: np.ndarray,
    room_height_m: float,
    wall_index: int,
    position_xy_m: np.ndarray,
    center_height_m: float,
    width_m: float,
    height_m: float,
    visible_depth_m: float,
    aim_xy: np.ndarray,
    pitch_deg: float = 0.,
) -> BoxPose:
    """Construct a rigid wall-mounted speaker box without crossing room planes.

    At zero yaw and pitch the entire back face lies on the wall. When rotated,
    a rigid rectangular back face cannot remain flush. The box is translated
    inward until its closest back corner touches the wall; its driver-face
    normal remains exactly aligned with the requested yaw and pitch.
    """
    room = validate_polygon(room_polygon_m)
    if room_height_m <= 0:
        raise ValueError("3D viewer requires positive room height")
    if min(width_m, height_m, visible_depth_m) <= 0:
        raise ValueError("speaker box dimensions must be positive")
    start, tangent, inward = wall_frame(room, wall_index)
    xy = np.asarray(position_xy_m, dtype=float)
    aim = np.array(aim_xy, dtype=float, copy=True)
    if xy.shape != (2,) or aim.shape != (2,) or np.linalg.norm(aim) == 0:
        raise ValueError("speaker position and horizontal aim must be 2-vectors")
    aim /= np.linalg.norm(aim)
    if float(aim @ inward) < -1e-9:
        raise ValueError("speaker aim points outside the room")
    pitch = np.radians(float(pitch_deg))
    front = np.array([aim[0] * np.cos(pitch), aim[1] * np.cos(pitch), np.sin(pitch)])
    right = np.array([aim[1], -aim[0], 0.])
    up = np.cross(right, front)
    # The user's 2D optimizer point sits just inside the wall; project it to
    # the actual mounting plane before constructing the physical box.
    projected = start + float((xy - start) @ tangent) * tangent
    center = np.array([projected[0], projected[1], center_height_m])
    corners = [(-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)]
    vertices = np.array([
        center + u * width_m * right + v * height_m * up + depth * front
        for depth in (0., visible_depth_m) for u, v in corners
    ])
    # Moving along the wall normal preserves the selected along-wall point.
    wall_depths = (vertices[:, :2] - start) @ inward
    vertices += np.r_[-float(wall_depths.min()) * inward, 0.]
    # An adjacent wall may constrain a near-corner speaker. Shift only along
    # the mounting wall, preserving both the aim and a wall-contact corner.
    lower, upper = -np.inf, np.inf
    for index in range(room.shape[1]):
        wall_start, _, wall_inward = wall_frame(room, index)
        distance = float(np.min((vertices[:, :2] - wall_start) @ wall_inward))
        coefficient = float(tangent @ wall_inward)
        if abs(coefficient) < 1e-10:
            if distance < -1e-9:
                raise ValueError("speaker box cannot fit within the room walls")
        elif coefficient > 0:
            lower = max(lower, -distance / coefficient)
        else:
            upper = min(upper, -distance / coefficient)
    if lower > upper + 1e-9:
        raise ValueError("speaker box is too wide for the selected wall")
    along_shift = float(np.clip(0., lower, upper))
    vertices += np.r_[along_shift * tangent, 0.]
    zmin, zmax = float(vertices[:, 2].min()), float(vertices[:, 2].max())
    if zmax - zmin > room_height_m + 1e-9:
        raise ValueError("speaker box is taller than the room")
    height_shift = max(0., -zmin)
    if zmax + height_shift > room_height_m:
        height_shift += room_height_m - (zmax + height_shift)
    vertices[:, 2] += height_shift
    mount = np.r_[projected + along_shift * tangent, center_height_m + height_shift]
    return BoxPose(vertices, front, right, up, mount, inward)


def _speaker_height(role: str, model: Any, ear_height_m: float, room_height_m: float,
                    requested_m: float | None) -> float:
    desired = requested_m if requested_m is not None else {
        "front": ear_height_m, "surround": ear_height_m + .45, "bass": .5,
    }.get(role, ear_height_m)
    low, high = model.mount_height_range_m
    minimum = max(float(low), model.height_m / 2. + .01)
    maximum = min(float(high), room_height_m - model.height_m / 2. - .01)
    if minimum > maximum:
        raise ValueError("speaker '{}' height range does not fit inside the room".format(model.model_id))
    if requested_m is not None: return float(np.clip(desired, minimum, maximum))
    # Search legal mounting heights on a 15 cm grid and choose the strongest
    # vertical response toward the listener's ears; the role default breaks ties.
    heights=np.arange(minimum,maximum+0.075,.15)
    heights=np.unique(np.append(heights,np.clip(ear_height_m,minimum,maximum)))
    scored=[]
    for candidate in heights:
        tilt=np.degrees(np.arctan2(ear_height_m-candidate,1.0))
        aimed=np.clip(tilt,-model.max_tilt_deg,model.max_tilt_deg)
        residual=tilt-aimed
        gain=model.gain_vertical_db(residual)
        scored.append((gain,-abs(candidate-desired),candidate))
    return float(max(scored)[2])


def build_layout(
    result: Any,
    models: dict[str, Any],
    room_height_m: float,
    ear_height_m: float = 1.10,
    mount_heights_m: dict[str, float] | None = None,
    inwall_protrusion_m: float = .012,
    standard: str = "itu",
    extra_speakers: list[dict] | None = None,
    seats: list[dict] | None = None,
) -> dict[str, Any]:
    """Snapshot optimizer output into a self-contained 3D layout JSON object."""
    room = validate_polygon(result.room_polygon_m)
    if room_height_m <= 0 or not 0 < ear_height_m < room_height_m:
        raise ValueError("room height and ear height must be positive and ear below ceiling")
    if not 0 < inwall_protrusion_m <= .05:
        raise ValueError("in-wall panel protrusion must be within 0-5 cm")
    listener_xy = np.asarray(result.listener_m, dtype=float)
    listener = [float(listener_xy[0]), float(listener_xy[1]), float(ear_height_m)]
    mount_heights_m = mount_heights_m or {}
    speakers = []
    height_by_role = {}
    for speaker in result.best_pair.get("speakers", []):
        model = models[speaker["model_id"]]
        role = speaker["type"]
        optimized_height=speaker.get("height_m")
        height = (float(np.clip(mount_heights_m[role],speaker["height_range_m"][0],speaker["height_range_m"][1]))
                  if role in mount_heights_m else
                  float(optimized_height) if optimized_height is not None else
                  _speaker_height(role, model, ear_height_m, room_height_m, None))
        height_by_role[role] = height
        if speaker.get("surface") in ("floor","ceiling"):
            box_center=np.r_[np.asarray(speaker["position_m"],dtype=float)[:2],float(speaker.get("height_m",height))]
            horizontal=np.asarray(speaker.get("aim_direction",[0.,1.]),dtype=float)[:2]
            if np.linalg.norm(horizontal)<1e-9: horizontal=np.array([0.,1.])
            horizontal/=np.linalg.norm(horizontal)
            vertical_offset,forward_offset=map(float,model.acoustic_center_offset_m)
            acoustic_center=box_center+np.r_[horizontal*forward_offset,vertical_offset]
            speakers.append({"type":role,"model_id":model.model_id,"mount_type":model.mount_type,
                "channel":speaker.get("channel",role),"surface":speaker["surface"],"wall_index":-1,
                "placement_mode":speaker.get("placement_mode",speaker["surface"]),
                "position_m":box_center.tolist(),"position_ft":(box_center/FT).tolist(),"box_center_m":box_center.tolist(),
                "acoustic_center_position_m":acoustic_center.tolist(),"acoustic_center_offset_m":[vertical_offset,forward_offset],
                "aim_xy":horizontal.tolist(),"aim_direction":[float(horizontal[0]),float(horizontal[1]),0.],
                "yaw_deg":0.,"pitch_deg":0.,"width_m":float(model.width_m),"height_m":float(model.height_m),
                "depth_m":float(model.depth_m),"visible_depth_m":float(model.depth_m),
                "coverage_h_deg":float(model.coverage_h_deg),"coverage_v_deg":float(model.coverage_v_deg),
                "predicted_spl_db":float(speaker.get("predicted_spl_db",float("nan"))),
                "headroom_db":float(speaker.get("headroom_db",float("nan"))),"warnings":list(speaker.get("warnings",[]))})
            continue
        visible_depth = float(model.depth_m if model.mount_type == "on_wall" else inwall_protrusion_m)
        source_xy = np.asarray(speaker["position_m"], dtype=float)
        horizontal_aim = np.asarray(speaker["aim_direction"], dtype=float)
        vertical_offset,forward_offset=map(float,model.acoustic_center_offset_m)
        wall_start,wall_tangent,wall_inward=wall_frame(room,int(speaker["wall_index"]))
        wall_xy=wall_start+float((source_xy-wall_start)@wall_tangent)*wall_tangent
        acoustic_xy=wall_xy+wall_inward*forward_offset
        acoustic_z=height+vertical_offset
        horizontal_distance = max(float(np.linalg.norm(listener_xy - acoustic_xy)), 1e-9)
        target_pitch = float(np.degrees(np.arctan2(ear_height_m - acoustic_z, horizontal_distance)))
        pitch = 0. if model.directivity_model=="omni" else float(np.clip(target_pitch,-model.max_tilt_deg,model.max_tilt_deg))
        yaw = 0. if model.directivity_model=="omni" else float(speaker.get("toe_in_deg",0.))
        pose = box_pose(room, room_height_m, int(speaker["wall_index"]), source_xy,
                        height, float(model.width_m), float(model.height_m), visible_depth,
                        horizontal_aim, pitch)
        acoustic_center=np.r_[acoustic_xy,acoustic_z]
        speakers.append({
            "type": role, "model_id": model.model_id, "mount_type": model.mount_type,
            "wall_index": int(speaker["wall_index"]),
            "wall_u_m": float((wall_xy-wall_start)@wall_tangent),
            "wall_t": float(speaker.get("wall_t",0.5)),
            "position_m": [float(wall_xy[0]),float(wall_xy[1]),float(height)],
            "position_ft": [float(wall_xy[0]/FT),float(wall_xy[1]/FT),float(height/FT)],
            "box_center_m": [float(wall_xy[0]),float(wall_xy[1]),float(height)],
            "acoustic_center_position_m": [float(x) for x in acoustic_center],
            "acoustic_center_offset_m": [vertical_offset,forward_offset],
            "allowed_height_range_m":list(speaker.get("height_range_m",model.mount_height_range_m)),
            "box_mount_position_m": [float(x) for x in pose.mount_position_m],
            "optimizer_position_xy_m": [float(x) for x in source_xy],
            "aim_xy": [float(x) for x in horizontal_aim],
            "aim_direction": [float(x) for x in pose.front_normal],
            "yaw_deg": yaw, "pitch_deg": pitch,
            "width_m": float(model.width_m), "height_m": float(model.height_m),
            "depth_m": float(model.depth_m), "visible_depth_m": visible_depth,
            "coverage_h_deg": float(model.coverage_h_deg),
            "coverage_v_deg": float(model.coverage_v_deg),
            "predicted_spl_db": float(speaker.get("predicted_spl_db", float("nan"))),
            "headroom_db": float(speaker.get("headroom_db", float("nan"))),
            "warnings": list(speaker.get("warnings", [])),
        })
    speakers.extend(dict(item) for item in (extra_speakers or []))
    from .home_theater import receiver_settings
    from .home_theater import compliance_rows,label_legacy_channels
    labels=label_legacy_channels([{**item,"listener_xy_m":listener_xy} for item in speakers],result.facing)
    for item,label in zip(speakers,labels): item["channel"]=label
    compliance=compliance_rows(speakers,listener,result.facing,standard)
    compliance_by_channel={row["channel"]:row for row in compliance}
    for item in speakers: item["compliance"]=compliance_by_channel.get(item["channel"])
    calibration,calibration_metrics=receiver_settings([
        (item["channel"],np.asarray(item.get("acoustic_center_position_m",item["position_m"]),dtype=float)-np.asarray(listener))
        for index,item in enumerate(speakers)])
    for item,setting in zip(speakers,calibration):
        item["receiver_delay_ms"]=setting.delay_ms
        item["receiver_trim_db"]=setting.trim_db
        item["distance_m"]=setting.distance_m
    candidates = []
    for row in result.candidate_scores:
        role=row["type"]
        from .speaker_models import DEFAULT_MODEL_BY_ROLE
        model_id=row.get("model_id",DEFAULT_MODEL_BY_ROLE.get("front" if role=="regular" else role))
        model=models[model_id]; wi=int(row["wall_index"])
        start,tangent,_=wall_frame(room,wi); position=np.asarray(row["position_m"],dtype=float)
        along=float((position-start)@tangent)
        candidate_row={"type":role,"wall_index":wi,"wall_u_m":along,
            "position_xy_m":[float(x) for x in position],"height_m":float(row.get("height_m",ear_height_m)),
            "score_db":float(row["score_db"]),
            "allowed_height_range_m":list(row.get("height_range_m",model.mount_height_range_m))}
        if "height_m" in row:
            candidates.append(candidate_row)
        else:
            # Compatibility for callers constructing OptimizationResult objects
            # from the pre-3D API: expose the legal height surface there too.
            from .optimize import _legal_height_grid, _vertical_response
            distance=max(float(np.linalg.norm(listener_xy-position)),.01)
            for z in _legal_height_grid(role,model,listener_xy,position,room_height_m,ear_height_m):
                gain,_=_vertical_response(float(z),model,distance,ear_height_m)
                candidates.append({**candidate_row,"height_m":float(z),"score_db":float(row["score_db"]+gain)})
    lx = float(np.linalg.norm(room[:, 1] - room[:, 0]))
    ly = float(np.linalg.norm(room[:, 3] - room[:, 0]))
    return {
        "schema_version": 2, "room_polygon_m": room.tolist(),
        "room_dimensions_m": [lx, ly, float(room_height_m)],
        "room_dimensions_ft": [lx / FT, ly / FT, room_height_m / FT],
        "listener_m": listener, "facing": result.facing,
        "speakers": speakers, "seats":list(seats or []),"standard":standard,"compliance":compliance,
        "receiver_calibration":calibration_metrics, "candidate_scores": candidates,
        "definitions": {
            "units": {"length":"metres in *_m; feet in *_ft","angles":"degrees"},
            "origin_and_axes":"world origin is the room polygon's first vertex; x/y follow the supplied world frame; z is up from floor",
            "facing":"listener forward direction in world coordinates (north=+y, east=+x, south=-y, west=-x)",
            "wall_index":"zero-based polygon edge from vertex i to vertex (i+1) modulo vertex count; vertices are counterclockwise",
            "aim_vector":"unit vector from speaker toward its acoustic/visual forward direction",
            "position_m":"mount point projected to the wall plane; position_xy optimizer points are offset inward by the search nudge",
            "optimizer_position_xy_m":"optimizer's horizontal acoustic candidate, nudged into the room for a valid image-source computation",
            "candidate_data":"stored separately when --save-candidates is supplied; each row is a wall-u and height-grid sample"
        },
        "warnings": list(result.warnings),
    }


def save_layout(layout: dict[str, Any], path: str | Path, candidates_path: str | Path | None = None) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    saved=dict(layout)
    rows=saved.pop("candidate_scores",[])
    if candidates_path is not None:
        candidates=Path(candidates_path).expanduser(); candidates.parent.mkdir(parents=True,exist_ok=True)
        candidates.write_text(json.dumps({"schema_version":1,"candidates":rows},indent=2,allow_nan=False)+"\n",encoding="utf-8")
        saved["candidate_scores_file"]=str(candidates.resolve())
    target.write_text(json.dumps(saved, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return target


def load_layout(path: str | Path) -> dict[str, Any]:
    layout = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if layout.get("schema_version") != 2:
        raise ValueError("unsupported layout JSON schema version")
    if "candidate_scores_file" in layout:
        candidate_path=Path(layout["candidate_scores_file"])
        if not candidate_path.is_absolute(): candidate_path=Path(path).expanduser().parent/candidate_path
        layout["candidate_scores"]=json.loads(candidate_path.read_text(encoding="utf-8")).get("candidates",[])
    else:
        layout["candidate_scores"]=[]
    room = validate_polygon(np.asarray(layout["room_polygon_m"], dtype=float))
    height = float(layout["room_dimensions_m"][2])
    for speaker in layout["speakers"]:
        if speaker.get("surface")!="ceiling": pose_for_speaker(layout, speaker)
    if len(layout["listener_m"]) != 3 or height <= 0:
        raise ValueError("saved layout needs a 3D listener and positive room height")
    return layout


def pose_for_speaker(layout: dict[str, Any], speaker: dict[str, Any]) -> BoxPose:
    return box_pose(np.asarray(layout["room_polygon_m"], dtype=float),
                    float(layout["room_dimensions_m"][2]), int(speaker["wall_index"]),
                    np.asarray(speaker["position_m"][:2], dtype=float),
                    float(speaker["position_m"][2]), float(speaker["width_m"]),
                    float(speaker["height_m"]), float(speaker["visible_depth_m"]),
                    np.asarray(speaker["aim_xy"], dtype=float), float(speaker["pitch_deg"]))


def _lighten(color: str, amount: float) -> tuple[float, float, float]:
    rgb = np.array(colors.to_rgb(color))
    return tuple(rgb * (1. - amount) + amount)


def _camera_azim(facing: str) -> float:
    return {"north": -70., "south": 110., "east": -160., "west": 20.}[facing]


def interactive_backend_available() -> bool:
    backend = matplotlib.get_backend().lower()
    if any(name in backend for name in ("agg", "pdf", "svg", "ps", "cairo", "template", "inline")):
        return False
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    return True


def plot_model_comparison_3d(first: Any, second: Any, model_ids: list[str], models: dict[str, Any],
                            output_dir: str | Path="output", room_height_m: float=2.4384,
                            ear_height_m: float=1.097, role: str | None=None) -> Path:
    """Save a side-by-side 3D comparison of model-specific position and aim."""
    from pathlib import Path
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    results=(first,second); fig=plt.figure(figsize=(14,6))
    for index,(result,model_id) in enumerate(zip(results,model_ids),1):
        scene=build_layout(result,models,room_height_m,ear_height_m)
        room=np.asarray(scene["room_polygon_m"]); height=float(scene["room_dimensions_m"][2])
        ax=fig.add_subplot(1,2,index,projection="3d"); n_walls=room.shape[1]; bottom=np.column_stack([room.T,np.zeros(n_walls)]); top=bottom.copy(); top[:,2]=height
        for i in range(n_walls):
            edge=np.vstack([bottom[i],bottom[(i+1)%n_walls],top[(i+1)%n_walls],top[i],bottom[i]])
            ax.plot(edge[:,0],edge[:,1],edge[:,2],color="#90a4ae",lw=.8)
        ax.add_collection3d(Poly3DCollection([bottom],facecolors="#eaf0f2",alpha=.3,edgecolors="none"))
        chosen=[speaker for speaker in scene["speakers"] if role is None or speaker["type"]==role]
        for speaker in chosen:
            pose=pose_for_speaker(scene,speaker); color=TYPE_COLORS.get(speaker["type"],"#607d8b")
            ax.add_collection3d(Poly3DCollection(pose.faces(),facecolors=color,edgecolors="#263238",linewidths=.8,alpha=.92))
            anchor=pose.front_center_m; ax.text(anchor[0],anchor[1],anchor[2]+.12,
                "{} {:.1f} ft, tilt {:+.0f}°".format(speaker["type"],speaker["position_m"][2]/FT,speaker["pitch_deg"]),fontsize=7)
        listener=np.asarray(scene["listener_m"]); ax.scatter(*listener,s=40,c="#d39f00",marker="o",label="Listener")
        ax.set(xlim=(room[0].min(),room[0].max()),ylim=(room[1].min(),room[1].max()),zlim=(0.,height),xlabel="x (ft)",ylabel="y (ft)",zlabel="z (ft)")
        formatter=FuncFormatter(lambda value,_pos:"{:.0f}".format(value/FT))
        ax.xaxis.set_major_formatter(formatter); ax.yaxis.set_major_formatter(formatter); ax.zaxis.set_major_formatter(formatter)
        ax.set_box_aspect((np.ptp(room[0]),np.ptp(room[1]),height)); ax.view_init(elev=24,azim=_camera_azim(result.facing))
        ax.set_title("{} · score {:.2f}".format(model_id,result.best_pair["score_db"]))
    fig.suptitle("3D model comparison · weighted sum of dB-like objective terms (relative score, not SPL)\nposition, height, yaw and tilt",fontsize=11)
    fig.tight_layout(); target=Path(output_dir)/"model_comparison_3d.png"; target.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(target,dpi=180); plt.close(fig); return target


class Viewer3D:
    """Matplotlib scene with checkboxes, camera presets, and PNG export."""

    def __init__(self, layout: dict[str, Any], output_dir: str | Path = "output",
                 elev: float | None = None, azim: float | None = None,
                 show_coverage: bool = False, show_candidates: bool = False,
                 reflection_index: int | None = None):
        self.layout = layout
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.elev = 25. if elev is None else float(elev)
        self.azim = _camera_azim(layout["facing"]) if azim is None else float(azim)
        self.reflection_index = reflection_index if reflection_index is not None else 0
        if reflection_index is not None and not 0 <= reflection_index < len(layout["speakers"]):
            raise ValueError("--show-reflections index must be 0 through {}".format(len(layout["speakers"]) - 1))
        self.state = {
            "ceiling": False, "nearest_wall": False, "all_walls": True,
            "labels": True, "aim_arrows": True, "listener_lines": True,
            "coverage": bool(show_coverage), "candidates": bool(show_candidates),
            "reflections": reflection_index is not None, "treatment":False,"sphere":False,
            "ear_plane": False,"keepouts":True,"framing":False,
            "floor_alternatives":False,"overhead_speakers":False,
            "screen_display":bool(layout.get("display")),"projector_display":bool(layout.get("display")),
            "projector_beam":bool(layout.get("display")),"view_wedges":False,"sightlines":False,
        }
        self.fig = plt.figure(figsize=(13.5, 8.5))
        self.ax = self.fig.add_axes([.02, .08, .74, .86], projection="3d")
        if hasattr(self.ax, "computed_zorder"):
            self.ax.computed_zorder = False
        labels = [label for _, label in TOGGLES]
        self._toggle_names = [name for name, _ in TOGGLES]
        checks_ax = self.fig.add_axes([.785, .37, .20, .52])
        self.checks = CheckButtons(checks_ax, labels, [self.state[name] for name in self._toggle_names])
        checks_ax.set_title("Show", fontsize=10)
        self.checks.on_clicked(self._clicked)
        self.buttons = {}
        for index, name in enumerate(("Top", "Front", "Side", "Perspective")):
            x = .785 + (index % 2) * .102
            y = .32 - (index // 2) * .065
            button = Button(self.fig.add_axes([x, y, .095, .05]), name)
            button.on_clicked(lambda _event, chosen=name: self.set_view(chosen.lower()))
            self.buttons[name] = button
        save_button = Button(self.fig.add_axes([.785, .17, .197, .055]), "Save PNG")
        save_button.on_clicked(lambda _event: self.save_png(self.output_dir / "layout_3d_view.png"))
        self.buttons["Save PNG"] = save_button
        self.fig.text(.785, .11, "T Top · F Front · S Side · P Perspective\nL Labels · C Coverage · Q Close",
                      fontsize=8, va="top")
        self.fig.canvas.mpl_connect("key_press_event", self._key)
        self._rendered = False
        self.render(preserve_camera=False)

    def _clicked(self, label: str) -> None:
        name = dict((display, key) for key, display in TOGGLES)[label]
        self.state[name] = not self.state[name]
        self.render()

    def set_toggle(self, name: str, value: bool) -> None:
        if name not in self.state:
            raise KeyError(name)
        if self.state[name] != bool(value):
            self.checks.set_active(self._toggle_names.index(name))

    def set_view(self, preset: str) -> None:
        behind = _camera_azim(self.layout["facing"])
        views = {
            "top": (90., behind), "front": (8., behind),
            "side": (18., behind + 90.), "perspective": (25., behind),
        }
        if preset not in views:
            raise ValueError("view preset must be top, front, side, or perspective")
        self.elev, self.azim = views[preset]
        self.render(preserve_camera=False)

    def _key(self, event: Any) -> None:
        key = (event.key or "").lower()
        if key in {"t": "top", "f": "front", "s": "side", "p": "perspective"}:
            self.set_view({"t": "top", "f": "front", "s": "side", "p": "perspective"}[key])
        elif key == "l": self.set_toggle("labels", not self.state["labels"])
        elif key == "c": self.set_toggle("coverage", not self.state["coverage"])
        elif key == "q": plt.close(self.fig)

    def render(self, preserve_camera: bool = True) -> None:
        if preserve_camera and self._rendered:
            self.elev, self.azim = float(self.ax.elev), float(self.ax.azim)
        self.ax.cla()
        self._draw_room()
        if self.state["keepouts"]: self._draw_keepouts()
        if self.state["framing"]: self._draw_framing()
        if self.state["floor_alternatives"]: self._draw_floor_alternatives()
        if self.state["screen_display"]: self._draw_display_screen()
        if self.state["projector_beam"]: self._draw_display_beam()
        if self.state["projector_display"]: self._draw_display_projector()
        if self.state["view_wedges"]: self._draw_display_wedges()
        if self.state["sightlines"]: self._draw_display_sightlines()
        if self.state["ear_plane"]: self._draw_ear_plane()
        if self.state["candidates"]: self._draw_candidates()
        if self.state["coverage"]: self._draw_coverage()
        if self.state["reflections"]: self._draw_reflections()
        if self.state["treatment"]: self._draw_treatment_panels()
        if self.state["sphere"]: self._draw_equidistance_sphere()
        self._draw_speakers()
        self._draw_seats()
        self._draw_listener()
        self._finish_axes()
        self.ax.view_init(elev=self.elev, azim=self.azim)
        self._rendered = True
        self.fig.canvas.draw_idle()

    def _draw_room(self) -> None:
        room = np.asarray(self.layout["room_polygon_m"], dtype=float)
        height = float(self.layout["room_dimensions_m"][2])
        n_walls = room.shape[1]
        bottom = np.column_stack([room.T, np.zeros(n_walls)])
        top = bottom.copy(); top[:, 2] = height
        self.ax.add_collection3d(Poly3DCollection([bottom], facecolors="#eaf0f2", alpha=.35,
                                                   edgecolors="#a0a9ad", linewidths=.6, zorder=1))
        camera = np.array([np.cos(np.radians(self.azim)), np.sin(np.radians(self.azim))])
        near = max(range(n_walls), key=lambda i: float(-wall_frame(room, i)[2] @ camera))
        for index in range(n_walls):
            face = [bottom[index], bottom[(index + 1) % n_walls], top[(index + 1) % n_walls], top[index]]
            if self.state["all_walls"] and (index != near or self.state["nearest_wall"]):
                self.ax.add_collection3d(Poly3DCollection([face], facecolors="#a8c2cd",
                                                           alpha=.045, edgecolors="none", zorder=2))
            edge = np.array(face + [face[0]])
            self.ax.plot(edge[:, 0], edge[:, 1], edge[:, 2], color="#78909c", lw=.65, alpha=.65)
        ceiling = np.vstack([top, top[0]])
        self.ax.plot(ceiling[:, 0], ceiling[:, 1], ceiling[:, 2], color="#9aa8af", lw=.7, alpha=.65)
        if self.state["ceiling"]:
            self.ax.add_collection3d(Poly3DCollection([top], facecolors="#b5ced5", alpha=.045,
                                                       edgecolors="none", zorder=2))
        lu,lv=np.ptp(room[0]),np.ptp(room[1])
        # Floor grid at roughly one-foot spacing in the room's local frame.
        if n_walls == 4:
            a = room[:, 0]; u = room[:, 1] - a; v = room[:, 3] - a
            lu, lv = np.linalg.norm(u), np.linalg.norm(v)
            if lu and lv:
                u, v = u / lu, v / lv
                for step in np.arange(FT, lu, FT):
                    x = a + step * u; y = x + lv * v
                    self.ax.plot([x[0], y[0]], [x[1], y[1]], [0, 0], color="#becbd0", alpha=.25, lw=.45)
                for step in np.arange(FT, lv, FT):
                    x = a + step * v; y = x + lu * u
                    self.ax.plot([x[0], y[0]], [x[1], y[1]], [0, 0], color="#becbd0", alpha=.25, lw=.45)
        front_index = front_wall_index(room, self.layout["facing"])
        front_a = room[:, front_index]; front_b = room[:, (front_index + 1) % n_walls]
        self.ax.plot([front_a[0], front_b[0]], [front_a[1], front_b[1]], [height, height],
                     color="#b71c1c", lw=3.0)
        midpoint = (front_a + front_b) / 2.
        self.ax.text(midpoint[0], midpoint[1], height * .83, "FRONT", color="#9b1b1b", fontsize=10,
                     ha="center", weight="bold")
        self.ax.text(midpoint[0], midpoint[1], .02,
                     "{:.1f} × {:.1f} ft bounds".format(lu / FT,lv / FT), fontsize=8, color="#52616b")
        self.ax.text(room[0, 0], room[1, 0], height / 2., "{:.1f} ft".format(height / FT),
                     fontsize=8, color="#52616b")

    def _draw_keepouts(self) -> None:
        room=np.asarray(self.layout["room_polygon_m"],dtype=float); xmin,xmax=room[0].min(),room[0].max(); ymin,ymax=room[1].min(),room[1].max()
        for zone in self.layout.get("keepouts",[]):
            if zone.get("label") == "display screen footprint":
                continue
            u0,u1=zone["u_range_m"]; z0,z1=zone["z_range_m"]; wall=zone["wall"]
            if "wall_index" in zone:
                wi=int(zone["wall_index"]); start,tangent,_=wall_frame(room,wi)
                a=start+tangent*u0; b=start+tangent*u1
                vertices=[[a[0],a[1],z0],[b[0],b[1],z0],[b[0],b[1],z1],[a[0],a[1],z1]]
            elif wall in ("north","south"):
                y=ymax if wall=="north" else ymin
                vertices=[[u0,y,z0],[u1,y,z0],[u1,y,z1],[u0,y,z1]]
            else:
                x=xmax if wall=="east" else xmin
                vertices=[[x,u0,z0],[x,u1,z0],[x,u1,z1],[x,u0,z1]]
            self.ax.add_collection3d(Poly3DCollection([vertices],facecolors="#ef5350",edgecolors="#b71c1c",
                                                       linewidths=1.,alpha=.35,hatch="///",zorder=11))
            center=np.mean(np.asarray(vertices),axis=0)
            self.ax.text(*center,zone.get("label","keep-out"),fontsize=7,color="#8e0000",zorder=12)

    def _draw_framing(self) -> None:
        """Draw configured stud and joist centerlines as planning guides."""
        frame=self.layout.get("framing",{}); room=np.asarray(self.layout["room_polygon_m"],dtype=float)
        height=float(self.layout["room_dimensions_m"][2])
        stud=frame.get("stud_spacing_m"); joist=frame.get("joist_spacing_m")
        if stud:
            for i in range(room.shape[1]):
                start,tangent,_=wall_frame(room,i); length=float(np.linalg.norm(room[:,(i+1)%room.shape[1]]-start))
                for along in np.arange(0.,length+1e-9,float(stud)):
                    point=start+tangent*along
                    self.ax.plot([point[0],point[0]],[point[1],point[1]],[0.,height],color="#795548",alpha=.4,lw=.7,zorder=3)
        if joist and room.shape[1] == 4:
            start=room[:,0]; u=room[:,1]-start; v=room[:,3]-start
            lu,lv=float(np.linalg.norm(u)),float(np.linalg.norm(v)); u/=lu; v/=lv
            for along in np.arange(float(joist)/2.,lu,float(joist)):
                a=start+along*u; b=a+lv*v
                self.ax.plot([a[0],b[0]],[a[1],b[1]],[height,height],color="#8d6e63",alpha=.4,lw=1.,zorder=4)

    def _draw_floor_alternatives(self) -> None:
        """Show searched floor/stand options as translucent enclosure markers."""
        for item in self.layout.get("floor_alternatives",[]):
            if "position_m" not in item: continue
            x,y,_=map(float,item["position_m"]); model_id=item.get("model_id")
            width=float(item.get("width_m",.24)); depth=float(item.get("depth_m",.32)); height=float(item.get("height_m",1.))
            self.ax.bar3d(x-width/2.,y-depth/2.,0.,width,depth,height,color="#43a047",alpha=.28,edgecolor="#1b5e20",linewidth=.8,shade=False)
            self.ax.text(x,y,height+.08,item.get("channel","floor"),fontsize=7,color="#1b5e20",ha="center")

    def _display_corners(self, image: bool=False):
        import numpy as np
        data=self.layout.get("display")
        if not data: return None
        screen=data["screen"]; geometry=screen["geometry"]; center=np.asarray(screen["center_m"],dtype=float)
        right=np.asarray(screen.get("right_xy",[FACING[self.layout["facing"]][1],-FACING[self.layout["facing"]][0]]),dtype=float)
        width=geometry["image_width_m"] if image else geometry["width_m"]
        height=geometry["image_height_m"] if image else geometry["height_m"]
        return [center+np.r_[-right*width/2.,-height/2.],center+np.r_[right*width/2.,-height/2.],
                center+np.r_[right*width/2.,height/2.],center+np.r_[-right*width/2.,height/2.]]

    def _draw_display_screen(self) -> None:
        if not self.layout.get("display"): return
        frame=self._display_corners(False); image=self._display_corners(True)
        self.ax.add_collection3d(Poly3DCollection([frame],facecolors="#d9e0e3",edgecolors="#37474f",alpha=.55,zorder=10))
        self.ax.add_collection3d(Poly3DCollection([image],facecolors="#455a64",edgecolors="#263238",alpha=.35,zorder=11))
        center=np.mean(image,axis=0); diag_in=self.layout["display"].get("screen",{}).get("diag_in")
        label="Screen {:.0f} in".format(diag_in) if diag_in else "Screen"
        self.ax.text(*center,label,color="#263238",fontsize=7,ha="center",zorder=15)

    def _draw_display_projector(self) -> None:
        if not self.layout.get("display"): return
        p=self.layout["display"]["projector"]; x,y,z=p["position_m"]
        self.ax.bar3d(x-p["body_width_m"]/2.,y-p["body_depth_m"]/2.,z-p["body_height_m"]/2.,
                      p["body_width_m"],p["body_depth_m"],p["body_height_m"],color="#6d4c41",edgecolor="#263238",alpha=.95,zorder=16)
        lens=p["lens_position_m"]; self.ax.scatter([lens[0]],[lens[1]],[lens[2]],s=24,c="#ffca28",edgecolors="#263238",zorder=18)
        self.ax.text(x,y,z+p["body_height_m"],"Projector · {:.1f} fL".format(p["brightness"]["foot_lamberts"]),fontsize=7,ha="center")

    def _draw_display_beam(self) -> None:
        if not self.layout.get("display"): return
        lens=np.asarray(self.layout["display"]["projector"]["lens_position_m"],dtype=float); corners=self._display_corners(True)
        faces=[[lens,corners[i],corners[(i+1)%4]] for i in range(4)]
        self.ax.add_collection3d(Poly3DCollection(faces,facecolors="#fdd835",edgecolors="#f9a825",alpha=.09,zorder=4))

    def _draw_display_wedges(self) -> None:
        if not self.layout.get("display"): return
        corners=self._display_corners(True)
        for seat in self.layout.get("seats",[]):
            eye=np.r_[seat["position_m"],seat["ear_height_m"]]
            for corner in (corners[0],corners[1]):
                self.ax.plot([eye[0],corner[0]],[eye[1],corner[1]],[eye[2],corner[2]],color="#8e24aa",lw=.7,alpha=.45)

    def _draw_display_sightlines(self) -> None:
        if not self.layout.get("display"): return
        corners=self._display_corners(True)
        bottom=(corners[0]+corners[1])/2.
        for seat in self.layout.get("seats",[]):
            eye=np.r_[seat["position_m"],seat["ear_height_m"]]
            self.ax.plot([eye[0],bottom[0]],[eye[1],bottom[1]],[eye[2],bottom[2]],color="#00897b",lw=.8,alpha=.65)

    def _draw_ear_plane(self) -> None:
        room = np.asarray(self.layout["room_polygon_m"], dtype=float)
        z = float(self.layout["listener_m"][2])
        face = np.column_stack([room.T, np.full(4, z)])
        self.ax.add_collection3d(Poly3DCollection([face], facecolors="#e6b35c", alpha=.055,
                                                   edgecolors="none", zorder=2))

    def _draw_candidates(self) -> None:
        rows = self.layout.get("candidate_scores", [])
        if not rows: return
        room = np.asarray(self.layout["room_polygon_m"], dtype=float)
        by_type: dict[str, list[dict[str, Any]]] = {}
        for row in rows: by_type.setdefault(row["type"], []).append(row)
        for role, group in by_type.items():
            scores = np.array([r["score_db"] for r in group], dtype=float)
            spread = float(np.ptp(scores))
            normalized = (scores - float(scores.min())) / (spread if spread > 1e-9 else 1.)
            points = []
            for row in group:
                start, tangent, inward = wall_frame(room, row["wall_index"])
                xy = np.asarray(row["position_xy_m"])
                projected = start + float((xy - start) @ tangent) * tangent + .008 * inward
                points.append([projected[0], projected[1], row["height_m"]])
            coords = np.asarray(points)
            self.ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2], c=cm.viridis(normalized),
                            s=11, depthshade=False, alpha=.85, zorder=4)

    def _draw_coverage(self) -> None:
        for speaker in self.layout["speakers"]:
            if speaker.get("surface")=="ceiling": continue
            pose = pose_for_speaker(self.layout, speaker)
            origin = pose.front_center_m
            color = TYPE_COLORS.get(speaker["type"], "#607d8b")
            horizontal = float(speaker["coverage_h_deg"])
            vertical = float(speaker["coverage_v_deg"])
            if horizontal >= 350.:
                radius = .65
                angles = np.linspace(0, 2 * np.pi, 40)
                for axis_a, axis_b in ((pose.right_axis, pose.front_normal),
                                       (pose.up_axis, pose.front_normal)):
                    ring = origin + radius * (np.cos(angles)[:, None] * axis_a
                                              + np.sin(angles)[:, None] * axis_b)
                    self.ax.plot(ring[:, 0], ring[:, 1], ring[:, 2], color=color, alpha=.18, lw=.8)
                continue
            reach = min(1.5, max(self.layout["room_dimensions_m"][:2]) * .35)
            h_radius = min(reach * np.tan(np.radians(min(horizontal / 2., 82.))), 2.5)
            v_radius = min(reach * np.tan(np.radians(min(vertical / 2., 82.))), 1.5)
            end = origin + reach * pose.front_normal
            angles = np.linspace(0, 2 * np.pi, 17)
            ring = [end + h_radius * np.cos(a) * pose.right_axis
                    + v_radius * np.sin(a) * pose.up_axis for a in angles]
            faces = [[origin, ring[i], ring[i + 1]] for i in range(len(ring) - 1)]
            self.ax.add_collection3d(Poly3DCollection(faces, facecolors=color, alpha=.035,
                                                       edgecolors="none", zorder=3))

    def _draw_reflections(self) -> None:
        guidance=self.layout.get("first_reflections",[])
        if guidance:
            points=np.asarray([row["reflection_point_m"] for row in guidance],dtype=float)
            self.ax.scatter(points[:,0],points[:,1],points[:,2],marker="x",s=25,c="#d95f02",depthshade=False,zorder=10)
            for row,point in zip(guidance,points):
                self.ax.text(point[0],point[1],point[2]+.04,row["surface"],fontsize=6,color="#9a3d00")
        if not self.layout["speakers"]: return
        index = self.reflection_index
        speaker = self.layout["speakers"][index]
        source = (np.asarray(speaker["position_m"],dtype=float) if speaker.get("surface")=="ceiling"
                  else pose_for_speaker(self.layout, speaker).front_center_m)
        listener = np.asarray(self.layout["listener_m"], dtype=float)
        self.ax.plot([source[0], listener[0]], [source[1], listener[1]],
                     [source[2], listener[2]], color="#d95f02", lw=1.6, alpha=.9)
        room = np.asarray(self.layout["room_polygon_m"], dtype=float)
        height = float(self.layout["room_dimensions_m"][2])
        planes = [(np.array([room[0, 0], room[1, 0], 0.]), np.array([0., 0., 1.]), "#1b9e77")]
        planes.append((np.array([room[0, 0], room[1, 0], height]), np.array([0., 0., -1.]), "#7570b3"))
        for wall_index in range(room.shape[1]):
            start, _, inward = wall_frame(room, wall_index)
            planes.append((np.r_[start, 0.], np.r_[inward, 0.], "#66a61e"))
        for point, normal, color in planes:
            image = source - 2. * float((source - point) @ normal) * normal
            direction = listener - image
            denominator = float(direction @ normal)
            if abs(denominator) < 1e-12: continue
            fraction = float((point - image) @ normal) / denominator
            if not 0. < fraction < 1.: continue
            hit = image + fraction * direction
            if hit[2] < -1e-8 or hit[2] > height + 1e-8: continue
            if any(float((hit[:2] - wall_frame(room, j)[0]) @ wall_frame(room, j)[2]) < -1e-8
                   for j in range(room.shape[1])): continue
            path = np.vstack([source, hit, listener])
            self.ax.plot(path[:, 0], path[:, 1], path[:, 2], color=color, lw=1.1, alpha=.72)

    def _draw_treatment_panels(self) -> None:
        for row in self.layout.get("first_reflections",[]):
            center=np.asarray(row["reflection_point_m"],dtype=float); surface=row["surface"]
            if surface.startswith("wall "):
                index=int(surface.split()[1]); _,tangent,_=wall_frame(np.asarray(self.layout["room_polygon_m"]),index)
                horizontal=np.r_[tangent,0.]; vertical=np.array([0.,0.,1.])
            elif surface=="floor": horizontal=np.array([1.,0.,0.]); vertical=np.array([0.,1.,0.])
            else: horizontal=np.array([1.,0.,0.]); vertical=np.array([0.,1.,0.])
            corners=[center+sx*.6*horizontal+sy*.6*vertical for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))]
            self.ax.add_collection3d(Poly3DCollection([corners],facecolors="#ef8a62",edgecolors="#b23c17",alpha=.22,linewidths=.6,zorder=8))

    def _draw_equidistance_sphere(self) -> None:
        listener=np.asarray(self.layout["listener_m"],dtype=float)
        distances=[float(np.linalg.norm(np.asarray(item["position_m"],dtype=float)-listener)) for item in self.layout["speakers"]]
        if not distances: return
        radius=float(np.median(distances)); u=np.linspace(0,2*np.pi,32); v=np.linspace(0,np.pi,18)
        x=listener[0]+radius*np.outer(np.cos(u),np.sin(v)); y=listener[1]+radius*np.outer(np.sin(u),np.sin(v)); z=listener[2]+radius*np.outer(np.ones_like(u),np.cos(v))
        self.ax.plot_wireframe(x,y,z,color="#555555",linewidth=.35,alpha=.25)

    def _draw_speakers(self) -> None:
        listener = np.asarray(self.layout["listener_m"], dtype=float)
        for index, speaker in enumerate(self.layout["speakers"]):
            if speaker.get("surface")=="ceiling" and not self.state["overhead_speakers"]: continue
            if speaker.get("surface")=="floor":
                point=np.asarray(speaker["position_m"],dtype=float); color=TYPE_COLORS.get(speaker["type"],"#607d8b")
                width=float(speaker.get("width_m",.24)); depth=float(speaker.get("depth_m",.32)); height=float(speaker.get("height_m",.8))
                self.ax.bar3d(point[0]-width/2.,point[1]-depth/2.,max(0.,point[2]-height/2.),width,depth,height,
                              color=color,edgecolor="#263238",alpha=.88,linewidth=.7,shade=True,zorder=12)
                acoustic=np.asarray(speaker.get("acoustic_center_position_m",point),dtype=float)
                self.ax.scatter([acoustic[0]],[acoustic[1]],[acoustic[2]],color="#ffca28",edgecolors="#263238",s=13,zorder=16)
                if self.state["aim_arrows"]:
                    direction=np.asarray(speaker["aim_direction"],dtype=float); self.ax.quiver(*point,*(.55*direction),color=color,linewidth=1.5,arrow_length_ratio=.2,zorder=14)
                if self.state["labels"]: self.ax.text(point[0],point[1],point[2]+height/2.+.08,speaker.get("channel","bass"),fontsize=7,ha="center",color="#263238")
                continue
            if speaker.get("surface")=="ceiling":
                point=np.asarray(speaker["position_m"],dtype=float); color=TYPE_COLORS.get(speaker["type"],"#607d8b")
                half_w=float(speaker.get("width_m",.22))/2.; half_h=float(speaker.get("height_m",.22))/2.
                corners=[[point[0]-half_w,point[1]-half_h,point[2]],[point[0]+half_w,point[1]-half_h,point[2]],
                         [point[0]+half_w,point[1]+half_h,point[2]],[point[0]-half_w,point[1]+half_h,point[2]]]
                self.ax.add_collection3d(Poly3DCollection([corners],facecolors=color,edgecolors="#263238",alpha=.9,zorder=14))
                direction=np.asarray(speaker["aim_direction"],dtype=float)
                self.ax.quiver(*point,*(.55*direction),color=color,linewidth=1.8,arrow_length_ratio=.2,zorder=15)
                if self.state["listener_lines"]: self.ax.plot([point[0],listener[0]],[point[1],listener[1]],[point[2],listener[2]],ls="--",lw=.8,color=color,alpha=.55,zorder=5)
                if self.state["labels"]:
                    channel=str(speaker.get("channel",""))
                    side=-1. if channel.startswith("L") else 1.
                    fore=1. if channel.endswith("tf") or channel.endswith("tm") else -1.
                    offset=np.array([.55*side,.48*fore,.12+.04*(index%2)])
                    anchor=point+np.array([.08*direction[0],.08*direction[1],0.])+offset
                    self.ax.plot([point[0],anchor[0]],[point[1],anchor[1]],[point[2],anchor[2]],color="#455a64",lw=.55,zorder=14)
                    self.ax.text(*anchor,speaker.get("channel",speaker["type"]),fontsize=8,color="#263238",zorder=15)
                continue
            pose = pose_for_speaker(self.layout, speaker)
            color = TYPE_COLORS.get(speaker["type"], "#607d8b")
            shade = _lighten(color, .18)
            facecolors = [_lighten(color, .55), shade, color, color, shade, color]
            collection = Poly3DCollection(pose.faces(), facecolors=facecolors,
                                          edgecolors="#273238", linewidths=.65,
                                          alpha=1., zorder=12)
            self.ax.add_collection3d(collection)
            front_center = pose.front_center_m
            self.ax.scatter([front_center[0]], [front_center[1]], [front_center[2]],
                            color="#1b1b1b", s=18, depthshade=False, zorder=13)
            acoustic=np.asarray(speaker.get("acoustic_center_position_m",front_center),dtype=float)
            self.ax.scatter([acoustic[0]],[acoustic[1]],[acoustic[2]],color="#ffca28",edgecolors="#263238",s=13,depthshade=False,zorder=16)
            if self.state["aim_arrows"]:
                vector = pose.front_normal * .55
                self.ax.quiver(*front_center, *vector, color=color, linewidth=1.8,
                               arrow_length_ratio=.22, zorder=14)
            if self.state["listener_lines"]:
                self.ax.plot([front_center[0], listener[0]], [front_center[1], listener[1]],
                             [front_center[2], listener[2]], ls="--", lw=.8,
                             color=color, alpha=.55, zorder=5)
            if self.state["labels"]:
                offset=np.array([((index%4)-1.5)*.34,((index//4)%3-1)*.28,.28+.13*(index%3)])
                anchor=front_center+.12*pose.front_normal+offset
                self.ax.plot([front_center[0],anchor[0]],[front_center[1],anchor[1]],[front_center[2],anchor[2]],color="#455a64",lw=.45,zorder=14)
                # Keep labels short; full model and XYZ detail live in the
                # speaker table, while the leader identifies this box.
                text=speaker.get("channel",speaker["type"])
                self.ax.text(*anchor, text, fontsize=8, color="#263238", zorder=15,
                             bbox={"facecolor": "white", "edgecolor": "none", "alpha": .7, "pad": 1.5})

    def _draw_listener(self) -> None:
        listener = np.asarray(self.layout["listener_m"], dtype=float)
        u, v = np.mgrid[0:2 * np.pi:14j, 0:np.pi:9j]
        radius = .095
        x = listener[0] + radius * np.cos(u) * np.sin(v)
        y = listener[1] + radius * np.sin(u) * np.sin(v)
        z = listener[2] + radius * np.cos(v)
        self.ax.plot_surface(x, y, z, color="#f2c899", alpha=1., linewidth=0, shade=True,
                             zorder=11)
        self.ax.plot([listener[0], listener[0]], [listener[1], listener[1]],
                     [listener[2] - .12, listener[2] - .55], color="#263238", lw=4.)
        facing = FACING[self.layout["facing"]]
        self.ax.quiver(listener[0], listener[1], listener[2], facing[0] * .55,
                       facing[1] * .55, 0., color="#d39f00", linewidth=2.,
                       arrow_length_ratio=.2)
        if self.state["labels"]:
            self.ax.text(listener[0], listener[1], listener[2] + .18, "Listener", fontsize=8,
                         color="#3e3e3e", ha="center")

    def _draw_seats(self) -> None:
        fwd=FACING[self.layout["facing"]]; right=np.array([fwd[1],-fwd[0]])
        for seat in self.layout.get("seats",[]):
            xy=np.asarray(seat["position_m"],dtype=float); z=float(seat["ear_height_m"])-.55
            corners=[np.r_[xy-.20*right-.20*fwd,z],np.r_[xy+.20*right-.20*fwd,z],
                     np.r_[xy+.20*right+.20*fwd,z],np.r_[xy-.20*right+.20*fwd,z]]
            self.ax.plot(*np.asarray(corners+[corners[0]]).T,color="#455a64",lw=1.2,zorder=8)
            upper=np.asarray([corners[2],corners[3]])+np.array([0.,0.,.55])
            self.ax.plot([corners[2][0],upper[0][0]],[corners[2][1],upper[0][1]],[corners[2][2],upper[0][2]],color="#455a64",lw=1.2,zorder=8)
            self.ax.plot([corners[3][0],upper[1][0]],[corners[3][1],upper[1][1]],[corners[3][2],upper[1][2]],color="#455a64",lw=1.2,zorder=8)
            self.ax.plot([upper[0][0],upper[1][0]],[upper[0][1],upper[1][1]],[upper[0][2],upper[1][2]],color="#455a64",lw=1.2,zorder=8)
            self.ax.scatter([xy[0]],[xy[1]],[seat["ear_height_m"]],s=12,c="#d39f00",zorder=9)
            if self.state["labels"]: self.ax.text(xy[0],xy[1],seat["ear_height_m"]+.04,"{}:{}".format(seat["row"],seat["seat"]),fontsize=6,color="#455a64")

    def _finish_axes(self) -> None:
        room = np.asarray(self.layout["room_polygon_m"], dtype=float)
        height = float(self.layout["room_dimensions_m"][2])
        xmin, xmax = float(room[0].min()), float(room[0].max())
        ymin, ymax = float(room[1].min()), float(room[1].max())
        self.ax.set(xlim=(xmin - .18, xmax + .18), ylim=(ymin - .18, ymax + .18),
                    zlim=(0., height + .18), xlabel="x (ft)", ylabel="y (ft)", zlabel="z (ft)")
        self.ax.set_box_aspect((xmax - xmin, ymax - ymin, height))
        formatter = FuncFormatter(lambda value, _pos: "{:.0f}".format(value / FT))
        self.ax.set_xticks(np.arange(np.ceil(xmin/FT)*FT,xmax+.5*FT,FT))
        self.ax.set_yticks(np.arange(np.ceil(ymin/FT)*FT,ymax+.5*FT,FT))
        self.ax.set_zticks(np.arange(0.,height+.5*FT,FT))
        self.ax.xaxis.set_major_formatter(formatter)
        self.ax.yaxis.set_major_formatter(formatter)
        self.ax.zaxis.set_major_formatter(formatter)
        lx, ly, h = self.layout["room_dimensions_ft"]
        self.ax.set_title("3D speaker layout — {:.1f} × {:.1f} × {:.1f} ft · facing {}".format(
            lx, ly, h, self.layout["facing"]), pad=14)
        self.ax.grid(False)
        self.ax.xaxis.pane.set_alpha(0.)
        self.ax.yaxis.pane.set_alpha(0.)
        self.ax.zaxis.pane.set_alpha(0.)

    def save_png(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.fig.savefig(target, dpi=170, bbox_inches="tight")
        print("3D view saved:", target)
        return target

    def save_presets(self) -> list[Path]:
        elev, azim = float(self.ax.elev), float(self.ax.azim)
        paths = []
        for name in ("top", "front", "side", "perspective"):
            self.set_view(name)
            paths.append(self.save_png(self.output_dir / ("layout_3d_" + name + ".png")))
        self.elev, self.azim = elev, azim
        self.render(preserve_camera=False)
        return paths


def open_viewer(layout: dict[str, Any], output_dir: str | Path = "output", *,
                show: bool = True, save_views: bool = False,
                elev: float | None = None, azim: float | None = None,
                show_coverage: bool = False, show_candidates: bool = False,
                reflection_index: int | None = None) -> Viewer3D:
    viewer = Viewer3D(layout, output_dir, elev=elev, azim=azim,
                      show_coverage=show_coverage, show_candidates=show_candidates,
                      reflection_index=reflection_index)
    viewer.save_png(Path(output_dir) / "layout_3d.png")
    interactive = interactive_backend_available()
    if save_views or (show and not interactive): viewer.save_presets()
    if not show:
        plt.close(viewer.fig)
    elif not interactive:
        print("Interactive 3D window unavailable with backend '{}'. Saved layout_3d.png and preset views. "
              "Use an interactive backend such as TkAgg or QtAgg with a display, or unset MPLBACKEND=Agg.".format(matplotlib.get_backend()))
        plt.close(viewer.fig)
    else:
        try:
            plt.show()
        except Exception as exc:
            viewer.save_presets()
            print("Could not open an interactive window ({}). PNG views were saved. "
                  "Check Tk/PyQt and your display or set MPLBACKEND to an interactive backend.".format(exc))
            plt.close(viewer.fig)
    return viewer
