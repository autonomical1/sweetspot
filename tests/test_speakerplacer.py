import numpy as np
import pytest
from speakerplacer.room import make_room,feet_to_m,default_listener
from speakerplacer.candidates import generate_candidates,facing_wall_index,mirror_candidate
from speakerplacer.optimize import optimize_speakers

def test_unit_conversion():
    assert feet_to_m(15)==pytest.approx(4.572)

def test_spl_prediction_matches_hand_calculation_and_2v83_basis():
    from speakerplacer.speaker_models import SpeakerModel, predicted_spl_db
    model=SpeakerModel("hand",sensitivity_db=88.,rated_power_w=100.,amp_power_w=50.,wall_gain_db=3.)
    expected=88.+10*np.log10(50.)-20*np.log10(2.)+3.
    assert predicted_spl_db(model,2.)==pytest.approx(expected)
    voltage_model=SpeakerModel("voltage",sensitivity_db=91.,sensitivity_basis="2.83V_1m",nominal_impedance_ohm=4.)
    assert voltage_model.sensitivity_1w_1m_db==pytest.approx(91.-10*np.log10(2.))

def test_analytic_angle_fan_includes_exact_ray():
    from speakerplacer.optimize import _analytic_angle_candidates
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    spec=parse_speaker_layout(["front:2"])[0]
    candidates=_analytic_angle_candidates(p,listener,"north",spec,.3,.05)
    assert candidates
    assert min(abs(abs(__import__("speakerplacer.scoring",fromlist=["angle_to_facing"]).angle_to_facing(c.position,listener,"north"))-30.) for c in candidates)<.2

def test_polar_table_interpolates_angle_and_frequency():
    from speakerplacer.speaker_models import SpeakerModel
    model=SpeakerModel("polar",polar_table=[
        {"angle_deg":0,"500":0,"1000":0},
        {"angle_deg":30,"500":-6,"1000":-12},
    ])
    assert model.gain_db(30,frequency_hz=1000)==pytest.approx(-12.)
    assert model.gain_db(15,frequency_hz=1000)==pytest.approx(-6.)
    assert model.gain_db(30,frequency_hz=np.sqrt(500*1000))==pytest.approx(-9.)

def test_cli_model_wizard_writes_valid_yaml(tmp_path,monkeypatch):
    import builtins
    from dataclasses import fields
    from speakerplacer.cli import main
    from speakerplacer.speaker_models import SpeakerModel,load_models_file
    answers=iter(["wizard_test"]+[""]*(len(fields(SpeakerModel))-1))
    monkeypatch.setattr(builtins,"input",lambda _prompt:next(answers))
    path=tmp_path/"custom_models.yaml"
    main(["--new-model","--models-file",str(path)])
    models,_=load_models_file(str(path))
    assert models["wizard_test"].model_id=="wizard_test"
    assert models["wizard_test"].sensitivity_basis=="1W_1m"

def test_toe_in_bounds_are_signed():
    from speakerplacer.optimize import _toe_grid
    from speakerplacer.speaker_models import resolve_model
    values=_toe_grid(resolve_model("generic_bookshelf_onwall"),bounds=(-20.,35.))
    assert min(values)==pytest.approx(-20.) and max(values)==pytest.approx(35.)
    inwall_values=_toe_grid(resolve_model("generic_inwall_lcr"),bounds=(-15.,20.))
    assert min(inwall_values)==pytest.approx(-15.) and max(inwall_values)==pytest.approx(20.)

def test_dipole_surround_searches_listener_near_null():
    from speakerplacer.candidates import Candidate
    from speakerplacer.optimize import optimize_layout,_directivity_angle
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    result=optimize_layout(p,listener,parse_speaker_layout(["surround:2:generic_dipole_surround"]))
    deviations=[abs(90.-_directivity_angle(Candidate(np.asarray(s["position_m"]),np.asarray(s["normal"]),s["wall_index"],.5),listener,s["toe_in_deg"])) for s in result.best_pair["speakers"]]
    assert max(deviations)<12.

