"""Type-aware wall candidate search with exact mirrored pairs and joint modal scoring."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
from math import log10
import numpy as np
from .candidates import Candidate, generate_candidates
from .room import validate_polygon
from .scoring import (ScoreWeights, angle_to_facing, band_clarity_score, clarity_score,
                      direct_arrival, early_reflection_score, modal_response, modal_score,
                      modal_step_for_damping, off_axis_score, room_modes, score_terms)
from .simulate import simulate_rir
from .speaker_types import SpeakerType, DEFAULT_LAYOUT, DEFAULT_SPEAKER_TYPES
from .speaker_models import DEFAULT_SPEAKER_MODELS, DEFAULT_MODEL_BY_ROLE, SpeakerModel, predicted_spl_db, resolve_model

@dataclass
class OptimizationResult:
    best_pair: dict
    ranked_pairs: list
    candidate_scores: list
    weights: dict
    room_polygon_m: np.ndarray = field(repr=False)
    listener_m: np.ndarray = field(repr=False)
    facing: str = "north"
    rir: Optional[np.ndarray] = field(default=None, repr=False)
    fs: int = 16000
    placements_by_type: list = field(default_factory=list)
    modal_response_data: Optional[dict] = field(default=None, repr=False)
    warnings: list = field(default_factory=list)


def _facing_vectors(facing):
    forward={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing.lower()]
    right=np.array([forward[1],-forward[0]])
    return forward,right


def _wall_roles(polygon, facing):
    p=validate_polygon(polygon); forward,right=_facing_vectors(facing); roles={}
    for i in range(p.shape[1]):
        edge=p[:,(i+1)%p.shape[1]]-p[:,i]; tangent=edge/np.linalg.norm(edge); outward=np.array([tangent[1],-tangent[0]])
        dots={"front":float(outward@forward),"back":float(-outward@forward),"right":float(outward@right),"left":float(-outward@right)}
        roles[i]=max(dots,key=dots.get) if max(dots.values())>.7 else "side"
    return roles


def _allowed(role_string, wall_role):
    roles=role_string.split(",")
    return "any" in roles or wall_role in roles


def _make_mirror(polygon, source: Candidate, listener, facing, allowed_wall_roles, margin=.3, nudge=.05):
    """Reflect a source exactly over the facing axis and validate its wall segment."""
    p=validate_polygon(polygon); forward,_=_facing_vectors(facing); transform=2*np.outer(forward,forward)-np.eye(2)
    target=np.asarray(listener)+transform.dot(source.position-np.asarray(listener)); roles=_wall_roles(p,facing); matches=[]
    for i in range(p.shape[1]):
        if not _allowed(allowed_wall_roles,roles[i]): continue
        a=p[:,i]; edge=p[:,(i+1)%p.shape[1]]-a; length=float(np.linalg.norm(edge)); tangent=edge/length; inward=np.array([-tangent[1],tangent[0]])
        delta=target-a; along=float(delta@tangent); depth=float(delta@inward)
        if margin-1e-9<=along<=length-margin+1e-9 and abs(depth-nudge)<=.01:
            matches.append(Candidate(target.copy(),inward,i,along/length))
    return min(matches,key=lambda c:abs(np.linalg.norm(c.position-target))) if matches else None


def _valid_angle(candidate, listener, facing, spec):
    angle=angle_to_facing(candidate.position,listener,facing)
    return spec.angle_target_deg is None or abs(abs(angle)-spec.angle_target_deg)<=spec.angle_tol_deg+1e-9


def _analytic_angle_candidates(polygon, listener, facing, spec, margin, nudge, step_deg=.5):
    """Intersect a fine continuous angle fan with eligible wall segments."""
    if spec.angle_target_deg is None: return []
    p=validate_polygon(polygon); origin=np.asarray(listener,dtype=float); forward,right=_facing_vectors(facing)
    target=float(spec.angle_target_deg); angles=np.arange(max(-179.,target-spec.angle_tol_deg),min(179.,target+spec.angle_tol_deg)+step_deg*.5,step_deg)
    angles=np.unique(np.append(angles,target)); found=[]
    cross=lambda a,b:float(a[0]*b[1]-a[1]*b[0])
    roles=_wall_roles(p,facing)
    for angle in angles:
        ray=np.sin(np.radians(angle))*right+np.cos(np.radians(angle))*forward
        for i in range(p.shape[1]):
            if not _allowed(spec.allowed_walls,roles[i]): continue
            a=p[:,i]; edge=p[:,(i+1)%p.shape[1]]-a; length=float(np.linalg.norm(edge)); den=cross(ray,edge)
            if abs(den)<1e-12: continue
            distance=cross(a-origin,edge)/den; fraction=cross(a-origin,ray)/den; along=fraction*length
            if distance<=0 or along<margin or along>length-margin: continue
            tangent=edge/length; inward=np.array([-tangent[1],tangent[0]])
            point=origin+distance*ray+nudge*inward
            found.append(Candidate(point,inward,i,fraction))
    unique={_candidate_key(c):c for c in found}
    return list(unique.values())


def _toe_grid(model, step_deg=5., bounds=None):
    """Return model swivel values, or an explicit signed CLI override range."""
    limit=float(model.max_toe_in_deg if model.mount_type == "on_wall" else min(model.max_toe_in_deg,10.))
    if bounds is not None:
        low,high=map(float,bounds)
        if low>high: return np.array([0.])
        values=np.arange(low,high+step_deg*.5,step_deg)
        return np.unique(np.append(values,[low,high]))
    return np.arange(-limit,limit+step_deg*.5,step_deg) if limit else np.array([0.])


def _directivity_angle(candidate,listener,toe_in_deg=0.):
    """Angle between the listener ray and the aimed (rotated inward-normal) axis."""
    direction=np.asarray(listener)-candidate.position
    theta=np.radians(float(toe_in_deg)); nx,ny=candidate.normal
    aim=np.array([nx*np.cos(theta)-ny*np.sin(theta),nx*np.sin(theta)+ny*np.cos(theta)])
    denom=np.linalg.norm(direction)*np.linalg.norm(aim)
    return float(np.degrees(np.arccos(np.clip(np.dot(direction,aim)/max(denom,1e-12),-1.,1.))))


def _headroom(model, distance_m, reference_spl_db=85., peak_headroom_db=20.):
    predicted=predicted_spl_db(model,distance_m)
    margin=min(predicted-reference_spl_db,(model.max_spl_lf_db or model.max_spl_db)-(predicted+peak_headroom_db))
    return predicted,float(margin)


def _first_order_reflection_gain(polygon,candidate,listener,model,toe_in_deg):
    """Estimate directivity on every valid first-order image-source path.

    The image source locates the specular wall hit exactly; RIR energy is not
    decomposed by order, so the mean path gain is applied to the reflection
    score as an explicit first-order approximation.
    """
    if polygon is None: return 0.
    p=validate_polygon(polygon); theta=np.radians(float(toe_in_deg)); n=candidate.normal
    aim=np.array([n[0]*np.cos(theta)-n[1]*np.sin(theta),n[0]*np.sin(theta)+n[1]*np.cos(theta)])
    source=candidate.position; listener=np.asarray(listener); path_gains=[]
    cross=lambda a,b:float(a[0]*b[1]-a[1]*b[0])
    for index in range(p.shape[1]):
        a=p[:,index]; edge=p[:,(index+1)%p.shape[1]]-a; wall_n=np.array([edge[1],-edge[0]])/np.linalg.norm(edge)
        image=source-2.*np.dot(source-a,wall_n)*wall_n
        ray=listener-image; den=cross(ray,edge)
        if abs(den)<1e-12: continue
        t=cross(a-image,edge)/den; u=cross(a-image,ray)/den
        if not (1e-7<t<1.-1e-7 and -1e-7<=u<=1.+1e-7): continue
        hit=image+t*ray; departure=hit-source; angle=np.degrees(np.arccos(np.clip(np.dot(aim,departure)/max(np.linalg.norm(aim)*np.linalg.norm(departure),1e-12),-1.,1.)))
        path_gains.append(model.gain_linear(angle))
    return 20.*log10(max(float(np.mean(path_gains)),1e-12)) if path_gains else 0.


def _imaging_terms(rir,fs,candidate,listener,spec,model,reference_spl_db,peak_headroom_db,toe_in_deg=0.,room_polygon=None,directivity_on_reflections=True):
    direct=direct_arrival(rir,fs); predicted,headroom=_headroom(model,np.linalg.norm(candidate.position-listener),reference_spl_db,peak_headroom_db)
    angle=_directivity_angle(candidate,listener,toe_in_deg)
    # Equal-weight octave-spaced speech/presence bands make measured polar
    # tables and frequency-dependent coverage affect the imaging objective.
    band_gains=np.asarray([model.gain_db(angle,frequency_hz=f) for f in (500.,1000.,2000.,4000.)])
    band_weights=np.asarray(model.directivity_band_weights,dtype=float); band_weights/=band_weights.sum()
    mean_band_gain=float(band_gains@band_weights)
    if model.directivity_model=="dipole" and spec.name=="surround":
        # Dipole surrounds conventionally aim their figure-8 null at the listener.
        directivity_db=-abs(mean_band_gain+30.)*spec.directivity
    else:
        directivity_db=mean_band_gain*spec.directivity
    reflection_gain=_first_order_reflection_gain(room_polygon,candidate,listener,model,toe_in_deg) if directivity_on_reflections else 0.
    terms={"clarity_db":clarity_score(rir,fs,direct),"off_axis_db":directivity_db,
           "early_reflection_db":early_reflection_score(rir,fs,direct)-reflection_gain,"headroom_db":headroom,
           "reflection_directivity_gain_db":reflection_gain}
    return terms

def _weighted_imaging(terms,spec):
    weights=spec.score_weights
    return float(sum(weights.get(name,0.)*terms.get(key,0.) for name,key in (("clarity","clarity_db"),("off_axis","off_axis_db"),("early_reflection","early_reflection_db"),("headroom","headroom_db"))))


def _modal_eval(polygon,sources,listener,absorption,spec,model,step_hz=1.,q_scale=20.):
    effective_high=min(spec.band_hz[1],model.freq_high_hz)
    band=(max(spec.band_hz[0],model.freq_low_hz),effective_high)
    effective_step=modal_step_for_damping(polygon,absorption,q_scale,step_hz,band)
    gains=[model.wall_gain_db for _ in sources]
    freq,pressure=modal_response(polygon,sources,listener,absorption,band,effective_step,q_scale,source_gains_db=gains)
    pressure=pressure*10.**(np.asarray([model.response_db(float(f)) for f in freq])/20.)
    terms=modal_score(freq,pressure)
    return terms["frequencies_hz"],pressure,terms


def _evaluate_group(polygon, sources, terms_by_source, listener, absorption, spec, facing, model, reference_spl_db, peak_headroom_db, step_hz=1.,q_scale=20.,coherent=True):
    if spec.scorer=="modal":
        freq,pressure,modal_terms=_modal_eval(polygon,[c.position for c in sources],listener,absorption,spec,model,step_hz,q_scale)
        individual=[_headroom(model,np.linalg.norm(c.position-listener),reference_spl_db,peak_headroom_db)[0] for c in sources]
        combine=(20. if coherent else 10.)*np.log10(max(1,len(sources)))
        combined_spl=float(np.mean(individual)+combine); group_max=(model.max_spl_lf_db or model.max_spl_db)+combine
        predicted_peak=combined_spl+peak_headroom_db
        headroom=min(combined_spl-reference_spl_db,group_max-predicted_peak)
        terms={"flatness":modal_terms["flatness"],"null_penalty":modal_terms["null_penalty"],"geometry_db":0.,"headroom_db":float(headroom)}
        value=(spec.score_weights.get("flatness",1.)*terms["flatness"]
               +spec.score_weights.get("null_penalty",1.)*terms["null_penalty"]
               +spec.score_weights.get("geometry",0.)*terms["geometry_db"]
               +spec.score_weights.get("headroom",0.)*headroom)
        return float(value),terms,{"frequencies_hz":freq,"pressure":pressure,"response_db":modal_terms["response_db"],"combined_spl_db":combined_spl,"predicted_peak_spl_db":predicted_peak,"max_spl_db":group_max}
    terms={key:float(np.mean([item[key] for item in terms_by_source])) for key in terms_by_source[0]}
    spls=[predicted_spl_db(model,np.linalg.norm(c.position-listener)) for c in sources]
    combine=(20. if coherent else 10.)*np.log10(max(1,len(sources)))
    combined_spl=float(np.mean(spls)+combine); group_max=(model.max_spl_lf_db or model.max_spl_db)+combine; predicted_peak=combined_spl+peak_headroom_db
    headroom=min(combined_spl-reference_spl_db,group_max-predicted_peak); terms["headroom_db"]=float(headroom)
    angle_errors=[]
    if spec.angle_target_deg is not None:
        angle_errors=[abs(abs(angle_to_facing(c.position,listener,facing))-spec.angle_target_deg) for c in sources]
    geom=-float(np.mean(np.square(angle_errors))) if angle_errors else 0.
    if spec.name=="front" and len(sources)==2:
        d1=float(np.linalg.norm(sources[0].position-listener)); d2=float(np.linalg.norm(sources[1].position-listener)); base=float(np.linalg.norm(sources[0].position-sources[1].position)); mean=(d1+d2+base)/3.
        geom+=-10.*(abs(d1-d2)+abs(base-(d1+d2)/2))/max(mean,1e-9)
    terms["geometry_db"]=float(geom)
    value=_weighted_imaging(terms,spec)+spec.score_weights.get("geometry",1.)*geom
    return float(value),terms,{"combined_spl_db":combined_spl,"predicted_peak_spl_db":predicted_peak,"max_spl_db":group_max}


def _candidate_key(candidate):
    return tuple(np.round(candidate.position,9))


def optimize_layout(room_polygon, listener, layout=None, facing="north", absorption=.2, top_n=5,
                    simulator=simulate_rir, spacing_m=.25, margin_m=.3, nudge_m=.05,
                    min_listener_distance_m=.5, min_speaker_spacing_m=.5, modal_q_scale=20., models=None,
                    reference_spl_db=85., peak_headroom_db=20., coherent=True, modal_step_hz=1.,
                    refinement_sweeps=1, reserved_speakers=None, directivity_on_reflections=True, toe_in_range_deg=None):
    """Optimize a sequential typed speaker layout; all geometry inputs are metres.

    `layout` is an ordered sequence of `SpeakerType` records. Each type is
    placed after earlier types, which reserve space for later searches.
    """
    p=validate_polygon(room_polygon); listener=np.asarray(listener,dtype=float)
    if listener.shape!=(2,) or top_n<1: raise ValueError("listener must be (x,y), and top_n >= 1")
    if not 0<=absorption<=1: raise ValueError("absorption must be between 0 and 1")
    specs=list(layout if layout is not None else [DEFAULT_SPEAKER_TYPES[name] for name,_ in DEFAULT_LAYOUT])
    if not specs: raise ValueError("layout must include at least one speaker type")
    candidates=generate_candidates(p,spacing_m,margin_m,nudge_m)
    roles=_wall_roles(p,facing); rir_cache={}; candidate_scores=[]; type_candidate_scores={}
    placed=list(reserved_speakers or []); placements=[]; best_rir=None; best_fs=16000; best_modal=None; warnings=[]
    models=DEFAULT_SPEAKER_MODELS if models is None else models

    def rir_for(c):
        key=_candidate_key(c)
        if key not in rir_cache: rir_cache[key]=simulator(p,c.position,listener,absorption=absorption)
        return rir_cache[key]

    for spec in specs:
        if spec.count==0: continue
        if spec.symmetric and spec.count%2:
            raise ValueError("speaker type '{}' is symmetric and requires an even count".format(spec.name))
        model_id=spec.model_id or DEFAULT_MODEL_BY_ROLE.get(spec.name) or (DEFAULT_MODEL_BY_ROLE["front"] if spec.name=="regular" else None)
        model=models[model_id] if model_id in models else resolve_model(model_id)
        role_name="front" if spec.name=="regular" else spec.name
        if role_name not in model.role_types:
            raise ValueError("model '{}' cannot fill role '{}'; supported roles: {}".format(model.model_id,role_name,", ".join(model.role_types)))
        target_band=(spec.band_hz[0],min(spec.band_hz[1],model.crossover_hz if spec.name=="bass" and model.crossover_hz>0 else spec.band_hz[1]))
        if model.freq_low_hz>target_band[0] or model.freq_high_hz<target_band[1]:
            raise ValueError("model '{}' bandwidth {}-{} Hz does not cover {} role band {}-{} Hz".format(model.model_id,model.freq_low_hz,model.freq_high_hz,spec.name,*target_band))
        if spec.name=="bass" and model.f3_hz>target_band[0]: warnings.append("WARN: bass model {} f3 {:.1f} Hz is above target lower band {:.1f} Hz".format(model.model_id,model.f3_hz,target_band[0]))
        spec_candidates=list(candidates)+_analytic_angle_candidates(p,listener,facing,spec,margin_m,nudge_m)
        allowed=[c for c in spec_candidates if _allowed(spec.allowed_walls,roles[c.wall_index])
                 and np.linalg.norm(c.position-listener)>=min_listener_distance_m
                 and c.wall_t*float(np.linalg.norm(p[:,(c.wall_index+1)%p.shape[1]]-p[:,c.wall_index]))>=model.corner_clearance_m
                 and (1.-c.wall_t)*float(np.linalg.norm(p[:,(c.wall_index+1)%p.shape[1]]-p[:,c.wall_index]))>=model.corner_clearance_m
                 and all(np.linalg.norm(c.position-other["position_m"])>=max(min_speaker_spacing_m,model.min_spacing_to_other_speakers_m,(model.width_m+other.get("footprint_width_m",0.))/2.) for other in placed)]
        valid=[c for c in allowed if _valid_angle(c,listener,facing,spec)]
        if not valid: raise ValueError("No valid candidates for speaker type '{}'; check its walls, angle window, and spacing".format(spec.name))
        single_scores={}
        for c in valid:
            response_data=None
            if spec.scorer=="modal":
                f,pr,mt=_modal_eval(p,[c.position],listener,absorption,spec,model,modal_step_hz,modal_q_scale)
                spl,headroom=_headroom(model,np.linalg.norm(c.position-listener),reference_spl_db,peak_headroom_db)
                terms={"flatness":mt["flatness"],"null_penalty":mt["null_penalty"],"geometry_db":0.,"headroom_db":headroom}
                score=(spec.score_weights.get("flatness",1.)*terms["flatness"]
                       +spec.score_weights.get("null_penalty",1.)*terms["null_penalty"]
                       +spec.score_weights.get("geometry",0.)*terms["geometry_db"]
                       +spec.score_weights.get("headroom",0.)*terms["headroom_db"])
                response_data={"frequencies_hz":f,"response_db":mt["response_db"]}
            else:
                h,fs=rir_for(c)
                toe_options=_toe_grid(model,bounds=toe_in_range_deg)
                scored=[(_weighted_imaging(_imaging_terms(h,fs,c,listener,spec,model,reference_spl_db,peak_headroom_db,float(toe),p,directivity_on_reflections),spec),float(toe),_imaging_terms(h,fs,c,listener,spec,model,reference_spl_db,peak_headroom_db,float(toe),p,directivity_on_reflections)) for toe in toe_options]
                score,toe,terms=max(scored,key=lambda item:item[0])
                c.toe_in_deg=toe
                response_data={"toe_in_deg":toe}
            single_scores[_candidate_key(c)]=(float(score),terms)
            spl,_=_headroom(model,np.linalg.norm(c.position-listener),reference_spl_db,peak_headroom_db)
            row={"type":spec.name,"model_id":model.model_id,"position_m":c.position.copy(),"wall_index":c.wall_index,"normal":c.normal.copy(),"score_db":float(score),"terms":terms,"predicted_spl_db":spl,"angle_deg":angle_to_facing(c.position,listener,facing)}
            if response_data is not None: row.update(response_data)
            candidate_scores.append(row)
        type_candidate_scores[spec.name]=single_scores

        options=[]
        if spec.symmetric:
            for c in valid:
                angle=angle_to_facing(c.position,listener,facing)
                if angle>1e-8: continue
                reflected=_make_mirror(p,c,listener,facing,spec.allowed_walls,margin_m,nudge_m)
                if reflected is None or np.linalg.norm(c.position-reflected.position)<.1: continue
                if np.linalg.norm(reflected.position-listener)<min_listener_distance_m: continue
                if not _allowed(spec.allowed_walls,roles[reflected.wall_index]) or not _valid_angle(reflected,listener,facing,spec): continue
                if any(np.linalg.norm(reflected.position-other["position_m"])<max(min_speaker_spacing_m,model.min_spacing_to_other_speakers_m,(model.width_m+other.get("footprint_width_m",0.))/2.) for other in placed): continue
                if spec.scorer=="imaging":
                    scored=[]
                    for point in (c,reflected):
                        h,fs=rir_for(point)
                        toe=max(_toe_grid(model,bounds=toe_in_range_deg),key=lambda value:_weighted_imaging(_imaging_terms(h,fs,point,listener,spec,model,reference_spl_db,peak_headroom_db,float(value),p,directivity_on_reflections),spec))
                        point.toe_in_deg=float(toe)
                        scored.append(_imaging_terms(h,fs,point,listener,spec,model,reference_spl_db,peak_headroom_db,float(toe),p,directivity_on_reflections))
                else: scored=[]
                options.append((c,reflected,scored))
            needed=spec.count//2
        else:
            for c in valid:
                h,fs=rir_for(c) if spec.scorer=="imaging" else (None,None)
                scored=[_imaging_terms(h,fs,c,listener,spec,model,reference_spl_db,peak_headroom_db,float(getattr(c,"toe_in_deg",0.)),p,directivity_on_reflections)] if h is not None else []
                options.append((c,)); options[-1]=(c,None,scored)
            needed=spec.count
        if not options: raise ValueError("No legal placements for speaker type '{}'".format(spec.name))

        # Beam-search multi-pair groups; modal groups are rescored coherently on each joint set.
        beam=[(0.,[],{},None)]
        for _ in range(needed):
            expanded=[]
            for _,selected_groups,_,_ in beam:
                for option in options:
                    new_points=[option[0]]+([option[1]] if option[1] is not None else [])
                    existing=[point for group in selected_groups for point in group[:2] if point is not None]
                    if any(np.linalg.norm(a.position-b.position)<max(min_speaker_spacing_m,model.min_spacing_to_other_speakers_m) for a in new_points for b in existing): continue
                    if len(new_points)==2 and np.linalg.norm(new_points[0].position-new_points[1].position)<max(min_speaker_spacing_m,model.min_spacing_to_other_speakers_m,model.width_m): continue
                    group=selected_groups+[option]; points=[point for pair in group for point in pair[:2] if point is not None]
                    score_terms_list=[]
                    if spec.scorer=="imaging":
                        for opt in group: score_terms_list.extend(opt[2])
                    value,terms,modal_data=_evaluate_group(p,points,score_terms_list,listener,absorption,spec,facing,model,reference_spl_db,peak_headroom_db,modal_step_hz,modal_q_scale,coherent)
                    expanded.append((value,group,terms,modal_data))
            expanded.sort(key=lambda x:x[0],reverse=True); beam=expanded[:150]
            if not beam: raise ValueError("Could not place all {} speakers of type '{}' with the spacing constraint".format(spec.count,spec.name))

        records=[]
        for value,groups,terms,modal_data in beam[:top_n]:
            points=[point for group in groups for point in group[:2] if point is not None]
            speakers=[]
            for point in points:
                angle=angle_to_facing(point.position,listener,facing)
                distance=float(np.linalg.norm(point.position-listener)); spl=predicted_spl_db(model,distance); speaker_headroom=(model.max_spl_lf_db or model.max_spl_db)-(spl+peak_headroom_db)
                toe=float(getattr(point,"toe_in_deg",0.)); theta=np.radians(toe); normal=point.normal.copy(); aim=np.array([normal[0]*np.cos(theta)-normal[1]*np.sin(theta),normal[0]*np.sin(theta)+normal[1]*np.cos(theta)])
                speakers.append({"type":spec.name,"model_id":model.model_id,"position_m":point.position.copy(),"position_ft":point.position.copy()/0.3048,"wall_index":point.wall_index,"wall_t":point.wall_t,"normal":normal,"aim_direction":aim,"toe_in_deg":toe,"angle_deg":angle,"predicted_spl_db":spl,"headroom_db":speaker_headroom,"coverage_h_deg":model.coverage_h_deg,"footprint_width_m":model.width_m,"footprint_height_m":model.height_m,"footprint_depth_m":model.depth_m})
                spec_warnings=[]
                toe_limits=toe_in_range_deg if toe_in_range_deg is not None else (-min(model.max_toe_in_deg,10.) if model.mount_type!="on_wall" else -model.max_toe_in_deg, min(model.max_toe_in_deg,10.) if model.mount_type!="on_wall" else model.max_toe_in_deg)
                if spec.scorer=="imaging" and (abs(toe-toe_limits[0])<1e-6 or abs(toe-toe_limits[1])<1e-6): spec_warnings.append("toe-in at allowed boundary")
                if spec.angle_target_deg is not None and abs(abs(angle)-spec.angle_target_deg)>=spec.angle_tol_deg-.2: spec_warnings.append("position at angle-window boundary")
                if distance<model.min_listening_distance_m or distance>model.max_listening_distance_m: spec_warnings.append("outside recommended listening-distance range")
                wall_edge=p[:,(point.wall_index+1)%p.shape[1]]-p[:,point.wall_index]; edge_clearance=min(point.wall_t,1.-point.wall_t)*float(np.linalg.norm(wall_edge))
                if edge_clearance<=max(margin_m,model.corner_clearance_m)+.01: spec_warnings.append("position at wall-margin boundary")
                nearby=[other["position_m"] for other in placed]+[other.position for other in points if other is not point]
                spacing_limit=max(min_speaker_spacing_m,model.min_spacing_to_other_speakers_m)
                if any(abs(float(np.linalg.norm(point.position-other))-spacing_limit)<=.01 for other in nearby): spec_warnings.append("position at minimum speaker-spacing boundary")
                speakers[-1]["warnings"]=spec_warnings
                for warning in spec_warnings: warnings.append("WARN: {} {}".format(spec.name,warning))
            record={"type":spec.name,"speakers":speakers,"score_db":float(value),"terms":dict(terms),"wall_index":speakers[0]["wall_index"],"modal_response":modal_data,"model_id":model.model_id}
            if modal_data is not None:
                record["combined_spl_db"]=modal_data["combined_spl_db"]; record["predicted_peak_spl_db"]=modal_data["predicted_peak_spl_db"]; record["max_spl_db"]=modal_data["max_spl_db"]
                if record["predicted_peak_spl_db"]>record["max_spl_db"]: warnings.append("WARN: {} combined peak {:.1f} dB exceeds model maximum {:.1f} dB".format(spec.name,record["predicted_peak_spl_db"],record["max_spl_db"]))
                if record["combined_spl_db"]<reference_spl_db: warnings.append("WARN: {} predicted average {:.1f} dB is below {:.1f} dB reference".format(spec.name,record["combined_spl_db"],reference_spl_db))
            records.append(record)
        best=records[0]
        if spec.scorer=="modal":
            modal_rows=[row for row in candidate_scores if row["type"]==spec.name and "response_db" in row]
            if modal_rows:
                poor=min(modal_rows,key=lambda row:row["score_db"])
                best["modal_response"]["poor_response"]={"frequencies_hz":poor["frequencies_hz"],"response_db":poor["response_db"]}
        placements.append({"type":spec.name,"count":spec.count,"best":best,"ranked":records,"scorer":spec.scorer,
                           "model_id":model.model_id,"spec":{"angle_target_deg":spec.angle_target_deg,"angle_tol_deg":spec.angle_tol_deg,"allowed_walls":spec.allowed_walls,"band_hz":spec.band_hz,"coverage_h_deg":model.coverage_h_deg}})
        placed.extend(best["speakers"])
        if spec.scorer=="modal": best_modal=best["modal_response"]
        elif best_rir is None:
            best_s=best["speakers"][0]; c=min(candidates,key=lambda point:np.linalg.norm(point.position-best_s["position_m"]))
            best_rir,best_fs=rir_for(c)

    all_speakers=[speaker for placement in placements for speaker in placement["best"]["speakers"]]
    total_score=float(sum(item["best"]["score_db"] for item in placements))
    combined_terms={item["type"]:item["best"]["terms"] for item in placements}
    best_record={"speakers":all_speakers,"score_db":total_score,"terms":combined_terms}
    result=OptimizationResult(best_record,[item["best"] for item in placements],candidate_scores,
                              {item["type"]:item["best"]["terms"] for item in placements},p,listener,facing,best_rir,best_fs,placements,best_modal)
    # Coordinate descent re-optimizes one role while holding every other
    # role fixed. Role z-scores keep bass's broader numerical range from
    # dominating the combined search objective.
    if refinement_sweeps>0 and len(specs)>1:
        role_results={}
        for placement in result.placements_by_type:
            role_results[placement["type"]]=None
        def aggregate_role_score(results):
            values=[]
            for name,role_result in results.items():
                placement=role_result.placements_by_type[0]
                vals=np.asarray([row["score_db"] for row in role_result.candidate_scores if row["type"]==name],dtype=float)
                scale=max(float(vals.std()),1e-9) if vals.size else 1.
                values.append((placement["best"]["score_db"]-(float(vals.mean()) if vals.size else 0.))/scale)
            return float(sum(values))
        # Start from the greedy solution, then keep role-specific diagnostic
        # objects while adjusting each role against the other current choices.
        for spec in specs:
            if spec.count==0: continue
            other=[s for placement in result.placements_by_type if placement["type"]!=spec.name for s in placement["best"]["speakers"]]
            role_results[spec.name]=optimize_layout(p,listener,[spec],facing,absorption,top_n,simulator,spacing_m,margin_m,nudge_m,
                min_listener_distance_m,min_speaker_spacing_m,modal_q_scale,models,reference_spl_db,peak_headroom_db,coherent,modal_step_hz,
                refinement_sweeps=0,reserved_speakers=other,directivity_on_reflections=directivity_on_reflections,toe_in_range_deg=toe_in_range_deg)
        best_score=aggregate_role_score(role_results)
        for sweep in range(min(int(refinement_sweeps),5)):
            improved=False
            for spec in specs:
                if spec.count==0: continue
                fixed=[speaker for name,role_result in role_results.items() if name!=spec.name for speaker in role_result.best_pair["speakers"]]
                trial=optimize_layout(p,listener,[spec],facing,absorption,top_n,simulator,spacing_m,margin_m,nudge_m,
                    min_listener_distance_m,min_speaker_spacing_m,modal_q_scale,models,reference_spl_db,peak_headroom_db,coherent,modal_step_hz,
                    refinement_sweeps=0,reserved_speakers=fixed,directivity_on_reflections=directivity_on_reflections,toe_in_range_deg=toe_in_range_deg)
                previous=role_results[spec.name]; role_results[spec.name]=trial
                value=aggregate_role_score(role_results)
                if value>best_score+1e-9: best_score,improved=value,True
                else: role_results[spec.name]=previous
            if not improved: break
        placements=[role_results[spec.name].placements_by_type[0] for spec in specs if spec.count>0]
        speakers=[speaker for placement in placements for speaker in placement["best"]["speakers"]]
        candidate_rows=[row for spec in specs if spec.count>0 for row in role_results[spec.name].candidate_scores]
        modal=next((role_results[spec.name].modal_response_data for spec in specs if spec.count>0 and role_results[spec.name].modal_response_data is not None),None)
        rir_result=next((role_results[spec.name] for spec in specs if spec.count>0 and role_results[spec.name].rir is not None),None)
        score=float(sum(placement["best"]["score_db"] for placement in placements)); term_map={placement["type"]:placement["best"]["terms"] for placement in placements}
        combined=OptimizationResult({"speakers":speakers,"score_db":score,"terms":term_map},[pl["best"] for pl in placements],candidate_rows,
            term_map,p,listener,facing,rir_result.rir if rir_result else None,rir_result.fs if rir_result else 16000,placements,modal,
            ["INFO: coordinate-descent refinement score {:.3f}".format(best_score)])
        return combined
    return result


def optimize_speakers(room_polygon,listener,facing="north",absorption=.2,half_angle_deg=30.,weights=None,top_n=5,simulator=simulate_rir,angle_tolerance_deg=4.,min_listener_distance_m=.5,candidate_spacing_m=.25,corner_margin_m=.3,num_speakers=2,speaker_types=None):
    """Compatibility wrapper for the earlier single-profile API."""
    from .specs import SpeakerSpec as LegacySpec, resolve_speaker_spec
    if speaker_types is None:
        count=num_speakers; name="front"; symmetric=count==2; target=half_angle_deg if count==2 else None
        layout=[SpeakerType(name,count,"front",target,angle_tolerance_deg,symmetric,(200.,20000.),1.,(weights.to_dict() if hasattr(weights,"to_dict") else weights) or {"clarity":1.,"off_axis":1.,"early_reflection":1.,"geometry":1.},"imaging",30.)]
    else:
        source_specs=[resolve_speaker_spec(item) if isinstance(item,str) else item for item in speaker_types]
        names=[item.name for item in source_specs]; layout=[]
        for index,spec in enumerate(source_specs):
            target={"fan":0.,"center":0.,"surround":100.,"rear":180.,"omni":None}[spec.target_mode]
            tolerance=angle_tolerance_deg if spec.target_mode in ("fan","center") else (10. if spec.target_mode=="surround" else 180.)
            role_band=(30.,200.) if spec.target_mode=="omni" else (200.,20000.)
            layout.append(SpeakerType(spec.name,1,spec.wall_role,target,tolerance,False,role_band,spec.directivity_scale,{"clarity":1.,"off_axis":1.,"early_reflection":1.,"geometry":1.,"flatness":1.,"null_penalty":1.},"modal" if spec.frequency_band_hz else "imaging",30.))
        # Treat a legacy two-speaker profile list as a single mirrored type where possible.
        if len(names)==2 and names[0]==names[1] and names[0]=="regular":
            layout=[SpeakerType("front",2,"front",half_angle_deg,angle_tolerance_deg,True,(200.,20000.),1.,{"clarity":1.,"off_axis":1.,"early_reflection":1.,"geometry":1.},"imaging",30.)]
    result=optimize_layout(room_polygon,listener,layout,facing,absorption,top_n,simulator,
                           candidate_spacing_m,corner_margin_m,.05,min_listener_distance_m,.5)
    if len(result.best_pair["speakers"])==2:
        left,right=result.best_pair["speakers"]
        result.best_pair["left"]=left["position_m"]; result.best_pair["right"]=right["position_m"]
        result.best_pair["angles_deg"]={"left":left["angle_deg"],"right":right["angle_deg"]}
        result.best_pair["wall_index"]=left["wall_index"]
    return result
