"""Type-aware wall candidate search with exact mirrored pairs and joint modal scoring."""
from dataclasses import dataclass, field
from functools import lru_cache
from math import ceil
from typing import Dict, List, Optional, Sequence, Tuple
from math import log10
import numpy as np
from .candidates import Candidate, generate_candidates, generate_horizontal_surface_candidates, snap_wall_candidate_to_bay
from .room import validate_polygon
from .scoring import (ScoreWeights, angle_to_facing, band_clarity_score, clarity_score,
                      direct_arrival, early_reflection_score, modal_response, modal_score,
                      modal_step_for_damping, off_axis_score, room_modes, score_terms, rectangular_room_frame)
from .simulate import simulate_rir
from .speaker_types import SpeakerType, DEFAULT_LAYOUT, DEFAULT_SPEAKER_TYPES
from .speaker_models import DEFAULT_SPEAKER_MODELS, DEFAULT_MODEL_BY_ROLE, SpeakerModel, predicted_spl_db, resolve_model
from .room_acoustics import (MaterialSet, room_metrics, level_components, directivity_q,
                             _level_components_with_polar, boundary_gain_for_mount)
from .parallel import ordered_map, worker_count

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
        # Every polygon edge needs a usable room-relative role. Irregular
        # walls rarely align within 45 degrees of a cardinal direction; mapping
        # each edge to its nearest facing/side sector keeps them available to
        # the channel-specific search.
        roles[i]=max(dots,key=dots.get)
    return roles


def _allowed(role_string, wall_role):
    roles=role_string.split(",")
    return "any" in roles or wall_role in roles


def _make_mirror(polygon, source: Candidate, listener, facing, allowed_wall_roles, margin=.3, nudge=.001):
    """Reflect a source exactly over the facing axis and validate its wall segment."""
    p=validate_polygon(polygon); forward,_=_facing_vectors(facing); transform=2*np.outer(forward,forward)-np.eye(2)
    target=np.asarray(listener)+transform.dot(source.position-np.asarray(listener)); roles=_wall_roles(p,facing); matches=[]
    for i in range(p.shape[1]):
        if not _allowed(allowed_wall_roles,roles[i]): continue
        a=p[:,i]; edge=p[:,(i+1)%p.shape[1]]-a; length=float(np.linalg.norm(edge)); tangent=edge/length; inward=np.array([-tangent[1],tangent[0]])
        delta=target-a; along=float(delta@tangent); depth=float(delta@inward)
        if margin-1e-9<=along<=length-margin+1e-9 and abs(depth-nudge)<=.01:
            matches.append(Candidate(target.copy(),inward,i,along/length,source.height_m))
    return min(matches,key=lambda c:abs(np.linalg.norm(c.position-target))) if matches else None


def _valid_angle(candidate, listener, facing, spec):
    angle=angle_to_facing(candidate.position,listener,facing)
    if spec.angle_target_deg is None: return True
    target=float(spec.angle_target_deg)
    if spec.channel_name:
        if spec.azimuth_range_deg is not None:
            return float(spec.azimuth_range_deg[0])-1e-9<=angle<=float(spec.azimuth_range_deg[1])+1e-9
        if spec.channel_name.startswith("L"): return abs(angle+target)<=spec.angle_tol_deg+1e-9
        if spec.channel_name.startswith("R"): return abs(angle-target)<=spec.angle_tol_deg+1e-9
        if spec.channel_name=="C": return abs(angle)<=spec.angle_tol_deg+1e-9
    return abs(abs(angle)-target)<=spec.angle_tol_deg+1e-9


def _analytic_angle_candidates(polygon, listener, facing, spec, margin, nudge, step_deg=.5):
    """Intersect a fine continuous angle fan with eligible wall segments."""
    if spec.angle_target_deg is None: return []
    p=validate_polygon(polygon); origin=np.asarray(listener,dtype=float); forward,right=_facing_vectors(facing)
    target=float(spec.angle_target_deg)
    if spec.channel_name and spec.azimuth_range_deg is not None:
        angles=np.arange(float(spec.azimuth_range_deg[0]),float(spec.azimuth_range_deg[1])+step_deg*.5,step_deg)
        exact=[float(spec.angle_target_deg)*(-1. if spec.channel_name.startswith("L") else 1.)]
        angles=np.unique(np.append(angles,exact))
    elif spec.channel_name and spec.channel_name.startswith("L"):
        angles=np.arange(-target-spec.angle_tol_deg,-target+spec.angle_tol_deg+step_deg*.5,step_deg); exact=[-target]
    elif spec.channel_name and spec.channel_name.startswith("R"):
        angles=np.arange(target-spec.angle_tol_deg,target+spec.angle_tol_deg+step_deg*.5,step_deg); exact=[target]
    elif spec.channel_name=="C":
        angles=np.arange(-spec.angle_tol_deg,spec.angle_tol_deg+step_deg*.5,step_deg); exact=[0.]
    else:
        angles=np.arange(max(-179.,-target-spec.angle_tol_deg),min(179.,target+spec.angle_tol_deg)+step_deg*.5,step_deg); exact=[-target,target]
    angles=np.unique(np.append(angles,exact)); found=[]
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
    if model.directivity_model=="omni": return np.array([0.])
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


def _toe_toward_listener(candidate, listener):
    """Signed yaw that rotates the wall normal directly toward the MLP."""
    direction=np.asarray(listener,dtype=float)-candidate.position
    normal=np.asarray(candidate.normal,dtype=float)
    cross=float(normal[0]*direction[1]-normal[1]*direction[0])
    return float(np.degrees(np.arctan2(cross,float(normal@direction))))


def _covers_all_seats(candidate, model, toe_in_deg, seats, ear_height_m, threshold_db=-3.):
    """Require every seat inside the model's horizontal and vertical gain mask."""
    # Dipoles intentionally put their null toward the listener; their seating
    # coverage is represented by the bipolar pattern rather than the forward
    # -3 dB cone used for direct-radiating speakers.
    if model.directivity_model=="dipole": return True
    theta=np.radians(float(toe_in_deg)); nx,ny=np.asarray(candidate.normal,dtype=float)
    aim=np.array([nx*np.cos(theta)-ny*np.sin(theta),nx*np.sin(theta)+ny*np.cos(theta)])
    z=float(getattr(candidate,"height_m",ear_height_m)); distance=max(float(np.linalg.norm(candidate.position-seats[0][0])),.01)
    mlp_ear=float(seats[0][1]); pitch=float(np.degrees(np.arctan2(mlp_ear-z,distance)))
    pitch=float(np.clip(pitch,-model.max_tilt_deg,model.max_tilt_deg))
    for point,seat_ear in seats:
        delta=np.asarray(point)-candidate.position; horizontal=max(float(np.linalg.norm(delta)),1e-12)
        angle=float(np.degrees(np.arccos(np.clip(float(aim@delta)/(max(np.linalg.norm(aim)*horizontal,1e-12)),-1.,1.))))
        elevation=float(np.degrees(np.arctan2(float(seat_ear-z),horizontal)))
        if model.gain_db(angle)<threshold_db or model.gain_vertical_db(abs(elevation-pitch))<threshold_db: return False
    return True


