"""Home-theater geometry and receiver/DSP calculations.

Angles are in degrees, distances in metres, and SPL trims in dB. Standards
guidance is maintained separately in ``standards.yaml`` and marked for review.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np

SPEED_OF_SOUND_M_S = 343.0


@dataclass(frozen=True)
class ReceiverSetting:
    channel: str
    distance_m: float
    delay_ms: float
    trim_db: float


def receiver_settings(channels, speed_m_s: float = SPEED_OF_SOUND_M_S,
                      reference_distance_m: float | None = None) -> tuple[list[ReceiverSetting], dict]:
    """Return relative receiver delays and distance compensation for 3D points.

    ``channels`` is an iterable of ``(name, xyz_m)``. Trim is the level
    correction relative to ``d_ref`` using the free-field inverse-distance law.
    The reference defaults to the median channel distance.
    """
    rows=[(str(name),np.asarray(point,dtype=float)) for name,point in channels]
    if not rows or speed_m_s<=0: raise ValueError("channels and positive speed of sound are required")
    if any(point.shape!=(3,) or not np.isfinite(point).all() for _,point in rows):
        raise ValueError("each channel position must be a finite 3D point")
    distances=np.asarray([np.linalg.norm(point) for _,point in rows],dtype=float)
    if np.any(distances<=0): raise ValueError("channel distances must be positive")
    d_ref=float(np.median(distances) if reference_distance_m is None else reference_distance_m)
    if d_ref<=0: raise ValueError("reference distance must be positive")
    d_max=float(distances.max())
    settings=[ReceiverSetting(name,float(distance),1000.*(d_max-distance)/speed_m_s,
                              float(20.*np.log10(distance/d_ref)))
              for (name,_),distance in zip(rows,distances)]
    metrics={"distance_spread_m":d_max-float(distances.min()),"d_ref_m":d_ref,"d_max_m":d_max,
             "trim_spread_db":max(row.trim_db for row in settings)-min(row.trim_db for row in settings)}
    return settings,metrics


def lr4_responses(frequency_hz, crossover_hz: float):
    """Complex Linkwitz-Riley fourth-order low/high-pass responses.

    Each branch is two cascaded Butterworth second-order sections. With aligned
    acoustic centers, their complex sum is unity at every frequency.
    """
    f=np.asarray(frequency_hz,dtype=float)
    if crossover_hz<=0 or np.any(f<0): raise ValueError("frequencies must be nonnegative and crossover positive")
    s=1j*f/float(crossover_hz)
    denominator=(s*s+np.sqrt(2.)*s+1.)**2
    low=1./denominator
    high=(s**4)/denominator
    return low,high


def phase_mismatch_sum_db(frequency_hz: float, crossover_hz: float,
                          relative_delay_s: float = 0., polarity: int = 1,
                          sub_gain_db: float = 0.) -> float:
    """Magnitude of summed LR4 branches after relative sub delay/polarity/gain."""
    low,high=lr4_responses(np.asarray([frequency_hz]),crossover_hz)
    gain=10.**(float(sub_gain_db)/20.)
    delayed=low[0]*int(polarity)*gain*np.exp(-2j*np.pi*frequency_hz*relative_delay_s)
    return float(20.*np.log10(max(abs(high[0]+delayed),1e-15)))


def optimize_bass_management(speakers, seats, models, crossover_range_hz=(60.,120.),
                             gain_range_db=(-12.,6.), delay_range_ms=(-10.,10.),
                             frequency_points=121):
    """Sweep LR4 gain/delay/polarity and return complex response per seat.

    This is a direct-field planning estimate. It does not replace measured
    in-room transfer functions or a receiver's calibration process.
    """
    mains=[s for s in speakers if not str(s.get("channel","")).startswith("LFE") and s.get("type")!="bass"]
    subs=[s for s in speakers if str(s.get("channel","")).startswith("LFE") or s.get("type")=="bass"]
    if not mains or not subs or not seats:
        return {"status":"not applicable","reason":"requires a main, sub, and listening seat"}
    if crossover_range_hz[0]<=0 or crossover_range_hz[1]<crossover_range_hz[0] or frequency_points<3:
        raise ValueError("crossover sweep range and frequency grid are invalid")
    f=np.linspace(20.,200.,int(frequency_points)); crossovers=np.arange(crossover_range_hz[0],crossover_range_hz[1]+.1,10.)
    gains=np.arange(gain_range_db[0],gain_range_db[1]+.1,3.); delays=np.arange(delay_range_ms[0],delay_range_ms[1]+.1,2.)/1000.
    seat_points=[np.r_[np.asarray(s["position_m"],dtype=float)[:2],float(s.get("ear_height_m",1.1))] for s in seats]
    pos=lambda item:np.asarray(item.get("acoustic_center_position_m",item["position_m"]),dtype=float)
    md=np.asarray([[np.linalg.norm(pos(sp)-seat) for sp in mains] for seat in seat_points])
    sd=np.asarray([[np.linalg.norm(pos(sp)-seat) for sp in subs] for seat in seat_points])
    dref=float(max(md.max(),sd.max())); best=None
    for crossover in crossovers:
        hp,lp=lr4_responses(f,float(crossover)); main=np.zeros((len(seats),len(f)),complex)
        for j,sp in enumerate(mains):
            model=models[sp["model_id"]]; response=10.**(np.asarray(model.response_db(f))/20.)
            for i in range(len(seats)):
                d=max(float(md[i,j]),.1); level=model.sensitivity_1w_1m_db+10*np.log10(model.effective_power_w)-20*np.log10(d)
                main[i]+=10.**(level/20.)*response*hp*np.exp(-2j*np.pi*f*(d-dref)/SPEED_OF_SOUND_M_S)
        for gain_db in gains:
            for delay in delays:
                for polarity in (1,-1):
                    total=main.copy()
                    for j,sp in enumerate(subs):
                        model=models[sp["model_id"]]; response=10.**(np.asarray(model.response_db(f))/20.)
                        for i in range(len(seats)):
                            d=max(float(sd[i,j]),.1); level=model.sensitivity_1w_1m_db+10*np.log10(model.effective_power_w)-20*np.log10(d)+gain_db
                            total[i]+=polarity*10.**(level/20.)*response*lp*np.exp(-2j*np.pi*f*((d-dref)/SPEED_OF_SOUND_M_S+delay))/len(subs)
                    mag=np.maximum(np.abs(total),1e-15); db=20*np.log10(mag)
                    band=(f>=max(35.,crossover*.75))&(f<=min(160.,crossover*1.25))
                    band_db=db[:,band]; seat_level=np.mean(band_db,axis=1)
                    seat_std=float(np.mean(np.std(band_db,axis=0)))
                    edge=np.mean(band_db[:,[0,-1]],axis=1)
                    dip=float(np.mean(np.maximum(0.,np.mean(edge)-seat_level)))
                    objective=seat_std+dip
                    if best is None or objective<best[0]:
                        best=(objective,{"status":"estimated","method":"coherent direct-field LR4 parameter sweep",
                            "crossover_hz":float(crossover),"sub_gain_trim_db":float(gain_db),
                            "additional_sub_delay_ms":float(delay*1000.),"sub_polarity":"normal" if polarity==1 else "inverted",
                            "objective_db":objective,"seat_std_db":seat_std,"crossover_dip_db":dip,
                            "frequencies_hz":f.tolist(),"seat_response_db":db.tolist(),
                            "seat_phase_deg":np.degrees(np.unwrap(np.angle(total),axis=1)).tolist(),
                            "seat_labels":["{}:{}".format(s["row"],s["seat"]) for s in seats],
                            "channel_size_recommendation":{s["channel"]:("large" if models[s["model_id"]].f3_hz<=crossover*.7 else "small") for s in mains},
                            "caveat":"Direct-field estimate; room phase and measured speaker response are not included."})
    # Refine each sub independently around the best common setting. This small
    # coordinate search emits receiver-ready relative controls per sub.
    setup=best[1]; crossover=float(setup["crossover_hz"]); hp,lp=lr4_responses(f,crossover)
    main=np.zeros((len(seats),len(f)),complex)
    for j,sp in enumerate(mains):
        model=models[sp["model_id"]]; response=10.**(np.asarray(model.response_db(f))/20.)
        for i in range(len(seats)):
            d=max(float(md[i,j]),.1); level=model.sensitivity_1w_1m_db+10*np.log10(model.effective_power_w)-20*np.log10(d)
            main[i]+=10.**(level/20.)*response*hp*np.exp(-2j*np.pi*f*(d-dref)/SPEED_OF_SOUND_M_S)
    sub_gain=np.full(len(subs),float(setup["sub_gain_trim_db"])); sub_delay=np.full(len(subs),float(setup["additional_sub_delay_ms"])/1000.)
    sub_pol=np.full(len(subs),1 if setup["sub_polarity"]=="normal" else -1,dtype=int)
    band=(f>=max(35.,crossover*.75))&(f<=min(160.,crossover*1.25))
    def evaluate_controls():
        total=main.copy()
        for j,sp in enumerate(subs):
            model=models[sp["model_id"]]; response=10.**(np.asarray(model.response_db(f))/20.)
            for i in range(len(seats)):
                d=max(float(sd[i,j]),.1); level=model.sensitivity_1w_1m_db+10*np.log10(model.effective_power_w)-20*np.log10(d)+sub_gain[j]
                total[i]+=sub_pol[j]*10.**(level/20.)*response*lp*np.exp(-2j*np.pi*f*((d-dref)/SPEED_OF_SOUND_M_S+sub_delay[j]))/len(subs)
        db=20*np.log10(np.maximum(np.abs(total),1e-15)); band_db=db[:,band]
        seat_level=np.mean(band_db,axis=1); spread=float(np.mean(np.std(band_db,axis=0)))
        edge=np.mean(band_db[:,[0,-1]],axis=1); dip=float(np.mean(np.maximum(0.,np.mean(edge)-seat_level)))
        return spread+dip,db,total,spread,dip
    for _ in range(2):
        for j in range(len(subs)):
            choices=[]
            local_gains=sorted(set([float(sub_gain[j]),max(gain_range_db[0],sub_gain[j]-3.),min(gain_range_db[1],sub_gain[j]+3.)]))
            local_delays=sorted(set([float(sub_delay[j]),max(delay_range_ms[0]/1000.,sub_delay[j]-.002),min(delay_range_ms[1]/1000.,sub_delay[j]+.002)]))
            old_gain,old_delay,old_pol=sub_gain[j],sub_delay[j],sub_pol[j]
            for g in local_gains:
                for delay in local_delays:
                    for polarity in (1,-1):
                        sub_gain[j],sub_delay[j],sub_pol[j]=g,delay,polarity
                        choices.append((evaluate_controls()[0],g,delay,polarity))
            _,sub_gain[j],sub_delay[j],sub_pol[j]=min(choices,key=lambda row:row[0])
            sub_gain[j],sub_delay[j],sub_pol[j]=float(sub_gain[j]),float(sub_delay[j]),int(sub_pol[j])
    objective,db,total,spread,dip=evaluate_controls()
    setup.update({"method":"coherent direct-field LR4 sweep plus per-sub coordinate refinement",
        "objective_db":objective,"seat_std_db":spread,"crossover_dip_db":dip,
        "sub_gain_trim_db":float(np.mean(sub_gain)),"additional_sub_delay_ms":float(np.mean(sub_delay)*1000.),
        "sub_polarity":"mixed" if len(set(sub_pol.tolist()))>1 else "normal" if sub_pol[0]==1 else "inverted",
        "sub_parameters":[{"channel":str(sp.get("channel","LFE{}".format(i+1))),"gain_trim_db":float(sub_gain[i]),
            "additional_delay_ms":float(sub_delay[i]*1000.),"polarity":"normal" if sub_pol[i]==1 else "inverted"} for i,sp in enumerate(subs)],
        "seat_response_db":db.tolist(),"seat_phase_deg":np.degrees(np.unwrap(np.angle(total),axis=1)).tolist()})
    return setup


def quarter_wave_notch_hz(distance_m: float, speed_m_s: float = SPEED_OF_SOUND_M_S) -> float:
    """First cancellation frequency for a direct path and equal inverted reflection."""
    if distance_m<=0 or speed_m_s<=0: raise ValueError("distance and sound speed must be positive")
    return float(speed_m_s/(4.*distance_m))


def screen_transmission_loss_db(frequency_hz, octave_loss_db):
    """Interpolate acoustic-screen insertion loss over log-frequency.

    ``octave_loss_db`` is a mapping of positive frequency in Hz to nonnegative
    transmission loss in dB. Empty mapping means no screen (0 dB loss).
    """
    f=np.asarray(frequency_hz,dtype=float); items=sorted((float(k),float(v)) for k,v in octave_loss_db.items())
    if not items:
        result=np.zeros_like(f); return float(result) if result.ndim==0 else result
    if any(x<=0 or y<0 or not np.isfinite(x+y) for x,y in items) or any(b[0]<=a[0] for a,b in zip(items,items[1:])):
        raise ValueError("screen loss requires increasing positive frequencies and nonnegative finite dB")
    result=np.interp(np.log10(np.maximum(f,items[0][0])),np.log10([x for x,_ in items]),[y for _,y in items])
    return float(result) if result.ndim==0 else result


def floor_mount_alternatives(speakers, room_polygon_m, seats, models, standard="itu", facing="north",
                             model_id="generic_floorstanding_tower", wall_clearance_m=None, grid_m=.2,
                             mlp_position_m=None):
    """Find a legal floor/stand alternative for each L/C/R channel.

    It keeps the wall solution and reports a separate floor candidate so users
    can compare mounting tradeoffs without mixing unlike optimizer score scales.
    """
    from .scoring import rectangular_room_frame
    from matplotlib.path import Path as PolygonPath
    table=load_standards()["standards"][standard]; model=models[model_id]
    if model.mount_type not in ("stand","floor_standing"):
        raise ValueError("--floor-model must use stand or floor_standing mount_type")
    if not {"front","surround"}.intersection(model.role_types):
        raise ValueError("floor alternative model must support front or surround roles")
    room=np.asarray(room_polygon_m,dtype=float); path=PolygonPath(room.T); origin,ux,uy,lx,ly=rectangular_room_frame(room)
    clearance=float(model.floor_wall_clearance_m if wall_clearance_m is None else wall_clearance_m)
    foot_x=float(model.width_m)/2.+clearance; foot_y=float(model.depth_m)/2.+clearance
    xvals=np.arange(foot_x,lx-foot_x+1e-9,grid_m); yvals=np.arange(foot_y,ly-foot_y+1e-9,grid_m)
    forward={"north":uy,"south":-uy,"east":ux,"west":-ux}[facing]; right=np.array([forward[1],-forward[0]])
    seat_points=[np.r_[np.asarray(s["position_m"],dtype=float)[:2],float(s["ear_height_m"])] for s in seats]
    mlp=np.asarray(seat_points[0] if mlp_position_m is None else mlp_position_m,dtype=float)
    out=[]
    for wall in speakers:
        channel=str(wall.get("channel",""))
        if channel not in ("L","C","R"): continue
        guideline=table.get(channel,{})
        target_az=float(guideline.get("azimuth_deg",0.)); alo,ahi=map(float,guideline.get("azimuth_range_deg",[-180.,180.]))
        best=None
        for x in xvals:
            for y in yvals:
                xy=origin+x*ux+y*uy
                if not path.contains_point(xy): continue
                pos=np.r_[xy,float(model.floor_source_height_m or model.height_m/2.)]
                target=mlp; aim=target-pos; aim/=max(float(np.linalg.norm(aim)),1e-12)
                horizontal=xy-mlp[:2]; az=float(np.degrees(np.arctan2(horizontal@right,horizontal@forward)))
                if not alo<=az<=ahi: continue
                covered=True; max_off=0.
                for seat in seat_points:
                    delta=seat-pos; dh=max(float(np.linalg.norm(delta[:2])),1e-12)
                    off_h=float(np.degrees(np.arccos(np.clip((aim[:2]/max(np.linalg.norm(aim[:2]),1e-12))@(delta[:2]/dh),-1.,1.))))
                    off_v=abs(float(np.degrees(np.arctan2(delta[2],dh))-np.degrees(np.arctan2(aim[2],np.linalg.norm(aim[:2])))))
                    max_off=max(max_off,off_h)
                    covered &= off_h<=model.coverage_h_deg/2. and off_v<=model.coverage_v_deg/2.
                if not covered: continue
                distances=[x-model.width_m/2.,lx-x-model.width_m/2.,y-model.depth_m/2.,ly-y-model.depth_m/2.]
                nearest=max(.01,min(distances))
                notch=quarter_wave_notch_hz(nearest)
                score=abs(az-target_az)+.02*max_off
                if best is None or score<best[0]:
                    best=(score,{"channel":channel,"model_id":model.model_id,"mount_type":model.mount_type,
                        "width_m":float(model.width_m),"height_m":float(model.height_m),"depth_m":float(model.depth_m),
                        "surface":"floor","position_m":pos.tolist(),"position_ft":(pos/.3048).tolist(),
                        "aim_direction":aim.tolist(),"yaw_deg":az-target_az,"distance_m":float(np.linalg.norm(pos-mlp)),
                        "azimuth_deg":az,"max_seat_off_axis_deg":max_off,"nearest_boundary_distance_m":nearest,
                        "first_boundary_notch_hz":notch,"wall_solution_position_m":wall["position_m"],
                        "comparison_note":"Floor alternative selected from standard-angle/coverage candidates; score units are not directly comparable to the wall optimizer."})
        if best:
            out.append(best[1])
        else:
            out.append({"channel":channel,"status":"no legal floor candidate","model_id":model.model_id,
                        "wall_solution_position_m":wall["position_m"]})
    return out


def first_reflection_guidance(room_polygon_m, source_xyz_m, listener_xyz_m, height_m,
                             source_level_db=85., wall_absorption=.2):
    """Return first-order wall/floor/ceiling points and suggested treatment panels."""
    from .room_acoustics import first_order_reflections
    rows=first_order_reflections(room_polygon_m,source_xyz_m,listener_xyz_m,height_m,wall_absorption)
    result=[]
    for row in rows:
        point=np.asarray(row["reflection_point_m"],dtype=float)
        result.append({**row,"reflection_point_ft":(point/.3048).tolist(),
            "source_level_db":float(source_level_db+row["level_relative_db"]),
            "panel":{"center_m":point.tolist(),"width_m":1.2,"height_m":1.2,"thickness_m":.05,
                     "type":"broadband absorber/diffuser guidance"}})
    return result


def compare_sub_strategies(room_polygon_m, seats_xy_m, facing="north", absorption=.2,
                          band_hz=(30.,120.), step_hz=1., q_scale=20., free_sources=None):
    """Compare common perimeter sub layouts with exact modal seat samples.

    Every topology is normalized to equal total electrical power. The delayed
    inverted front/rear midpoint case is only a two-source approximation to a
    real double-bass array, which uses arrays across both opposing walls.
    """
    from .scoring import modal_response,modal_score,rectangular_room_frame
    room=np.asarray(room_polygon_m,dtype=float); origin,ux,uy,lx,ly=rectangular_room_frame(room)
    forward={"north":uy,"south":-uy,"east":ux,"west":-ux}[facing]
    right=np.array([forward[1],-forward[0]])
    center=origin+.5*lx*ux+.5*ly*uy
    margin=.15
    forward_half=lx/2. if abs(float(forward@ux))>.5 else ly/2.
    right_half=ly/2. if abs(float(forward@ux))>.5 else lx/2.
    front=center+(forward_half-margin)*forward
    rear=center-(forward_half-margin)*forward
    left=center-(right_half-margin)*right
    right_mid=center+(right_half-margin)*right
    specs={
        "front midpoint":[front],
        "front corners":[front+(right_half-margin)*right,front-(right_half-margin)*right],
        "front + rear midpoints":[front,rear],
        "four wall midpoints":[front,rear,left,right_mid],
    }
    specs["delayed inverted rear array"]=[front,rear]
    if free_sources:
        specs["optimizer placement"]=[np.asarray(point,dtype=float)[:2] for point in free_sources]
    seats=np.asarray(seats_xy_m,dtype=float); output=[]
    for name,sources in specs.items():
        gains=np.full(len(sources),-10.*np.log10(max(len(sources),1)))
        if name=="delayed inverted rear array":
            freq,pf=modal_response(room,[front],seats,absorption,band_hz,step_hz,q_scale,source_gains_db=[-10.*np.log10(2.)])
            _,pr=modal_response(room,[rear],seats,absorption,band_hz,step_hz,q_scale,source_gains_db=[-10.*np.log10(2.)])
            delay=float(np.linalg.norm(front-rear)/SPEED_OF_SOUND_M_S)
            pressure=pf-pr*np.exp(-2j*np.pi*freq[None,:]*delay)
        else:
            freq,pressure=modal_response(room,sources,seats,absorption,band_hz,step_hz,q_scale,source_gains_db=gains)
        db=20.*np.log10(np.maximum(np.abs(pressure),1e-15)); mean_curve=np.mean(db,axis=0)
        stats=modal_score(freq,np.mean(pressure,axis=0))
        mean_level=float(np.mean(mean_curve)); mean_pressure=np.mean(db,axis=0)
        output.append({"strategy":name,"sub_count":len(sources),"positions_m":[p.tolist() for p in sources],
            "mean_level_db":mean_level,"seat_std_db":float(np.mean(np.std(db,axis=0))),
            "worst_null_db":float(np.min(db-mean_pressure[None,:])),"null_depth_db":float(np.min(db-mean_pressure[None,:])),
            "flatness_db":float(stats["flatness"]),"normalization":"equal total electrical power","source_gains_db":gains.tolist(),
            "frequencies_hz":freq.tolist(),"mean_response_db":mean_curve.tolist(),
            "seat_response_db":db.tolist()})
    reference=next((item["mean_level_db"] for item in output if item["strategy"]=="front midpoint"),0.)
    for item in output: item["cancellation_cost_db"]=float(item["mean_level_db"]-reference)
    return output


def seat_coverage_rows(speakers, seats, threshold_db=-3.):
    """Approximate seat inclusion at a configurable horizontal/vertical gain threshold."""
    rows=[]
    for speaker in speakers:
        source=np.asarray(speaker.get("acoustic_center_position_m",speaker["position_m"]),dtype=float)
        aim=np.asarray(speaker.get("aim_direction",[0.,1.,0.]),dtype=float); aim/=max(float(np.linalg.norm(aim)),1e-12)
        horizontal_axis=aim[:2]/max(float(np.linalg.norm(aim[:2])),1e-12)
        axis_elevation=float(np.degrees(np.arctan2(aim[2],np.linalg.norm(aim[:2]))))
        for seat in seats:
            target=np.r_[np.asarray(seat["position_m"],dtype=float),float(seat["ear_height_m"])]
            delta=target-source; horizontal=max(float(np.linalg.norm(delta[:2])),1e-12)
            target_az=np.degrees(np.arctan2(horizontal_axis[0]*delta[1]-horizontal_axis[1]*delta[0],horizontal_axis@delta[:2]))
            target_el=float(np.degrees(np.arctan2(delta[2],horizontal)))
            h=float(abs(target_az)); v=float(abs(target_el-axis_elevation))
            covered=h<=float(speaker.get("coverage_h_deg",360.))/2.*np.sqrt(abs(threshold_db)/6.)+1e-8 and v<=float(speaker.get("coverage_v_deg",180.))/2.*np.sqrt(abs(threshold_db)/6.)+1e-8
            rows.append({"channel":speaker["channel"],"row":seat["row"],"seat":seat["seat"],"horizontal_off_axis_deg":h,
                         "vertical_off_axis_deg":v,"covered":bool(covered)})
    return rows


def load_standards(path: str | Path | None = None) -> dict:
    """Load the documented, review-needed channel-angle guidance table."""
    import yaml
    file=Path(path) if path is not None else Path(__file__).with_name("standards.yaml")
    data=yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    if data.get("status")!="verify": raise ValueError("standards.yaml must remain explicitly marked verify")
    # THX installation ranges have not been independently encoded here; keep a
    # documented conservative seed and require the table's verify status.
    data["standards"].setdefault("thx",dict(data["standards"].get("dolby",{})))
    data["standards"].setdefault("custom",dict(data["standards"].get("itu",{})))
    return data


def label_legacy_channels(speakers, facing: str = "north") -> list[str]:
    """Map the legacy front/surround/bass aliases to conventional channel labels."""
    forward={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),
             "east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing]
    right=np.array([forward[1],-forward[0]])
    indexed=list(enumerate(speakers)); result=[""]*len(indexed)
    for i,speaker in indexed:
        if speaker.get("channel"): result[i]=str(speaker["channel"])
    center_group=[(i,s) for i,s in indexed if s.get("type")=="center"]
    for i,_ in center_group: result[i]="C"
    for role in ("front","surround","rear_surround","wide","bass"):
        if any(result[i] for i,s in indexed if s.get("type")==role): continue
        group=[(i,s) for i,s in indexed if s.get("type")==role]
        if role=="bass":
            for n,(i,_) in enumerate(group,1): result[i]="LFE" if len(group)==1 else "LFE{}".format(n)
            continue
        measured=[]
        for i,s in group:
            delta=np.asarray(s["position_m"],dtype=float)[:2]
            origin=np.asarray(s.get("listener_xy_m",[0.,0.]),dtype=float)
            vec=delta-origin
            az=float(np.degrees(np.arctan2(vec@right,vec@forward)))
            measured.append((az,i,s))
        if role=="front" and len(measured)==1:
            result[measured[0][1]]="C"
        elif role=="front":
            for n,(_,i,_) in enumerate(sorted(measured),1): result[i]="L" if n==1 else "R" if n==2 else "C{}".format(n)
        else:
            side=[row for row in measured if abs(row[0])<=125.]
            rear=[row for row in measured if abs(row[0])>125.]
            for label,group_rows in (("ss",side),("rs",rear)):
                for n,(_,i,_) in enumerate(sorted(group_rows),1): result[i]="L{}".format(label) if n==1 else "R{}".format(label) if n==2 else "{}{}".format(label,n)
            if role=="rear_surround":
                for n,(_,i,_) in enumerate(sorted(measured),1): result[i]="Lrs" if n==1 else "Rrs" if n==2 else "Rrs{}".format(n)
        if role=="wide":
            for n,(_,i,_) in enumerate(sorted(measured),1): result[i]="Lw" if n==1 else "Rw" if n==2 else "W{}".format(n)
    return result


def expand_layout(layout_name: str, standard: str = "itu", role_models: dict | None = None):
    """Expand a named channel preset into legacy optimizer groups and overhead channels."""
    data=load_standards(); channels=data["layouts"].get(layout_name)
    if channels is None: raise ValueError("unknown layout {!r}; choose {} or custom".format(layout_name,", ".join(data["layouts"])))
    guide=data["standards"].get(standard)
    if guide is None: raise ValueError("unknown speaker standard {!r}".format(standard))
    channels=list(channels); role_models=role_models or {}; groups=[]; overhead=[]; assignments={}
    mappings=(("front",("L","R")),("center",("C",)),("surround",("Lss","Rss")),
              ("rear_surround",("Lrs","Rrs")),("wide",("Lw","Rw")),("bass",("LFE","LFE2")))
    for role,pair in mappings:
        present=[name for name in pair if name in channels]
        if not present: continue
        if role in ("front","surround","rear_surround","wide","bass") and len(present)==2:
            token="{}:2".format(role)
        else:
            token="{}:1".format(role)
        model=role_models.get(role)
        if model: token += ":"+model
        groups.append(token); assignments[role]=present
    for name in channels:
        if name not in {item for _,pair in mappings for item in pair}:
            if name not in guide: raise ValueError("channel {} has no {} standard definition".format(name,standard))
            overhead.append(name)
    return groups,overhead,assignments


def channel_layout_specs(layout_name: str, standard: str = "itu", role_models: dict | None = None,
                         channel_models: dict | None = None, angle_overrides: dict | None = None):
    """Create one signed-angle optimizer spec per wall channel in a preset."""
    from dataclasses import replace
    from .speaker_types import DEFAULT_SPEAKER_TYPES
    data=load_standards(); channels=data["layouts"].get(layout_name)
    if channels is None: raise ValueError("unknown channel layout {!r}".format(layout_name))
    table=data["standards"].get(standard)
    if table is None: raise ValueError("unknown standard {!r}".format(standard))
    role_models=role_models or {}; channel_models=channel_models or {}; angle_overrides=angle_overrides or {}
    mapping={"L":"front","R":"front","C":"center","Lss":"surround","Rss":"surround",
             "Lrs":"rear_surround","Rrs":"rear_surround","Lw":"wide","Rw":"wide","LFE":"bass","LFE2":"bass"}
    layout=[]; overhead=[]
    for channel in channels:
        if channel=="LFE2": continue  # Represent 7.2.4 as one jointly optimized two-sub group.
        base_role=mapping.get(channel)
        if base_role is None:
            overhead.append(channel); continue
        base=DEFAULT_SPEAKER_TYPES[base_role]; guidance=table.get(channel,table.get("LFE"))
        surfaces=(['front','back','left','right'] if base_role=="bass" else
                  [wall for wall in guidance["surfaces"] if wall in ("front","back","left","right")])
        if not surfaces: overhead.append(channel); continue
        target=None if base_role=="bass" else abs(float(guidance["azimuth_deg"]))
        bounds=guidance["azimuth_range_deg"]
        signed_bounds=tuple(float(v) for v in bounds)
        if channel in angle_overrides:
            override=angle_overrides[channel]
            target=abs(float(override[0])); bounds=[float(override[1]),float(override[2])]
            signed_bounds=(float(override[1]),float(override[2]))
        tolerance=0. if target is None else max(abs(abs(float(bounds[0]))-target),abs(abs(float(bounds[1]))-target),.05)
        model_id=channel_models.get(channel,role_models.get(base_role,base.model_id))
        sub_count=channels.count("LFE")+channels.count("LFE2") if base_role=="bass" else 1
        layout.append(replace(base,count=sub_count,allowed_walls=tuple(surfaces),angle_target_deg=target,
                              angle_tol_deg=tolerance,symmetric=False,model_id=model_id,channel_name=channel,
                              elevation_range_deg=(tuple(float(v) for v in guidance["elevation_range_deg"])
                                  if base_role!="bass" and max(map(abs,guidance["elevation_range_deg"]))<90. else None),
                              azimuth_range_deg=signed_bounds))
    return layout,overhead


def place_overhead_channels(channels, room_polygon_m, room_height_m, listener_xy_m, ear_height_m,
                           standard="itu", facing="north", model=None, grid_m=.15,
                           joist_spacing_m=None, joist_thickness_m=.0381, forbidden_boxes=None):
    """Search legal ceiling grid positions nearest each channel's target azimuth/elevation."""
    from .speaker_models import resolve_model,predicted_spl_db
    table=load_standards()["standards"][standard]
    model=resolve_model("generic_in_ceiling") if model is None else model
    if model.mount_type not in ("in_ceiling","on_ceiling"):
        raise ValueError("overhead channels require an in_ceiling or on_ceiling speaker model")
    room=np.asarray(room_polygon_m,dtype=float); lo=room.min(axis=1); hi=room.max(axis=1)
    forward={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}
    out=[]
    forbidden_boxes=list(forbidden_boxes or [])
    if joist_spacing_m is not None:
        from .candidates import ceiling_bay_centers
        grid_points=ceiling_bay_centers(room,joist_spacing_m,joist_thickness_m,
                                       max(model.width_m,model.height_m),.15)
    else:
        grid_points=[np.array([x,y]) for x in np.arange(lo[0]+.35,hi[0]-.35+grid_m*.5,grid_m)
                     for y in np.arange(lo[1]+.35,hi[1]-.35+grid_m*.5,grid_m)]
    for channel in channels:
        spec=table[channel]; target_az=float(spec["azimuth_deg"]); target_el=float(spec["elevation_deg"])
        azlo,azhi=spec["azimuth_range_deg"]; ello,elhi=spec["elevation_range_deg"]
        points=[]; nearest=[]
        for xy in grid_points:
            half=float(np.hypot(model.width_m,model.depth_m)/2.)
            source=np.r_[xy,room_height_m]
            if any(np.all(np.abs(source-np.asarray(box["center_m"],dtype=float)) <=
                           np.array([half,half,model.height_m/2.])+np.asarray(box["dimensions_m"],dtype=float)/2.+float(box.get("clearance_m",0.)))
                   for box in forbidden_boxes): continue
            delta=xy-np.asarray(listener_xy_m); horizontal=float(np.linalg.norm(delta))
            if horizontal<.25: continue
            # Contain candidates inside non-rectangular polygon footprints too.
            from matplotlib.path import Path as PolygonPath
            if not PolygonPath(room.T).contains_point(xy): continue
            right=np.array([forward[facing][1],-forward[facing][0]])
            az=float(np.degrees(np.arctan2(delta@right,delta@forward[facing])))
            elevation=float(np.degrees(np.arctan2(room_height_m-ear_height_m,horizontal)))
            violation=max(azlo-az,0.,az-azhi)/max(azhi-azlo,1.)+max(ello-elevation,0.,elevation-elhi)/max(elhi-ello,1.)
            nearest.append((violation,az,elevation,xy))
            if azlo-.01<=az<=azhi+.01 and ello-.01<=elevation<=elhi+.01:
                penalty=((az-target_az)/max(azhi-azlo,1.))**2+((elevation-target_el)/max(elhi-ello,1.))**2
                points.append((penalty,xy,az,elevation))
        if not points:
            if nearest:
                _,near_az,near_el,near_xy=min(nearest,key=lambda row:row[0])
                detail="closest available grid point ({:.2f}, {:.2f}) m has azimuth {:+.1f}° and elevation {:.1f}°".format(*near_xy,near_az,near_el)
            else: detail="no unobstructed ceiling grid points remain inside the room"
            raise ValueError("{} has no legal ceiling point: allowed azimuth {:.1f}°..{:.1f}°, elevation {:.1f}°..{:.1f}°; room ceiling {:.2f} m, ear height {:.2f} m; {}. Enlarge/reshape the room, move the listener, change ceiling height or choose a layout without this channel".format(channel,azlo,azhi,ello,elhi,room_height_m,ear_height_m,detail))
        _,xy,az,elevation=min(points,key=lambda row:row[0])
        point=np.r_[xy,float(room_height_m)]; listener=np.r_[np.asarray(listener_xy_m),float(ear_height_m)]
        aim=listener-point; distance=float(np.linalg.norm(aim)); aim=aim/max(distance,1e-12)
        acoustic_center=point+np.array([aim[0]*model.acoustic_center_offset_m[1],aim[1]*model.acoustic_center_offset_m[1],model.acoustic_center_offset_m[0]])
        out.append({"type":"height","channel":channel,"model_id":model.model_id,"mount_type":model.mount_type,
            "surface":"ceiling","position_m":point.tolist(),"position_ft":(point/.3048).tolist(),
            "box_center_m":point.tolist(),"acoustic_center_position_m":acoustic_center.tolist(),
            "acoustic_center_offset_m":list(model.acoustic_center_offset_m),
            "optimizer_position_xy_m":xy.tolist(),"wall_index":-1,"wall_t":0.,"wall_u_m":None,
            "aim_direction":aim.tolist(),"aim_xy":aim[:2].tolist(),"normal":aim[:2].tolist(),
            "yaw_deg":0.,"pitch_deg":float(np.degrees(np.arctan2(aim[2],np.linalg.norm(aim[:2])))),
            "width_m":float(model.width_m),"height_m":float(model.height_m),"depth_m":float(model.depth_m),
            "visible_depth_m":float(model.depth_m),"coverage_h_deg":float(model.coverage_h_deg),
            "coverage_v_deg":float(model.coverage_v_deg),"height_m":float(room_height_m),
            "allowed_height_range_m":[float(room_height_m),float(room_height_m)],
            "distance_m":distance,"predicted_spl_db":predicted_spl_db(model,distance),"headroom_db":0.,
            "receiver_delay_ms":0.,"receiver_trim_db":0.,"warnings":[],
            "azimuth_deg":az,"elevation_deg":elevation,
            "ceiling_candidates":[{"x_m":float(point[0]),"y_m":float(point[1]),"score":float(-penalty)} for penalty,point,_,_ in points]})
    return out


