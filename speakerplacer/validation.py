"""Physics and sensitivity validation experiments for the placement optimizer."""
from dataclasses import replace
from pathlib import Path
import random
import time
import numpy as np
import matplotlib.pyplot as plt
from .optimize import optimize_layout
from .room import make_room, feet_to_m, default_listener
from .simulate import simulate_rir
from .speaker_types import parse_speaker_layout
from .scoring import direct_arrival, room_modes, modal_response, angle_to_facing
from .candidates import Candidate
from .optimize import _evaluate_group, _make_mirror, _wall_roles, _allowed, _valid_angle, _toe_grid, _imaging_terms, _weighted_imaging
from .speaker_models import resolve_model
from .speaker_models import DEFAULT_SPEAKER_MODELS, SpeakerModel


def _type_spec(layout,name):
    return next(spec for spec in layout if spec.name==name)

def _positions(record): return [np.asarray(s["position_m"],dtype=float) for s in record["speakers"]]
def _move_ft(before,after):
    if not before or not after:return 0.
    return float(np.mean([np.linalg.norm(a-b) for a,b in zip(before,after)])/0.3048)
def _clone(spec,**kwargs):
    values={"score_weights":dict(spec.score_weights)}
    values.update(kwargs)
    return replace(spec,**values)
def _run(room,listener,specs,facing,absorption,simulator=None,**kwargs):
    return optimize_layout(room,listener,specs,facing,absorption,simulator=simulator or simulate_rir,**kwargs)