def _headroom(model, distance_m, reference_spl_db=85., peak_headroom_db=20., role=None, room_env=None, off_axis_deg=0., boundary_gain_db=None):
    """Return rated-power level and positive peak capacity above the target.

    Max-SPL specifications are normalized from 1 m to the listener distance.
    LFE uses a 10 dB peak allowance; other roles use the configured allowance.
    """
    distance=max(float(distance_m),1e-6)
    cache=room_env.get("_headroom_cache") if room_env is not None else None
    key=(id(model),distance,reference_spl_db,peak_headroom_db,role,float(off_axis_deg),boundary_gain_db)
    if cache is not None and key in cache:
        return cache[key][1]
    predicted=predicted_spl_db(model,distance)
    max_spl=model.max_spl_lf_db if role=="bass" and model.max_spl_lf_db is not None else model.max_spl_db
    if room_env is not None:
        band_indices=(0,1) if role=="bass" else (2,3,4,5)
        q=directivity_q(model,off_axis_deg)
        gain_db=model.gain_db(off_axis_deg)
        components=[_level_components_with_polar(model,distance,model.effective_power_w,room_env,index,boundary_gain_db,q,gain_db)
                    for index in band_indices]
        predicted=sum(row["total_spl_db"] for row in components)/len(components)
        direct=sum(row["direct_spl_db"] for row in components)/len(components)
        boundary_gain=boundary_gain_for_mount(model.mount_type) if boundary_gain_db is None else float(boundary_gain_db)
        cap=predicted-direct+max_spl-20.*log10(distance)+boundary_gain
    else:
        cap=max_spl-20.*log10(distance)
    available_peak=min(predicted,cap)
    lfe_allowance=10. if role=="bass" else 0.
    required_peak=reference_spl_db+max(0.,peak_headroom_db-lfe_allowance)
    # Report the SPL actually available after the model's max-SPL cap. Keeping
    # the uncapped sensitivity/power extrapolation here overstated output by
    # 5–10 dB for the placeholder bookshelf and in-wall models.
    result=(float(available_peak),float(available_peak-required_peak))
    if cache is not None:
        cache[key]=(model,result)
    return result


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
    return 20.*log10(max(sum(path_gains)/len(path_gains),1e-12)) if path_gains else 0.


@lru_cache(maxsize=512)
def _rir_base_terms(rir_bytes,fs,is_center):
    """Clarity and early energy depend on the RIR, not on speaker toe angle."""
    rir=np.frombuffer(rir_bytes,dtype=float)
    direct=direct_arrival(rir,fs)
    if is_center:
        c50={"c50_1k_db":band_clarity_score(rir,fs,(707.,1414.),direct),
             "c50_2k_db":band_clarity_score(rir,fs,(1414.,2828.),direct),
             "c50_4k_db":band_clarity_score(rir,fs,(2828.,5657.),direct)}
        clarity=float(np.mean(list(c50.values())))
    else:
        c50={}
        clarity=clarity_score(rir,fs,direct)
    return clarity,tuple(c50.items()),early_reflection_score(rir,fs,direct)


def _imaging_terms(rir,fs,candidate,listener,spec,model,reference_spl_db,peak_headroom_db,toe_in_deg=0.,room_polygon=None,directivity_on_reflections=True,room_env=None,ear_height_m=1.097):
    clarity,c50_items,early_reflection=_rir_base_terms(np.asarray(rir,dtype=float).tobytes(),fs,spec.name=="center")
    c50=dict(c50_items)
    angle=_directivity_angle(candidate,listener,toe_in_deg)
    source_z=float(getattr(candidate,"height_m",ear_height_m))+float(model.acoustic_center_offset_m[0])
    source_xy=np.asarray(candidate.position)+np.asarray(candidate.normal)*float(model.acoustic_center_offset_m[1])
    acoustic_distance=float(np.sqrt(np.linalg.norm(source_xy-listener)**2+(source_z-ear_height_m)**2))
    predicted,headroom=_headroom(model,acoustic_distance,reference_spl_db,peak_headroom_db,spec.name,room_env,angle,_candidate_boundary_gain(candidate,model))
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
    terms={"clarity_db":clarity,"off_axis_db":directivity_db,
           "early_reflection_db":early_reflection-reflection_gain,"headroom_db":headroom,
           "reflection_directivity_gain_db":reflection_gain}
    if room_env is not None:
        distance=acoustic_distance
        direct_level=level_components(model,distance,model.effective_power_w,room_env,3,angle)["direct_spl_db"]
        on_axis_level=level_components(model,distance,model.effective_power_w,room_env,3,0.)["direct_spl_db"]
        direct_relative=float(direct_level-on_axis_level)
    else: direct_relative=float(directivity_db)
    minimum_level_penalty=-max(0.,(reference_spl_db-6.)-float(direct_level)) if room_env is not None else 0.
    terms["direct_level_db"]=direct_relative+minimum_level_penalty
    terms["early_reflection_db"]+=directivity_db
    terms.update(c50)
    if spec.name=="center" and room_polygon is not None:
        from .room_acoustics import first_order_reflections
        source=np.r_[candidate.position,float(getattr(candidate,"height_m",1.1))]
        listener_xyz=np.r_[np.asarray(listener,dtype=float),1.097]
        poly=np.asarray(room_polygon,dtype=float); area=.5*abs(float(np.sum(poly[0]*np.roll(poly[1],-1)-poly[1]*np.roll(poly[0],-1))))
        room_height=float(room_env["volume_m3"])/max(area,1e-12) if room_env is not None else 2.4384
        paths=first_order_reflections(poly,source,listener_xyz,room_height)
        direct_m=float(np.linalg.norm(source-listener_xyz)); deltas=[row["path_length_m"]-direct_m for row in paths if row["surface"] in ("floor","ceiling") and row["path_length_m"]>direct_m+1e-6]
        terms["floor_ceiling_comb_notch_hz"]=float(343./(2.*min(deltas))) if deltas else float("nan")
    return terms

def _weighted_imaging(terms,spec):
    weights=spec.score_weights
    return float(sum(weights.get(name,0.)*terms.get(key,0.) for name,key in (("clarity","clarity_db"),("off_axis","off_axis_db"),("early_reflection","early_reflection_db"),("headroom","headroom_db"),("direct_level","direct_level_db"))))


def _modal_eval(polygon,sources,listener,absorption,spec,model,step_hz=1.,q_scale=20.,seat_cluster_spacing_m=.3,surface_absorption=None,seat_positions_m=None):
    effective_high=min(spec.band_hz[1],model.freq_high_hz)
    band=(max(spec.band_hz[0],model.freq_low_hz),effective_high)
    effective_step=modal_step_for_damping(polygon,absorption,q_scale,step_hz,band)
    # The image-source model already contains the coincident mounting-wall image.
    gains=[0. for _ in sources]
    origin,ux,uy,lx,ly=rectangular_room_frame(polygon)
    center=np.asarray(listener,dtype=float); local=center-origin
    cx=float(local@ux); cy=float(local@uy)
    cluster=[]
    for dx in (-seat_cluster_spacing_m,0.,seat_cluster_spacing_m):
        for dy in (-seat_cluster_spacing_m,0.,seat_cluster_spacing_m):
            x=np.clip(cx+dx,.05,lx-.05); y=np.clip(cy+dy,.05,ly-.05)
            cluster.append(origin+x*ux+y*uy)
    other_seats=[]
    for seat in seat_positions_m or []:
        point=np.asarray(seat,dtype=float)[:2]
        if np.linalg.norm(point-center)>.05: other_seats.append(point)
    cluster.extend(other_seats)
    freq,pressures=modal_response(polygon,sources,np.asarray(cluster),absorption,band,effective_step,q_scale,source_gains_db=gains,surface_absorption=surface_absorption)
    response_filter=10.**(model.response_db(freq)/20.)
    pressures=pressures*response_filter[None,:]
    center_index=4
    group_power=[np.mean(np.abs(pressures[:9])**2,axis=0)]
    group_power.extend(np.abs(pressures[index])**2 for index in range(9,len(cluster)))
    pressure=np.sqrt(np.mean(np.asarray(group_power),axis=0))*np.exp(1j*np.angle(pressures[center_index]))
    terms=modal_score(freq,pressure)
    cluster_db=20.*np.log10(np.maximum(np.abs(pressures),1e-15))
    exact_indices=[center_index]+list(range(9,len(cluster)))
    seat_db=cluster_db[exact_indices]
    terms["spatial_variance_db"]=-float(np.mean(np.std(seat_db,axis=0)))
    terms["seat_response_db"]=seat_db
    terms["seat_max_min_db"]=float(np.mean(np.max(seat_db,axis=0)-np.min(seat_db,axis=0)))
    exact_db=20.*np.log10(np.maximum(np.abs(pressures[center_index]),1e-15))
    terms["exact_response_db"]=np.interp(terms["frequencies_hz"],freq,exact_db)
    terms["cluster_pressure"]=pressure
    terms["exact_pressure"]=pressures[center_index]
    return terms["frequencies_hz"],pressure,terms


