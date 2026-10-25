"""Geometry and headless interaction checks for the primary 3D viewer."""
from types import SimpleNamespace
import json

import matplotlib
matplotlib.use("Agg", force=True)
import numpy as np
import pytest

from speakerplacer.room import make_room, feet_to_m
from speakerplacer.speaker_models import DEFAULT_SPEAKER_MODELS
from speakerplacer.viewer3d import (Viewer3D, box_pose, build_layout, load_layout,
                                     front_wall_index, open_viewer, pose_for_speaker,
                                     save_layout, wall_frame)


def _sample_layout():
    room = make_room(15, 12)
    normal = np.array([0., -1.])
    yaw = np.radians(25.)
    speakers = []
    for x, toe in ((feet_to_m(3.4), 25.), (feet_to_m(11.6), -25.)):
        angle = np.radians(toe)
        aim = np.array([normal[0] * np.cos(angle) - normal[1] * np.sin(angle),
                        normal[0] * np.sin(angle) + normal[1] * np.cos(angle)])
        speakers.append({"type": "front", "model_id": "generic_bookshelf_onwall",
                         "position_m": np.array([x, room[1, 2] - .05]),
                         "wall_index": 2, "aim_direction": aim, "toe_in_deg": toe,
                         "predicted_spl_db": 100., "headroom_db": -12., "warnings": []})
    result = SimpleNamespace(room_polygon_m=room, listener_m=np.array([feet_to_m(7.5), feet_to_m(4)]),
                             facing="north", best_pair={"speakers": speakers},
                             candidate_scores=[{"type": "front", "wall_index": 2,
                                                "position_m": speakers[0]["position_m"], "score_db": 2.}],
                             warnings=[])
    return build_layout(result, DEFAULT_SPEAKER_MODELS, feet_to_m(8), feet_to_m(3.6))


def _assert_inside(room, height, pose):
    for wall_index in range(4):
        start, _, inward = wall_frame(room, wall_index)
        assert np.min((pose.vertices_m[:, :2] - start) @ inward) >= -1e-9
    assert pose.vertices_m[:, 2].min() >= -1e-9
    assert pose.vertices_m[:, 2].max() <= height + 1e-9


@pytest.mark.parametrize("wall_index", range(4))
def test_box_geometry_mount_contact_size_and_aim(wall_index):
    room = make_room(15, 12); height = feet_to_m(8)
    start, tangent, normal = wall_frame(room, wall_index)
    wall_length = np.linalg.norm(room[:, (wall_index + 1) % 4] - start)
    center = start + wall_length / 2 * tangent
    pose = box_pose(room, height, wall_index, center, 1.2, .3, .2, .15, normal)
    depths = (pose.vertices_m[:4, :2] - start) @ normal
    assert np.max(np.abs(depths)) < 1e-9  # zero toe/pitch: whole back face flush
    assert np.linalg.norm(pose.vertices_m[1] - pose.vertices_m[0]) == pytest.approx(.3)
    assert np.linalg.norm(pose.vertices_m[3] - pose.vertices_m[0]) == pytest.approx(.2)
    assert np.linalg.norm(pose.vertices_m[4] - pose.vertices_m[0]) == pytest.approx(.15)
    assert pose.front_normal == pytest.approx(np.r_[normal, 0.], abs=1e-9)
    _assert_inside(room, height, pose)
    # At nonzero toe/pitch, a rigid back face pivots: one back corner touches.
    rotation = np.radians(27.)
    aim = np.array([normal[0] * np.cos(rotation) - normal[1] * np.sin(rotation),
                    normal[0] * np.sin(rotation) + normal[1] * np.cos(rotation)])
    tilted = box_pose(room, height, wall_index, center, 1.2, .3, .2, .15, aim, 12.)
    assert np.min((tilted.vertices_m[:4, :2] - start) @ normal) == pytest.approx(0., abs=1e-9)
    expected = np.r_[aim * np.cos(np.radians(12.)), np.sin(np.radians(12.))]
    front_face = tilted.faces()[1]
    derived_normal = np.cross(front_face[1] - front_face[0], front_face[3] - front_face[0])
    derived_normal /= np.linalg.norm(derived_normal)
    assert tilted.front_normal == pytest.approx(expected, abs=1e-9)
    assert derived_normal == pytest.approx(expected, abs=1e-9)
    _assert_inside(room, height, tilted)


def test_pair_symmetry_and_rotation_of_box_poses():
    layout = _sample_layout()
    a, b = [pose_for_speaker(layout, speaker) for speaker in layout["speakers"]]
    center_x = feet_to_m(15) / 2.
    reflected = a.vertices_m.copy(); reflected[:, 0] = 2 * center_x - reflected[:, 0]
    assert np.sort(reflected, axis=0) == pytest.approx(np.sort(b.vertices_m, axis=0), abs=1e-9)
    room = np.asarray(layout["room_polygon_m"])
    source = a.mount_position_m[:2]
    turn = np.array([[0., -1.], [1., 0.]])
    rotated_room = turn @ room
    rotated_aim = turn @ np.asarray(layout["speakers"][0]["aim_xy"])
    rotated = box_pose(rotated_room, layout["room_dimensions_m"][2], 2, turn @ source,
                       a.mount_position_m[2], layout["speakers"][0]["width_m"],
                       layout["speakers"][0]["height_m"], layout["speakers"][0]["visible_depth_m"],
                       rotated_aim, layout["speakers"][0]["pitch_deg"])
    expected = a.vertices_m.copy(); expected[:, :2] = (turn @ a.vertices_m[:, :2].T).T
    assert rotated.vertices_m == pytest.approx(expected, abs=1e-9)
    _assert_inside(rotated_room, layout["room_dimensions_m"][2], rotated)


