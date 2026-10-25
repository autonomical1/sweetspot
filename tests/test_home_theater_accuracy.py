import numpy as np
import pytest

from speakerplacer.home_theater import (
    channel_layout_specs,
    compare_sub_strategies,
    first_reflection_guidance,
    seating_grid,
)
from speakerplacer.room import make_room


def test_seating_grid_selects_requested_mlp_and_tracks_riser_height():
    seats, mlp, ear = seating_grid(
        "rows=2,seats=3,seat_spacing=0.7,row_spacing=1.1,riser=0.2,ear_height=1.1",
        "row=2,seat=3", (2.5, 2.5), "north", 1.0,
    )
    assert len(seats) == 6
    assert np.allclose(mlp, seats[-1]["position_m"])
    assert ear == 1.3


def test_first_reflection_guidance_contains_points_and_panel_advice():
    room = make_room(18, 14)
    source = np.array([2.0, 3.0, 1.0])
    listener = np.array([2.5, 2.0, 1.0])
    rows = first_reflection_guidance(room, source, listener, 2.7)
    assert rows
    assert all(len(row["reflection_point_m"]) == 3 for row in rows)
    assert all("panel" in row and "reflection_point_ft" in row for row in rows)


def test_reference_sub_strategies_include_optimizer_and_dba():
    room = make_room(18, 14)
    rows = compare_sub_strategies(room, [[2.2, 2.2], [2.4, 2.2]], free_sources=[[1.0, 2.0]])
    names = {row["strategy"] for row in rows}
    assert "optimizer placement" in names
    assert "delayed inverted rear array" in names
    assert all(np.isfinite(row["seat_std_db"]) for row in rows)
    corners=next(row for row in rows if row["strategy"]=="front corners")
    assert corners["normalization"]=="equal total electrical power"
    assert corners["source_gains_db"]==pytest.approx([-3.0103,-3.0103])
    assert all("cancellation_cost_db" in row and row["null_depth_db"]<=0 for row in rows)


def test_surround_height_candidates_obey_channel_elevation_window():
    from speakerplacer.optimize import _legal_height_grid
    from speakerplacer.speaker_models import DEFAULT_SPEAKER_MODELS
    layout,_=channel_layout_specs("7.1.4","dolby")
    left=next(spec for spec in layout if spec.channel_name=="Lss")
    room=make_room(18,14); listener=np.array([9.,5.])*0.3048
    source=np.array([0.001,5.*0.3048])
    heights=_legal_height_grid(left.name,DEFAULT_SPEAKER_MODELS[left.model_id],listener,source,9.*0.3048,
                               3.6*0.3048,elevation_range_deg=left.elevation_range_deg)
    elevations=np.degrees(np.arctan2(heights-3.6*0.3048,np.linalg.norm(source-listener)))
    assert len(heights)>0
    assert elevations.min()>=-1e-6 and elevations.max()<=15.+1e-6


def test_wall_sub_height_grid_spans_room_with_cabinet_clearance():
    from speakerplacer.optimize import _legal_height_grid
    from speakerplacer.speaker_models import resolve_model
    model=resolve_model("generic_inwall_sub")
    heights=_legal_height_grid("bass",model,np.array([2.,2.]),np.array([1.,2.]),2.7432,.95)
    assert heights.min()<=model.height_m/2.+.02
    assert heights.max()>=2.7432-model.height_m/2.-.02


def test_center_toe_is_directed_at_mlp():
    from speakerplacer.candidates import Candidate
    from speakerplacer.optimize import _toe_toward_listener
    listener=np.array([2.,3.]); candidate=Candidate(np.array([1.,4.]),np.array([0.,1.]),0,.5)
    toe=_toe_toward_listener(candidate,listener)
    theta=np.radians(toe); normal=candidate.normal
    aim=np.array([normal[0]*np.cos(theta)-normal[1]*np.sin(theta),normal[0]*np.sin(theta)+normal[1]*np.cos(theta)])
    assert np.dot(aim,(listener-candidate.position)/np.linalg.norm(listener-candidate.position))>0.999999