def _evaluate_group(polygon, sources, terms_by_source, listener, absorption, spec, facing, model, reference_spl_db, peak_headroom_db, step_hz=1.,q_scale=20.,coherent=True,room_env=None,seat_cluster_spacing_m=.3,seat_positions_m=None):
    if spec.scorer=="modal":
        wall_alpha=None
        if room_env is not None:
            wall_alpha=np.full(4,float(np.mean(room_env["surface_absorption_coefficients"]["walls"][:2])))
        acoustic_sources=[c.position+c.normal*float(model.acoustic_center_offset_m[1]) for c in sources]
        freq,pressure,modal_terms=_modal_eval(polygon,acoustic_sources,listener,absorption,spec,model,step_hz,q_scale,seat_cluster_spacing_m,wall_alpha,seat_positions_m)
        individual=[_headroom(model,_acoustic_distance(c,model,listener),reference_spl_db,peak_headroom_db,spec.name,room_env,boundary_gain_db=_candidate_boundary_gain(c,model))[0] for c in sources]
        combine=(20. if coherent else 10.)*np.log10(max(1,len(sources)))
        combined_spl=float(sum(individual)/len(individual)+combine)
        max_spl=model.max_spl_lf_db if spec.name=="bass" and model.max_spl_lf_db is not None else model.max_spl_db
        cap=float(sum(max_spl-20.*log10(max(_acoustic_distance(c,model,listener),1e-6))+_candidate_boundary_gain(c,model) for c in sources)/len(sources)+combine)
        # Headroom is a per-channel placement check; don't let N subwoofers
        # hide an under-capable individual unit by summing their peaks.
        available_peak=float(min(individual))
        required_allowance=max(0.,peak_headroom_db-(10. if spec.name=="bass" else 0.))
        required_peak=reference_spl_db+required_allowance
        headroom=available_peak-required_peak
        terms={"flatness":modal_terms["flatness"],"null_penalty":modal_terms["null_penalty"],"spatial_variance_db":modal_terms["spatial_variance_db"],"seat_max_min_db":modal_terms["seat_max_min_db"],"geometry_db":0.,"headroom_db":float(headroom)}
        value=(spec.score_weights.get("flatness",1.)*terms["flatness"]
               +spec.score_weights.get("null_penalty",1.)*terms["null_penalty"]
               +spec.score_weights.get("spatial_variance",0.)*terms["spatial_variance_db"]
               +spec.score_weights.get("geometry",0.)*terms["geometry_db"]
               +spec.score_weights.get("headroom",0.)*headroom)
        schroeder=float(np.mean(room_env["schroeder_hz"])) if room_env is not None else float("nan")
        return float(value),terms,{"frequencies_hz":freq,"pressure":pressure,"response_db":modal_terms["response_db"],"exact_response_db":modal_terms["exact_response_db"],"seat_response_db":modal_terms["seat_response_db"],"seat_max_min_db":modal_terms["seat_max_min_db"],"spatial_variance_db":modal_terms["spatial_variance_db"],"schroeder_frequency_hz":schroeder,"combined_spl_db":combined_spl,"available_peak_spl_db":available_peak,"required_peak_spl_db":required_peak,"max_spl_db":cap}
    common_keys=set.intersection(*(set(item) for item in terms_by_source))
    terms={key:float(sum(item[key] for item in terms_by_source)/len(terms_by_source)) for key in common_keys}
    spls=[_headroom(model,_acoustic_distance(c,model,listener),reference_spl_db,peak_headroom_db,spec.name,room_env,boundary_gain_db=_candidate_boundary_gain(c,model))[0] for c in sources]
    combine=(20. if coherent else 10.)*np.log10(max(1,len(sources)))
    combined_spl=float(sum(spls)/len(spls)+combine)
    # Report the weakest member's per-channel capability, not the summed
    # peak of a mirrored pair or multi-sub group.
    group_max=float(min(spls))
    available_peak=group_max
    required_allowance=max(0.,peak_headroom_db-(10. if spec.name=="bass" else 0.))
    required_peak=reference_spl_db+required_allowance
    headroom=available_peak-required_peak; terms["headroom_db"]=float(headroom)
    angle_errors=[]
    if spec.angle_target_deg is not None:
        angle_errors=[abs(abs(angle_to_facing(c.position,listener,facing))-spec.angle_target_deg) for c in sources]
    geom=-float(np.mean(np.square(angle_errors))) if angle_errors else 0.
    if spec.name=="front" and len(sources)==2:
        d1=float(np.linalg.norm(sources[0].position-listener)); d2=float(np.linalg.norm(sources[1].position-listener)); base=float(np.linalg.norm(sources[0].position-sources[1].position)); mean=(d1+d2+base)/3.
        geom+=-10.*(abs(d1-d2)+abs(base-(d1+d2)/2))/max(mean,1e-9)
    terms["geometry_db"]=float(geom)
    value=_weighted_imaging(terms,spec)+spec.score_weights.get("geometry",1.)*geom
    return float(value),terms,{"combined_spl_db":combined_spl,"available_peak_spl_db":available_peak,"required_peak_spl_db":required_peak,"max_spl_db":group_max}


def _expand_beam_chunk(task):
    """Evaluate consecutive beam rows, retaining their serial tie positions."""
    (start, selected_rows, options, polygon, listener, absorption, spec, facing,
     model, reference_spl_db, peak_headroom_db, step_hz, q_scale, coherent,
     room_env, seat_cluster_spacing_m, seat_positions_m,
     min_speaker_spacing_m) = task
    expanded=[]
    for row_index, selected_groups in enumerate(selected_rows, start):
        existing=[point for group in selected_groups for point in group[:2] if point is not None]
        for option_index, option in enumerate(options):
            new_points=[option[0]]+([option[1]] if option[1] is not None else [])
            spacing=max(min_speaker_spacing_m,model.min_spacing_to_other_speakers_m)
            if any(np.linalg.norm(a.position-b.position)<spacing for a in new_points for b in existing): continue
            if len(new_points)==2 and np.linalg.norm(new_points[0].position-new_points[1].position)<max(spacing,model.width_m): continue
            group=selected_groups+[option]; points=[point for pair in group for point in pair[:2] if point is not None]
            terms_by_source=[]
            if spec.scorer=="imaging":
                for pair in group: terms_by_source.extend(pair[2])
            value,terms,modal_data=_evaluate_group(polygon,points,terms_by_source,listener,absorption,spec,facing,model,
                reference_spl_db,peak_headroom_db,step_hz,q_scale,coherent,room_env,seat_cluster_spacing_m,seat_positions_m)
            expanded.append((row_index*len(options)+option_index,(value,group,terms,modal_data)))
    # Anything below the best 150 in a chunk cannot enter the global beam.
    expanded.sort(key=lambda item:item[1][0],reverse=True)
    return expanded[:150]


