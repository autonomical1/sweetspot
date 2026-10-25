"""CLI for typed, model-aware wall speaker placement."""
import argparse
import json
import sys
from pathlib import Path
from dataclasses import replace
import threading
import time
import numpy as np
from .room import make_room,default_listener,feet_to_m,validate_polygon
from .optimize import optimize_layout
from .speaker_types import DEFAULT_LAYOUT, parse_speaker_layout
from .speaker_models import DEFAULT_SPEAKER_MODELS, DEFAULT_MODEL_BY_ROLE, resolve_model, load_models_file, validate_models
from .plotting import plot_results, plot_model_comparison, plot_model_specs
from .room_acoustics import parse_materials, room_metrics


class _Progress:
    """Small elapsed-time ticker while an expensive CLI stage runs."""
    def __init__(self, stage):
        self.stage=stage; self.stop=threading.Event(); self.start=0.; self.thread=None

    def __enter__(self):
        self.start=time.perf_counter()
        print("{}...".format(self.stage),flush=True)
        def tick():
            while not self.stop.wait(5.):
                print("{}: {:.0f}s elapsed".format(self.stage,time.perf_counter()-self.start),flush=True)
        self.thread=threading.Thread(target=tick,daemon=True); self.thread.start()
        return self

    def __exit__(self,exc_type,exc_value,traceback):
        self.stop.set(); self.thread.join(timeout=.2)
        print("{}: finished in {:.1f}s".format(self.stage,time.perf_counter()-self.start),flush=True)


def _mount_height_overrides(tokens,parser):
    result={}
    for token in tokens:
        try: role,feet=token.split("=",1); value=float(feet)
        except ValueError: parser.error("--mount-height needs ROLE=FEET")
        if role not in ("front","center","surround","bass") or value<=0:
            parser.error("--mount-height needs front, center, surround, or bass with positive feet")
        result[role]=feet_to_m(value)
    return result

def _keepout_zones(tokens,parser):
    zones=[]
    for token in tokens:
        fields={}
        try:
            for item in token.split(","):
                key,value=item.split("=",1); fields[key.strip()]=value.strip()
            wall=fields["wall"].lower(); u=tuple(float(x) for x in fields["u"].split(":")); z=tuple(float(x) for x in fields["z"].split(":"))
            clearance=float(fields.get("clearance",0.))
            if wall not in ("north","south","east","west") or len(u)!=2 or len(z)!=2 or min(*u,*z,clearance)<0 or u[1]<=u[0] or z[1]<=z[0]: raise ValueError
            zones.append({"wall":wall,"u_range_m":list(u),"z_range_m":list(z),"label":fields.get("label","keep-out"),"clearance_m":clearance})
        except (KeyError,ValueError):
            parser.error("--keepout syntax: wall=north,u=1.2:2.1,z=0:2.1,label=door[,clearance=0.1] (metres)")
    return zones

def _parse_screen_loss(token,parser):
    if not token: return {}
    try:
        rows={float(item.split(":",1)[0]):float(item.split(":",1)[1]) for item in token.split(",")}
        if len(rows)!=len(token.split(",")) or any(f<=0 or db<0 for f,db in rows.items()): raise ValueError
        return rows
    except (ValueError,IndexError):
        parser.error("--screen-loss-db syntax: 125:1,250:2,1000:3 (Hz:dB; nonnegative)")

def _print_models(models, role=None):
    print("ID | roles | band Hz | sensitivity dB | coverage deg | mount | directivity")
    for model in models.values():
        if role and role not in model.role_types: continue
        print("{} | {} | {:.0f}-{:.0f} | {:.1f} | {:.0f} | {} | {}".format(model.model_id,",".join(model.role_types),model.freq_low_hz,model.freq_high_hz,model.sensitivity_db,model.coverage_h_deg,model.mount_type,model.directivity_model))

def _describe(model):
    from dataclasses import fields
    for item in fields(model): print("{} = {} [{}] — {}".format(item.name,getattr(model,item.name),item.metadata.get("unit",""),item.metadata.get("doc","")))
    print("directivity_exponent = {:.4f}".format(model.directivity_exponent))
    print("effective_power_w = {:.2f}".format(model.effective_power_w))
    print("sensitivity_1w_1m_db = {:.2f}".format(model.sensitivity_1w_1m_db))
    if "bass" in model.role_types:
        print("usable_band_fraction_30_200 = {:.3f}".format(model.usable_band_fraction))
    else:
        print("usable_band_fraction_30_200 = not applicable (non-bass role)")
    print("polar_source = {}".format(model.polar_source))

def _fmt_angle(value):
    return "{:+.1f}°".format(value) if isinstance(value,(int,float,np.number)) else str(value)

def _parse_inline_model(token, registry=None):
    if "@" not in token: return token, {}
    model_id, raw=token.split("@",1); values={}
    registry=DEFAULT_SPEAKER_MODELS if registry is None else registry
    if model_id not in registry: raise ValueError("unknown model id {!r} for inline override".format(model_id))
    assignments=[]; start=0; depth=0; quote=None
    for index,char in enumerate(raw):
        if quote:
            if char==quote and (index==0 or raw[index-1]!="\\"): quote=None
        elif char in ("'",'"'): quote=char
        elif char in "[{(": depth+=1
        elif char in "]})": depth-=1
        elif char=="," and depth==0:
            assignments.append(raw[start:index]); start=index+1
    assignments.append(raw[start:])
    for assignment in assignments:
        if "=" not in assignment: raise ValueError("inline model overrides must use key=value")
        key,value=assignment.split("=",1)
        if key not in registry[model_id].__dataclass_fields__: raise ValueError("unknown SpeakerModel field {!r}".format(key))
        try:
            import yaml
            values[key]=yaml.safe_load(value)
        except Exception as exc: raise ValueError("invalid value for model field {}: {}".format(key,value)) from exc
    return model_id, values

def _new_model_wizard(path):
    """Prompt for every model field, validate, then append it to the YAML registry."""
    import yaml
    from dataclasses import fields
    from pathlib import Path
    from .speaker_models import SpeakerModel
    model_id=input("model_id [my_speaker]: ").strip() or "my_speaker"
    values={"model_id":model_id}
    defaults=SpeakerModel(model_id=model_id)
    print("Press Enter to keep each default. Use YAML syntax for lists/tuples and null for an empty optional value.")
    for item in fields(SpeakerModel):
        if item.name=="model_id": continue
        default=getattr(defaults,item.name)
        if item.name=="highpass_slope_db_oct" and values.get("enclosure",defaults.enclosure)=="ported": default=24.
        answer=input("{} [{}] ({}): ".format(item.name,default,item.metadata.get("unit",""))).strip()
        if not answer: values[item.name]=default; continue
        try: values[item.name]=yaml.safe_load(answer)
        except yaml.YAMLError as exc: raise ValueError("invalid YAML value for {}: {}".format(item.name,exc)) from exc
    model=SpeakerModel(**values)
    file=Path(path).expanduser(); data=yaml.safe_load(file.read_text(encoding="utf-8")) if file.exists() else {}
    data=data or {}; entries=data.setdefault("models",{})
    if model_id in entries: raise ValueError("model {!r} already exists in {}".format(model_id,file))
    def plain(value):
        if isinstance(value,tuple): return [plain(item) for item in value]
        if isinstance(value,list): return [plain(item) for item in value]
        if isinstance(value,dict): return {key:plain(item) for key,item in value.items()}
        return value
    entries[model_id]=plain(values); file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding="utf-8")
    print("Added {} to {}".format(model.model_id,file))