def seating_grid(spec: str | None, mlp: str | None, center_xy_m, facing="north", ear_height_m=1.097):
    """Build a centered rows-by-seats grid; row and seat selectors are one-based."""
    options={"rows":1,"seats":1,"seat_spacing":.7,"row_spacing":1.1,"riser":0.,"ear_height":ear_height_m}
    if spec:
        for token in spec.split(","):
            try:
                key,value=token.split("=",1)
                if key not in options: raise ValueError
                options[key]=int(value) if key in ("rows","seats") else float(value)
            except ValueError as exc: raise ValueError("--seats uses rows=R,seats=S,seat_spacing=0.7,row_spacing=1.1,riser=0.2,ear_height=1.1") from exc
    rows,seats=int(options["rows"]),int(options["seats"])
    if rows<1 or seats<1 or min(options["seat_spacing"],options["row_spacing"],options["ear_height"])<=0 or options["riser"]<0:
        raise ValueError("seat counts/spacing/ear height must be positive and riser nonnegative")
    selector={"row":(rows+1)//2,"seat":(seats+1)//2}
    if mlp:
        try:
            for token in mlp.split(","):
                key,value=token.split("=",1); selector[key]=int(value)
            if set(selector)!={"row","seat"}: raise ValueError
        except ValueError as exc: raise ValueError("--mlp uses row=r,seat=s with one-based indices") from exc
    if not 1<=selector["row"]<=rows or not 1<=selector["seat"]<=seats: raise ValueError("MLP row/seat is outside the seating grid")
    fwd={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing]
    right=np.array([fwd[1],-fwd[0]]); center=np.asarray(center_xy_m,dtype=float)
    points=[]
    for row in range(rows):
        row_offset=(row-(rows-1)/2.)*float(options["row_spacing"])
        for seat in range(seats):
            seat_offset=(seat-(seats-1)/2.)*float(options["seat_spacing"])
            xy=center+seat_offset*right-row_offset*fwd
            points.append({"row":row+1,"seat":seat+1,"position_m":[float(x) for x in xy],
                           "ear_height_m":float(options["ear_height"]+row*options["riser"])})
    mlp_row=next(row for row in points if row["row"]==selector["row"] and row["seat"]==selector["seat"])
    return points,np.asarray(mlp_row["position_m"]),float(mlp_row["ear_height_m"])


def compliance_rows(speakers, listener_xyz, facing="north", standard="itu", reference="d_ref", angle_overrides=None):
    """Compute geometry-derived azimuth/elevation compliance for legacy roles."""
    table=load_standards(); definitions=table["standards"].get(standard)
    if definitions is None: raise ValueError("unknown speaker standard {!r}".format(standard))
    listener=np.asarray(listener_xyz,dtype=float)
    named=[]
    for source in speakers:
        item=dict(source); item["listener_xy_m"]=listener[:2]; named.append(item)
    labels=label_legacy_channels(named,facing)
    forward={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),
             "east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing]
    right=np.array([forward[1],-forward[0]]); rows=[]
    for source,label in zip(speakers,labels):
        position=np.asarray(source.get("acoustic_center_position_m",source["position_m"]),dtype=float)
        if position.shape==(2,): position=np.r_[position,float(source.get("height_m",listener[2]))]
        delta=position-listener; horizontal=float(np.linalg.norm(delta[:2])); distance=float(np.linalg.norm(delta))
        if label.startswith("LFE"):
            rows.append({"channel":label,"azimuth_deg":"N/A","azimuth_allowed":"N/A","elevation_deg":"N/A",
                         "elevation_allowed":"N/A","distance_m":distance,"status":"N/A","provenance":"not applicable","note":"LFE is not an azimuth/elevation channel"})
            continue
        az=float(np.degrees(np.arctan2(delta[:2]@right,delta[:2]@forward)))
        elevation=float(np.degrees(np.arctan2(delta[2],max(horizontal,1e-12))))
        spec=definitions.get(label,definitions.get("LFE") if label.startswith("LFE") else None)
        if spec is None:
            rows.append({"channel":label,"azimuth_deg":az,"azimuth_allowed":"n/a","elevation_deg":elevation,"elevation_allowed":"n/a","distance_m":distance,"status":"WARN","note":"channel absent from selected standard table"}); continue
        alo,ahi=spec["azimuth_range_deg"]; elo,ehi=spec["elevation_range_deg"]
        if angle_overrides and label in angle_overrides:
            _,alo,ahi=angle_overrides[label]
        # LFE has intentionally unrestricted positional guidance.
        passed=alo-1e-8<=az<=ahi+1e-8 and elo-1e-8<=elevation<=ehi+1e-8
        source_status=("cited: ITU-R BS.775-3 (verify bounds)" if standard=="itu" and label in ("L","C","R","Lss","Rss") else
                       "cited: Dolby 7.1.4 guide (verify bounds)" if standard=="dolby" and label in ("Ltf","Rtf","Ltm","Rtm","Ltr","Rtr") else "provisional")
        rows.append({"channel":label,"azimuth_deg":az,"azimuth_allowed":"{:+.0f}..{:+.0f}°".format(alo,ahi),
                     "elevation_deg":elevation,"elevation_allowed":"{:+.0f}..{:+.0f}°".format(elo,ehi),
                     "distance_m":distance,"status":"PASS" if passed else "WARN","provenance":source_status})
    return rows


def per_seat_compliance_rows(speakers, seats, facing="north", standard="itu"):
    """Return channel angle checks at every seat and the worst seat per channel."""
    table=load_standards()["standards"][standard]
    forward={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing]
    right=np.array([forward[1],-forward[0]]); rows=[]
    for source in speakers:
        channel=str(source.get("channel","")); point=np.asarray(source.get("acoustic_center_position_m",source["position_m"]),dtype=float)
        if point.shape== (2,): point=np.r_[point,float(source.get("height_m",0.))]
        spec=table.get(channel,table.get("LFE") if channel.startswith("LFE") else None)
        for seat in seats:
            target=np.r_[np.asarray(seat["position_m"],dtype=float),float(seat["ear_height_m"])]
            delta=point-target; horizontal=float(np.linalg.norm(delta[:2])); distance=float(np.linalg.norm(delta))
            if channel.startswith("LFE"):
                rows.append({"channel":channel,"row":seat["row"],"seat":seat["seat"],"azimuth_deg":"N/A","elevation_deg":"N/A","status":"N/A"}); continue
            az=float(np.degrees(np.arctan2(delta[:2]@right,delta[:2]@forward)))
            el=float(np.degrees(np.arctan2(delta[2],max(horizontal,1e-12))))
            bounds=spec or {}; alo,ahi=bounds.get("azimuth_range_deg",[-180.,180.]); elo,ehi=bounds.get("elevation_range_deg",[-90.,90.])
            rows.append({"channel":channel,"row":seat["row"],"seat":seat["seat"],"azimuth_deg":az,"elevation_deg":el,
                         "distance_m":distance,"azimuth_violation_deg":max(alo-az,0.,az-ahi),
                         "elevation_violation_deg":max(elo-el,0.,el-ehi),
                         "status":"PASS" if alo<=az<=ahi and elo<=el<=ehi else "WARN"})
    return rows