def _candidate_key(candidate):
    return (candidate.surface,tuple(np.round(candidate.position,9)))


def _acoustic_distance(candidate, model, listener_xy, ear_height_m=1.097):
    """3D source-to-ear distance using model acoustic-center offsets."""
    xy=np.asarray(candidate.position,dtype=float)+np.asarray(candidate.normal,dtype=float)*float(model.acoustic_center_offset_m[1])
    z=float(candidate.height_m if candidate.height_m is not None else ear_height_m)+float(model.acoustic_center_offset_m[0])
    return float(np.sqrt(np.linalg.norm(xy-np.asarray(listener_xy,dtype=float))**2+(z-ear_height_m)**2))


def _candidate_boundary_gain(candidate, model):
    surface="corner" if candidate.surface=="corner" else candidate.surface
    return boundary_gain_for_mount(model.mount_type,surface)


def _legal_height_grid(role, model, listener_xy, source_xy, room_height_m, ear_height_m=1.097, screen_height_m=None,elevation_range_deg=None):
    """Enumerate mountable z values on 15 cm increments under role-specific policies."""
    distance=max(float(np.linalg.norm(np.asarray(source_xy)-listener_xy)),.01)
    low,high=map(float,model.mount_height_range_m)
    vertical_offset=float(model.acoustic_center_offset_m[0])
    low=max(low,float(model.height_m)/2.+.01)
    high=min(high,float(room_height_m)-float(model.height_m)/2.-.01)
    if role in ("front","regular","center","wide"):
        # Main tweeters should remain close to seated ear level; the elevation
        # sector is expressed at the listener and clipped by the cabinet bounds.
        reference=float(screen_height_m if screen_height_m is not None else ear_height_m)
        low=max(low,reference+distance*np.tan(np.radians(-10.))-vertical_offset)
        high=min(high,reference+distance*np.tan(np.radians(15.))-vertical_offset)
        preferred=reference
    elif role in ("surround","rear_surround"):
        low=max(low,float(ear_height_m)+.6); high=min(high,float(ear_height_m)+1.2)
        preferred=float(ear_height_m)+.9
    elif role=="bass":
        # Allow a wall sub across nearly the full room height. The cabinet's
        # half-height remains a hard floor/ceiling clearance constraint.
        low=max(float(model.height_m)/2.+.01,.1)
        high=float(room_height_m)-float(model.height_m)/2.-.01
        preferred=float(np.clip(.3,low,high))
    else:
        preferred=float(ear_height_m)
    if elevation_range_deg is not None:
        # The channel's documented angle sector is the hard rule. The generic
        # surround-above-ear recommendation remains a soft z preference when
        # the two cannot both fit at short throw distances.
        low=max(float(model.mount_height_range_m[0]),float(model.height_m)/2.+.01)
        high=min(float(model.mount_height_range_m[1]),float(room_height_m)-float(model.height_m)/2.-.01)
        if role in ("surround","rear_surround"): preferred=float(ear_height_m)+.9
        elif role in ("front","regular","center","wide"): preferred=float(screen_height_m if screen_height_m is not None else ear_height_m)
    if low>high:
        # Keep a legal cabinet height when a small room makes the recommended
        # elevation sector impossible; report the constraint in output later.
        low=max(float(model.mount_height_range_m[0]),float(model.height_m)/2.+.01)
        high=min(float(model.mount_height_range_m[1]),float(room_height_m)-float(model.height_m)/2.-.01)
    if elevation_range_deg is not None:
        elevation_low,elevation_high=map(float,elevation_range_deg)
        horizontal=max(float(np.linalg.norm(np.asarray(source_xy)-np.asarray(listener_xy))),.01)
        standard_low=float(ear_height_m+horizontal*np.tan(np.radians(elevation_low))-vertical_offset)
        standard_high=float(ear_height_m+horizontal*np.tan(np.radians(elevation_high))-vertical_offset)
        low=max(low,standard_low); high=min(high,standard_high)
    if low>high:
        if elevation_range_deg is not None: return np.asarray([],dtype=float)
        raise ValueError("speaker '{}' height range does not fit inside the room".format(model.model_id))
    values=np.arange(low,high+1e-9,.15)
    return np.unique(np.r_[values,np.clip(preferred,low,high),low,high])


def _vertical_response(z, model, distance, ear_height_m):
    acoustic_z=float(z)+float(model.acoustic_center_offset_m[0])
    target_pitch=float(np.degrees(np.arctan2(ear_height_m-acoustic_z,distance)))
    pitch=0. if model.directivity_model=="omni" else float(np.clip(target_pitch,-model.max_tilt_deg,model.max_tilt_deg))
    residual=target_pitch-pitch
    gain=0. if model.directivity_model=="omni" else float(model.gain_vertical_db(residual))
    return gain,pitch


def _wall_box_fits(room, candidate, model, listener, room_height_m, ear_height_m, visible_depth_m=None, toe_deg=None):
    """Check the final tilted cabinet against every room wall before scoring."""
    if candidate.surface!="wall": return True
    visible=float((model.depth_m if model.mount_type=="on_wall" else .012)
                  if visible_depth_m is None else visible_depth_m)
    polygon=np.asarray(room,dtype=float)
    return _wall_box_fits_cached(
        polygon.shape,polygon.tobytes(),candidate.wall_index,
        tuple(float(x) for x in candidate.position),tuple(float(x) for x in candidate.normal),
        float(candidate.height_m),tuple(float(x) for x in np.asarray(listener)),
        float(model.width_m),float(model.height_m),visible,
        float(model.acoustic_center_offset_m[0]),model.directivity_model,float(model.max_tilt_deg),
        float(room_height_m),float(ear_height_m),None if toe_deg is None else float(toe_deg))


@lru_cache(maxsize=32768)
def _wall_box_fits_cached(room_shape, room_bytes, wall_index, position, normal, height,
                          listener, width, box_height, visible, offset_z, directivity_model,
                          max_tilt, room_height, ear_height, toe_override):
    from .viewer3d import box_pose,wall_frame
    room=np.frombuffer(room_bytes,dtype=float).reshape(room_shape)
    position=np.asarray(position,dtype=float)
    normal=np.asarray(normal,dtype=float)
    listener=np.asarray(listener,dtype=float)
    if toe_override is None:
        direction=listener-position
        cross=float(normal[0]*direction[1]-normal[1]*direction[0])
        toe=float(np.degrees(np.arctan2(cross,float(normal@direction))))
    else:
        toe=toe_override
    theta=np.radians(toe)
    aim=np.array([normal[0]*np.cos(theta)-normal[1]*np.sin(theta),
                  normal[0]*np.sin(theta)+normal[1]*np.cos(theta)])
    distance=max(float(np.linalg.norm(position-listener)),.01)
    target_pitch=float(np.degrees(np.arctan2(ear_height-(height+offset_z),distance)))
    pitch=0. if directivity_model=="omni" else float(np.clip(target_pitch,-max_tilt,max_tilt))
    try:
        pose=box_pose(room,room_height,wall_index,position,height,width,box_height,visible,aim,pitch)
    except ValueError:
        return False
    start,tangent,_=wall_frame(room,wall_index)
    expected=start+float((position-start)@tangent)*tangent
    shift=float((pose.mount_position_m[:2]-expected)@tangent)
    return abs(shift)<=.01