def test_full_height_room_modes_detect_18_by_14_by_9_coincidence():
    from speakerplacer.scoring import room_modes_3d
    rows=room_modes_3d(make_room(18,14),9*.3048,(20.,100.))
    axial=next(row for row in rows if (row["n"],row["m"],row["l"])==(2,0,0))
    vertical=next(row for row in rows if (row["n"],row["m"],row["l"])==(0,0,1))
    assert abs(axial["frequency_hz"]-vertical["frequency_hz"])<.1
    assert axial["near_coincident"] and vertical["near_coincident"]


def test_treatment_presets_allow_surface_overrides():
    from speakerplacer.room_acoustics import parse_materials
    treated=parse_materials(None,"treated_theater")
    assert treated.walls=="acoustic_panels" and treated.floor=="carpet"
    overridden=parse_materials("floor=tile","treated_theater")
    assert overridden.walls=="acoustic_panels" and overridden.floor=="tile"


def test_72_4_preset_has_two_jointly_optimized_subs():
    layout,overhead=channel_layout_specs("7.2.4","dolby")
    bass=next(item for item in layout if item.name=="bass")
    assert bass.count==2 and not bass.symmetric
    assert len(overhead)==4


def test_stud_bay_snap_and_clearance_flags_header_need():
    from speakerplacer.candidates import Candidate,snap_wall_candidate_to_bay
    room=make_room(18,14); point=Candidate(np.array([1.03,.001]),np.array([0.,1.]),0,.2)
    snapped=snap_wall_candidate_to_bay(point,room,.6096,.0381,.46)
    assert snapped.position[0] == pytest.approx(.9144,abs=1e-6)
    with pytest.raises(ValueError,match="needs header"):
        snap_wall_candidate_to_bay(point,room,.4064,.0381,.46)


def test_ceiling_joist_bays_fit_cutout_and_can_flag_header():
    from speakerplacer.candidates import ceiling_bay_centers
    centers=ceiling_bay_centers(make_room(18,14),.4064,.0381,.22)
    assert centers and all((point[0]-.2032)/.4064 == pytest.approx(round((point[0]-.2032)/.4064)) for point in centers)
    with pytest.raises(ValueError,match="needs header"):
        ceiling_bay_centers(make_room(18,14),.254,.0381,.22)


def test_acoustic_center_offset_moves_source_and_changes_vertical_aim():
    from dataclasses import replace
    from speakerplacer.speaker_models import resolve_model
    from speakerplacer.viewer3d import build_layout
    from speakerplacer.optimize import OptimizationResult
    model=replace(resolve_model("generic_bookshelf_onwall"),acoustic_center_offset_m=(.08,.03))
    room=make_room(18,14); position=np.array([2.0,4.0]); listener=np.array([2.4,3.0])
    normal=np.array([0.,1.])
    result=OptimizationResult({"speakers":[{"type":"front","channel":"L","model_id":model.model_id,
        "position_m":position,"position_ft":position/.3048,"height_m":1.2,"height_range_m":[.5,2.],
        "wall_index":0,"wall_t":.5,"normal":normal,"aim_direction":normal,"toe_in_deg":0.,
        "predicted_spl_db":90.,"headroom_db":1.}]},[],[],{},room,listener)
    scene=build_layout(result,{model.model_id:model},2.7,1.1)
    speaker=scene["speakers"][0]
    assert speaker["acoustic_center_position_m"][2] == pytest.approx(1.28)
    assert speaker["acoustic_center_offset_m"] == pytest.approx([.08,.03])


def test_dummy_acoustically_transparent_screen_applies_frequency_loss():
    from speakerplacer.home_theater import screen_transmission_loss_db
    curve={125.:1.,250.:2.,1000.:4.}
    assert screen_transmission_loss_db(np.array([125.,500.,1000.]),curve) == pytest.approx([1.,3.,4.])
    assert screen_transmission_loss_db(1000.,{}) == 0.


def test_bass_management_sweep_returns_per_seat_magnitude_and_phase():
    from speakerplacer.home_theater import optimize_bass_management
    from speakerplacer.speaker_models import resolve_model,DEFAULT_MODEL_BY_ROLE
    models={v:resolve_model(v) for v in DEFAULT_MODEL_BY_ROLE.values()}
    front=resolve_model(DEFAULT_MODEL_BY_ROLE["front"]); bass=resolve_model(DEFAULT_MODEL_BY_ROLE["bass"])
    speakers=[{"type":"front","channel":"L","model_id":front.model_id,"position_m":[1.,3.,1.1]},
              {"type":"bass","channel":"LFE","model_id":bass.model_id,"position_m":[2.,2.,.3]}]
    seats=[{"row":1,"seat":1,"position_m":[2.,4.],"ear_height_m":1.1}]
    result=optimize_bass_management(speakers,seats,models,(80.,80.),(0.,0.),(0.,0.),21)
    assert result["status"]=="estimated"
    assert len(result["seat_response_db"])==len(result["seat_phase_deg"])==1
    assert len(result["frequencies_hz"])==21


