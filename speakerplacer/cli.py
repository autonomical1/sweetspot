"""CLI for typed, model-aware wall speaker placement."""
import argparse
from dataclasses import replace
import numpy as np
from .room import make_room,default_listener,feet_to_m
from .optimize import optimize_layout
from .speaker_types import DEFAULT_LAYOUT, parse_speaker_layout
from .speaker_models import DEFAULT_SPEAKER_MODELS, DEFAULT_MODEL_BY_ROLE, resolve_model, load_models_file, validate_models
from .plotting import plot_results, plot_model_comparison, plot_model_specs

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
    parser=argparse.ArgumentParser(description="Optimize typed wall-mounted speakers in a 2D room")
    parser.add_argument("--length",type=float,help="room length in feet")
    parser.add_argument("--width",type=float,help="room width in feet")
    parser.add_argument("--listener",nargs=2,type=float,metavar=("X","Y"),help="listener position in feet")
    parser.add_argument("--facing",choices=("north","south","east","west"),default="north")
    parser.add_argument("--absorption",type=float,default=.2)
    parser.add_argument("--speakers",nargs="+",default=None,metavar="TYPE:COUNT[:MODEL]",help="e.g. front:2:generic_inwall_lcr surround:2:generic_surround_wide bass:2:generic_inwall_sub")
    parser.add_argument("--priority",default="front,bass,surround",help="type search order")
    parser.add_argument("--modal-q-scale",type=float,default=20.,help="Q = scale / sqrt(absorption)")
    parser.add_argument("--reference-spl",type=float,default=85.,help="target average SPL at listener")
    parser.add_argument("--peak-headroom",type=float,default=20.,help="peak allowance above average SPL")
    parser.add_argument("--coherence",choices=("coherent","incoherent"),default="coherent")
    parser.add_argument("--toe-in-range",nargs=2,type=float,default=None,metavar=("MIN","MAX"),help="override toe-in search bounds in degrees")
    parser.add_argument("--bass-count",type=int,choices=(1,2,4),help="run an optional bass count comparison")
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
    parser.add_argument("--output",default="output",help="figure output directory")
    args=parser.parse_args(argv)
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
    if args.length is None or args.width is None: parser.error("--length and --width are required unless a registry action is used")
    room=make_room(args.length,args.width)
    listener=default_listener(room,args.facing) if args.listener is None else tuple(feet_to_m(x) for x in args.listener)
    speaker_tokens=args.speakers or ["{}:{}".format(name,count) for name,count in DEFAULT_LAYOUT]
    clean_tokens=[]; inline_overrides={}
    for item in speaker_tokens:
        parts=item.split(":")
        if len(parts)==3 and "@" in parts[2]:
            try: model_id,updates=_parse_inline_model(parts[2],models)
            except ValueError as exc: parser.error(str(exc))
            parts[2]=model_id; inline_overrides[model_id]=updates
        clean_tokens.append(":".join(parts))
    layout=parse_speaker_layout(clean_tokens)
    # Inline overrides are converted into temporary immutable model records.
    from dataclasses import replace
    for model_id,updates in inline_overrides.items():
        try: models[model_id]=replace(models[model_id],**updates)
        except (TypeError,ValueError) as exc: parser.error("invalid override for {}: {}".format(model_id,exc))
    if args.toe_in_range is not None:
        low,high=args.toe_in_range
        if low>high or low < -90 or high > 90: parser.error("--toe-in-range requires MIN <= MAX within -90..90")
    priority=[name.strip() for name in args.priority.split(",") if name.strip()]; rank={name:index for index,name in enumerate(priority)}
    layout.sort(key=lambda spec:rank.get(spec.name,len(rank)))
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
                directivity_on_reflections=args.directivity_on_reflections,models=models))
        for model_id,trial in zip(model_ids,trials):
            row=next(item for item in trial.placements_by_type if item["type"]==role)["best"]
            print("{} | score {:.2f} | terms {}".format(model_id,row["score_db"],row["terms"]))
            for speaker in row["speakers"]: print("  position={} ft toe={:+.0f} SPL={:.1f} dB headroom={:+.1f} dB".format(tuple(float(x) for x in np.round(speaker["position_ft"],2)),speaker["toe_in_deg"],speaker["predicted_spl_db"],speaker["headroom_db"]))
        print("Comparison figure saved:",plot_model_comparison(trials[0],trials[1],model_ids,args.output,role=role))
        return
    result=optimize_layout(room,listener,layout,args.facing,args.absorption,modal_q_scale=args.modal_q_scale,
                           reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,
                           coherent=args.coherence=="coherent",directivity_on_reflections=args.directivity_on_reflections,models=models,toe_in_range_deg=args.toe_in_range)
    for warning in result.warnings: print(warning)
    for placement in result.placements_by_type:
        print("{} / {} (score {:.2f}):".format(placement["type"],placement["model_id"],placement["best"]["score_db"]))
        for speaker in placement["best"]["speakers"]:
            x,y=speaker["position_m"]/0.3048
            print("  {} ({:.2f}, {:.2f}) ft; SPL {:.1f} dB; headroom {:+.1f} dB; angle {:+.1f} deg; toe-in {:+.0f} deg{}".format(speaker["model_id"],x,y,speaker["predicted_spl_db"],speaker["headroom_db"],speaker["angle_deg"],speaker.get("toe_in_deg",0.),"; WARN: "+", ".join(speaker.get("warnings",[])) if speaker.get("warnings") else ""))
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
    print("Figures saved:",", ".join(map(str,plot_results(result,args.output,not args.no_show))))
    if args.validate:
        from .validation import run_validation
        report=run_validation(room,listener,layout,args.facing,args.absorption,args.output,base_result=result,simulator=None,
                              modal_q_scale=args.modal_q_scale,reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom)
        print(report)
    # Compare two catalog models for the first imaging role so model sensitivity is visible.
    imaging=next((spec for spec in layout if spec.scorer=="imaging"),None)
    if imaging is not None:
        alternatives={"front":["generic_compact_wall","generic_narrow_onwall"],"surround":["generic_surround_wide","generic_compact_wall"]}.get(imaging.name,[])
        if len(alternatives)==2:
            comparison=[]
            for model_id in alternatives:
                trial=[replace(spec,model_id=model_id) if spec is imaging else spec for spec in layout]
                try: comparison.append(optimize_layout(room,listener,trial,args.facing,args.absorption,modal_q_scale=args.modal_q_scale,reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,coherent=args.coherence=="coherent",directivity_on_reflections=args.directivity_on_reflections))
                except ValueError: pass
            if len(comparison)==2: print("Comparison figure saved:",plot_model_comparison(comparison[0],comparison[1],alternatives,args.output,role=imaging.name))
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
                                  reference_spl_db=args.reference_spl,peak_headroom_db=args.peak_headroom,coherent=args.coherence=="coherent",directivity_on_reflections=args.directivity_on_reflections)
            bass=next(item for item in trial.placements_by_type if item["type"]=="bass")["best"]
            response=bass["modal_response"]; experiment.append((count,response["frequencies_hz"],response["response_db"],bass["terms"]["flatness"],bass["speakers"]))
            print("Bass-count experiment {} speakers: flatness {:.2f}; positions {}".format(count,bass["terms"]["flatness"],[tuple(np.round(s["position_m"]/.3048,1)) for s in bass["speakers"]]))
        fig,ax=plt.subplots(figsize=(8,4))
        for count,freq,response,flatness,_ in experiment: ax.plot(freq,response,label="{} bass (flatness {:.2f})".format(count,flatness))
        ax.set(xlabel="Frequency (Hz)",ylabel="Relative pressure (dB)",title="Bass-count modal response experiment"); ax.legend(); fig.tight_layout()
        path=__import__("pathlib").Path(args.output)/"bass_count_experiment.png"; path.parent.mkdir(parents=True,exist_ok=True); fig.savefig(path,dpi=180); plt.close(fig); print("Bass-count figure saved:",path)

if __name__=="__main__": main()