def test_f3_is_minus_three_db_and_raises_low_band_penalty():
    from speakerplacer.speaker_models import SpeakerModel
    low=SpeakerModel("sub25",f3_hz=25.,freq_low_hz=20.)
    high=SpeakerModel("sub45",f3_hz=45.,freq_low_hz=20.)
    assert high.response_db(45.)==pytest.approx(-3.)
    assert high.response_db(30.)<low.response_db(30.)
    assert high.usable_band_fraction<low.usable_band_fraction

def test_crossover_filter_applies_configured_slope():
    from speakerplacer.speaker_models import SpeakerModel
    model=SpeakerModel("crossover",freq_low_hz=20.,crossover_hz=100.,crossover_slope_db_oct=24.)
    assert model.response_db(100.)==pytest.approx(-3.)
    assert model.response_db(200.)==pytest.approx(-27.)
    from speakerplacer.speaker_models import resolve_model
    assert resolve_model("generic_onwall_sub_ported").highpass_slope_db_oct==24.
    custom=SpeakerModel("ported_custom",enclosure="ported",highpass_slope_db_oct=12.)
    assert custom.highpass_slope_db_oct==12.

def test_inline_model_override_parsing_and_errors():
    from speakerplacer.cli import _parse_inline_model
    model_id,values=_parse_inline_model("generic_bookshelf_onwall@sensitivity_db=90,directivity_band_weights=[0.1,0.2,0.3,0.4]")
    assert model_id=="generic_bookshelf_onwall"
    assert values["sensitivity_db"]==90
    assert values["directivity_band_weights"]==[.1,.2,.3,.4]
    with pytest.raises(ValueError,match="key=value"):
        _parse_inline_model("generic_bookshelf_onwall@sensitivity_db")

def test_custom_yaml_override_notices_existing_model(tmp_path):
    from speakerplacer.speaker_models import load_models_file
    path=tmp_path/"override.yaml"
    path.write_text("models:\n  generic_bookshelf_onwall:\n    sensitivity_db: 90\n",encoding="utf-8")
    models,notices=load_models_file(str(path))
    assert models["generic_bookshelf_onwall"].sensitivity_db==90
    assert notices and "overrides" in notices[0]

def test_candidate_normals_point_inward():
    p=make_room(15,12); center=p.mean(axis=1)
    for c in generate_candidates(p): assert np.dot(c.normal,center-c.position)>0