def test_floor_mount_search_respects_clearance_and_reports_sbir():
    from speakerplacer.home_theater import floor_mount_alternatives
    from speakerplacer.speaker_models import DEFAULT_SPEAKER_MODELS
    room=make_room(18,14); seats=[{"row":1,"seat":1,"position_m":[2.74,1.52],"ear_height_m":1.1}]
    wall=[{"channel":"L","type":"front","position_m":[1.,3.,1.1]},
          {"channel":"C","type":"center","position_m":[2.,3.,1.1]},
          {"channel":"R","type":"front","position_m":[3.,3.,1.1]}]
    rows=floor_mount_alternatives(wall,room,seats,DEFAULT_SPEAKER_MODELS,"dolby","north")
    assert len(rows)==3
    assert all(row.get("surface")=="floor" and row["nearest_boundary_distance_m"]>=.3 for row in rows)
    assert all(row["first_boundary_notch_hz"]>0 for row in rows)


def test_headroom_hand_calculation_caps_peak_and_uses_positive_margin_sign():
    from speakerplacer.optimize import _headroom
    from speakerplacer.speaker_models import SpeakerModel
    model=SpeakerModel("hand",sensitivity_db=87.,rated_power_w=80.,max_spl_db=108.)
    available,headroom=_headroom(model,2.,85.,20.,"front")
    expected=min(87.+10*np.log10(80.)-20*np.log10(2.),108.-20*np.log10(2.))
    assert available==pytest.approx(expected)
    assert headroom==pytest.approx(expected-105.)
    assert headroom<0. # Negative means the required peak is not available.


def test_bass_position_grid_includes_wall_floor_ceiling_and_corners():
    from speakerplacer.candidates import generate_candidates,generate_horizontal_surface_candidates
    from speakerplacer.speaker_models import resolve_model
    room=make_room(18,14); model=resolve_model("generic_floor_sub")
    surfaces={item.surface for item in generate_horizontal_surface_candidates(room,9*.3048,model,.25)}
    assert surfaces=={"floor","ceiling","corner"}
    walls=generate_candidates(room,.25)
    assert walls and all(point.surface=="wall" for point in walls)


def test_projector_obstacle_rejects_intersecting_wall_speaker_candidate():
    from speakerplacer.candidates import Candidate
    from speakerplacer.optimize import _overlaps_forbidden_box
    from speakerplacer.speaker_models import resolve_model
    model=resolve_model("generic_bookshelf_onwall")
    candidate=Candidate(np.array([2.,0.]),np.array([0.,1.]),0,.5,height_m=1.2)
    obstacle={"center_m":[2.,.1,1.2],"dimensions_m":[.5,.3,.2],"clearance_m":.1}
    clear={"center_m":[4.,.1,1.2],"dimensions_m":[.5,.3,.2],"clearance_m":.1}
    assert _overlaps_forbidden_box(candidate,model,1.2,[obstacle])
    assert not _overlaps_forbidden_box(candidate,model,1.2,[clear])


@pytest.mark.parametrize(("model_id","expected_surface"),[("generic_floor_sub","floor"),("generic_ceiling_sub","ceiling")])
def test_joint_sub_optimizer_honors_floor_or_ceiling_mount_type(model_id,expected_surface):
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    from speakerplacer.speaker_models import DEFAULT_SPEAKER_MODELS
    from speakerplacer.viewer3d import build_layout
    room=make_room(18,14)
    result=optimize_layout(room,np.array([9.,5.])*.3048,
        parse_speaker_layout(["bass:1:"+model_id]),spacing_m=.5,refinement_sweeps=0,
        room_height_m=9*.3048,modal_step_hz=5.)
    assert result.best_pair["speakers"][0]["surface"]==expected_surface
    scene=build_layout(result,DEFAULT_SPEAKER_MODELS,9*.3048,1.1)
    assert scene["speakers"][0]["surface"]==expected_surface