def main(argv=None):
    parser=argparse.ArgumentParser(description="Optimize wall speakers and view their placement in a 3D room")
    parser.add_argument("--config",metavar="PATH",help="load run defaults from a YAML file; explicit CLI flags override them")
    parser.add_argument("--mode",choices=("3d","2d"),default="3d",help="primary output mode (default: 3d)")
    parser.add_argument("--length",type=float,help="room length in feet")
    parser.add_argument("--width",type=float,help="room width in feet")
    parser.add_argument("--design-room",action="store_true",help="open a draggable room editor and choose a theatre format before optimization")
    parser.add_argument("--room-polygon-json",help=argparse.SUPPRESS)
    parser.add_argument("--room-retry-attempt",type=int,default=0,help=argparse.SUPPRESS)
    parser.add_argument("--height",type=float,default=8.,help="3D room height in feet (default: 8)")
    parser.add_argument("--listener",nargs=2,type=float,metavar=("X","Y"),help="listener position in feet")
    parser.add_argument("--ear-height",type=float,default=3.6,help="listener ear height in feet (default: 3.6)")
    parser.add_argument("--seats",metavar="GRID",help="rows=R,seats=S,seat_spacing=.7,row_spacing=1.1,riser=.2,ear_height=1.1 (metres)")
    parser.add_argument("--mlp",metavar="ROW_SEAT",help="choose main listening position with one-based row=r,seat=s")
    parser.add_argument("--screen-height",type=float,help="screen center height in feet; aligns the front-stage height policy")
    parser.add_argument("--screen-spec",metavar="PATH",help="YAML file with user-supplied screen dimensions and material")
    parser.add_argument("--projector-spec",metavar="PATH",help="YAML file with projector constraints (generic placeholder if omitted)")
    parser.add_argument("--screen",action="append",default=[],metavar="KEY=VALUE,...",help="inline screen overrides; dimensional suffixes _in, _ft, _m are accepted")
    parser.add_argument("--projector",action="append",default=[],metavar="KEY=VALUE,...",help="inline projector overrides; dimensional suffixes _in, _ft, _m are accepted")
    parser.add_argument("--screen-pos",nargs=2,type=float,metavar=("X_FT","Z_FT"),help="manual screen center X and Z in feet")
    parser.add_argument("--projector-pos",nargs=3,type=float,metavar=("X_FT","Y_FT","Z_FT"),help="manual projector body center in feet")
    parser.add_argument("--check-display",action="store_true",help="report display feasibility from supplied positions without changing them")
    parser.add_argument("--ambient-light",default="dark",help="dark, dim, lit, or ambient illuminance in lux")
    parser.add_argument("--target-fl",type=float,default=16.,help="target screen brightness in foot-lamberts (verify convention)")
    parser.add_argument("--noise-floor-dba",type=float,default=30.,help="target room noise floor in dBA")
    parser.add_argument("--lumen-derate",type=float,default=1.,help="lamp/eco derating factor in [0,1]")
    parser.add_argument("--no-display",action="store_true",help="skip screen/projector calculations and rendering")
    parser.add_argument("--init-specs",nargs="?",const="specs",metavar="DIR",help="write commented screen/projector YAML templates")
    parser.add_argument("--new-screen",action="store_true",help="write a commented screen template and exit")
    parser.add_argument("--new-projector",action="store_true",help="write a commented projector template and exit")
    parser.add_argument("--describe-screen",action="store_true",help="describe supported screen fields")
    parser.add_argument("--describe-projector",action="store_true",help="describe supported projector fields")
    parser.add_argument("--list-screens",action="store_true",help="list generic screen placeholder")
    parser.add_argument("--list-projectors",action="store_true",help="list generic projector placeholder")
    parser.add_argument("--validate-specs",action="store_true",help="validate supplied display spec files")
    parser.add_argument("--screen-loss-db",default="",metavar="HZ:DB,...",help="acoustically transparent screen insertion loss by frequency, e.g. 125:1,250:2,1000:3,4000:4")
    parser.add_argument("--keepout",action="append",default=[],metavar="ZONE",help="wall keep-out, e.g. wall=north,u=1.2:2.1,z=0:2.1,label=door (metres)")
    parser.add_argument("--mount-height",action="append",default=[],metavar="ROLE=FEET",help="override a role's 3D mounting-center height")
    parser.add_argument("--stud-spacing",choices=("16in","24in","none"),default="none",help="in-wall stud bay spacing measured from each wall origin")
    parser.add_argument("--joist-spacing",choices=("16in","24in","none"),default="none",help="in-ceiling joist bay spacing measured from room origin")
    parser.add_argument("--stud-thickness-in",type=float,default=1.5,help="nominal stud/joist thickness in inches (default 1.5)")
    parser.add_argument("--allow-floor",action="store_true",help="search and report floor/stand alternatives for L/C/R")
    parser.add_argument("--floor-model",default="generic_floorstanding_tower",help="floor/stand placeholder model ID used with --allow-floor")
    parser.add_argument("--floor-wall-clearance",type=float,default=1.0,help="minimum floor speaker clearance from walls in feet")
    parser.add_argument("--panel-protrusion-mm",type=float,default=12.,help="visible in-wall/flush panel depth in millimetres")
    parser.add_argument("--facing",choices=("north","south","east","west"),default="north")
    parser.add_argument("--standard",choices=("itu","dolby","thx","custom"),default="itu",help="reference angle ranges for channel compliance; initial data is marked verify")
    parser.add_argument("--layout",choices=("5.1","5.2","7.1","7.2","5.1.2","5.1.4","7.1.2","7.1.4","7.2.4","9.1.6","custom"),help="expand a standards-based channel layout; use custom with --speakers")
    parser.add_argument("--role-model",action="append",default=[],metavar="ROLE=ID",help="override model for a channel role in --layout mode")
    parser.add_argument("--channel-model",action="append",default=[],metavar="CHANNEL=ID",help="override a specific channel model, e.g. C=generic_center_inwall")
    parser.add_argument("--channel-angle",action="append",default=[],metavar="CHANNEL=TARGET:MIN:MAX",help="override signed azimuth target and inclusive limits in degrees")
    parser.add_argument("--fast",action="store_true",help="use a coarser wall grid for faster multi-channel placement")
    parser.add_argument("--absorption",type=float,default=.2)
    parser.add_argument("--materials",help="octave-band room materials, e.g. walls=drywall,floor=carpet,ceiling=tile")
    parser.add_argument("--treatment-preset",choices=("untreated","carpeted","draped","treated_theater","bass_trapped"),help="typical material bundle; explicit --materials overrides individual surfaces")
    parser.add_argument("--seat-cluster-spacing",type=float,default=.3,help="bass seat-grid spacing in metres (default: 0.3)")
    parser.add_argument("--mlp-weight",type=float,default=.6,help="fraction of imaging score assigned to the MLP (remaining weight shared across other seats)")
    parser.add_argument("--coverage-threshold-db",type=float,choices=(-3.,-6.),default=-3.,help="hard per-seat directivity coverage threshold")
    parser.add_argument("--crossover-hz",type=float,default=80.,help="bass-management LR4 crossover frequency (default: 80 Hz)")
    parser.add_argument("--crossover-search-range",nargs=2,type=float,metavar=("LOW","HIGH"),help="LR4 optimization range in Hz (default: ±25%% around --crossover-hz)")
    parser.add_argument("--lfe-gain-db",type=float,default=10.,help="LFE reference gain convention in dB (default: +10 dB)")
    parser.add_argument("--receiver-max-delay-ms",type=float,default=20.,help="warn when receiver delay compensation exceeds this")
    parser.add_argument("--receiver-max-trim-db",type=float,default=12.,help="warn when channel trim magnitude exceeds this")
    parser.add_argument("--rt60-target",type=float,default=.3,help="advisory home-theater RT60 target in seconds")
    parser.add_argument("--speakers",nargs="+",default=None,metavar="TYPE:COUNT[:MODEL]",help="e.g. front:2:generic_inwall_lcr surround:2:generic_surround_wide bass:2:generic_inwall_sub")
    parser.add_argument("--priority",default="front,bass,surround",help="type search order")
    parser.add_argument("--modal-q-scale",type=float,default=20.,help="Q = scale / sqrt(absorption)")
    parser.add_argument("--reference-spl",type=float,default=85.,help="target average SPL at listener")
    parser.add_argument("--peak-headroom",type=float,default=20.,help="peak allowance above average SPL")
    parser.add_argument("--coherence",choices=("coherent","incoherent"),default="coherent")
    parser.add_argument("--toe-in-range",nargs=2,type=float,default=None,metavar=("MIN","MAX"),help="override toe-in search bounds in degrees")
    parser.add_argument("--bass-count",type=int,choices=(1,2,4),help="run an optional bass count comparison")
    parser.add_argument("--subs",type=int,choices=(1,2,4),help="number of jointly positioned subwoofers (overrides the layout LFE count)")
    parser.add_argument("--disable-reflection-directivity",action="store_false",dest="directivity_on_reflections",default=True,help="skip first-order image-source departure-angle gains")
    parser.add_argument("--list-models",action="store_true",help="print placeholder model registry and exit")
    parser.add_argument("--role",choices=("front","surround","bass"),help="filter --list-models by role")
    parser.add_argument("--describe-model",metavar="ID",help="print a model specification")
    parser.add_argument("--models-file",help="load or override models from a YAML file")
    parser.add_argument("--validate-models",action="store_true",help="validate the loaded model registry")
    parser.add_argument("--new-model",action="store_true",help="interactively create a validated model in --models-file")
    parser.add_argument("--plot",action="store_true",help="save polar and response plots with --describe-model")
    parser.add_argument("--compare-models",metavar="ROLE=ID_A,ID_B",help="compare two models for one role")
    parser.add_argument("--target-spl",dest="reference_spl",type=float,default=argparse.SUPPRESS,help="target average SPL at listener")
    parser.add_argument("--peak-headroom-db",dest="peak_headroom",type=float,default=argparse.SUPPRESS,help="peak allowance above average SPL")
    parser.add_argument("--validate",action="store_true",help="run physics validation and save its report/plots")
    parser.add_argument("--no-show",action="store_true",help="save figures without opening them")
    parser.add_argument("--view3d",action=argparse.BooleanOptionalAction,default=True,help="open the 3D window in 3D mode")
    parser.add_argument("--save-views",action="store_true",help="save top, front, side, and perspective 3D PNGs")
    parser.add_argument("--view-elev",type=float,help="initial 3D camera elevation in degrees")
    parser.add_argument("--view-azim",type=float,help="initial 3D camera azimuth in degrees")
    parser.add_argument("--show-coverage",action="store_true",help="start with 3D coverage cones visible")
    parser.add_argument("--show-candidates",action="store_true",help="start with 3D candidate-score dots visible")
    parser.add_argument("--show-reflections",type=int,metavar="IDX",help="start with first-order paths for zero-based speaker index")
    parser.add_argument("--save-layout",metavar="PATH",help="write a self-contained 3D layout JSON file")
    parser.add_argument("--save-candidates",metavar="PATH",help="write optional wall/height candidate scores to a separate JSON file")
    parser.add_argument("--view-layout",metavar="PATH",help="open a previously saved layout without optimizing")
    parser.add_argument("--output",default="output",help="figure output directory")
    bootstrap=argparse.ArgumentParser(add_help=False); bootstrap.add_argument("--config")
    config_args,_=bootstrap.parse_known_args(argv)
    if config_args.config:
        import yaml
        try: config=yaml.safe_load(Path(config_args.config).expanduser().read_text(encoding="utf-8")) or {}
        except (OSError,yaml.YAMLError) as exc: parser.error("could not read config: {}".format(exc))
        if not isinstance(config,dict): parser.error("run config must be a YAML mapping of argument names to values")
        defaults={str(key).replace("-","_"):value for key,value in config.items()}
        known={action.dest for action in parser._actions}
        unknown=sorted(set(defaults)-known)
        if unknown: parser.error("unknown config fields: {}".format(", ".join(unknown)))
        parser.set_defaults(**defaults)
    args=parser.parse_args(argv)
    if args.check_display and not (args.screen_spec or args.screen or args.screen_pos):
        parser.error("--check-display requires a screen specification or --screen values")
    if args.target_fl<=0 or args.noise_floor_dba<0 or not 0<=args.lumen_derate<=1:
        parser.error("--target-fl must be positive, --noise-floor-dba nonnegative, and --lumen-derate between 0 and 1")
    if args.init_specs or args.new_screen or args.new_projector:
        from .display import init_spec_templates
        target=args.init_specs or "specs"; screen_file,projector_file=init_spec_templates(target)
        print("Screen template:",screen_file); print("Projector template:",projector_file); return
    if args.describe_screen or args.list_screens:
        print("Generic screen placeholder: diag_in, aspect_ratio, material, gain, half_gain_angle_deg, border_width_m, thickness_m, standoff_from_wall_m, bottom_edge_height_m, image_fit, curvature, transmission_loss_db, standoff_behind_m, fixed_x_offset_m")
        return
    if args.describe_projector or args.list_projectors:
        print("Generic projector placeholder: native_resolution, native_aspect, lumens_ansi, eco_mode_factor, native_contrast, throw_ratio_min/max, lumens_loss_at_tele_pct, lens-shift ranges/convention, keystone limits, lens/body offsets and dimensions, noise, mounts, mount-drop range, distance range, ventilation clearance")
        return
    if args.new_model:
        if not args.models_file: parser.error("--new-model requires --models-file PATH")
        _new_model_wizard(args.models_file); return
    models=dict(DEFAULT_SPEAKER_MODELS)
    if args.models_file:
        models, notices=load_models_file(args.models_file,models)
        for notice in notices: print(notice)
    if args.list_models: _print_models(models,args.role); return
    if args.validate_models:
        errors=validate_models(models)
        print("Model validation: {}".format("PASS" if not errors else "FAIL"))
        for error in errors: print(" ",error)
        if errors: raise SystemExit(1)
        if not args.describe_model and args.length is None: return
    if args.describe_model:
        if args.describe_model not in models: parser.error("unknown model id: {}".format(args.describe_model))
        _describe(models[args.describe_model])
        if args.plot:
            modal_data=None
            if "bass" in models[args.describe_model].role_types and args.length is not None and args.width is not None:
                room=make_room(args.length,args.width); listener=default_listener(room,args.facing) if args.listener is None else tuple(feet_to_m(x) for x in args.listener)
                spec=next(s for s in parse_speaker_layout(["bass:2:{}".format(args.describe_model)]) if s.name=="bass")
                trial=optimize_layout(room,listener,[spec],args.facing,args.absorption,models=models)
                modal_data=trial.placements_by_type[0]["best"]["modal_response"]
            print("Model plots saved:",", ".join(map(str,plot_model_specs(models[args.describe_model],args.output,modal_data))))
        return
    if args.view_layout:
        from .viewer3d import load_layout,open_viewer
        try: saved=load_layout(args.view_layout)
        except (OSError,ValueError,KeyError,TypeError) as exc: parser.error("could not load layout: {}".format(exc))
        print("Loaded {} speakers from {}".format(len(saved["speakers"]),args.view_layout))
        try:
            open_viewer(saved,args.output,show=not args.no_show and args.view3d,
                        save_views=args.save_views,elev=args.view_elev,azim=args.view_azim,
                        show_coverage=args.show_coverage,show_candidates=args.show_candidates,
                        reflection_index=args.show_reflections)
        except ValueError as exc: parser.error(str(exc))
        return
    if args.length is None or args.width is None: parser.error("--length and --width are required unless a registry action is used")
    if args.height<=0 or args.ear_height<=0 or args.ear_height>=args.height:
        parser.error("--height must exceed the positive --ear-height")
    if not 40.<=args.crossover_hz<=160. or args.receiver_max_delay_ms<0 or args.receiver_max_trim_db<=0 or args.rt60_target<=0:
        parser.error("--crossover-hz must be 40–160; RT60 target must be positive and receiver limits nonnegative")
    if args.crossover_search_range is not None and not (40.<=args.crossover_search_range[0]<=args.crossover_search_range[1]<=160.):
        parser.error("--crossover-search-range must satisfy 40 <= LOW <= HIGH <= 160 Hz")
    if not 0<=args.mlp_weight<=1: parser.error("--mlp-weight must be between 0 and 1")
    if args.screen_height is not None and not 0<args.screen_height<args.height:
        parser.error("--screen-height must be positive and below --height")
    mount_heights=_mount_height_overrides(args.mount_height,parser)
    screen_loss=_parse_screen_loss(args.screen_loss_db,parser)
    if args.stud_thickness_in<=0: parser.error("--stud-thickness-in must be positive")
    if args.floor_wall_clearance<0: parser.error("--floor-wall-clearance must be nonnegative")
    if args.floor_model not in models: parser.error("unknown --floor-model ID; use --list-models")
    stud_spacing_m=None if args.stud_spacing=="none" else float(args.stud_spacing[:-2])/12.*.3048
    joist_spacing_m=None if args.joist_spacing=="none" else float(args.joist_spacing[:-2])/12.*.3048
    framing_thickness_m=args.stud_thickness_in/12.*.3048
    keepouts=_keepout_zones(args.keepout,parser)
    try: materials=parse_materials(args.materials,args.treatment_preset)
    except ValueError as exc: parser.error(str(exc))
    room=make_room(args.length,args.width)
    if args.room_polygon_json:
        try: room=validate_polygon(np.asarray(json.loads(args.room_polygon_json),dtype=float))
        except (ValueError,TypeError,json.JSONDecodeError) as exc: parser.error("internal room polygon is invalid: {}".format(exc))
        args.length=float(np.ptp(room[0])/.3048); args.width=float(np.ptp(room[1])/.3048)
    if args.design_room:
        from .viewer3d import interactive_backend_available
        if not interactive_backend_available(): parser.error("--design-room needs a graphical Matplotlib backend (TkAgg or QtAgg)")
        from .room_editor import edit_room
        def check_room_layout(candidate_room,layout_name):
            from .home_theater import channel_layout_specs,place_overhead_channels,seating_grid
            overhead=[]
            if layout_name!="custom":
                _,overhead=channel_layout_specs(layout_name,args.standard)
            center=default_listener(candidate_room,args.facing) if args.listener is None else tuple(feet_to_m(x) for x in args.listener)
            candidate_seats,candidate_listener,candidate_ear=seating_grid(args.seats,args.mlp,center,args.facing,feet_to_m(args.ear_height))
            from matplotlib.path import Path as PolygonPath
            if any(not PolygonPath(candidate_room.T).contains_point(np.asarray(seat["position_m"])) for seat in candidate_seats):
                raise ValueError("room invalid for selected seating: every seat must fit inside the room boundary; reshape the room or adjust --seats and retry")
            if overhead:
                height_id=next((token.split("=",1)[1] for token in args.role_model if token.startswith("height=") and token.split("=",1)[1] in models),"generic_in_ceiling")
                place_overhead_channels(overhead,candidate_room,feet_to_m(args.height),candidate_listener,
                    candidate_ear,args.standard,args.facing,models[height_id],.15 if not args.fast else .3,
                    joist_spacing_m=joist_spacing_m,joist_thickness_m=framing_thickness_m)
            if not args.no_display:
                from .display import (load_spec,parse_unit_overrides,solve_display_positions,
                                      DEFAULT_SCREEN_SPEC,DEFAULT_PROJECTOR_SPEC)
                try:
                    screen=dict(DEFAULT_SCREEN_SPEC); projector=dict(DEFAULT_PROJECTOR_SPEC)
                    if args.screen_spec: screen.update(load_spec(args.screen_spec))
                    if args.projector_spec: projector.update(load_spec(args.projector_spec))
                    for group,target in ((args.screen,screen),(args.projector,projector)):
                        for token in group:
                            for part in token.split(","): target.update(parse_unit_overrides([part],"screen/projector"))
                    solve_display_positions(candidate_room,args.facing,screen,projector,feet_to_m(args.height),
                        screen_pos=([feet_to_m(v) for v in args.screen_pos] if args.screen_pos else None),
                        projector_pos=([feet_to_m(v) for v in args.projector_pos] if args.projector_pos else None))
                except (OSError,ValueError,TypeError,KeyError) as exc:
                    raise ValueError(str(exc)) from exc
        if not args.room_polygon_json:
            try: room,args.layout=edit_room(room,args.layout or "5.1",validator=check_room_layout)
            except ValueError as exc: parser.error(str(exc))
            args.length=float(np.ptp(room[0])/.3048); args.width=float(np.ptp(room[1])/.3048)
    def retry_room_after_placement_error(exc):
        message=str(exc)
        retryable=message.startswith("Room invalid for selected layout:")
        if not args.design_room or not retryable: parser.error(message)
        if args.room_retry_attempt>=5:
            parser.error(message+" (five interactive retries reached; rerun with --design-room to continue editing)")
        from .room_editor import edit_room
        try:
            revised_room,revised_layout=edit_room(room,args.layout or "5.1",validator=check_room_layout,
                initial_message="The selected layout could not fit:\n{}\nAdjust the room or format and retry.".format(message))
        except ValueError as editor_error: parser.error(str(editor_error))
        raw=list(argv if argv is not None else sys.argv[1:]); clean=[]; index=0
        while index<len(raw):
            if raw[index] in ("--room-polygon-json","--room-retry-attempt"):
                index+=2; continue
            clean.append(raw[index]); index+=1
        found=False
        for index,token in enumerate(clean):
            if token=="--layout" and index+1<len(clean): clean[index+1]=revised_layout; found=True
            elif token.startswith("--layout="): clean[index]="--layout="+revised_layout; found=True
        if not found: clean.extend(["--layout",revised_layout])
        clean.extend(["--room-polygon-json",json.dumps(revised_room.tolist()),
                      "--room-retry-attempt",str(args.room_retry_attempt+1)])
        main(clean)
        return True
    listener_center=default_listener(room,args.facing) if args.listener is None else tuple(feet_to_m(x) for x in args.listener)
    from .home_theater import seating_grid
    try: seats,listener,mlp_ear_height=seating_grid(args.seats,args.mlp,listener_center,args.facing,feet_to_m(args.ear_height))
    except ValueError as exc: parser.error(str(exc))
    from matplotlib.path import Path as PolygonPath
    if any(not PolygonPath(room.T).contains_point(np.asarray(seat["position_m"])) for seat in seats): parser.error("seating grid must fit inside the room boundary")
    display_result=None; projector_forbidden_boxes=[]
    if not args.no_display:
        from .display import (load_spec,parse_unit_overrides,evaluate_display,solve_display_positions,
                              DEFAULT_SCREEN_SPEC,DEFAULT_PROJECTOR_SPEC)
        try:
            screen_spec=dict(DEFAULT_SCREEN_SPEC)
            projector_spec=dict(DEFAULT_PROJECTOR_SPEC)
            if args.screen_spec: screen_spec.update(load_spec(args.screen_spec))
            if args.projector_spec: projector_spec.update(load_spec(args.projector_spec))
            for group,target in ((args.screen,screen_spec),(args.projector,projector_spec)):
                for token in group:
                    for part in token.split(","):
                        target.update(parse_unit_overrides([part],"screen/projector"))
            if isinstance(screen_spec.get("transmission_loss_db"),dict):
                screen_loss.update({float(k):float(v) for k,v in screen_spec["transmission_loss_db"].items()})
            placement=solve_display_positions(room,args.facing,screen_spec,projector_spec,feet_to_m(args.height),
                screen_pos=([feet_to_m(v) for v in args.screen_pos] if args.screen_pos else None),
                projector_pos=([feet_to_m(v) for v in args.projector_pos] if args.projector_pos else None))
            geometry=placement["screen_geometry"]; bottom=placement["screen_bottom_m"]
            screen_center=placement["screen_center_m"]; projector_position=placement["projector_position_m"]
            forward=np.asarray(placement["forward_xy"],dtype=float); right_xy=np.asarray(placement["right_xy"],dtype=float)
            front_index=int(placement["wall_index"]); wall_start=np.asarray(placement["wall_start_m"]); wall_tangent=np.asarray(placement["wall_tangent_xy"])
            ambient_values={"dark":0.,"dim":10.,"lit":100.}
            ambient=float(ambient_values.get(args.ambient_light.lower(),args.ambient_light))
            display_result=evaluate_display(screen_spec,projector_spec,screen_center,
                [[*seat["position_m"],seat["ear_height_m"]] for seat in seats],projector_position,
                args.target_fl,ambient,args.lumen_derate,right_xy)
            display_result["screen"]["right_xy"]=right_xy.tolist()
            display_result["screen"]["forward_xy"]=forward.tolist()
            display_result["spec_sources"]={"screen":"user supplied" if args.screen_spec or args.screen else "generic 100-inch 16:9 planning placeholder",
                                             "projector":"user supplied" if args.projector_spec or args.projector else "generic 3000-lumen projector planning placeholder"}
            if args.projector_pos is None:
                display_result["projector"]["position_source"]="nearest legal in-room throw position"
            # Convert solid screen and wall-adjacent projector footprints into
            # the optimizer's existing wall keep-outs so the next candidate is
            # selected before layout scoring, not merely hidden in the viewer.
            half=float(geometry.width_m)/2.+float(screen_spec.get("border_width_m",.05))+float(screen_spec.get("clearance_m",.05))
            ucenter=float((np.asarray(screen_center[:2])-wall_start)@wall_tangent)
            keepouts.append({"wall":args.facing,"wall_index":front_index,"u_range_m":[ucenter-half,ucenter+half],
                "z_range_m":[max(0.,bottom-float(screen_spec.get("border_width_m",.05))),bottom+geometry.height_m+float(screen_spec.get("border_width_m",.05))],
                "label":"display screen footprint","clearance_m":0.})
            pp=np.asarray(display_result["projector"]["position_m"],dtype=float); pd=display_result["projector"]
            vent=float(projector_spec.get("ventilation_clearance_m",0.))
            projector_forbidden_boxes=[{"center_m":pp.tolist(),"dimensions_m":[pd["body_width_m"],pd["body_depth_m"],pd["body_height_m"]],"clearance_m":vent,"label":"projector body and ventilation clearance"}]
            if args.validate_specs:
                print("Display spec validation: PASS")
            if args.check_display:
                out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
                (out/"display.json").write_text(json.dumps(display_result,indent=2)+"\n",encoding="utf-8")
                rows=display_result["per_seat"]
                report=["# Display feasibility report","","Values and targets are planning estimates; verify user-supplied specifications.","",
                        "| Item | Value | Allowed/target | Status | Note |","|---|---:|---:|---|---|"]
                angles=[r["viewing_angle_deg"] for r in rows]
                report.append("| Horizontal viewing angle (MLP / worst) | {:.1f}° / {:.1f}° | 30–40° verify | {} | actual image-edge vectors |".format(angles[0],max(angles),"PASS" if 30<=angles[0]<=40 else "WARN"))
                report.append("| Image size | {:.2f} × {:.2f} m | user spec | PASS | screen {:.2f} × {:.2f} m |".format(display_result["screen"]["geometry"]["image_width_m"],display_result["screen"]["geometry"]["image_height_m"],display_result["screen"]["geometry"]["width_m"],display_result["screen"]["geometry"]["height_m"]))
                report.append("| Throw ratio | {:.3f} | {:.3f}–{:.3f} | {} | zoom {:.2f} |".format(display_result["projector"]["implied_throw_ratio"],display_result["projector"]["throw_ratio_min"],display_result["projector"]["throw_ratio_max"],"PASS" if display_result["projector"]["feasible"] else "FAIL",display_result["projector"]["zoom_position"]))
                report.append("| Brightness | {:.1f} fL / {:.1f} nits | {:.1f} fL verify | {} | effective lumens {:.0f} |".format(display_result["projector"]["brightness"]["foot_lamberts"],display_result["projector"]["brightness"]["nits"],args.target_fl,display_result["brightness_status"],display_result["projector"]["lumens_effective"]))
                report.append("| Effective contrast | {:.1f}:1 | ambient-light estimate | WARN | ambient {:.0f} lux |".format(display_result["projector"]["effective_contrast"],ambient))
                (out/"display_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
                print("Display report saved:",out/"display_report.md")
                if not display_result["projector"]["feasible"]:
                    p=display_result["projector"]
                    print("CONFLICT throw ratio {:.3f} outside {:.3f}–{:.3f}; nearest feasible distance {:.2f} m, width {:.2f} m".format(p["implied_throw_ratio"],p["throw_ratio_min"],p["throw_ratio_max"],p["nearest_feasible_distance_m"],p["nearest_feasible_image_width_m"]))
                return
        except (OSError,ValueError,TypeError,KeyError) as exc: parser.error("display specification: {}".format(exc))
    channel_mode=args.layout not in (None,"custom")
    if channel_mode and args.speakers: parser.error("use --layout or --speakers, not both")
    if args.layout=="custom" and not args.speakers: parser.error("--layout custom requires --speakers")
    from .home_theater import load_standards
    role_models={}; channel_models={}; angle_overrides={}
    inline_overrides={}
    for token,target,valid in [(x,role_models,{"front","center","surround","rear_surround","wide","bass","height"}) for x in args.role_model]+[(x,channel_models,set(load_standards()["standards"][args.standard])) for x in args.channel_model]:
        try: key,value=token.split("=",1)
        except ValueError: parser.error("model overrides must use NAME=MODEL_ID")
        if key not in valid: parser.error("unknown role/channel override {!r}".format(key))
        if value not in models: parser.error("unknown model id {!r}".format(value))
        target[key]=value
    channel_names=set(load_standards()["standards"][args.standard])
    for token in args.channel_angle:
        try:
            name,values=token.split("=",1); target,min_angle,max_angle=(float(value) for value in values.split(":"))
            if name not in channel_names or min_angle>max_angle or not min_angle<=target<=max_angle: raise ValueError
            angle_overrides[name]=(target,min_angle,max_angle)
        except ValueError: parser.error("--channel-angle uses CHANNEL=TARGET:MIN:MAX with target inside the signed limits")
    overhead_channels=[]; channel_assignments={}
    if channel_mode:
        from .home_theater import channel_layout_specs
        try: layout,overhead_channels=channel_layout_specs(args.layout,args.standard,role_models,channel_models,angle_overrides)
        except ValueError as exc: parser.error(str(exc))
        if display_result is not None and "C" not in angle_overrides:
            # Keep the center on-axis. Search a wider vertical range so the
            # screen keep-out can select a clear position above or below it.
            half=float(display_result["screen"]["geometry"]["width_m"])/2.+.35
            horizontal=max(.1,float(np.linalg.norm(np.asarray(screen_center[:2])-np.asarray(listener))))
            relaxed=min(65.,max(40.,float(np.degrees(np.arctan2(half,horizontal)))+1.))
            adjusted=[]
            for spec in layout:
                if spec.name=="center":
                    adjusted.append(replace(spec,elevation_range_deg=(-45.,45.)))
                elif spec.channel_name=="L":
                    adjusted.append(replace(spec,azimuth_range_deg=(-relaxed,spec.azimuth_range_deg[1]),angle_tol_deg=max(spec.angle_tol_deg,relaxed-abs(spec.azimuth_range_deg[1]))))
                elif spec.channel_name=="R":
                    adjusted.append(replace(spec,azimuth_range_deg=(spec.azimuth_range_deg[0],relaxed),angle_tol_deg=max(spec.angle_tol_deg,relaxed-spec.azimuth_range_deg[0])))
                else: adjusted.append(spec)
            layout=adjusted
        for role in ("front","center","surround","rear_surround","wide","bass"):
            channel_assignments[role]=[s.channel_name for s in layout if s.name==role]
        for pair in (("L","R"),("Lss","Rss"),("Lrs","Rrs"),("Lw","Rw")):
            if pair[0] in channel_models and pair[1] in channel_models and channel_models[pair[0]]!=channel_models[pair[1]]:
                print("WARN: {} and {} use different models; front/surround timbre may not match".format(*pair))
    else:
        speaker_tokens=args.speakers or ["{}:{}".format(name,count) for name,count in DEFAULT_LAYOUT]
        clean_tokens=[]
        for item in speaker_tokens:
            parts=item.split(":")
            if len(parts)==3 and "@" in parts[2]:
                try: model_id,updates=_parse_inline_model(parts[2],models)
                except ValueError as exc: parser.error(str(exc))
                parts[2]=model_id; inline_overrides[model_id]=updates
            clean_tokens.append(":".join(parts))
        layout=parse_speaker_layout(clean_tokens)
    if args.subs is not None:
        bass=next((i for i,item in enumerate(layout) if item.name=="bass"),None)
        if bass is None: parser.error("--subs requires a layout containing LFE or a bass speaker type")
        layout[bass]=replace(layout[bass],count=args.subs,symmetric=False)
    # The selected reference changes the horizontal optimizer's angle windows,
    # while the same table drives the final geometry-compliance report.
    guideline=load_standards()["standards"][args.standard]
    if not channel_mode:
        for index,spec in enumerate(layout):
            channel="C" if spec.name=="center" else "L" if spec.name=="front" else "Lss" if spec.name=="surround" else None
            if channel is None: continue
            angles=guideline[channel]["azimuth_range_deg"]
            target=abs(float(guideline[channel]["azimuth_deg"]))
            tolerance=max(abs(abs(float(angles[0]))-target),abs(abs(float(angles[1]))-target),.05)
            layout[index]=replace(spec,angle_target_deg=target,angle_tol_deg=tolerance)
    # Inline overrides are converted into temporary immutable model records.
    for model_id,updates in inline_overrides.items():
        try: models[model_id]=replace(models[model_id],**updates)
        except (TypeError,ValueError) as exc: parser.error("invalid override for {}: {}".format(model_id,exc))
    if args.toe_in_range is not None:
        low,high=args.toe_in_range
        if low>high or low < -90 or high > 90: parser.error("--toe-in-range requires MIN <= MAX within -90..90")
    priority=[name.strip() for name in args.priority.split(",") if name.strip()]; rank={name:index for index,name in enumerate(priority)}
    if not channel_mode: layout.sort(key=lambda spec:rank.get(spec.name,len(rank)))
    if args.compare_models:
        try: role,ids=args.compare_models.split("=",1); model_ids=[item.strip() for item in ids.split(",")]
        except ValueError: parser.error("--compare-models syntax is ROLE=ID_A,ID_B")
        if role not in ("front","surround","bass") or len(model_ids)!=2: parser.error("--compare-models requires front, surround, or bass and exactly two model IDs")
        if any(item not in models for item in model_ids): parser.error("both comparison model IDs must exist in the loaded registry")
        base=next((spec for spec in layout if spec.name==role),None)
        if base is None: base=next((spec for spec in parse_speaker_layout(["{}:2".format(role)]) if spec.name==role))
        trials=[]
        for model_id in model_ids:
            trial_layout=[replace(spec,model_id=model_id) if spec.name==role else spec for spec in layout]
            if not any(spec.name==role for spec in trial_layout): trial_layout.append(replace(base,model_id=model_id))
            trials.append(optimize_layout(room,listener,trial_layout,args.facing,args.absorption,modal_q_scale=args.modal_q_scale,
                reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,coherent=args.coherence=="coherent",
                directivity_on_reflections=args.directivity_on_reflections,models=models,
                room_height_m=feet_to_m(args.height),materials=materials,seat_cluster_spacing_m=args.seat_cluster_spacing))
        for model_id,trial in zip(model_ids,trials):
            row=next(item for item in trial.placements_by_type if item["type"]==role)["best"]
            print("{} | score {:.2f} | terms {}".format(model_id,row["score_db"],row["terms"]))
            for speaker in row["speakers"]: print("  position={} ft toe={:+.0f} SPL={:.1f} dB headroom={:+.1f} dB".format(tuple(float(x) for x in np.round(speaker["position_ft"],2)),speaker["toe_in_deg"],speaker["predicted_spl_db"],speaker["headroom_db"]))
        from .viewer3d import plot_model_comparison_3d
        print("3D comparison figure saved:",plot_model_comparison_3d(trials[0],trials[1],model_ids,models,args.output,feet_to_m(args.height),mlp_ear_height,role=role))
        return
    try:
        with _Progress("Optimizing speaker positions"):
            result=optimize_layout(room,listener,layout,args.facing,args.absorption,modal_q_scale=args.modal_q_scale,
                                   reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,
                                   coherent=args.coherence=="coherent",directivity_on_reflections=args.directivity_on_reflections,models=models,toe_in_range_deg=args.toe_in_range,
                                   room_height_m=feet_to_m(args.height),materials=materials,seat_cluster_spacing_m=args.seat_cluster_spacing,
                                   ear_height_m=mlp_ear_height,
                                   screen_height_m=feet_to_m(args.screen_height) if args.screen_height is not None else None,
                                   mount_heights_m=mount_heights,keepouts=keepouts,spacing_m=.5 if args.fast else .25,
                                   refinement_sweeps=0 if channel_mode else 1,
                                   seat_positions_m=seats,mlp_weight=args.mlp_weight,coverage_threshold_db=args.coverage_threshold_db,
                                   stud_spacing_m=stud_spacing_m,stud_thickness_m=framing_thickness_m,
                                   forbidden_boxes=projector_forbidden_boxes)
    except ValueError as exc:
        retry_room_after_placement_error(exc)
        return
    extra_speakers=[]
    if overhead_channels:
        from .home_theater import place_overhead_channels
        height_model=models[role_models.get("height","generic_in_ceiling")]
        try:
            extra_speakers=place_overhead_channels(overhead_channels,room,feet_to_m(args.height),listener,
                mlp_ear_height,args.standard,args.facing,height_model,.15 if not args.fast else .3,
                joist_spacing_m=joist_spacing_m,joist_thickness_m=framing_thickness_m,
                forbidden_boxes=projector_forbidden_boxes)
        except ValueError as exc: parser.error(str(exc))
    from .viewer3d import build_layout,save_layout,open_viewer
    try:
        scene=build_layout(result,models,feet_to_m(args.height),mlp_ear_height,
                           mount_heights, args.panel_protrusion_mm/1000.,args.standard,extra_speakers,seats)
        scene["keepouts"]=keepouts
        if display_result is not None:
            scene["display"]=display_result
        scene["framing"]={"stud_spacing_m":stud_spacing_m,"joist_spacing_m":joist_spacing_m,
                          "member_thickness_m":framing_thickness_m,
                          "origin_convention":"wall/room polygon origin; verify actual framing on site"}
        if angle_overrides:
            from .home_theater import compliance_rows
            scene["compliance"]=compliance_rows(scene["speakers"],scene["listener_m"],args.facing,args.standard,angle_overrides=angle_overrides)
            compliance_by_channel={row["channel"]:row for row in scene["compliance"]}
            for speaker in scene["speakers"]: speaker["compliance"]=compliance_by_channel.get(speaker["channel"])
    except ValueError as exc: parser.error("3D layout could not be built: {}".format(exc))
    if args.allow_floor:
        from .home_theater import floor_mount_alternatives
        try:
            scene["floor_alternatives"]=floor_mount_alternatives(scene["speakers"],room,seats,models,args.standard,args.facing,
                args.floor_model,feet_to_m(args.floor_wall_clearance),.2 if not args.fast else .35,
                np.r_[listener,mlp_ear_height])
        except ValueError as exc: parser.error("floor alternative search: {}".format(exc))
    for item in scene["speakers"]:
        item["distance_trim_db"]=float(item["receiver_trim_db"])
        if item["channel"].startswith("LFE"):
            item["receiver_trim_db"]=float(args.lfe_gain_db)
    non_lfe_trims=[float(item["receiver_trim_db"]) for item in scene["speakers"] if not item["channel"].startswith("LFE")]
    scene["receiver_calibration"]["trim_spread_db"]=(max(non_lfe_trims)-min(non_lfe_trims)) if non_lfe_trims else 0.
    acoustic=room_metrics(room,feet_to_m(args.height),materials)
    scene["crossover"]={"frequency_hz":float(args.crossover_hz),"filter":"Linkwitz-Riley 4th order",
                        "lfe_gain_db":float(args.lfe_gain_db),"lfe_reference_convention":"+10 dB default"}
    from .home_theater import screen_transmission_loss_db
    scene["screen"]={"present":bool(screen_loss or args.screen_height is not None or keepouts),
        "front_wall_keepouts":keepouts,"transmission_loss_by_frequency_db":{str(f):v for f,v in sorted(screen_loss.items())},
        "note":"Screen loss is applied to L/C/R direct-level and headroom estimates; no loss is assumed without supplied data."}
    if display_result is not None:
        scene["screen"].update(display_result["screen"])
        scene["screen"]["present"]=True
        scene["projector"]=display_result["projector"]
        pg=display_result["projector"]; px,py,pz=pg["position_m"]
        pg["body_inside_room"]=bool(px-pg["body_width_m"]/2.>=room[0].min() and px+pg["body_width_m"]/2.<=room[0].max() and
            py-pg["body_depth_m"]/2.>=room[1].min() and py+pg["body_depth_m"]/2.<=room[1].max() and
            pz-pg["body_height_m"]/2.>=0. and pz+pg["body_height_m"]/2.<=feet_to_m(args.height))
        center=np.asarray(display_result["screen"]["center_m"],dtype=float); gw=display_result["screen"]["geometry"]["width_m"]; gh=display_result["screen"]["geometry"]["height_m"]
        conflicts=[]
        from .viewer3d import front_wall_index
        front_wall=front_wall_index(room,args.facing)
        screen_right=np.asarray(scene["screen"].get("right_xy",[1.,0.]),dtype=float)
        if display_result["screen"].get("material","matte_white")!="ats":
            for sp in scene["speakers"]:
                if sp["channel"] not in ("L","C","R") or sp.get("wall_index")!=front_wall: continue
                pos=np.asarray(sp["position_m"],dtype=float); speaker_model=models[sp["model_id"]]
                half_w=float(speaker_model.width_m)/2.; half_h=float(speaker_model.height_m)/2.
                lateral=abs(float((pos[:2]-center[:2])@screen_right))
                if lateral-half_w<=gw/2. and lateral+half_w>=-gw/2. and pos[2]+half_h>=center[2]-gh/2. and pos[2]-half_h<=center[2]+gh/2.:
                    conflicts.append(sp["channel"])
        scene["screen"]["speaker_conflicts"]=conflicts
        scene["screen"]["conflict_options"]=([] if not conflicts else ["use an ATS screen and place L/C/R behind it","reduce screen width","raise the screen bottom edge","place center above the screen","relax L/R azimuth","use in-wall L/R flanking the screen"])
    from .home_theater import optimize_bass_management
    crossover_search=tuple(args.crossover_search_range) if args.crossover_search_range else (max(40.,args.crossover_hz*.75),min(160.,args.crossover_hz*1.25))
    scene["bass_management_setup"]=optimize_bass_management(scene["speakers"],seats,models,crossover_range_hz=crossover_search)
    from .home_theater import receiver_settings,lr4_responses,phase_mismatch_sum_db,first_reflection_guidance
    from .home_theater import seat_coverage_rows,per_seat_compliance_rows
    scene["seat_coverage"]=seat_coverage_rows(scene["speakers"],seats,args.coverage_threshold_db)
    scene["per_seat_compliance"]=per_seat_compliance_rows(scene["speakers"],seats,args.facing,args.standard)
    scene["worst_compliance_seat"]={}
    for row in scene["per_seat_compliance"]:
        if row["status"]=="N/A": continue
        violation=float(row["azimuth_violation_deg"]+row["elevation_violation_deg"])
        old=scene["worst_compliance_seat"].get(row["channel"])
        if old is None or violation>old["violation_deg"]:
            scene["worst_compliance_seat"][row["channel"]]={"row":row["row"],"seat":row["seat"],"violation_deg":violation,
                "azimuth_deg":row["azimuth_deg"],"elevation_deg":row["elevation_deg"],"status":row["status"]}
    uncovered=[row for row in scene["seat_coverage"] if not row["covered"]]
    scene["seat_acoustics"]={"seat_count":len(seats),"mlp_weight":args.mlp_weight,
        "seats":[{"row":s["row"],"seat":s["seat"],"position_m":s["position_m"],
                  "ear_height_m":s["ear_height_m"],"mlp":bool(np.linalg.norm(np.asarray(s["position_m"])-listener)<1e-6 and abs(s["ear_height_m"]-mlp_ear_height)<1e-6)} for s in seats]}
    scene["seat_acoustics"]["worst_coverage_seat"]=("{}:{}".format(uncovered[0]["row"],uncovered[0]["seat"]) if uncovered else None)
    reflection_rows=[]
    for item in scene["speakers"]:
        if item["channel"] in ("L","C","R"):
            reflections=first_reflection_guidance(room,np.asarray(item["position_m"]),np.asarray(scene["listener_m"]),feet_to_m(args.height),float(item.get("predicted_spl_db",85.)))
            reflection_rows.extend({**row,"source_channel":item["channel"]} for row in reflections)
    scene["first_reflections"]=reflection_rows
    scene["room_acoustics"]={"rt60_target_s":args.rt60_target,"rt60_sabine":[float(x) for x in acoustic["sabine_rt60_s"]],
                             "rt60_eyring":[float(x) for x in acoustic["eyring_rt60_s"]]}
    from .scoring import room_modes_3d,bonello_mode_counts
    scene["room_modes_3d"]=room_modes_3d(room,feet_to_m(args.height),(20.,250.))
    scene["bonello_screening"]=bonello_mode_counts(scene["room_modes_3d"],(20.,250.))
    from .scoring import rectangular_room_frame
    from .home_theater import quarter_wave_notch_hz
    origin,ux,uy,lx,ly=rectangular_room_frame(room)
    sbir_rows=[]
    for speaker in scene["speakers"]:
        local=np.asarray(speaker["position_m"][:2])-origin
        x=float(local@ux); y=float(local@uy)
        distances=[y,lx-x,ly-y,x]
        mount_wall=int(speaker.get("wall_index",-1))
        if 0<=mount_wall<4: distances.pop(mount_wall)
        boundary_distance=max(.01,min(distances))
        sbir_rows.append({"channel":speaker["channel"],"nearest_boundary_distance_m":boundary_distance,
                          "first_quarter_wave_hz":quarter_wave_notch_hz(boundary_distance)})
    forward={"north":uy,"south":-uy,"east":ux,"west":-ux}[args.facing]
    back_plane=float(np.min(room.T@forward))
    seat_sbir=[]
    for seat in seats:
        point=np.asarray(seat["position_m"])
        distance=max(.01,float(point@forward-back_plane))
        seat_sbir.append({"row":seat["row"],"seat":seat["seat"],"back_wall_distance_m":distance,
                          "first_quarter_wave_hz":quarter_wave_notch_hz(distance)})
    scene["sbir_estimates"]={"speakers":sbir_rows,"seats":seat_sbir,"formula":"f=c/(4d), c=343 m/s"}
    optimized_bass=next((row["best"]["speakers"] for row in result.placements_by_type if row["type"]=="bass"),[])
    if optimized_bass:
        from .home_theater import compare_sub_strategies
        scene["sub_strategy_comparison"]=compare_sub_strategies(room,[seat["position_m"] for seat in seats],args.facing,args.absorption,
            band_hz=(30.,args.crossover_hz),step_hz=1.,q_scale=args.modal_q_scale,
            free_sources=[speaker["position_m"] for speaker in optimized_bass])
    else: scene["sub_strategy_comparison"]=[]
    headroom_rows=[]
    for item in scene["speakers"]:
        from .room_acoustics import boundary_gain_for_mount
        model=models[item["model_id"]]; distance=float(item["distance_m"])
        surface=item.get("placement_mode",item.get("surface","wall"))
        boundary=boundary_gain_for_mount(model.mount_type,surface)
        aim=np.asarray(item.get("aim_direction",[0.,1.,0.]),dtype=float); aim/=max(float(np.linalg.norm(aim)),1e-12)
        source=np.asarray(item["position_m"],dtype=float); ray=np.asarray(scene["listener_m"],dtype=float)-source
        ray/=max(float(np.linalg.norm(ray)),1e-12)
        off_axis=float(np.degrees(np.arccos(np.clip(aim@ray,-1.,1.))))
        band_indices=(0,1) if item["type"]=="bass" else (2,3,4,5)
        levels=[__import__("speakerplacer.room_acoustics",fromlist=["level_components"]).level_components(
            model,distance,model.effective_power_w,acoustic,index,off_axis,boundary) for index in band_indices]
        screen_loss_by_band=np.asarray(screen_transmission_loss_db(np.asarray(acoustic["bands_hz"]),screen_loss),dtype=float)
        apply_screen=item["channel"] in ("L","C","R")
        band_loss=screen_loss_by_band[list(band_indices)] if apply_screen else np.zeros(len(band_indices))
        predicted=float(np.mean([row["total_spl_db"]-loss for row,loss in zip(levels,band_loss)]))
        direct=float(np.mean([row["direct_spl_db"]-loss for row,loss in zip(levels,band_loss)]))
        reverberant_add=predicted-direct
        boundary_gain=float(np.mean([row["boundary_gain_db"] for row in levels]))
        cap_db=(model.max_spl_lf_db if item["type"]=="bass" and model.max_spl_lf_db is not None else model.max_spl_db)-20.*np.log10(max(distance,1e-6))+boundary_gain+reverberant_add-float(np.mean(band_loss))
        available=min(predicted,cap_db); required=args.reference_spl+max(0.,args.peak_headroom-(10. if item["type"]=="bass" else 0.))
        headroom_rows.append({"channel":item["channel"],"model":model.model_id,"sensitivity_db":model.sensitivity_1w_1m_db,
            "power_w":model.effective_power_w,"distance_m":distance,"directivity_db":float(model.gain_db(off_axis)),"boundary_gain_db":boundary_gain,
            "reverberant_add_db":reverberant_add,"max_spl_cap_db":cap_db,"predicted_peak_db":available,
            "required_peak_db":required,"headroom_db":available-required,
            "screen_loss_db":float(np.mean(band_loss))})
    scene["headroom_derivation"]=headroom_rows
    report_lines=["# Speaker placement report","", "- Layout: `{}`".format(args.layout or "custom"),
        "- Standard: `{}` (guidance marked verify)".format(args.standard),
        "- Room: {:.2f} × {:.2f} × {:.2f} ft".format(args.length,args.width,args.height),
        "- Seats: {}; MLP imaging weight: {:.2f}".format(len(seats),args.mlp_weight),
        "- Treatment preset: `{}`; coefficients are typical estimates, not measured data.".format(args.treatment_preset or "custom/default")]
    if display_result is not None:
        p=display_result["projector"]; g=display_result["screen"]["geometry"]
        seats_display=display_result["per_seat"]; view=[r["viewing_angle_deg"] for r in seats_display]
        report_lines += ["", "## Display feasibility (user specs; targets marked verify)", "",
            "| Item | Value | Allowed/target | Status | Note |", "|---|---:|---:|---|---|",
            "| Screen/image | {:.2f}×{:.2f} / {:.2f}×{:.2f} m | supplied | PASS | image inscribed in physical screen |".format(g["width_m"],g["height_m"],g["image_width_m"],g["image_height_m"]),
            "| Viewing angle MLP / worst | {:.1f}° / {:.1f}° | 30–40° verify | {} | vectors to image edges |".format(view[0],max(view),"PASS" if 30<=view[0]<=40 else "WARN"),
            "| Throw ratio / zoom | {:.3f} / {:.2f} | {:.3f}–{:.3f} | {} | throw {:.2f} m |".format(p["implied_throw_ratio"],p["zoom_position"],p["throw_ratio_min"],p["throw_ratio_max"],"PASS" if p["feasible"] else "FAIL",p["throw_distance_m"]),
            "| Brightness | {:.1f} fL / {:.1f} nits | {:.1f} fL verify | {} | effective lumens {:.0f} |".format(p["brightness"]["foot_lamberts"],p["brightness"]["nits"],args.target_fl,display_result["brightness_status"],p["lumens_effective"]),
            "| Effective contrast | {:.1f}:1 | ambient estimate | WARN | ambient {:.0f} lux |".format(p["effective_contrast"],p["ambient_lux"]),
            "| Vertical lens shift | {:+.3f} | configured range | {} | keystone {:.2f}° |".format(p["lens_shift"]["required_vertical_shift"],"PASS" if p["lens_shift"]["keystone_allowed"] else "FAIL",p["lens_shift"]["keystone_angle_deg"]),
            "| Projector body fit | {} | within room shell | {} | position {} |".format("inside" if p.get("body_inside_room",True) else "outside/overlap", "PASS" if p.get("body_inside_room",True) else "FAIL",p["position_source"]),
            "| Projector noise | {:.1f} dBA worst seat | {:.1f} dBA floor | {} | direct-field estimate |".format(max(p["noise_at_seats_dba"]),args.noise_floor_dba,"PASS" if max(p["noise_at_seats_dba"])<=args.noise_floor_dba else "WARN")]
        report_lines += ["", "### Per-seat display results", "", "| Seat | Viewing angle | Top-edge angle | Distance (screen heights) | Brightness | Pixel acuity |", "|---:|---:|---:|---:|---:|---|"]
        for row in seats_display:
            report_lines.append("| {} | {:.1f}° | {:.1f}° | {:.2f} | {:.1f} fL | {} |".format(row["index"]+1,row["viewing_angle_deg"],row["vertical_top_angle_deg"],row["distance_in_screen_heights"],row["foot_lamberts"],"pixels resolved" if not row["pixels_unresolved"] else "unresolved"))
        conflicts=scene["screen"].get("speaker_conflicts",[])
        if conflicts:
            report_lines += ["", "### CONFLICT: front speakers intersect the solid screen frame", "",
                "| Channel | Conflict | Suggested resolution |", "|---|---|---|"]
            options="; ".join(scene["screen"].get("conflict_options",[]))
            for channel in conflicts: report_lines.append("| {} | speaker box intersects screen footprint | {} |".format(channel,options))
    report_lines += ["", "## Channel compliance", "", "| Channel | Azimuth | Allowed | Elevation | Allowed | Distance (m) | Status | Provenance |", "|---|---:|---|---:|---|---:|---|---|"]
    for row in scene["compliance"]:
        report_lines.append("| {} | {} | {} | {} | {} | {:.2f} | {} | {} |".format(row["channel"],_fmt_angle(row["azimuth_deg"]),row["azimuth_allowed"],_fmt_angle(row["elevation_deg"]),row["elevation_allowed"],row["distance_m"],row["status"],row.get("provenance","provisional")))
    report_lines += ["", "### Worst-seat angular compliance", "", "| Channel | Seat | Azimuth | Elevation | Status |", "|---|---|---:|---:|---|"]
    for channel,row in scene["worst_compliance_seat"].items():
        report_lines.append("| {} | {}:{} | {:+.1f}° | {:+.1f}° | {} |".format(channel,row["row"],row["seat"],row["azimuth_deg"],row["elevation_deg"],row["status"]))
    report_lines += ["", "## Receiver delay and trim", "", "LFE reference gain is kept separate from inverse-distance trim.", "| Channel | Distance (m) | Delay (ms) | Distance trim (dB) | Receiver/LFE reference (dB) |", "|---|---:|---:|---:|---:|"]
    for speaker in scene["speakers"]:
        report_lines.append("| {} | {:.2f} | {:.2f} | {:+.2f} | {:+.2f} |".format(speaker["channel"],speaker["distance_m"],speaker["receiver_delay_ms"],speaker["distance_trim_db"],speaker["receiver_trim_db"]))
    if scene["screen"]["present"]:
        report_lines += ["", "Acoustic screen insertion-loss curve applied to L/C/R headroom (dB):", "", "| Frequency (Hz) | Loss (dB) |", "|---:|---:|"]
        for freq,loss in scene["screen"]["transmission_loss_by_frequency_db"].items(): report_lines.append("| {} | {:.1f} |".format(freq,loss))
    report_lines += ["", "## Peak SPL headroom derivation", "", "Positive headroom means available peak SPL exceeds the requested peak. Available SPL is capped by the model maximum.",
        "| Channel | Model | Sensitivity (dB/1W/1m) | Power (W) | Distance (m) | Directivity to MLP (dB) | Boundary gain (dB) | Reverberant addition (dB) | Screen loss (dB) | Max-SPL cap (dB) | Required peak (dB) | Headroom (dB) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in headroom_rows:
        report_lines.append("| {} | {} | {:.1f} | {:.1f} | {:.2f} | {:+.1f} | {:+.1f} | {:.1f} | {:.1f} | {:.1f} | {:.1f} | {:+.1f} |".format(
            row["channel"],row["model"],row["sensitivity_db"],row["power_w"],row["distance_m"],row["directivity_db"],row["boundary_gain_db"],
            row["reverberant_add_db"],row["screen_loss_db"],row["max_spl_cap_db"],row["required_peak_db"],row["headroom_db"]))
    report_lines += ["", "## SBIR / quarter-wave estimates", "", "First-order screening estimate f=c/(4d), c=343 m/s; actual notch depth depends on boundary impedance and placement.",
        "| Speaker | Nearest horizontal boundary (m) | First notch (Hz) |", "|---|---:|---:|"]
    for row in sbir_rows:
        report_lines.append("| {} | {:.2f} | {:.1f} |".format(row["channel"],row["nearest_boundary_distance_m"],row["first_quarter_wave_hz"]))
    if scene.get("floor_alternatives"):
        wall_sbir={row["channel"]:row["first_quarter_wave_hz"] for row in sbir_rows}
        report_lines += ["", "## Wall vs floor/stand alternatives", "", "Floor candidates use standard azimuth bounds, cabinet clearance and seat coverage. This geometric comparison is not an acoustic measurement.",
            "| Channel | Wall position (ft) | Floor alternative (ft) | Wall notch (Hz) | Floor notch (Hz) | Max seat off-axis (deg) |", "|---|---|---|---:|---:|---:|"]
        for row in scene["floor_alternatives"]:
            floor=row.get("position_ft")
            report_lines.append("| {} | {} | {} | {} | {} | {} |".format(row["channel"],", ".join("{:.2f}".format(x) for x in np.asarray(row["wall_solution_position_m"])/.3048),
                "none" if floor is None else ", ".join("{:.2f}".format(x) for x in floor),"—" if row["channel"] not in wall_sbir else "{:.1f}".format(wall_sbir[row["channel"]]),
                "—" if "first_boundary_notch_hz" not in row else "{:.1f}".format(row["first_boundary_notch_hz"]),
                "—" if "max_seat_off_axis_deg" not in row else "{:.1f}".format(row["max_seat_off_axis_deg"])))
    report_lines += ["", "### Seat-to-back-wall estimates", "", "| Seat | Back-wall distance (m) | First notch (Hz) |", "|---|---:|---:|"]
    for row in seat_sbir:
        report_lines.append("| {}:{} | {:.2f} | {:.1f} |".format(row["row"],row["seat"],row["back_wall_distance_m"],row["first_quarter_wave_hz"]))
    report_lines += ["", "## Room and bass management", "", "- LR4 crossover: {:.1f} Hz; LFE reference gain: {:+.1f} dB.".format(args.crossover_hz,args.lfe_gain_db),
        "- RT60 target: {:.2f} s; Sabine mean estimate: {:.2f} s.".format(args.rt60_target,float(np.mean(acoustic["sabine_rt60_s"]))),
        "", "### RT60 by octave band", "", "| Band (Hz) | Sabine (s) | Eyring (s) | Target (s) |", "|---:|---:|---:|---:|"]
    for i,band in enumerate(acoustic["bands_hz"]):
        report_lines.append("| {:.0f} | {:.2f} | {:.2f} | {:.2f} |".format(band,acoustic["sabine_rt60_s"][i],acoustic["eyring_rt60_s"][i],args.rt60_target))
    setup=scene["bass_management_setup"]
    if setup.get("status")=="estimated":
        report_lines += ["", "### Bass-management setup estimate", "",
            "Coherent direct-field LR4 sweep; use measurements/receiver calibration to confirm this estimate.",
            "| Crossover (Hz) | Sub trim (dB) | Additional delay (ms) | Polarity | Seat spread (dB) | Crossover dip (dB) |", "|---:|---:|---:|---|---:|---:|"]
        report_lines.append("| {:.0f} | {:+.1f} | {:+.1f} | {} | {:.2f} | {:.2f} |".format(setup["crossover_hz"],setup["sub_gain_trim_db"],setup["additional_sub_delay_ms"],setup["sub_polarity"],setup["seat_std_db"],setup["crossover_dip_db"]))
        report_lines += ["", "Per-sub receiver controls:", "", "| Sub | Gain trim (dB) | Additional delay (ms) | Polarity |", "|---|---:|---:|---|"]
        for row in setup.get("sub_parameters",[]): report_lines.append("| {} | {:+.1f} | {:+.1f} | {} |".format(row["channel"],row["gain_trim_db"],row["additional_delay_ms"],row["polarity"]))
        report_lines += ["", "Per-main size based on model F3:", "", "| Channel | Recommendation |", "|---|---|"]
        for channel,size in setup["channel_size_recommendation"].items(): report_lines.append("| {} | {} |".format(channel,size))
    report_lines += ["", "### 3D room modes (20–250 Hz)", "", "| (n,m,l) | Hz | Type | Near-coincident modes |", "|---|---:|---|---|"]
    for mode in scene["room_modes_3d"]:
        if mode["near_coincident"] or mode["type"]=="axial":
            coincident=", ".join("({}, {}, {}) {:.1f} Hz".format(x["n"],x["m"],x["l"],x["frequency_hz"]) for x in mode["coincident_with"]) or "—"
            report_lines.append("| ({}, {}, {}) | {:.1f} | {} | {} |".format(mode["n"],mode["m"],mode["l"],mode["frequency_hz"],mode["type"],coincident))
    report_lines += ["", "Coincidence threshold is max(1 Hz, 2% of frequency), with sound speed 343 m/s.",
        "", "### Room-ratio guidance", "", "Normalized L:W:H ratio is {:.2f}:{:.2f}:1.00. Bonello 1/3-octave screening from 20–250 Hz is {}; this is advisory, not an installation certification.".format(args.length/args.height,args.width/args.height,"non-decreasing" if scene["bonello_screening"][1] else "not non-decreasing"),
        "Bolt-area ratio classification is not evaluated; ratios are shown as a design cue.",
        "", "| 1/3-octave center (Hz) | 3D mode count |", "|---:|---:|"]
    for row in scene["bonello_screening"][0]:
        report_lines.append("| {:.1f} | {} |".format(row["center_hz"],row["mode_count"]))
    report_lines += [
        "", "## First reflections", "", "| Source speaker | Surface | Point (ft) | Delay (ms) | Relative level (dB) | Suggested panel |", "|---|---|---|---:|---:|---|"]
    for row in reflection_rows:
        panel=row["panel"]
        report_lines.append("| {} | {} | {} | {:.2f} | {:+.1f} | {:.1f} × {:.1f} m |".format(row["source_channel"],row["surface"],", ".join("{:.2f}".format(v) for v in row["reflection_point_ft"]),row["time_ms"],row["level_relative_db"],panel["width_m"],panel["height_m"]))
    if scene["sub_strategy_comparison"]:
        report_lines += ["", "## Reference sub-strategy comparison", "", "Strategies use equal total electrical power; null depth and cancellation cost are relative to the mean/front-midpoint reference.",
            "The delayed inverted rear array is a two-source approximation, not a full opposing-wall double-bass array.",
            "| Strategy | Subs | Seat std (dB) | Null depth (dB) | Cancellation cost (dB) | Mean level (dB) |", "|---|---:|---:|---:|---:|---:|"]
        for item in scene["sub_strategy_comparison"]:
            report_lines.append("| {} | {} | {:.2f} | {:.1f} | {:+.1f} | {:.1f} |".format(item["strategy"],item["sub_count"],item["seat_std_db"],item["null_depth_db"],item["cancellation_cost_db"],item["mean_level_db"]))
    report_path=Path(args.output).expanduser()/"report.md"; report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text("\n".join(report_lines)+"\n",encoding="utf-8")
    scene["report_file"]=str(report_path.resolve())
    if args.save_layout:
        print("Layout JSON saved:",save_layout(scene,args.save_layout,args.save_candidates))
    elif args.save_candidates:
        candidate_path=Path(args.save_candidates).expanduser(); candidate_path.parent.mkdir(parents=True,exist_ok=True)
        candidate_path.write_text(json.dumps({"schema_version":1,"candidates":scene["candidate_scores"]},indent=2,allow_nan=False)+"\n",encoding="utf-8")
        print("Candidate scores saved:",candidate_path)
    print("Receiver distance compensation (relative delays and free-field trims):")
    print("channel | distance m | delay ms | distance trim dB | receiver/LFE reference dB")
    for index,speaker in enumerate(scene["speakers"],1):
        print("{} | {:.2f} | {:.2f} | {:+.2f} | {:+.2f}".format(speaker["channel"],speaker["distance_m"],speaker["receiver_delay_ms"],speaker["distance_trim_db"],speaker["receiver_trim_db"]))
    print("Distance spread {:.2f} m; trim spread {:.2f} dB (receiver reference {:.2f} m)".format(
        scene["receiver_calibration"]["distance_spread_m"],scene["receiver_calibration"]["trim_spread_db"],scene["receiver_calibration"]["d_ref_m"]))
    if max((s["receiver_delay_ms"] for s in scene["speakers"]),default=0.)>args.receiver_max_delay_ms:
        print("WARN receiver delay exceeds configured {:.1f} ms limit".format(args.receiver_max_delay_ms))
    if max((abs(s["receiver_trim_db"]) for s in scene["speakers"]),default=0.)>args.receiver_max_trim_db:
        print("WARN receiver trim exceeds configured ±{:.1f} dB limit".format(args.receiver_max_trim_db))
    print("Channel compliance ({})".format(args.standard))
    print("channel | azimuth | allowed | elevation | allowed | distance m | result | provenance")
    for row in scene["compliance"]:
        print("{} | {} | {} | {} | {} | {:.2f} | {} | {}".format(row["channel"],_fmt_angle(row["azimuth_deg"]),row["azimuth_allowed"],_fmt_angle(row["elevation_deg"]),row["elevation_allowed"],row["distance_m"],row["status"],row.get("provenance","provisional")))
    if uncovered: print("WARN: approximate model coverage excludes {} of {} channel-seat combinations; see layout JSON".format(len(uncovered),len(scene["seat_coverage"])))
    for warning in result.warnings: print(warning)
    scene_speakers=iter(scene["speakers"])
    for placement in result.placements_by_type:
        print("{} / {} (score {:.2f}):".format(placement["type"],placement["model_id"],placement["best"]["score_db"]))
        for speaker in placement["best"]["speakers"]:
            visual=next(scene_speakers)
            x,y,z=visual["position_ft"]
            model=models[speaker["model_id"]]
            distance=float(np.linalg.norm(speaker["position_m"]-listener))
            band_index=0 if placement["type"]=="bass" else 3
            level=__import__("speakerplacer.room_acoustics",fromlist=["level_components"]).level_components(
                model,distance,model.effective_power_w,acoustic,band_index,
                boundary_gain_db=__import__("speakerplacer.room_acoustics",fromlist=["boundary_gain_for_mount"]).boundary_gain_for_mount(
                    model.mount_type,visual.get("placement_mode",visual.get("surface","wall"))))
            print("  {} ({:.2f}, {:.2f}, {:.2f}) ft; yaw {:+.0f} deg; tilt {:+.1f} deg; SPL {:.1f} dB; headroom {:+.1f} dB{}".format(
                speaker["model_id"],x,y,z,visual["yaw_deg"],visual["pitch_deg"],
                speaker["predicted_spl_db"],speaker["headroom_db"],
                "; WARN: "+", ".join(speaker.get("warnings",[])) if speaker.get("warnings") else ""))
            print("    {:.0f} Hz level: direct {:.1f}, reverberant {:.1f}, total {:.1f} dB SPL; critical distance {:.2f} m{}".format(
                acoustic["bands_hz"][band_index],level["direct_spl_db"],level["reverberant_spl_db"],level["total_spl_db"],level["critical_distance_m"],
                " (listener beyond critical distance)" if level["warn_beyond_critical"] else ""))
        for term,value in placement["best"]["terms"].items(): print("  {}: {:.2f}".format(term,value))
    front_spec=next((spec for spec in layout if spec.name in ("front","regular")),None)
    bass_spec=next((spec for spec in layout if spec.name=="bass"),None)
    if front_spec and bass_spec:
        front_model=models[front_spec.model_id or DEFAULT_MODEL_BY_ROLE["front"]]
        bass_model=models[bass_spec.model_id or DEFAULT_MODEL_BY_ROLE["bass"]]
        upper=min(front_model.crossover_hz or front_model.freq_high_hz,bass_model.crossover_hz or bass_model.freq_high_hz)
        lower=max(front_model.freq_low_hz,bass_model.f3_hz or bass_model.freq_low_hz)
        overlap=max(0.,upper-lower); gap=max(0.,front_model.freq_low_hz-(bass_model.crossover_hz or bass_model.freq_high_hz))
        print("Crossover handoff: {:.0f}-{:.0f} Hz overlap ({:.0f} Hz); front low edge {:.0f} Hz, bass crossover {:.0f} Hz, bass F3 {:.0f} Hz".format(lower,upper,overlap,front_model.freq_low_hz,bass_model.crossover_hz, bass_model.f3_hz))
        if gap>0: print("WARN crossover gap: {:.0f} Hz before front model's rated low edge".format(gap))
        elif overlap>50: print("WARN large crossover overlap ({:.0f} Hz); verify filters and phase in the actual system".format(overlap))
        frequencies=np.linspace(args.crossover_hz*.75,args.crossover_hz*1.25,101)
        low,high=lr4_responses(frequencies,args.crossover_hz)
        aligned_db=20*np.log10(np.maximum(np.abs(low+high),1e-12))
        print("Bass management: LR4 HP mains + LP subs at {:.1f} Hz; LFE gain {:+.1f} dB; aligned sum {:.2f}..{:.2f} dB".format(
            args.crossover_hz,args.lfe_gain_db,float(aligned_db.min()),float(aligned_db.max())))
        half_period=1./(2.*args.crossover_hz)
        print("Crossover phase diagnostic: {:.2f} ms offset sums to {:.1f} dB at crossover".format(
            half_period*1000.,phase_mismatch_sum_db(args.crossover_hz,args.crossover_hz,half_period)))
    print("First-reflection points (L/C/R): {} points; coordinates and relative levels are included in layout JSON".format(len(reflection_rows)))
    if float(np.mean(acoustic["sabine_rt60_s"]))>args.rt60_target:
        print("WARN average Sabine RT60 {:.2f} s exceeds {:.2f} s target; consider broadband absorption/diffusion".format(float(np.mean(acoustic["sabine_rt60_s"])),args.rt60_target))
    print("Figures saved:",", ".join(map(str,plot_results(result,args.output,args.mode=="2d" and not args.no_show))))
    from .plotting import plot_channel_table,plot_ceiling_heatmaps
    table_path=plot_channel_table(scene,args.output); ceiling_path=plot_ceiling_heatmaps(scene,args.output)
    if table_path: print("Full channel table saved:",table_path)
    if ceiling_path: print("Ceiling channel heatmaps saved:",ceiling_path)
    from .plotting import plot_wall_height_heatmaps
    heatmap_path=plot_wall_height_heatmaps(scene,args.output)
    if heatmap_path: print("Wall/height score heatmaps saved:",heatmap_path)
    from .plotting import plot_seat_bass_response
    axial_mode_frequencies=[mode["frequency_hz"] for mode in scene["room_modes_3d"] if mode["type"]=="axial"]
    seat_bass_path=plot_seat_bass_response(result,args.output,axial_mode_frequencies)
    if seat_bass_path: print("Seat-by-seat bass response saved:",seat_bass_path)
    if scene["sub_strategy_comparison"]:
        from .plotting import plot_sub_strategy_comparison
        strategy_path=plot_sub_strategy_comparison(scene["sub_strategy_comparison"],args.output)
        print("Sub-strategy comparison saved:",strategy_path)
    if scene["bass_management_setup"].get("status")=="estimated":
        from .plotting import plot_bass_management_response
        crossover_path=plot_bass_management_response(scene["bass_management_setup"],args.output)
        print("Bass-management response saved:",crossover_path)
    modal_frequencies=np.unique(np.round(np.asarray(__import__("speakerplacer.scoring",fromlist=["room_modes"]).room_modes(room,(30.,200.)))[:,0],8))
    gaps=np.diff(modal_frequencies)
    print("Room acoustics (typical material estimates; replace with measured data):")
    for index,frequency in enumerate(acoustic["bands_hz"]):
        print("  {:.0f} Hz: RT60 Sabine {:.2f} s / Eyring {:.2f} s; mean absorption {:.3f}".format(frequency,acoustic["sabine_rt60_s"][index],acoustic["eyring_rt60_s"][index],acoustic["mean_absorption"][index]))
    print("  Schroeder frequency {:.0f} Hz; modal count {} (30-200 Hz); smallest modal gap {:.2f} Hz".format(float(np.mean(acoustic["schroeder_hz"])),len(modal_frequencies),float(gaps.min()) if len(gaps) else float("nan")))
    if args.validate:
        from .validation import run_validation
        with _Progress("Running physics validation"):
            report=run_validation(room,listener,layout,args.facing,args.absorption,args.output,base_result=result,simulator=None,
                                  modal_q_scale=args.modal_q_scale,reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,
                                  room_height_m=feet_to_m(args.height),materials=materials,ear_height_m=mlp_ear_height)
        print(report)
    # Compare two catalog models for the first imaging role so model sensitivity is visible.
    imaging=next((spec for spec in layout if spec.scorer=="imaging"),None)
    if imaging is not None:
        alternatives={"front":["generic_compact_wall","generic_narrow_onwall"],"surround":["generic_surround_wide","generic_compact_wall"]}.get(imaging.name,[])
        if len(alternatives)==2:
            comparison=[]
            for model_id in alternatives:
                trial=[replace(spec,model_id=model_id) if spec is imaging else spec for spec in layout]
                try: comparison.append(optimize_layout(room,listener,trial,args.facing,args.absorption,modal_q_scale=args.modal_q_scale,reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,coherent=args.coherence=="coherent",directivity_on_reflections=args.directivity_on_reflections,room_height_m=feet_to_m(args.height),materials=materials,seat_cluster_spacing_m=args.seat_cluster_spacing))
                except ValueError: pass
            if len(comparison)==2:
                from .viewer3d import plot_model_comparison_3d
                print("3D comparison figure saved:",plot_model_comparison_3d(comparison[0],comparison[1],alternatives,models,args.output,feet_to_m(args.height),mlp_ear_height,role=imaging.name))
    if args.bass_count is not None:
        import matplotlib.pyplot as plt
        from .speaker_types import DEFAULT_SPEAKER_TYPES
        base_bass=next((spec for spec in layout if spec.name=="bass"),DEFAULT_SPEAKER_TYPES["bass"])
        experiment=[]
        for count in (1,2,4):
            spec=replace(base_bass,count=count,symmetric=False)
            trial_layout=[spec if item.name=="bass" else item for item in layout]
            if not any(item.name=="bass" for item in layout): trial_layout.append(spec)
            trial=optimize_layout(room,listener,trial_layout,args.facing,args.absorption,modal_q_scale=args.modal_q_scale,
                                  reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,coherent=args.coherence=="coherent",directivity_on_reflections=args.directivity_on_reflections,room_height_m=feet_to_m(args.height),materials=materials,seat_cluster_spacing_m=args.seat_cluster_spacing)
            bass=next(item for item in trial.placements_by_type if item["type"]=="bass")["best"]
            response=bass["modal_response"]; experiment.append((count,response["frequencies_hz"],response["response_db"],bass["terms"]["flatness"],bass["speakers"]))
            print("Bass-count experiment {} speakers: flatness {:.2f}; positions {}".format(count,bass["terms"]["flatness"],[tuple(np.round(s["position_m"]/.3048,1)) for s in bass["speakers"]]))
        fig,ax=plt.subplots(figsize=(8,4))
        for count,freq,response,flatness,_ in experiment: ax.plot(freq,response,label="{} bass (flatness {:.2f})".format(count,flatness))
        ax.set(xlabel="Frequency (Hz)",ylabel="Relative pressure (dB)",title="Bass-count modal response experiment"); ax.legend(); fig.tight_layout()
        path=__import__("pathlib").Path(args.output)/"bass_count_experiment.png"; path.parent.mkdir(parents=True,exist_ok=True); fig.savefig(path,dpi=180); plt.close(fig); print("Bass-count figure saved:",path)
    if args.mode=="3d":
        print("Preparing interactive 3D viewer...")
        try:
            open_viewer(scene,args.output,show=not args.no_show and args.view3d,
                        save_views=args.save_views,elev=args.view_elev,azim=args.view_azim,
                        show_coverage=args.show_coverage,show_candidates=args.show_candidates,
                        reflection_index=args.show_reflections)
        except ValueError as exc: parser.error(str(exc))

if __name__=="__main__": main()