def _select_candidate_height(candidate, role, model, listener_xy, room_height_m, ear_height_m, screen_height_m=None, height_values=None,elevation_range_deg=None):
    """Choose z using the same vertical-polar and aiming limits used for scoring."""
    distance=max(float(np.linalg.norm(candidate.position-listener_xy)),.01)
    values=np.asarray(height_values if height_values is not None else
        _legal_height_grid(role,model,listener_xy,candidate.position,room_height_m,ear_height_m,screen_height_m,elevation_range_deg))
    reference=float(screen_height_m if screen_height_m is not None else ear_height_m)
    preferred={"front":reference,"regular":reference,"center":reference,"wide":reference,
               "surround":ear_height_m+.9,"rear_surround":ear_height_m+.9,"bass":min(.3,float(values[-1]))}.get(role,reference)
    ranked=[]
    for z in values:
        gain,pitch=_vertical_response(float(z),model,distance,ear_height_m)
        # Height contributes through direct vertical response; the gentle prior
        # resolves broad-polar ties without forcing all speakers to one z.
        ranked.append((gain-0.05*abs(float(z)-float(preferred)),float(z),gain,pitch))
    _,z,gain,pitch=max(ranked,key=lambda row:(row[0],-abs(row[1]-preferred)))
    candidate.height_m=z
    return z,gain,pitch


def _overlaps_wall_keepout(polygon, candidate, model, height_m, keepouts):
    """Test cabinet footprint against wall-local or legacy cardinal keep-outs."""
    p=validate_polygon(polygon); xy=np.asarray(candidate.position); xmin,xmax=p[0].min(),p[0].max(); ymin,ymax=p[1].min(),p[1].max()
    for zone in keepouts:
        if "wall_index" in zone:
            wall_index=int(zone["wall_index"])
            if int(candidate.wall_index)!=wall_index: continue
            start=p[:,wall_index]; edge=p[:,(wall_index+1)%p.shape[1]]-start
            length=float(np.linalg.norm(edge))
            if length<=0: continue
            tangent=edge/length; along=float((xy-start)@tangent)
            half_width=float(model.width_m)/2.+float(zone.get("clearance_m",0.))
            half_height=float(model.height_m)/2.+float(zone.get("clearance_m",0.))
            if along+half_width>=zone["u_range_m"][0] and along-half_width<=zone["u_range_m"][1] and height_m+half_height>=zone["z_range_m"][0] and height_m-half_height<=zone["z_range_m"][1]: return True
            continue
        wall=zone["wall"]
        wall_value={"north":ymax,"south":ymin,"east":xmax,"west":xmin}[wall]
        candidate_value={"north":xy[1],"south":xy[1],"east":xy[0],"west":xy[0]}[wall]
        if abs(candidate_value-wall_value)>.02: continue
        along=float(xy[0] if wall in ("north","south") else xy[1])
        half_width=float(model.width_m)/2.+float(zone.get("clearance_m",0.))
        half_height=float(model.height_m)/2.+float(zone.get("clearance_m",0.))
        if along+half_width>=zone["u_range_m"][0] and along-half_width<=zone["u_range_m"][1] and height_m+half_height>=zone["z_range_m"][0] and height_m-half_height<=zone["z_range_m"][1]:
            return True
    return False


def _overlaps_forbidden_box(candidate, model, height_m, forbidden_boxes):
    """Conservatively reject a speaker cabinet intersecting a 3D obstacle."""
    center=np.r_[np.asarray(candidate.position,dtype=float),float(height_m)]
    half=float(np.hypot(float(model.width_m),float(model.depth_m))/2.)
    speaker_half=np.array([half,half,float(model.height_m)/2.])
    for obstacle in forbidden_boxes:
        other=np.asarray(obstacle["center_m"],dtype=float)
        obstacle_half=np.asarray(obstacle["dimensions_m"],dtype=float)/2.+float(obstacle.get("clearance_m",0.))
        if np.all(np.abs(center-other)<=(speaker_half+obstacle_half)): return True
    return False