def test_centered_mirror_symmetry_and_constraints():
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    # Deterministic fake RIR keeps this test independent of pyroomacoustics.
    def sim(poly,source,listener,absorption=.2):
        fs=16000; h=np.zeros(fs//2); h[round(np.linalg.norm(source-listener)/343*fs)]=1.; h[round(np.linalg.norm(source-listener)/343*fs)+100]=.1
        return h,fs
    result=optimize_speakers(p,listener,simulator=sim)
    pair=result.best_pair; l,r=pair['left'],pair['right']
    assert l[0]+r[0]==pytest.approx(2*listener[0],abs=.02)
    assert pair['wall_index']==facing_wall_index(p,'north')
    assert min(np.linalg.norm(l-listener),np.linalg.norm(r-listener))>=.5
    assert abs(abs(pair['angles_deg']['left'])-30)<=4.1

def test_rir_smoke():
    from speakerplacer.simulate import simulate_rir
    p=make_room(15,12); source=np.array([2.,2.]); listener=np.array([2.,1.])
    rir,fs=simulate_rir(p,source,listener)
    expected=round(np.linalg.norm(source-listener)/343*fs)
    assert abs(np.argmax(np.abs(rir))-expected)<=2
    assert np.max(np.abs(rir[expected+1:]))>0
    assert np.sum(rir[-1000:]**2)<np.sum(rir[:min(len(rir),fs//10)]**2)

def test_all_facing_directions_use_the_correct_wall():
    p=make_room(15,12)
    def sim(poly,source,listener,absorption=.2):
        h=np.zeros(600); h[100]=1.; h[250]=.1; return h,16000
    cases={"north":(7.5,4),"south":(7.5,8),"east":(5,6),"west":(10,6)}
    for facing,xy in cases.items():
        listener=np.array([feet_to_m(v) for v in xy])
        result=optimize_speakers(p,listener,facing=facing,simulator=sim)
        assert result.best_pair["wall_index"]==facing_wall_index(p,facing)
        assert result.best_pair["angles_deg"]["left"]<0<result.best_pair["angles_deg"]["right"]

def test_custom_speaker_counts():
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    def sim(poly,source,listener,absorption=.2):
        h=np.zeros(800); h[100]=1.; h[250]=.1; return h,16000
    for count in (1,3):
        result=optimize_speakers(p,listener,simulator=sim,num_speakers=count)
        assert len(result.best_pair["speakers"])==count
        assert len(result.ranked_pairs)>0

def test_mixed_speaker_profiles_use_role_specific_placement():
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    def sim(poly,source,listener,absorption=.2):
        h=np.zeros(1200); h[100]=1.; h[300]=.1; return h,16000
    result=optimize_speakers(p,listener,simulator=sim,speaker_types=["regular","bass"])
    speakers=result.best_pair["speakers"]
    assert [item["type"] for item in speakers]==["regular","bass"]
    assert speakers[0]["wall_index"]==facing_wall_index(p,"north")
    assert np.linalg.norm(speakers[0]["position_m"]-speakers[1]["position_m"])>=.35

def _typed_fake_sim(poly,source,listener,absorption=.2):
    fs=16000; h=np.zeros(1200); h[100]=1.; h[260]=.08
    return h,fs

def test_type_layout_parsing_and_even_pair_validation():
    from speakerplacer.speaker_types import parse_speaker_layout
    layout=parse_speaker_layout(["front:2","surround:2","bass:2"])
    assert [(spec.name,spec.count) for spec in layout]==[("front",2),("surround",2),("bass",2)]
    with pytest.raises(ValueError,match="even count"):
        parse_speaker_layout(["front:1"])

def test_front_pairs_are_exactly_symmetric_and_angles_are_hard_filtered():
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    result=optimize_layout(p,listener,parse_speaker_layout(["front:2"]),simulator=_typed_fake_sim)
    left,right=[speaker["position_m"] for speaker in result.best_pair["speakers"]]
    assert left[0]+right[0]==pytest.approx(2*listener[0],abs=1e-9)
    assert left[1]==pytest.approx(right[1],abs=1e-9)
    for speaker in result.best_pair["speakers"]:
        assert 25.-1e-9 <= abs(speaker["angle_deg"]) <= 35.+1e-9

def test_surround_pair_is_symmetric_across_facing_axis():
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    result=optimize_layout(p,listener,parse_speaker_layout(["surround:2"]),simulator=_typed_fake_sim)
    speakers=result.best_pair["speakers"]; lateral=np.array([1.,0.]); forward=np.array([0.,1.])
    lateral_offsets=[float((speaker["position_m"]-listener)@lateral) for speaker in speakers]
    forward_offsets=[float((speaker["position_m"]-listener)@forward) for speaker in speakers]
    assert lateral_offsets[0]+lateral_offsets[1]==pytest.approx(0.,abs=1e-9)
    assert forward_offsets[0]==pytest.approx(forward_offsets[1],abs=1e-9)
    assert all(90.-1e-9<=abs(s["angle_deg"])<=110.+1e-9 for s in speakers)

def test_rotation_by_90_degrees_preserves_front_pair():
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    layout=parse_speaker_layout(["front:2","surround:2","bass:2"])
    original=optimize_layout(p,listener,layout,facing="north",simulator=_typed_fake_sim)
    rotate=np.array([[0.,1.],[-1.,0.]])
    rotated=optimize_layout(rotate@p,rotate@listener,layout,facing="east",simulator=_typed_fake_sim)
    expected={name:sorted([tuple(np.round(rotate@s["position_m"],8)) for s in original.best_pair["speakers"] if s["type"]==name]) for name in ("front","surround","bass")}
    actual={name:sorted([tuple(np.round(s["position_m"],8)) for s in rotated.best_pair["speakers"] if s["type"]==name]) for name in ("front","surround","bass")}
    assert actual==expected

def test_modal_modes_and_pressure_peaks():
    from scipy.signal import find_peaks
    from speakerplacer.scoring import room_modes,modal_response
    p=make_room(15,12); modes=room_modes(p,(30.,200.));
    assert modes[0][0]==pytest.approx(343/(2*feet_to_m(15)),abs=.05)
    assert modes[1][0]==pytest.approx(343/(2*feet_to_m(12)),abs=.05)
    freq,pressure=modal_response(p,[np.array([.05,.05])],np.array([.5,.5]),band_hz=(30.,200.))
    db=20*np.log10(np.maximum(np.abs(pressure),1e-15)); peaks,_=find_peaks(db,distance=3)
    peak_freqs=freq[peaks]
    assert np.min(abs(peak_freqs-modes[0][0]))<=1.
    assert np.min(abs(peak_freqs-modes[1][0]))<=1.

def test_plot_label_is_tied_to_its_speaker_coordinate():
    from matplotlib.figure import Figure
    from speakerplacer.plotting import add_speaker_label
    speaker={"type":"bass","normal":np.array([0.,-1.])}; position=np.array([7.25,11.84])
    artist=add_speaker_label(Figure().subplots(),speaker,position,0)
    assert artist.xy==pytest.approx(position)
    assert "bass: model (7.25, 11.84 ft)"==artist.get_text()
    assert artist.get_ha()=="right"

def test_modal_bass_layout_does_not_call_rir_backend():
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    def forbidden(*args,**kwargs): raise AssertionError("modal bass should not invoke the RIR backend")
    result=optimize_layout(p,listener,parse_speaker_layout(["bass:2"]),simulator=forbidden)
    assert result.rir is None
    assert result.modal_response_data is not None
    assert "poor_response" in result.modal_response_data

def test_modal_sources_sum_coherently():
    from speakerplacer.scoring import modal_response
    p=make_room(15,12); listener=np.array([.5,.6]); left=np.array([.05,.05]); right=np.array([feet_to_m(15)-.05,.05])
    freq,both=modal_response(p,[left,right],listener,band_hz=(30.,200.))
    _,a=modal_response(p,[left],listener,band_hz=(30.,200.)); _,b=modal_response(p,[right],listener,band_hz=(30.,200.))
    assert both==pytest.approx(a+b)

def test_model_directivity_coverage_point_and_back_floor():
    from speakerplacer.speaker_models import resolve_model
    model=resolve_model("generic_bookshelf_onwall")
    assert model.gain_db(0.)==pytest.approx(0.)
    assert model.gain_db(model.coverage_h_deg/2)==pytest.approx(-6.0206,abs=.02)
    values=[model.gain_db(angle) for angle in (0,15,30,45,60,90,180)]
    assert all(a>=b for a,b in zip(values,values[1:]))
    assert values[-1]==pytest.approx(-30.)

def test_model_spl_scaling_with_power_and_distance():
    from dataclasses import replace
    from speakerplacer.speaker_models import resolve_model,predicted_spl_db
    model=resolve_model("generic_bookshelf_onwall"); base=predicted_spl_db(model,1.)
    assert predicted_spl_db(replace(model,rated_power_w=model.rated_power_w*2),1.)-base==pytest.approx(3.0103,abs=.01)
    assert predicted_spl_db(model,2.)-base==pytest.approx(-6.0206,abs=.01)

def test_model_band_eligibility_and_model_change_affect_score():
    from dataclasses import replace
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    layout=parse_speaker_layout(["front:2:generic_inwall_lcr"])
    layout=[replace(layout[0],score_weights={"clarity":1.,"off_axis":1.,"early_reflection":0.,"geometry":.1,"headroom":0.})]
    def directional_scene(poly,source,listener,absorption=.2):
        h=np.zeros(1400); h[100]=1.
        offset=abs(source[0]-listener[0]); h[1000]=.21 if offset<1.35 else .19
        return h,16000
    narrow=optimize_layout(p,listener,layout,simulator=directional_scene)
    wide_layout=[replace(layout[0],model_id="generic_compact_wall")]
    wide=optimize_layout(p,listener,wide_layout,simulator=directional_scene)
    assert narrow.best_pair["terms"]!=wide.best_pair["terms"]
    narrow_positions=np.array([s["position_m"] for s in narrow.best_pair["speakers"]])
    wide_positions=np.array([s["position_m"] for s in wide.best_pair["speakers"]])
    narrow_toe=np.array([s["toe_in_deg"] for s in narrow.best_pair["speakers"]])
    wide_toe=np.array([s["toe_in_deg"] for s in wide.best_pair["speakers"]])
    assert (not np.allclose(narrow_positions,wide_positions)
            or not np.allclose(narrow_toe,wide_toe)
            or narrow.best_pair["score_db"]!=pytest.approx(wide.best_pair["score_db"]))
    bad=[replace(layout[0],model_id="generic_inwall_sub")]
    with pytest.raises(ValueError,match="cannot fill role|bandwidth"):
        optimize_layout(p,listener,bad,simulator=_typed_fake_sim)

def test_model_toe_in_respects_mount_limit_and_role_eligibility():
    from dataclasses import replace
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    p=make_room(15,12); listener=np.array([feet_to_m(7.5),feet_to_m(4)])
    inwall=optimize_layout(p,listener,parse_speaker_layout(["front:2:generic_inwall_lcr"]),simulator=_typed_fake_sim)
    assert all(abs(s["toe_in_deg"])<=10. for s in inwall.best_pair["speakers"])
    wide=optimize_layout(p,listener,parse_speaker_layout(["front:2:generic_compact_wall"]),simulator=_typed_fake_sim)
    assert all(abs(s["toe_in_deg"])<=45. for s in wide.best_pair["speakers"])
    wrong=[replace(parse_speaker_layout(["front:2"])[0],model_id="generic_inwall_sub")]
    with pytest.raises(ValueError,match="cannot fill role"):
        optimize_layout(p,listener,wrong,simulator=_typed_fake_sim)

def test_off_center_modal_peak_and_centerline_nodal_suppression():
    from scipy.signal import find_peaks
    from speakerplacer.scoring import modal_response,room_modes
    p=make_room(15,12); source=np.array([feet_to_m(2),feet_to_m(2)])
    f10=343/(2*feet_to_m(15))
    offcenter=np.array([feet_to_m(5.3),feet_to_m(4)])
    freq,pressure=modal_response(p,[source],offcenter,absorption=.08,band_hz=(30.,80.),step_hz=.1)
    db=20*np.log10(np.maximum(np.abs(pressure),1e-15)); peaks,_=find_peaks(db,distance=8)
    assert np.min(np.abs(freq[peaks]-f10))<=1.5
    centerline=np.array([feet_to_m(7.5),feet_to_m(4)])
    freq_center,pressure_center=modal_response(p,[source],centerline,absorption=.08,band_hz=(35.,40.),step_hz=.1)
    assert np.max(np.abs(pressure_center))<1e-8

def test_optimizer_front_group_beats_textbook_candidate_in_five_rooms():
    from speakerplacer.optimize import optimize_layout
    from speakerplacer.speaker_types import parse_speaker_layout
    rooms=[(12,10),(14,13),(15,12),(18,14),(20,15)]
    for length,width in rooms:
        p=make_room(length,width); listener=np.array([feet_to_m(length*.5),feet_to_m(width*.38)])
        result=optimize_layout(p,listener,parse_speaker_layout(["front:2"]),simulator=_typed_fake_sim,top_n=500)
        textbook=min(result.ranked_pairs,key=lambda rec:np.mean([abs(abs(sp["angle_deg"])-30.) for sp in rec["speakers"]]))
        assert result.best_pair["score_db"]+1e-8>=textbook["score_db"],(length,width,result.best_pair["score_db"],textbook["score_db"])

def test_first_order_reflection_directivity_depends_on_model():
    from speakerplacer.candidates import Candidate
    from speakerplacer.optimize import _first_order_reflection_gain
    from speakerplacer.speaker_models import resolve_model
    p=make_room(15,12); speaker=Candidate(np.array([1.,3.6]),np.array([0.,-1.]),2,.5); listener=np.array([2.3,1.2])
    wide=_first_order_reflection_gain(p,speaker,listener,resolve_model("generic_compact_wall"),0.)
    narrow=_first_order_reflection_gain(p,speaker,listener,resolve_model("generic_narrow_onwall"),0.)
    assert narrow<wide