def test_all_four_facing_directions_select_the_correct_front_wall():
    room = make_room(15, 12); height = feet_to_m(8)
    for facing, expected_index in (("north", 2), ("south", 0), ("east", 1), ("west", 3)):
        index = front_wall_index(room, facing)
        assert index == expected_index
        start, tangent, inward = wall_frame(room, index)
        length = np.linalg.norm(room[:, (index + 1) % 4] - start)
        pose = box_pose(room, height, index, start + length / 2 * tangent,
                        1.1, .3, .2, .15, inward)
        assert pose.front_normal[:2] == pytest.approx(inward)
        _assert_inside(room, height, pose)


def test_saved_layout_round_trip_and_headless_widgets(tmp_path, capsys):
    layout = _sample_layout()
    path = save_layout(layout, tmp_path / "layout.json", tmp_path / "candidates.json")
    restored = load_layout(path)
    assert restored["schema_version"] == 2
    assert restored["definitions"]["wall_index"].startswith("zero-based")
    assert restored["candidate_scores"]
    assert len({round(row["height_m"],3) for row in layout["candidate_scores"]})>1
    lower_ear=_sample_layout()
    result=SimpleNamespace(room_polygon_m=make_room(15,12),listener_m=np.array([feet_to_m(7.5),feet_to_m(4)]),facing="north",
        best_pair={"speakers":[{"type":"front","model_id":"generic_bookshelf_onwall","position_m":np.array([1.,3.6]),
            "wall_index":2,"aim_direction":np.array([0.,-1.]),"toe_in_deg":0.}]},candidate_scores=[],warnings=[])
    high_ear=build_layout(result,DEFAULT_SPEAKER_MODELS,feet_to_m(8),feet_to_m(4.2))
    assert high_ear["speakers"][0]["position_m"][2]>lower_ear["speakers"][0]["position_m"][2]
    assert "candidate_scores" not in json.loads(path.read_text())
    for original, copied in zip(layout["speakers"], restored["speakers"]):
        assert pose_for_speaker(layout, original).vertices_m == pytest.approx(
            pose_for_speaker(restored, copied).vertices_m, abs=1e-9)
    viewer = Viewer3D(restored, tmp_path)
    assert viewer.state["floor_alternatives"] is False
    assert viewer.state["overhead_speakers"] is False
    viewer.set_toggle("floor_alternatives", True)
    viewer.set_toggle("overhead_speakers", True)
    for key in viewer.state:
        viewer.set_toggle(key, not viewer.state[key])
    for preset in ("top", "front", "side", "perspective"):
        viewer.set_view(preset)
    viewer.save_png(tmp_path / "widget_smoke.png")
    assert (tmp_path / "widget_smoke.png").exists()
    import matplotlib.pyplot as plt
    plt.close(viewer.fig)
    open_viewer(restored, tmp_path / "fallback", show=True)
    captured = capsys.readouterr().out
    assert "Interactive 3D window unavailable" in captured
    assert all((tmp_path / "fallback" / ("layout_3d_" + name + ".png")).exists()
               for name in ("top", "front", "side", "perspective"))


def test_view_layout_cli_skips_optimizer(tmp_path, monkeypatch):
    from speakerplacer import cli
    path = save_layout(_sample_layout(), tmp_path / "layout.json")
    monkeypatch.setattr(cli, "optimize_layout", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("--view-layout must not optimize")))
    cli.main(["--view-layout", str(path), "--no-show", "--output", str(tmp_path / "reopened")])
    assert (tmp_path / "reopened" / "layout_3d.png").exists()


def test_saved_layout_loads_flush_ceiling_channels(tmp_path):
    layout=_sample_layout()
    layout["speakers"].append({"type":"height","channel":"Ltf","model_id":"generic_in_ceiling",
        "surface":"ceiling","position_m":[2.,3.,layout["room_dimensions_m"][2]],
        "wall_index":-1,"wall_t":0.,"wall_u_m":None,"aim_direction":[0.,0.,-1.],"aim_xy":[0.,1.],
        "normal":[0.,1.],"yaw_deg":0.,"pitch_deg":-90.,"width_m":.22,"height_m":.22,
        "depth_m":.10,"visible_depth_m":.10,"height_m":layout["room_dimensions_m"][2],
        "coverage_h_deg":100.,"coverage_v_deg":100.,"position_ft":[6.56,9.84,8.]})
    path=save_layout(layout,tmp_path/"with-ceiling.json")
    restored=load_layout(path)
    assert restored["speakers"][-1]["surface"]=="ceiling"


def test_display_scene_layers_render_and_toggle(tmp_path):
    layout=_sample_layout()
    layout["display"]={"screen":{"center_m":[2.,3.,1.3],"geometry":{"width_m":2.,"height_m":1.2,"image_width_m":2.,"image_height_m":1.125}},
        "projector":{"position_m":[2.,1.,1.3],"lens_position_m":[2.,1.,1.3],"body_width_m":.35,"body_depth_m":.3,"body_height_m":.15,
            "brightness":{"foot_lamberts":16.}}}
    viewer=Viewer3D(layout,tmp_path)
    assert viewer.state["screen_display"] and viewer.state["projector_beam"]
    viewer.set_toggle("sightlines",True); viewer.set_toggle("view_wedges",True)
    viewer.save_png(tmp_path/"display.png")
    assert (tmp_path/"display.png").exists()
    import matplotlib.pyplot as plt
    plt.close(viewer.fig)