def optimize_layout(room_polygon, listener, layout=None, facing="north", absorption=.2, top_n=5,
                    simulator=simulate_rir, spacing_m=.25, margin_m=.3, nudge_m=.001,
                    min_listener_distance_m=.5, min_speaker_spacing_m=.5, modal_q_scale=20., models=None,
                    reference_spl_db=85., peak_headroom_db=20., coherent=True, modal_step_hz=1.,
                    refinement_sweeps=1, reserved_speakers=None, directivity_on_reflections=True, toe_in_range_deg=None,
                    room_height_m=2.4384, materials=None, seat_cluster_spacing_m=.3, ear_height_m=1.097, screen_height_m=None,
                    mount_heights_m=None, keepouts=None, seat_positions_m=None, mlp_weight=.6,coverage_threshold_db=-3.,
                    stud_spacing_m=None, stud_thickness_m=.0381, forbidden_boxes=None):
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
    forbidden_boxes=list(forbidden_boxes or [])
    models=DEFAULT_SPEAKER_MODELS if models is None else models
    if not 0. <= mlp_weight <= 1.: raise ValueError("mlp_weight must be between 0 and 1")
    if coverage_threshold_db not in (-3.,-6.): raise ValueError("coverage_threshold_db must be -3 or -6 dB")
    seats=[]
    for seat in seat_positions_m or []:
        if isinstance(seat,dict): seats.append((np.asarray(seat["position_m"],dtype=float)[:2],float(seat.get("ear_height_m",ear_height_m))))
        else: seats.append((np.asarray(seat,dtype=float)[:2],float(ear_height_m)))
    if not seats: seats=[(listener.copy(),float(ear_height_m))]
    seats.sort(key=lambda item:float(np.linalg.norm(item[0]-listener)))
    environment=room_metrics(p,float(room_height_m),materials if materials is not None else MaterialSet())
    environment["_headroom_cache"]={}
    mount_heights_m=dict(mount_heights_m or {})
    keepouts=list(keepouts or [])

    def rir_for(c, point=None, source_model=None):
        point=listener if point is None else np.asarray(point,dtype=float)[:2]
        offset=(0.,0.) if source_model is None else tuple(source_model.acoustic_center_offset_m)
        key=(_candidate_key(c),tuple(np.round(point,6)),offset)
        source_xy=np.asarray(c.position,dtype=float)+np.asarray(c.normal,dtype=float)*float(offset[1])
        if key not in rir_cache: rir_cache[key]=simulator(p,source_xy,point,absorption=absorption)
        return rir_cache[key]

    imaging_cache={}

    def imaging_for(c, toe):
        """Score every seat, weighting the MLP most heavily."""
        key=(id(c),float(c.height_m),float(toe))
        cached=imaging_cache.get(key)
        if cached is not None:
            return cached[1]
        rows=[]
        for index,(point,seat_ear) in enumerate(seats):
            h,fs=rir_for(c,point,model)
            terms=_imaging_terms(h,fs,c,point,spec,model,reference_spl_db,peak_headroom_db,float(toe),p,directivity_on_reflections,environment,seat_ear)
            gain,_=_vertical_response(float(c.height_m),model,max(float(np.linalg.norm(c.position-point)),.01),seat_ear)
            terms=dict(terms); terms["off_axis_db"]+=gain*spec.directivity
            rows.append(terms)
        other_weight=(1.-mlp_weight)/max(len(rows)-1,1) if len(rows)>1 else 0.
        weights=([mlp_weight]+[other_weight]*(len(rows)-1)) if len(rows)>1 else [1.]
        aggregate={key:float(sum(w*row[key] for w,row in zip(weights,rows))) for key in rows[0]}
        aggregate["worst_seat_clarity_db"]=float(min(row["clarity_db"] for row in rows))
        aggregate["worst_seat_headroom_db"]=float(min(row["headroom_db"] for row in rows))
        imaging_cache[key]=(c,aggregate)
        return aggregate

    for spec in specs:
        if spec.count==0: continue
        imaging_cache.clear()
        if spec.symmetric and spec.count%2:
            raise ValueError("speaker type '{}' is symmetric and requires an even count".format(spec.name))
        model_id=spec.model_id or DEFAULT_MODEL_BY_ROLE.get(spec.name) or (DEFAULT_MODEL_BY_ROLE["front"] if spec.name in ("regular","wide") else None)
        model=models[model_id] if model_id in models else resolve_model(model_id)
        role_name="front" if spec.name in ("regular","center","wide") else "surround" if spec.name=="rear_surround" else spec.name
        if role_name not in model.role_types:
            raise ValueError("model '{}' cannot fill role '{}'; supported roles: {}".format(model.model_id,role_name,", ".join(model.role_types)))
        target_band=(spec.band_hz[0],min(spec.band_hz[1],model.crossover_hz if spec.name=="bass" and model.crossover_hz>0 else spec.band_hz[1]))
        if model.freq_low_hz>target_band[0] or model.freq_high_hz<target_band[1]:
            raise ValueError("model '{}' bandwidth {}-{} Hz does not cover {} role band {}-{} Hz".format(model.model_id,model.freq_low_hz,model.freq_high_hz,spec.name,*target_band))
        if spec.name=="bass" and model.f3_hz>target_band[0]: warnings.append("WARN: bass model {} f3 {:.1f} Hz is above target lower band {:.1f} Hz".format(model.model_id,model.f3_hz,target_band[0]))
        spec_candidates=list(candidates)+_analytic_angle_candidates(p,listener,facing,spec,margin_m,nudge_m)
        if spec.name=="bass":
            spec_candidates.extend(generate_horizontal_surface_candidates(p,room_height_m,model,spacing_m,.15))
            if model.mount_type in ("in_wall","flush"):
                spec_candidates=[c for c in spec_candidates if c.surface=="wall"]
            elif model.mount_type in ("stand","floor_standing"):
                spec_candidates=[c for c in spec_candidates if c.surface in ("floor","corner")]
            elif model.mount_type in ("in_ceiling","on_ceiling"):
                spec_candidates=[c for c in spec_candidates if c.surface=="ceiling"]
            elif model.mount_type=="on_wall":
                spec_candidates=[c for c in spec_candidates if c.surface in ("wall","floor","corner")]
        if model.mount_type=="in_wall" and stud_spacing_m is not None:
            try:
                spec_candidates=[snap_wall_candidate_to_bay(c,p,stud_spacing_m,stud_thickness_m,model.cutout_width_m or model.width_m,margin_m,nudge_m) if c.surface=="wall" else c for c in spec_candidates]
            except ValueError as exc:
                raise ValueError("in-wall {} mounting constraint: {}".format(model.model_id,exc)) from exc
            spec_candidates=list({_candidate_key(c):c for c in spec_candidates}.values())
        physical=[c for c in spec_candidates if np.linalg.norm(c.position-listener)>=min_listener_distance_m
                 and c.wall_t*float(np.linalg.norm(p[:,(c.wall_index+1)%p.shape[1]]-p[:,c.wall_index]))>=model.corner_clearance_m
                 and (1.-c.wall_t)*float(np.linalg.norm(p[:,(c.wall_index+1)%p.shape[1]]-p[:,c.wall_index]))>=model.corner_clearance_m
                 and all(np.linalg.norm(c.position-other["position_m"])>=max(min_speaker_spacing_m,model.min_spacing_to_other_speakers_m,(model.width_m+other.get("footprint_width_m",0.))/2.) for other in placed)]
        allowed=[c for c in physical if _allowed(spec.allowed_walls,roles[c.wall_index])]
        valid=[c for c in allowed if _valid_angle(c,listener,facing,spec)]
        elevation_valid=list(valid)
        height_values={}
        height_filtered=[]
        for c in valid:
            if c.surface in ("floor","ceiling","corner"):
                height_values[_candidate_key(c)]=np.asarray([float(c.height_m)])
            elif spec.name in mount_heights_m:
                low=max(float(model.mount_height_range_m[0]),model.height_m/2.+.01)
                high=min(float(model.mount_height_range_m[1]),room_height_m-model.height_m/2.-.01)
                fixed=float(mount_heights_m[spec.name])
                if not low<=fixed<=high: raise ValueError("mount height for {} must be within {:.2f}-{:.2f} m".format(spec.name,low,high))
                if spec.elevation_range_deg is not None:
                    legal=_legal_height_grid(spec.name,model,listener,c.position,room_height_m,ear_height_m,screen_height_m,spec.elevation_range_deg)
                    if not np.any(np.isclose(legal,fixed,atol=.01)):
                        raise ValueError("fixed mount height for {} violates elevation window {}..{} degrees at this seat".format(spec.channel_name,*spec.elevation_range_deg))
                height_values[_candidate_key(c)]=np.asarray([fixed]); c.height_m=fixed
            else:
                height_values[_candidate_key(c)]=_legal_height_grid(spec.name,model,listener,c.position,room_height_m,ear_height_m,screen_height_m,spec.elevation_range_deg)
                if c.surface=="wall":
                    height_values[_candidate_key(c)]=np.asarray([z for z in height_values[_candidate_key(c)]
                        if not _overlaps_wall_keepout(p,c,model,float(z),keepouts)])
                if not len(height_values[_candidate_key(c)]): continue
                if c.surface=="wall": _select_candidate_height(c,spec.name,model,listener,room_height_m,ear_height_m,screen_height_m,height_values[_candidate_key(c)],spec.elevation_range_deg)
            if forbidden_boxes:
                height_values[_candidate_key(c)]=np.asarray([z for z in height_values[_candidate_key(c)]
                    if not _overlaps_forbidden_box(c,model,float(z),forbidden_boxes)])
                if not len(height_values[_candidate_key(c)]): continue
            if c.surface=="wall" and keepouts and any(_overlaps_wall_keepout(p,c,model,float(z),keepouts) for z in height_values[_candidate_key(c)]):
                height_values[_candidate_key(c)]=np.asarray([z for z in height_values[_candidate_key(c)]
                    if not _overlaps_wall_keepout(p,c,model,float(z),keepouts)])
                if not len(height_values[_candidate_key(c)]): continue
                _select_candidate_height(c,spec.name,model,listener,room_height_m,ear_height_m,screen_height_m,height_values[_candidate_key(c)],spec.elevation_range_deg)
            if c.surface=="wall" and not _wall_box_fits(p,c,model,listener,room_height_m,ear_height_m): continue
            height_filtered.append(c)
        relaxed_azimuth=False
        if not height_filtered and spec.elevation_range_deg is not None and physical:
            # Small or unusually shaped rooms can make a standards elevation
            # window unreachable from every legal wall point. Preserve all
            # physical, spacing, keep-out, and projector constraints, then
            # retry with the model's mountable height range and report that
            # the channel angle is outside its reference window.
            fallback_range=(-80.,80.)
            fallback_candidates=list({_candidate_key(c):c for c in (elevation_valid+allowed+physical)}.values())
            relaxed_azimuth=not bool(elevation_valid)
            for c in fallback_candidates:
                values=_legal_height_grid(spec.name,model,listener,c.position,room_height_m,
                    ear_height_m,screen_height_m,fallback_range)
                values=np.asarray([z for z in values
                    if c.surface!="wall" or not _overlaps_wall_keepout(p,c,model,float(z),keepouts)
                    if not _overlaps_forbidden_box(c,model,float(z),forbidden_boxes)])
                if not len(values): continue
                height_values[_candidate_key(c)]=values
                _select_candidate_height(c,spec.name,model,listener,room_height_m,ear_height_m,
                    screen_height_m,values,fallback_range)
                if c.surface=="wall" and not _wall_box_fits(p,c,model,listener,room_height_m,ear_height_m): continue
                height_filtered.append(c)
            if height_filtered:
                warnings.append("WARN: {} could not meet reference elevation {}..{}°; selected the nearest legal mount height and report marks the deviation".format(spec.channel_name or spec.name,*spec.elevation_range_deg))
                if relaxed_azimuth:
                    warnings.append("WARN: {} had no candidate inside its reference azimuth sector; selected the nearest legal wall position and report marks the deviation".format(spec.channel_name or spec.name))
                if any(not _allowed(spec.allowed_walls,roles[c.wall_index]) for c in height_filtered):
                    warnings.append("WARN: {} used a wall outside its reference surface sector to avoid a placement conflict".format(spec.channel_name or spec.name))
        valid=height_filtered
        if spec.scorer=="imaging":
            for c in valid:
                center_toe=_toe_toward_listener(c,listener)
                c._legal_toes=([center_toe] if spec.channel_name=="C" and abs(center_toe)<=model.max_toe_in_deg and
                    _wall_box_fits(p,c,model,listener,room_height_m,ear_height_m,toe_deg=center_toe) else
                    [] if spec.channel_name=="C" else
                    [float(toe) for toe in _toe_grid(model,bounds=toe_in_range_deg)
                     if _covers_all_seats(c,model,toe,seats,ear_height_m,coverage_threshold_db) and
                     _wall_box_fits(p,c,model,listener,room_height_m,ear_height_m,toe_deg=float(toe))])
            valid=[c for c in valid if c._legal_toes]
        if not valid:
            if spec.elevation_range_deg is not None:
                raise ValueError("Room invalid for selected layout: no legal position for channel {} remains after room-boundary, spacing, and screen/projector-separation checks (reference elevation {}..{}°). Edit the room, listener position, or layout and retry".format(spec.channel_name or spec.name,*spec.elevation_range_deg))
            if spec.scorer=="imaging": raise ValueError("Room invalid for selected layout: no candidate for {} covers every seat within {:.0f} dB while remaining separate from other components. Edit the room or seating, or change the speaker model/coverage threshold and retry".format(spec.channel_name or spec.name,coverage_threshold_db))
            raise ValueError("Room invalid for selected layout: no legal candidate for speaker type '{}' remains after room-boundary, spacing, and keep-out checks. Edit the room or layout and retry".format(spec.name))
        single_scores={}
        for c in valid:
            response_data=None; vertical_gain=0.
            if spec.scorer=="modal":
                wall_alpha=np.full(4,float(np.mean(environment["surface_absorption_coefficients"]["walls"][:2])))
                source_xy=np.asarray(c.position)+np.asarray(c.normal)*float(model.acoustic_center_offset_m[1])
                f,pr,mt=_modal_eval(p,[source_xy],listener,absorption,spec,model,modal_step_hz,modal_q_scale,seat_cluster_spacing_m,wall_alpha,[point for point,_ in seats])
                spl,headroom=_headroom(model,_acoustic_distance(c,model,listener,ear_height_m),reference_spl_db,peak_headroom_db,spec.name,environment,boundary_gain_db=_candidate_boundary_gain(c,model))
                terms={"flatness":mt["flatness"],"null_penalty":mt["null_penalty"],"spatial_variance_db":mt["spatial_variance_db"],"geometry_db":0.,"headroom_db":headroom}
                score=(spec.score_weights.get("flatness",1.)*terms["flatness"]
                       +spec.score_weights.get("null_penalty",1.)*terms["null_penalty"]
                       +spec.score_weights.get("spatial_variance",0.)*terms["spatial_variance_db"]
                       +spec.score_weights.get("geometry",0.)*terms["geometry_db"]
                       +spec.score_weights.get("headroom",0.)*terms["headroom_db"])
                response_data={"frequencies_hz":f,"response_db":mt["response_db"]}
            else:
                toe_options=np.asarray(c._legal_toes,dtype=float)
                scored=[]
                for toe in toe_options:
                    terms=imaging_for(c,toe)
                    scored.append((_weighted_imaging(terms,spec),float(toe),terms))
                score,toe,terms=max(scored,key=lambda item:item[0])
                vertical_gain,_=_vertical_response(float(c.height_m),model,
                    max(float(np.linalg.norm(c.position-listener)),.01),ear_height_m)
                score=_weighted_imaging(terms,spec)
                c.toe_in_deg=toe
                response_data={"toe_in_deg":toe}
            single_scores[_candidate_key(c)]=(float(score),terms)
            spl,_=_headroom(model,_acoustic_distance(c,model,listener,ear_height_m),reference_spl_db,peak_headroom_db,spec.name,environment,boundary_gain_db=_candidate_boundary_gain(c,model))
            row={"type":spec.name,"channel":spec.channel_name,"model_id":model.model_id,"position_m":c.position.copy(),"height_m":float(c.height_m),"height_range_m":[float(height_values[_candidate_key(c)][0]),float(height_values[_candidate_key(c)][-1])],"wall_index":c.wall_index,"surface":c.surface,"normal":c.normal.copy(),"score_db":float(score),"terms":terms,"predicted_spl_db":spl,"angle_deg":angle_to_facing(c.position,listener,facing)}
            if response_data is not None: row.update(response_data)
            candidate_scores.append(row)
            # Keep the full (u,z) surface for inspection. The RIR is horizontal,
            # while each z sample changes vertical directivity and the reported score.
            for z in height_values[_candidate_key(c)]:
                if abs(float(z)-float(c.height_m))<1e-9: continue
                if spec.scorer=="imaging":
                    gain,_=_vertical_response(float(z),model,max(float(np.linalg.norm(c.position-listener)),.01),ear_height_m)
                    delta=(gain-vertical_gain)*spec.directivity*spec.score_weights.get("off_axis",0.)
                else:
                    delta=0.
                candidate_scores.append({**row,"height_m":float(z),"score_db":float(score+delta)})
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
                        center_toe=_toe_toward_listener(point,listener)
                        legal_toes=([center_toe] if spec.channel_name=="C" and abs(center_toe)<=model.max_toe_in_deg else
                            [] if spec.channel_name=="C" else
                            [float(value) for value in _toe_grid(model,bounds=toe_in_range_deg)
                             if _covers_all_seats(point,model,value,seats,ear_height_m,coverage_threshold_db)])
                        if not legal_toes: break
                        def aimed_terms(value):
                            return imaging_for(point,value)
                        toe=max(legal_toes,key=lambda value:_weighted_imaging(aimed_terms(value),spec))
                        point.toe_in_deg=float(toe)
                        scored.append(aimed_terms(toe))
                    if len(scored)!=2: continue
                else: scored=[]
                options.append((c,reflected,scored))
            needed=spec.count//2
        else:
            joint_valid=valid
            if spec.scorer=="modal":
                # Keep joint beam search bounded while retaining high-scoring
                # wall/floor/ceiling options from every physical surface.
                joint_valid=[]
                for surface in ("wall","floor","ceiling"):
                    ranked_surface=sorted((c for c in valid if c.surface==surface),
                        key=lambda c:single_scores[_candidate_key(c)][0],reverse=True)
                    joint_valid.extend(ranked_surface[:50])
            for c in joint_valid:
                scored=[]
                if spec.scorer=="imaging":
                    scored=[imaging_for(c,float(getattr(c,"toe_in_deg",0.)))]
                options.append((c,)); options[-1]=(c,None,scored)
            needed=spec.count
        if not options: raise ValueError("Room invalid for selected layout: no legal placements for speaker type '{}' remain after room-boundary and component-separation checks. Edit the room/layout and retry".format(spec.name))

        # Beam-search multi-pair groups; modal groups are rescored coherently on each joint set.
        beam=[(0.,[],{},None)]
        for _ in range(needed):
            expanded=[]
            workers=worker_count()
            if spec.scorer=="modal" and workers>1 and len(beam)>=2*workers:
                chunk_size=ceil(len(beam)/(workers*4))
                tasks=[(start,[row[1] for row in beam[start:start+chunk_size]],options,p,listener,
                        absorption,spec,facing,model,reference_spl_db,peak_headroom_db,modal_step_hz,
                        modal_q_scale,coherent,{**environment,"_headroom_cache":{}},seat_cluster_spacing_m,
                        [point for point,_ in seats],min_speaker_spacing_m)
                       for start in range(0,len(beam),chunk_size)]
                ranked=[entry for chunk in ordered_map(_expand_beam_chunk,tasks,workers=workers,chunksize=1)
                        for entry in chunk]
                ranked.sort(key=lambda item:item[0])
                expanded=[entry[1] for entry in ranked]
            else:
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
                        value,terms,modal_data=_evaluate_group(p,points,score_terms_list,listener,absorption,spec,facing,model,reference_spl_db,peak_headroom_db,modal_step_hz,modal_q_scale,coherent,environment,seat_cluster_spacing_m,[point for point,_ in seats])
                        expanded.append((value,group,terms,modal_data))
            expanded.sort(key=lambda x:x[0],reverse=True); beam=expanded[:150]
            if not beam: raise ValueError("Room invalid for selected layout: could not place all {} speakers of type '{}' while maintaining component separation. Edit the room/layout and retry".format(spec.count,spec.name))

        records=[]
        for value,groups,terms,modal_data in beam[:top_n]:
            points=[point for group in groups for point in group[:2] if point is not None]
            speakers=[]
            for point in points:
                angle=angle_to_facing(point.position,listener,facing)
                distance=_acoustic_distance(point,model,listener,ear_height_m); spl,speaker_headroom=_headroom(model,distance,reference_spl_db,peak_headroom_db,spec.name,environment,boundary_gain_db=_candidate_boundary_gain(point,model))
                toe=float(getattr(point,"toe_in_deg",0.)); theta=np.radians(toe); normal=point.normal.copy(); aim=np.array([normal[0]*np.cos(theta)-normal[1]*np.sin(theta),normal[0]*np.sin(theta)+normal[1]*np.cos(theta)])
                legal_height_bounds=(_legal_height_grid(spec.name,model,listener,point.position,room_height_m,ear_height_m,screen_height_m,spec.elevation_range_deg) if spec.elevation_range_deg is not None else np.asarray([]))
                allowed_heights=([float(point.height_m)]*2 if point.surface in ("floor","ceiling","corner") else
                    [float(mount_heights_m[spec.name])]*2 if spec.name in mount_heights_m else
                    [float(x) for x in legal_height_bounds[[0,-1]]] if len(legal_height_bounds) else [float(point.height_m)]*2)
                speakers.append({"type":spec.name,"channel":spec.channel_name,"model_id":model.model_id,"position_m":point.position.copy(),"position_ft":point.position.copy()/0.3048,"height_m":float(point.height_m if point.height_m is not None else ear_height_m),"height_range_m":allowed_heights,"wall_index":point.wall_index,"wall_t":point.wall_t,"surface":("floor" if point.surface=="corner" else point.surface),"placement_mode":point.surface,"normal":normal,"aim_direction":aim,"toe_in_deg":toe,"angle_deg":angle,"predicted_spl_db":spl,"headroom_db":speaker_headroom,"coverage_h_deg":model.coverage_h_deg,"footprint_width_m":model.width_m,"footprint_height_m":model.height_m,"footprint_depth_m":model.depth_m})
                spec_warnings=[]
                if spec.name in ("surround","rear_surround") and model.directivity_model in ("dipole","bipole"):
                    spec_warnings.append("legacy 5.1 dipole/bipole surround; verify current immersive-audio guidance")
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
                record["combined_spl_db"]=modal_data["combined_spl_db"]
                record["available_peak_spl_db"]=modal_data["available_peak_spl_db"]
                record["required_peak_spl_db"]=modal_data["required_peak_spl_db"]
                record["max_spl_db"]=modal_data["max_spl_db"]
                if record["available_peak_spl_db"]<record["required_peak_spl_db"]: warnings.append("WARN: {} available peak {:.1f} dB is {:.1f} dB below required {:.1f} dB".format(spec.name,record["available_peak_spl_db"],record["terms"]["headroom_db"],record["required_peak_spl_db"]))
                if record["combined_spl_db"]<reference_spl_db: warnings.append("WARN: {} predicted average {:.1f} dB is below {:.1f} dB reference".format(spec.name,record["combined_spl_db"],reference_spl_db))
            records.append(record)
        best=records[0]
        if spec.scorer=="modal":
            modal_rows=[row for row in candidate_scores if row["type"]==spec.name and "response_db" in row]
            if modal_rows:
                poor=min(modal_rows,key=lambda row:row["score_db"])
                best["modal_response"]["poor_response"]={"frequencies_hz":poor["frequencies_hz"],"response_db":poor["response_db"]}
        placements.append({"type":spec.name,"channel":spec.channel_name,"count":spec.count,"best":best,"ranked":records,"scorer":spec.scorer,
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
                refinement_sweeps=0,reserved_speakers=other,directivity_on_reflections=directivity_on_reflections,toe_in_range_deg=toe_in_range_deg,
                room_height_m=room_height_m,materials=materials,seat_cluster_spacing_m=seat_cluster_spacing_m,ear_height_m=ear_height_m,screen_height_m=screen_height_m,mount_heights_m=mount_heights_m,keepouts=keepouts,seat_positions_m=seat_positions_m,mlp_weight=mlp_weight,stud_spacing_m=stud_spacing_m,stud_thickness_m=stud_thickness_m,forbidden_boxes=forbidden_boxes)
        best_score=aggregate_role_score(role_results)
        for sweep in range(min(int(refinement_sweeps),5)):
            improved=False
            for spec in specs:
                if spec.count==0: continue
                fixed=[speaker for name,role_result in role_results.items() if name!=spec.name for speaker in role_result.best_pair["speakers"]]
                trial=optimize_layout(p,listener,[spec],facing,absorption,top_n,simulator,spacing_m,margin_m,nudge_m,
                    min_listener_distance_m,min_speaker_spacing_m,modal_q_scale,models,reference_spl_db,peak_headroom_db,coherent,modal_step_hz,
                    refinement_sweeps=0,reserved_speakers=fixed,directivity_on_reflections=directivity_on_reflections,toe_in_range_deg=toe_in_range_deg,
                room_height_m=room_height_m,materials=materials,seat_cluster_spacing_m=seat_cluster_spacing_m,ear_height_m=ear_height_m,screen_height_m=screen_height_m,mount_heights_m=mount_heights_m,keepouts=keepouts,seat_positions_m=seat_positions_m,mlp_weight=mlp_weight,stud_spacing_m=stud_spacing_m,stud_thickness_m=stud_thickness_m,forbidden_boxes=forbidden_boxes)
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
                           candidate_spacing_m,corner_margin_m,.001,min_listener_distance_m,.5)
    if len(result.best_pair["speakers"])==2:
        left,right=result.best_pair["speakers"]
        result.best_pair["left"]=left["position_m"]; result.best_pair["right"]=right["position_m"]
        result.best_pair["angles_deg"]={"left":left["angle_deg"],"right":right["angle_deg"]}
        result.best_pair["wall_index"]=left["wall_index"]
    return result