def _spec_influence(room,listener,layout,facing,absorption,report,modal_q_scale,reference_spl_db,peak_headroom_db):
    """Perturb numeric fields on each role's default model and measure outputs."""
    cache={}
    def cached_sim(poly,source,mic,absorption=.2):
        key=tuple(np.round(np.r_[source,mic,absorption],8))
        if key not in cache: cache[key]=simulate_rir(poly,source,mic,absorption=absorption)
        return cache[key]
    report.extend(["", "SPEC INFLUENCE (single-role ±20% model perturbations)", "field | changed outputs; unchanged numeric specs are labeled informational only"])
    for spec in layout:
        model_id=spec.model_id or {"front":"generic_bookshelf_onwall","surround":"generic_surround_wide","bass":"generic_inwall_sub"}.get(spec.name,"generic_bookshelf_onwall")
        base_model=DEFAULT_SPEAKER_MODELS[model_id]; registry=dict(DEFAULT_SPEAKER_MODELS)
        local_spec=replace(spec,count=2 if spec.symmetric else 1)
        def optimize(model):
            models=dict(registry); models[model_id]=model
            return optimize_layout(room,listener,[local_spec],facing,absorption,top_n=1,simulator=cached_sim,
                modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db,
                refinement_sweeps=0,models=models)
        baseline=optimize(base_model).best_pair
        base_points=np.asarray([s["position_m"] for s in baseline["speakers"]]); base_toe=np.asarray([s.get("toe_in_deg",0.) for s in baseline["speakers"]])
        baseline_spl=float(np.mean([s["predicted_spl_db"] for s in baseline["speakers"]])); base_score=float(baseline["score_db"])
        for field_info in __import__("dataclasses").fields(SpeakerModel):
            name=field_info.name; value=getattr(base_model,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or name=="model_id": continue
            if value is None:
                report.append("{} / {}: informational only (unset)".format(spec.name,name)); continue
            if name in ("height_m", "coverage_v_deg"):
                report.append("{} / {}: informational only (2D model)".format(spec.name,name)); continue
            changed=set()
            for factor in (.8,1.2):
                candidate_value=float(value)*factor if value else .2
                try: changed_model=replace(base_model,**{name:candidate_value}); trial=optimize(changed_model).best_pair
                except (ValueError,TypeError): continue
                points=np.asarray([s["position_m"] for s in trial["speakers"]]); toes=np.asarray([s.get("toe_in_deg",0.) for s in trial["speakers"]])
                if points.shape!=base_points.shape or not np.allclose(points,base_points,atol=.01): changed.add("position")
                if not np.allclose(toes,base_toe,atol=.1): changed.add("toe-in")
                if abs(float(trial["score_db"])-base_score)>.01: changed.add("score")
                trial_spl=float(np.mean([s["predicted_spl_db"] for s in trial["speakers"]]))
                if abs(trial_spl-baseline_spl)>.01: changed.add("predicted SPL")
            report.append("{} / {}: {}".format(spec.name,name,", ".join(sorted(changed)) if changed else "informational only"))
        for name in ("coverage_h_vs_freq","polar_table","on_axis_response","mount_height_range_m"):
            value=getattr(base_model,name)
            note="unset" if value is None else ("2D model" if name=="mount_height_range_m" else "curve is model-specific")
            report.append("{} / {}: informational only ({})".format(spec.name,name,note))
        report.append("{} / directivity_band_weights: informational only for current frequency-flat model".format(spec.name))
    surround=next((s for s in layout if s.name=="surround"),parse_speaker_layout(["surround:2"])[0])
    report.append("Surround model comparison (same room and constraints):")
    for model_id in ("generic_narrow_onwall","generic_surround_wide","generic_dipole_surround"):
        trial_spec=replace(surround,model_id=model_id)
        try:
            trial=optimize_layout(room,listener,[trial_spec],facing,absorption,simulator=cached_sim,refinement_sweeps=0,models=DEFAULT_SPEAKER_MODELS)
            best=trial.best_pair; pts=[tuple(float(x) for x in np.round(s["position_m"]/.3048,2)) for s in best["speakers"]]
            toes=[round(s.get("toe_in_deg",0.)) for s in best["speakers"]]
            report.append("{}: positions {} ft, toe-in {}, score {:.2f}".format(model_id,pts,toes,best["score_db"]))
            if model_id=="generic_dipole_surround":
                null_errors=[abs(90.-__import__("speakerplacer.optimize",fromlist=["_directivity_angle"])._directivity_angle(
                    Candidate(np.asarray(s["position_m"]),np.asarray(s["normal"]),s["wall_index"],.5),listener,s.get("toe_in_deg",0.))) for s in best["speakers"]]
                report.append("dipole listener-to-null deviation: {:.1f}° (usual guidance targets 0° deviation)".format(float(np.mean(null_errors))))
        except ValueError as exc: report.append("{}: unavailable ({})".format(model_id,exc))
    bass=next((s for s in layout if s.name=="bass"),parse_speaker_layout(["bass:2"])[0])
    if bass:
        report.append("Bass F3 sensitivity:")
        for f3 in (25.,45.):
            model_id=bass.model_id or "generic_inwall_sub"; model=replace(DEFAULT_SPEAKER_MODELS[model_id],f3_hz=f3)
            models=dict(DEFAULT_SPEAKER_MODELS); models[model_id]=model
            trial=optimize_layout(room,listener,[bass],facing,absorption,simulator=cached_sim,refinement_sweeps=0,models=models)
            best=trial.best_pair
            report.append("F3 {:.0f} Hz: bass score {:.2f}; usable 30-200 Hz fraction {:.3f}".format(f3,best["score_db"],model.usable_band_fraction))
    basis_1w=SpeakerModel("basis_1w",sensitivity_db=85.,sensitivity_basis="1W_1m",nominal_impedance_ohm=4.)
    basis_v=SpeakerModel("basis_v",sensitivity_db=85.+10.*np.log10(2.),sensitivity_basis="2.83V_1m",nominal_impedance_ohm=4.)
    report.append("Sensitivity basis check (4 ohm, same acoustic sensitivity): normalized SPL delta {:+.3f} dB".format(
        basis_v.sensitivity_1w_1m_db-basis_1w.sensitivity_1w_1m_db))

def _emit(lines,status,message): lines.append("{} {}".format(status,message))

def run_validation(room_polygon,listener,layout,facing="north",absorption=.2,output_dir="output",base_result=None,simulator=None,modal_q_scale=20.,reference_spl_db=85.,peak_headroom_db=20.):
    """Run score spread, ablation, baselines, sweeps, convergence, and analytic checks."""
    out=Path(output_dir)/"validation"; out.mkdir(parents=True,exist_ok=True)
    rng=random.Random(2026); report=["Physics validation report", "Room: {} x {} m; facing {}; absorption {:.2f}".format(*(np.ptp(room_polygon,axis=1)),facing,absorption)]
    base=base_result or _run(room_polygon,listener,layout,facing,absorption,simulator,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
    for speaker in base.best_pair.get("speakers",[]):
        if speaker.get("warnings"):
            _emit(report,"WARN","selected {} {}: {}".format(speaker["type"],speaker["model_id"],", ".join(speaker["warnings"])))
    imaging_spec=next((spec for spec in layout if spec.scorer=="imaging"),None)
    if imaging_spec:
        costs=[]
        for enabled in (False,True):
            start=time.perf_counter(); _run(room_polygon,listener,[_clone(imaging_spec,count=2 if imaging_spec.symmetric else 1)],facing,absorption,simulator,
                modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db,directivity_on_reflections=enabled)
            costs.append(time.perf_counter()-start)
        _emit(report,"INFO","first-order reflection-directivity estimate enabled; runtime {:.3f}s vs {:.3f}s disabled ({:+.1f}%)".format(costs[1],costs[0],100.*(costs[1]-costs[0])/max(costs[0],1e-9)))
        report.append("Reflection directivity estimates first-order specular wall hits from image geometry; higher-order RIR taps are not individually decomposed.")

    # 1. Per-role score discrimination and sparse hard windows.
    spread={}; fig,axes=plt.subplots(len(layout),1,figsize=(8,max(3,2.8*len(layout))),squeeze=False)
    for ax,spec in zip(axes[:,0],layout):
        rows=[r for r in base.candidate_scores if r["type"]==spec.name]
        scores=np.array([r["score_db"] for r in rows],dtype=float); spread[spec.name]=scores
        if not len(scores): continue
        low,high=float(scores.min()),float(scores.max()); std=float(scores.std()); gap=high-float(np.median(scores))
        _emit(report,"WARN" if high-low<1. else "PASS","{} score spread min/max/std {:.2f}/{:.2f}/{:.2f} dB; best-median {:.2f} dB ({} candidates)".format(spec.name,low,high,std,gap,len(scores)))
        if len(scores)<8: _emit(report,"WARN","{} has only {} candidates after hard filters; widen angle tolerance or reduce spacing".format(spec.name,len(scores)))
        points=np.array([r["position_m"] for r in rows])/.3048; sc=ax.scatter(points[:,0],points[:,1],c=scores,cmap="viridis",s=24,label="eligible candidates"); fig.colorbar(sc,ax=ax,label="Score (dB-like), higher is better"); ax.set(xlabel="x (ft)",ylabel="y (ft)",title="{} candidate score spread".format(spec.name)); ax.legend(); ax.set_aspect("equal")
    fig.tight_layout(); fig.savefig(out/"score_spread.png",dpi=160); plt.close(fig)

    # 2. Hard filter, widened filter, soft geometry, and acoustics-only choice.
    filter_rows=[]; fig,ax=plt.subplots(figsize=(8,6)); poly=np.column_stack([room_polygon,room_polygon[:,0]])/.3048; ax.plot(poly[0],poly[1],"k-")
    for spec in layout:
        if spec.angle_target_deg is None:
            weights=dict(spec.score_weights); weights["geometry"]=0.
            trial=_run(room_polygon,listener,[_clone(spec,score_weights=weights)],facing,absorption,simulator,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
            pts=_positions(trial.best_pair); filter_rows.append((spec.name,"soft_no_geometry",pts,trial.best_pair["score_db"]))
            xy=np.array(pts)/.3048; ax.scatter(xy[:,0],xy[:,1],s=88,label="{} acoustic-only".format(spec.name),marker="X")
            continue
        no_geometry=dict(spec.score_weights); no_geometry["geometry"]=0.
        variants=[("hard",spec), ("wide",_clone(spec,angle_tol_deg=max(20.,spec.angle_tol_deg))),
                  ("soft",_clone(spec,angle_tol_deg=180.)),
                  ("soft_no_geometry",_clone(spec,angle_tol_deg=180.,score_weights=no_geometry))]
        for label,var in variants:
            trial=_run(room_polygon,listener,[var],facing,absorption,simulator,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
            pts=_positions(trial.best_pair); filter_rows.append((spec.name,label,pts,trial.best_pair["score_db"]))
            xy=np.array(pts)/.3048
            marker={"hard":"o","wide":"s","soft":"^","soft_no_geometry":"X"}[label]
            ax.scatter(xy[:,0],xy[:,1],s={"hard":100,"wide":58,"soft":72,"soft_no_geometry":88}[label],label="{} {}".format(spec.name,label),marker=marker)
        candidate_rows=[r for r in base.candidate_scores if r["type"]==spec.name]
        if candidate_rows:
            best=next(x for x in filter_rows if x[0]==spec.name and x[1]=="hard")
            acoustic=next(x for x in filter_rows if x[0]==spec.name and x[1]=="soft_no_geometry")
            textbook=min(candidate_rows,key=lambda r:abs(abs(r["angle_deg"])-spec.angle_target_deg))
            acoustic_angle=abs(float(angle_to_facing(acoustic[2][0],listener,facing)))
            _emit(report,"PASS","{} hard/wide/soft/acoustics-only evaluated; hard vs soft shift {:.2f} ft; acoustics-only angle {:.1f} deg (textbook {:.1f}), score {:.2f} vs textbook candidate {:.2f} dB".format(spec.name,_move_ft(best[2],next(x[2] for x in filter_rows if x[0]==spec.name and x[1]=="soft")),acoustic_angle,spec.angle_target_deg,acoustic[3],textbook["score_db"]))
    ax.set(xlabel="x (ft)",ylabel="y (ft)",title="Angle filters: hard, wide, soft, and acoustics-only"); ax.set_aspect("equal"); ax.legend(fontsize=7,bbox_to_anchor=(1.02,1),loc="upper left"); fig.tight_layout(); fig.savefig(out/"filter_vs_physics.png",dpi=160); plt.close(fig)

    # 3. Score-term ablation at default and widened windows, avoiding false
    # dead-weight warnings when the discrete candidate set is too small.
    ablation=[]
    for spec in layout:
        terms=("flatness","null_penalty") if spec.scorer=="modal" else ("clarity","off_axis","early_reflection","geometry","headroom")
        baseline=next((p["best"] for p in base.placements_by_type if p["type"]==spec.name),None)
        if baseline is None: continue
        tolerances=(spec.angle_tol_deg,15.,20.) if spec.angle_target_deg is not None else (spec.angle_tol_deg,)
        for tolerance in tolerances:
            widened=_clone(spec,angle_tol_deg=tolerance)
            reference=_run(room_polygon,listener,[widened],facing,absorption,simulator,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
            eligible=[r for r in reference.candidate_scores if r["type"]==spec.name]
            reference_record=reference.best_pair
            for term in terms:
                weights=dict(widened.score_weights); weights[term]=0.
                trial=_run(room_polygon,listener,[_clone(widened,score_weights=weights)],facing,absorption,simulator,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
                shift=_move_ft(_positions(reference_record),_positions(trial.best_pair)); ablation.append((spec.name,term,tolerance,shift))
                dead=(shift<.05 and len(eligible)>=20)
                window="±{:.0f}°".format(tolerance) if spec.angle_target_deg is not None else "all candidates"
                _emit(report,"WARN" if dead else "PASS","{} ablate {} at {} ({} candidates): movement {:.2f} ft{}".format(spec.name,term,window,len(eligible),shift," (dead weight at adequate candidate count)" if dead else ""))
    fig,ax=plt.subplots(figsize=(11,4)); ax.bar(["{}\n{} {}".format(a,b,"±{}°".format(int(c)) if next(s for s in layout if s.name==a).angle_target_deg is not None else "all candidates") for a,b,c,_ in ablation],[d for *_,d in ablation]); ax.set_ylabel("Mean speaker movement (ft)"); ax.set_title("Score-term ablation across angle windows"); ax.tick_params(axis="x",labelrotation=45); fig.tight_layout(); fig.savefig(out/"ablation.png",dpi=160); plt.close(fig)

    # 4. Random candidate-layout and rule-of-thumb comparisons.
    per_type={spec.name:[r for r in base.candidate_scores if r["type"]==spec.name] for spec in layout}
    random_valid_count=0; random_type_scores={spec.name:[] for spec in layout}
    random_roles=_wall_roles(room_polygon,facing)
    for _ in range(200):
        valid=True; chosen=[]; sampled={}; random_sources={}
        for spec in layout:
            rows=per_type[spec.name]
            selected=[]
            attempts=0
            if spec.symmetric:
                left_rows=[row for row in rows if row.get("angle_deg",0.)<0]
                while len(selected)<spec.count and attempts<500:
                    attempts+=1
                    if not left_rows: break
                    row=rng.choice(left_rows); source=Candidate(np.asarray(row["position_m"]),np.asarray(row["normal"]),int(row["wall_index"]),.5)
                    mirror=_make_mirror(room_polygon,source,listener,facing,spec.allowed_walls,.3,.05)
                    if mirror is None or not _allowed(spec.allowed_walls,random_roles[mirror.wall_index]) or not _valid_angle(mirror,listener,facing,spec): continue
                    edge=room_polygon[:,(mirror.wall_index+1)%room_polygon.shape[1]]-room_polygon[:,mirror.wall_index]
                    model=resolve_model(spec.model_id or {"front":"generic_bookshelf_onwall","surround":"generic_surround_wide","bass":"generic_inwall_sub"}.get(spec.name,"generic_bookshelf_onwall"))
                    if min(mirror.wall_t,1.-mirror.wall_t)*np.linalg.norm(edge)<model.corner_clearance_m: continue
                    if any(np.linalg.norm(point-other)<.5 for point in (source.position,mirror.position) for other in chosen): continue
                    if np.linalg.norm(source.position-mirror.position)<.5: continue
                    mate=min(rows,key=lambda item:np.linalg.norm(item["position_m"]-mirror.position))
                    if np.linalg.norm(mate["position_m"]-mirror.position)>.3: continue
                    selected.extend([row,mate]); chosen.extend([source.position,mirror.position]); random_sources[spec.name]=[source,mirror]
            else:
                while len(selected)<spec.count and attempts<500:
                    row=rng.choice(rows); pos=np.asarray(row["position_m"]); attempts+=1
                    if all(np.linalg.norm(pos-other)>=.5 for other in chosen):
                        selected.append(row); chosen.append(pos); random_sources.setdefault(spec.name,[]).append(Candidate(pos,np.asarray(row["normal"]),int(row["wall_index"]),.5))
            if len(selected)<spec.count: valid=False; break
            model=resolve_model(spec.model_id or {"front":"generic_bookshelf_onwall","surround":"generic_surround_wide","bass":"generic_inwall_sub"}.get(spec.name,"generic_bookshelf_onwall"))
            score,_,_=_evaluate_group(room_polygon,random_sources[spec.name],[row["terms"] for row in selected],listener,absorption,spec,facing,model,reference_spl_db,peak_headroom_db,1.,modal_q_scale,True)
            sampled[spec.name]=score
        if valid:
            random_valid_count+=1
            for name,value in sampled.items(): random_type_scores[name].append(value)
    if random_valid_count>=200: _emit(report,"PASS","random valid candidate layouts: {} / 200 draws; per-role distributions follow".format(random_valid_count))
    else: _emit(report,"WARN","sampled {} / 200 non-overlapping random candidate layouts".format(random_valid_count))
    rule_score=0.; rule_by_type={}; rule_group_scores={}; rule_terms_by_type={}; rule_violations=[]; rule_points=[]; rule_speaker_positions={}; wall_roles=_wall_roles(room_polygon,facing)
    for spec in layout:
        rows=per_type[spec.name]
        if spec.count==2:
            before=len(rule_violations)
            if spec.angle_target_deg is not None:
                seeds=sorted((r for r in rows if r["angle_deg"]<0),key=lambda r:abs(abs(r["angle_deg"])-spec.angle_target_deg))
            else:
                corners=np.array([room_polygon[:,0],room_polygon[:,1],room_polygon[:,2],room_polygon[:,3]])
                seeds=sorted((r for r in rows if r["angle_deg"]<0),key=lambda r:min(np.linalg.norm(r["position_m"]-corner) for corner in corners))
            selected=[]; source_pair=[]
            for seed in seeds:
                source=Candidate(np.asarray(seed["position_m"]),np.asarray(seed["normal"]),int(seed["wall_index"]),.5)
                mirror=_make_mirror(room_polygon,source,listener,facing,spec.allowed_walls,.3,.05)
                if mirror is None or not _allowed(spec.allowed_walls,wall_roles[mirror.wall_index]): continue
                match=min(rows,key=lambda row:np.linalg.norm(row["position_m"]-mirror.position))
                if spec.angle_target_deg is not None and abs(abs(match["angle_deg"])-spec.angle_target_deg)>spec.angle_tol_deg+1e-8: continue
                model=resolve_model(spec.model_id or {"front":"generic_bookshelf_onwall","surround":"generic_surround_wide","bass":"generic_inwall_sub"}.get(spec.name,"generic_bookshelf_onwall"))
                edge=room_polygon[:,(mirror.wall_index+1)%room_polygon.shape[1]]-room_polygon[:,mirror.wall_index]
                if min(mirror.wall_t,1.-mirror.wall_t)*np.linalg.norm(edge)<model.corner_clearance_m: continue
                if any(np.linalg.norm(source.position-point)<.5 or np.linalg.norm(mirror.position-point)<.5 for point in rule_points): continue
                if np.linalg.norm(source.position-mirror.position)<.5: continue
                selected=[seed,match]; source_pair=[source,mirror]; break
            if len(selected)==2:
                positions=[np.asarray(point.position) for point in source_pair]
                if np.linalg.norm(positions[0]-positions[1])<.5: rule_violations.append("{} pair violates minimum spacing".format(spec.name))
                if spec.symmetric:
                    axis=np.array([0.,1.]) if facing in ("north","south") else np.array([1.,0.]); reflection=2*np.outer(axis,axis)-np.eye(2)
                    error=np.linalg.norm((positions[1]-listener)-reflection@(positions[0]-listener))
                    if error>.03: rule_violations.append("{} pair violates mirrored-pair constraint by {:.2f} m".format(spec.name,error))
                model=resolve_model(spec.model_id or {"front":"generic_bookshelf_onwall","surround":"generic_surround_wide","bass":"generic_inwall_sub"}.get(spec.name,"generic_bookshelf_onwall"))
                term_rows=[selected[0]["terms"]]
                if spec.scorer=="imaging":
                    h,fs=simulate_rir(room_polygon,source_pair[1].position,listener,absorption=absorption)
                    toe=max(_toe_grid(model),key=lambda value:_weighted_imaging(_imaging_terms(h,fs,source_pair[1],listener,spec,model,reference_spl_db,peak_headroom_db,float(value),room_polygon,True),spec))
                    term_rows.append(_imaging_terms(h,fs,source_pair[1],listener,spec,model,reference_spl_db,peak_headroom_db,float(toe),room_polygon,True))
                score,terms,_=_evaluate_group(room_polygon,source_pair,term_rows,listener,absorption,spec,facing,model,reference_spl_db,peak_headroom_db,1.,modal_q_scale,True)
                if len(rule_violations)>before:
                    rule_by_type[spec.name]=float("nan")
                else:
                    rule_by_type[spec.name]=score; rule_group_scores[spec.name]=score; rule_terms_by_type[spec.name]=terms; rule_points.extend(positions); rule_speaker_positions[spec.name]=positions; rule_score+=score
            else:
                rule_by_type[spec.name]=float("nan"); rule_violations.append("{} has no eligible textbook pair".format(spec.name))
        else:
            selected=sorted(rows,key=lambda r:abs(abs(r.get("angle_deg",0.))-spec.angle_target_deg) if spec.angle_target_deg is not None else r["score_db"],reverse=False)[:spec.count]
            rule_by_type[spec.name]=float(np.mean([r["score_db"] for r in selected])) if selected else float("nan")
    _emit(report,"INFO","Per-role comparison (scores are dB-like; do not sum across unlike role metrics):")
    losing_types=[]; selected_metrics={}
    for spec in layout:
        opt=next(p["best"] for p in base.placements_by_type if p["type"]==spec.name)
        random_mean_type=float(np.mean(random_type_scores[spec.name])) if random_type_scores[spec.name] else float("nan")
        cand=np.asarray([r["score_db"] for r in per_type[spec.name]],dtype=float)
        chosen_rows=[min(per_type[spec.name],key=lambda row:np.linalg.norm(np.asarray(row["position_m"])-speaker["position_m"])) for speaker in opt["speakers"]]
        chosen_score=float(np.mean([row["score_db"] for row in chosen_rows])) if chosen_rows else float("nan")
        percentile=100.*float(np.mean(cand<=chosen_score)) if len(cand) else float("nan")
        random_improvement=opt["score_db"]-random_mean_type; rule_improvement=opt["score_db"]-rule_group_scores.get(spec.name,float("nan"))
        selected_metrics[spec.name]={"score":chosen_score,"percentile":percentile,"random_delta":random_improvement,"rule_delta":rule_improvement}
        if rule_improvement<0: losing_types.append(spec.name)
        opt_terms=", ".join("{}={:.2f}".format(k,v) for k,v in opt["terms"].items())
        rule_terms=", ".join("{}={:.2f}".format(k,v) for k,v in rule_terms_by_type.get(spec.name,{}).items()) or "unavailable"
        report.append("  {} selected group {:.2f}, matched candidate mean {:.2f} | rule group {:.2f} | random group mean {:.2f} | Δrandom {:+.2f}, Δrule {:+.2f} dB-like | percentile {:.1f} | terms optimized [{}] vs rule [{}]".format(spec.name,opt["score_db"],chosen_score,rule_group_scores.get(spec.name,float("nan")),random_mean_type,random_improvement,rule_improvement,percentile,opt_terms,rule_terms))
    if rule_violations: _emit(report,"WARN","Rule-of-thumb layout is not comparable under the same constraints: {}".format("; ".join(rule_violations)))
    _emit(report,"INFO","Random legal candidate layouts are scored as groups; the rule-of-thumb is rescored with the same role scorer. Roles where optimized group score loses: {}".format(", ".join(losing_types) if losing_types else "none"))

    # 5. Listener sweep, clipped 3 ft from every room boundary.
    bounds=room_polygon; lo=bounds.min(axis=1)+feet_to_m(3); hi=bounds.max(axis=1)-feet_to_m(3)
    xs=np.linspace(lo[0],hi[0],5); ys=np.linspace(lo[1],hi[1],5); front_spec=next((s for s in layout if s.name=="front"),None); bass_spec=next((s for s in layout if s.name=="bass"),None)
    sweep=[]
    if front_spec and bass_spec:
        sweep_front=_clone(front_spec,angle_tol_deg=max(30.,front_spec.angle_tol_deg))
        for x in xs:
            for y in ys:
                li=np.array([x,y])
                try:
                    rr=_run(room_polygon,li,[sweep_front,bass_spec],facing,absorption,simulator,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
                    fp=next(t["best"]["speakers"] for t in rr.placements_by_type if t["type"]=="front"); bass_record=next(t for t in rr.placements_by_type if t["type"]=="bass"); bp=bass_record["best"]["speakers"]
                    sweep.append((x,y,float(np.linalg.norm(fp[0]["position_m"]-fp[1]["position_m"])/.3048),np.array([s["position_m"] for s in bp])/.3048,bass_record["best"]["wall_index"],bass_record["best"]["score_db"],bass_record["ranked"][1]["score_db"] if len(bass_record["ranked"])>1 else bass_record["best"]["score_db"]))
                except ValueError: pass
    jumps=[]
    ordered_sweep=sorted(sweep,key=lambda q:(q[1],q[0]))
    for a,b in zip(ordered_sweep,ordered_sweep[1:]):
        if a[4]!=b[4]:
            gap=min(a[5]-a[6],b[5]-b[6]); jumps.append((a,b,gap))
    maxjump=max([abs(a[2]-b[2]) for a,b in zip(ordered_sweep,ordered_sweep[1:])],default=0.)
    _emit(report,"PASS" if len(sweep)>=20 else "WARN","listener sweep evaluated 25 grid points ({} with legal layouts), all listener points at least 3 ft from walls; largest adjacent spacing change {:.2f} ft; {} bass wall transitions".format(len(sweep),maxjump,len(jumps)))
    for a,b,gap in jumps: report.append("  bass wall transition ({:.1f},{:.1f}) -> ({:.1f},{:.1f}) ft; runner-up gap {:.3f} dB-like".format(a[0]/.3048,a[1]/.3048,b[0]/.3048,b[1]/.3048,gap))
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    if sweep:
        fwd={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing]; distances=[]
        for row in sweep:
            if facing=="north": distance=room_polygon[1].max()-row[1]
            elif facing=="south": distance=row[1]-room_polygon[1].min()
            elif facing=="east": distance=room_polygon[0].max()-row[0]
            else: distance=row[0]-room_polygon[0].min()
            distances.append(distance/.3048)
        axes[0].scatter(distances,[x[2] for x in sweep],c=[x[1]/.3048 for x in sweep],cmap="viridis",label="listener grid"); axes[0].set(xlabel="Distance from front wall (ft)",ylabel="Best front spacing (ft)",title="Front spacing across listener grid"); axes[0].legend()
        bass_points=np.vstack([x[3] for x in sweep]); walls=np.repeat([x[4] for x in sweep],2); axes[1].plot(poly[0],poly[1],"k-",label="room boundary")
        for wall in sorted(set(walls)): axes[1].scatter(bass_points[walls==wall,0],bass_points[walls==wall,1],s=32,label="wall {}".format(wall))
        axes[1].set(xlabel="x (ft)",ylabel="y (ft)",title="Bass location / selected wall map"); axes[1].legend()
    fig.tight_layout(); fig.savefig(out/"listener_sweep.png",dpi=160); plt.close(fig)

    # 6. Room-size and absorption sweep.
    sizes=[(length,round(length*ratio,2)) for length in (10,12,15,18,20,25) for ratio in (.8,1.,1.25,1.5)]; absorptions=[.05,.2,.6]; room_rows=[]
    selected_specs=[s for s in layout if s.name in ("front","bass")]
    for length,width in sizes:
        poly=make_room(length,width); li=default_listener(poly,facing)
        for alpha in absorptions:
            try:
                rr=_run(poly,li,selected_specs,facing,alpha,simulator,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
                bass_modes=room_modes(poly,(30.,150.)); freqs=np.unique(np.round([m[0] for m in bass_modes],6)); smallest=min(np.diff(freqs),default=float("nan"))
                scores={t["type"]:t["best"]["score_db"] for t in rr.placements_by_type}
                room_rows.append((length,width,alpha,None,rr.best_pair["speakers"],scores,len(freqs),smallest))
                _emit(report,"INFO","room {:.0f}x{:.0f} ft alpha {:.2f}: modal count 30-150 Hz {}, smallest adjacent gap {:.2f} Hz, per-role scores {}".format(length,width,alpha,len(freqs),smallest,", ".join("{}={:.2f}".format(k,v) for k,v in scores.items())))
            except ValueError as exc: _emit(report,"INFO","room sweep {}x{} ft alpha {} has no legal placement for this fixed role layout: {}".format(length,width,alpha,exc))
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    if room_rows:
        normalized=[]
        for spec in selected_specs:
            vals=np.asarray([row[5].get(spec.name,np.nan) for row in room_rows]); mean=np.nanmean(vals); std=max(float(np.nanstd(vals)),1e-9)
            normalized.append((vals-mean)/std)
        norm_total=np.sum(np.vstack(normalized),axis=0) if normalized else np.zeros(len(room_rows))
        room_rows=[(*row[:8],float(norm_total[i])) for i,row in enumerate(room_rows)]
        axes[0].scatter([x[0] for x in room_rows],[x[8] for x in room_rows],c=[x[2] for x in room_rows],cmap="viridis",label="configurations"); axes[0].set(xlabel="Room length (ft)",ylabel="Sum of per-role z-scores",title="Normalized room-size / absorption score"); axes[0].legend()
        axes[1].scatter([x[0] for x in room_rows],[x[1] for x in room_rows],c=[x[6] for x in room_rows],s=48,cmap="viridis",label="marker color: mode count"); axes[1].set(xlabel="Length (ft)",ylabel="Width (ft)",title="Aspect ratios and low-mode count"); axes[1].legend()
    fig.tight_layout(); fig.savefig(out/"room_absorption_sweep.png",dpi=160); plt.close(fig)
    if room_rows: _emit(report,"PASS","room/absorption sweep completed {} configurations; bass/mode locations vary with geometry".format(len(room_rows)))
    default_row=next((row for row in room_rows if abs(row[0]-15)<1e-9 and abs(row[1]-12)<1e-9 and abs(row[2]-absorption)<1e-9),None)
    same_alpha=[row for row in room_rows if abs(row[2]-absorption)<1e-9]
    if default_row:
        bass_rank=1+sum(row[5].get("bass",float("-inf"))>default_row[5].get("bass",float("-inf")) for row in same_alpha)
        _emit(report,"INFO","default {:.0f}x{:.0f} ft bass score {:.2f} ranks {}/{} at alpha {:.2f}; {} modes in 30-150 Hz, nearest distinct gap {:.2f} Hz".format(default_row[0],default_row[1],default_row[5].get("bass",float("nan")),bass_rank,len(same_alpha),default_row[2],default_row[6],default_row[7]))
        if bass_rank==len(same_alpha): _emit(report,"INFO","default bass result is the weakest in the same-absorption sweep; modal density/spacing above are evidence for room-specific modal behavior")

    # 7. Numerical convergence checks.
    front=front_spec or next((s for s in layout if s.scorer=="imaging"),None); bass=bass_spec
    conv=[]; baseline_spacing=.25; baseline_bass_step=1.
    if front:
        for order in (4,8,12,16):
            sim=lambda poly,src,li,absorption=.2,order=order:simulate_rir(poly,src,li,absorption=absorption,max_order=order)
            rr=_run(room_polygon,listener,[front],facing,absorption,sim,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
            conv.append(("order",order,_positions(rr.best_pair),rr.best_pair["score_db"]))
        for spacing in (.5,.25,.1):
            rr=_run(room_polygon,listener,[front],facing,absorption,simulator,spacing_m=spacing,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
            conv.append(("spacing",spacing,_positions(rr.best_pair),rr.best_pair["score_db"]))
    if bass:
        for step in (.5,1.,2.):
            rr=_run(room_polygon,listener,[bass],facing,absorption,simulator,modal_step_hz=step,modal_q_scale=modal_q_scale,reference_spl_db=reference_spl_db,peak_headroom_db=peak_headroom_db)
            conv.append(("bass_step",step,_positions(rr.best_pair),rr.best_pair["score_db"]))
    labels=["{} {}".format(a,b) for a,b,_,_ in conv]; ref=conv[0][2] if conv else []; moves=[_move_ft(ref,x[2]) for x in conv]
    _emit(report,"INFO","convergence baseline candidate spacing {:.2f} m; bass frequency step {:.2f} Hz; equivalence threshold 0.50 dB".format(baseline_spacing,baseline_bass_step))
    bass_rows=[row for row in conv if row[0]=="bass_step"]
    bass_reference=next((row[3] for row in bass_rows if row[1]==baseline_bass_step),None)
    for name,value,positions,score in bass_rows:
        diff=abs(score-bass_reference) if bass_reference is not None else float("nan")
        _emit(report,"PASS" if diff<.5 else "WARN","bass frequency step {:.2f} Hz score shift {:+.3f} dB-like from baseline; equivalent optimum={}".format(value,score-bass_reference if bass_reference is not None else float("nan"),diff<.5))
    maxmove=max(moves,default=0.); _emit(report,"PASS" if maxmove<=1. else "WARN","placement convergence maximum movement {:.2f} ft across {} numerical settings".format(maxmove,len(conv)))
    fig,ax=plt.subplots(figsize=(9,4)); ax.bar(labels,moves,label="placement shift"); ax.set(xlabel="Numerical setting",ylabel="Movement from baseline (ft)",title="Placement convergence"); ax.tick_params(axis="x",rotation=45); ax.legend(); fig.tight_layout(); fig.savefig(out/"convergence.png",dpi=160); plt.close(fig)

    # 8. Analytic direct and first-order wall-reflection timing.
    checks=[]
    try:
        src=np.array([.8,.8]); mic=np.array([1.4,.8]); h,fs=simulate_rir(room_polygon,src,mic,absorption=.999,max_order=10)
        expected=np.linalg.norm(src-mic)/343*fs; direct=direct_arrival(h,fs); tail=float(np.sum(h[direct+1:]**2)/max(np.sum(h**2),1e-15))
        checks.append(abs(direct-expected)<=2 and tail<.02)
        _emit(report,"PASS" if checks[-1] else "WARN","near-anechoic direct arrival {} samples vs {:.1f}; post-direct energy {:.4f}".format(direct,expected,tail))
    except Exception as exc: _emit(report,"WARN","near-anechoic RIR check unavailable: {}".format(exc))
    try:
        # For a rectangular room the image of the source reflected across the
        # bottom wall predicts the first-order echo distance analytically.
        src=np.array([.8,.8]); mic=np.array([1.4,.8]); h,fs=simulate_rir(room_polygon,src,mic,absorption=.2,max_order=10)
        image=np.array([src[0],-src[1]])
        echo_sample=np.linalg.norm(image-mic)/343.*fs
        lo=max(0,int(round(echo_sample))-2); hi=min(len(h),int(round(echo_sample))+3)
        found=lo<hi and int(np.argmax(np.abs(h[lo:hi])))+lo in range(lo,hi)
        _emit(report,"PASS" if found else "WARN","bottom-wall image-source echo predicted at {:.1f} samples; local peak {:.1f} samples".format(echo_sample,lo+int(np.argmax(np.abs(h[lo:hi]))) if found else float("nan")))
    except Exception as exc: _emit(report,"WARN","wall-reflection timing check unavailable: {}".format(exc))
    modes=room_modes(room_polygon,(30.,200.)); axial=next((f for f,n,m in modes if (n,m)==(1,0)),None)
    _emit(report,"PASS" if axial is not None else "WARN","first axial mode {} Hz; analytic formula verified by room_modes".format("{:.2f}".format(axial) if axial else "missing"))
    # Symmetric sources and a centered listener in the rectangular local frame.
    center=room_polygon.mean(axis=1); p0=room_polygon[:,0]; p1=room_polygon[:,1]; ux=(p1-p0)/np.linalg.norm(p1-p0); width=np.linalg.norm(p1-p0)
    a=center-.2*ux; b=center+.2*ux
    f1,v1=modal_response(room_polygon,[a,b],center,absorption,(30.,200.)); f2,v2=modal_response(room_polygon,[b,a],center,absorption,(30.,200.))
    sym=float(np.max(np.abs(v1-v2))); _emit(report,"PASS" if sym<1e-10 else "WARN","symmetric coherent bass response max difference {:.3e}".format(sym))

    # 9. Perimeter bass heatmap.
    bass_rows=[r for r in base.candidate_scores if r["type"]=="bass"]
    if bass_rows:
        fig,ax=plt.subplots(figsize=(8,6)); poly=np.column_stack([room_polygon,room_polygon[:,0]])/.3048; ax.plot(poly[0],poly[1],"k-")
        points=np.array([r["position_m"] for r in bass_rows])/.3048; vals=np.array([r["score_db"] for r in bass_rows]); sc=ax.scatter(points[:,0],points[:,1],c=vals,cmap="viridis",s=45); fig.colorbar(sc,ax=ax,label="Bass modal score, higher is better")
        bass_place=next((pl for pl in base.placements_by_type if pl["type"]=="bass"),None)
        if bass_place:
            chosen=np.array([s["position_m"] for s in bass_place["best"]["speakers"]])/.3048; ax.scatter(chosen[:,0],chosen[:,1],marker="*",s=180,c="red",edgecolors="black",label="Chosen bass locations"); ax.legend()
        ax.set_aspect("equal"); ax.set_title("Bass score along room perimeter"); fig.tight_layout(); fig.savefig(out/"bass_perimeter_heatmap.png",dpi=160); plt.close(fig)
    bass_best=next((pl["best"] for pl in base.placements_by_type if pl["type"]=="bass"),None)
    influence_start=len(report)
    _spec_influence(room_polygon,listener,layout,facing,absorption,report,modal_q_scale,reference_spl_db,peak_headroom_db)
    influence_summary=[line for line in report[influence_start:] if line.startswith(("generic_narrow_onwall:","generic_surround_wide:","generic_dipole_surround:","dipole listener-to-null", "F3 ","Sensitivity basis check"))]
    report.extend(["", "SUMMARY"])
    for spec in layout:
        metric=selected_metrics.get(spec.name,{})
        acoustic=next((row for row in filter_rows if row[0]==spec.name and row[1]=="soft_no_geometry"),None)
        if acoustic and spec.angle_target_deg is not None: deviation=abs(abs(angle_to_facing(acoustic[2][0],listener,facing))-spec.angle_target_deg)
        elif acoustic and spec.name in rule_speaker_positions: deviation=_move_ft(rule_speaker_positions[spec.name],acoustic[2])
        else: deviation=float("nan")
        unit="° from textbook angle" if spec.angle_target_deg is not None else "ft from textbook positions"
        changed=sorted({term for role,term,tol,shift in ablation if role==spec.name and tol>=20. and shift>=.05})
        report.append("{}: percentile {:.1f}; Δrandom {:+.2f}; Δrule {:+.2f} dB-like; acoustics-only deviation {:.1f} {}; answer-changing terms {}".format(spec.name,metric.get("percentile",float("nan")),metric.get("random_delta",float("nan")),metric.get("rule_delta",float("nan")),deviation,unit,", ".join(changed) if changed else "none demonstrated"))
    report.extend(influence_summary)
    if bass_best and bass_best.get("modal_response"):
        response=np.asarray(bass_best["modal_response"]["response_db"]); swing=float(np.max(response)-np.min(response))
        report.append("Bass peak-to-dip response swing {:.2f} dB. Placement alone cannot flatten the response in a small room; equalization, treatment, or additional subwoofers may be needed.".format(swing))
    report.append("The modal model is 2D and omits floor-to-ceiling modes; those require a 3D room model.")
    report.append("Validation plots: {}".format(out))
    report_text="\n".join(report)
    (out/"report.txt").write_text(report_text+"\n",encoding="utf-8")
    return report_text
