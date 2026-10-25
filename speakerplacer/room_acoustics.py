"""Frequency-band room estimates using simple, explicit diffuse-field formulas.

Material values are typical estimates only; measure a room or use manufacturer
data before relying on absolute RT60 or SPL predictions.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log, log10, pi, sqrt
import numpy as np
from scipy.signal import butter, sosfiltfilt

BANDS_HZ=(125.,250.,500.,1000.,2000.,4000.)
MATERIALS={
    "drywall":(.29,.10,.05,.04,.07,.09),
    "glass":(.18,.12,.06,.04,.03,.02),
    "concrete":(.01,.01,.02,.02,.02,.03),
    "carpet":(.02,.06,.14,.37,.60,.65),
    "curtain":(.07,.31,.49,.75,.70,.60),
    "tile":(.20,.10,.06,.04,.04,.05),
    "acoustic_tile":(.30,.55,.75,.80,.75,.70),
    # Typical broad-band estimates; use measured coefficients for real products.
    "drapes":(.07,.31,.49,.75,.70,.60),
    "acoustic_panels":(.20,.55,.85,.95,.95,.90),
    "bass_traps":(.15,.35,.65,.85,.90,.90),
}

TREATMENT_PRESETS={
    "untreated":{"walls":"drywall","floor":"tile","ceiling":"drywall"},
    "carpeted":{"walls":"drywall","floor":"carpet","ceiling":"drywall"},
    "draped":{"walls":"drapes","floor":"carpet","ceiling":"drywall"},
    "treated_theater":{"walls":"acoustic_panels","floor":"carpet","ceiling":"acoustic_tile"},
    "bass_trapped":{"walls":"bass_traps","floor":"carpet","ceiling":"acoustic_tile"},
}


@dataclass(frozen=True)
class MaterialSet:
    walls: str="drywall"
    floor: str="carpet"
    ceiling: str="drywall"

    def __post_init__(self):
        for name in (self.walls,self.floor,self.ceiling):
            if name not in MATERIALS:
                raise ValueError("unknown room material {!r}; choose {}".format(name,", ".join(sorted(MATERIALS))))

    def coefficients(self) -> dict[str,np.ndarray]:
        return {surface:np.asarray(MATERIALS[name],dtype=float) for surface,name in
                (("walls",self.walls),("floor",self.floor),("ceiling",self.ceiling))}


def parse_materials(value: str | None, preset: str | None=None) -> MaterialSet:
    """Parse e.g. ``walls=drywall,floor=carpet,ceiling=tile``."""
    if preset is not None and preset not in TREATMENT_PRESETS:
        raise ValueError("unknown treatment preset {!r}; choose {}".format(preset,", ".join(TREATMENT_PRESETS)))
    data=dict(TREATMENT_PRESETS.get(preset,{"walls":"drywall","floor":"carpet","ceiling":"drywall"}))
    if not value: return MaterialSet(**data)
    for item in value.split(","):
        try: surface,material=item.split("=",1)
        except ValueError as exc: raise ValueError("materials must use surface=material pairs") from exc
        if surface not in data: raise ValueError("material surface must be walls, floor, or ceiling")
        data[surface]=material
    return MaterialSet(**data)


def room_surface_areas(room_polygon_m: np.ndarray, height_m: float) -> dict[str,float]:
    """Surface areas for a polygonal vertical-walled room."""
    room=np.asarray(room_polygon_m,dtype=float)
    if room.ndim!=2 or room.shape[0]!=2 or room.shape[1]<3 or height_m<=0: raise ValueError("room acoustics require a polygon and positive height")
    area=.5*abs(float(np.sum(room[0]*np.roll(room[1],-1)-room[1]*np.roll(room[0],-1))))
    perimeter=float(sum(np.linalg.norm(room[:,(i+1)%room.shape[1]]-room[:,i]) for i in range(room.shape[1])))
    return {"walls":perimeter*height_m,"floor":area,"ceiling":area}


def room_metrics(room_polygon_m: np.ndarray, height_m: float, materials: MaterialSet=MaterialSet(),
                 directivity_q: float=1.) -> dict[str,np.ndarray | float]:
    """Sabine/Eyring RT60, room constant, critical distance, and Schroeder Hz."""
    areas=room_surface_areas(room_polygon_m,height_m); total=float(sum(areas.values()))
    room=np.asarray(room_polygon_m,dtype=float)
    volume=float(areas["floor"]*height_m)
    coeffs=materials.coefficients()
    absorption=sum(area*coeffs[surface] for surface,area in areas.items())/total
    alpha=np.clip(absorption,1e-6,.999999)
    sabine=.161*volume/(total*alpha)
    eyring=.161*volume/(-total*np.log1p(-alpha))
    constant=total*alpha/(1.-alpha)
    critical=.057*np.sqrt(max(directivity_q,1e-9)*volume/np.maximum(sabine,1e-9))
    schroeder=2000.*np.sqrt(sabine/volume)
    return {"bands_hz":np.asarray(BANDS_HZ),"mean_absorption":alpha,"sabine_rt60_s":sabine,
            "eyring_rt60_s":eyring,"room_constant_m2":constant,"critical_distance_m":critical,
            "schroeder_hz":schroeder,"volume_m3":volume,"surface_area_m2":total,
            "surface_areas_m2":areas,"surface_absorption_coefficients":coeffs}


def directivity_q(model, off_axis_deg: float=0.) -> float:
    """Approximate directivity factor from the model's nominal coverage cone."""
    h=np.radians(min(float(model.coverage_h_deg),360.)); v=np.radians(min(float(model.coverage_v_deg),180.))
    q=4.*pi/max(h*v,1e-6)
    # The coincident mounting-wall image doubles pressure (up to +6 dB power
    # level); wall_gain_db is therefore never added separately.
    directivity=max(1.,q*10.**(model.gain_db(off_axis_deg)/10.))
    return float(np.clip(4.*directivity,4.,128.))


def boundary_gain_for_mount(mount_type: str, placement_mode: str="wall") -> float:
    """Ideal low-frequency boundary-image estimate for a mounted placement."""
    mode=str(placement_mode)
    image_gain=20.*log10(2.)
    if mode=="corner": return 3.*image_gain
    if mode in ("floor","ceiling"): return image_gain
    if mount_type in ("on_wall","in_wall","flush","on_ceiling","in_ceiling"): return image_gain
    return 0.


def level_components(model, distance_m: float, power_w: float, metrics: dict, band_index: int,
                     off_axis_deg: float=0., boundary_gain_db: float | None=None) -> dict[str,float]:
    """Direct + reverberant SPL using sensitivity normalized to 1 W at 1 m."""
    r=max(float(distance_m),1e-6); q=directivity_q(model,off_axis_deg)
    absorption=float(metrics["mean_absorption"][band_index]); room_constant=float(metrics["room_constant_m2"][band_index])
    lw=model.sensitivity_1w_1m_db+10.*log10(max(float(power_w),1e-9))+10.*log10(4.*pi)
    # Sensitivity is already on-axis SPL at 1 m; multiplying the direct ray by
    # the directivity factor again double-counts DI. The first-order coincident
    # wall image doubles pressure (+6 dB power) for wall/flush mounts. Apply
    # the model's polar only as an off-axis correction.
    boundary_gain=boundary_gain_for_mount(model.mount_type) if boundary_gain_db is None else float(boundary_gain_db)
    boundary_power=10.**(boundary_gain/10.)
    direct_power=boundary_power/(4.*pi*r*r)*10.**(float(model.gain_db(off_axis_deg))/10.)
    reverberant_power=4./max(room_constant,1e-9)
    direct=lw+10.*log10(max(direct_power,1e-15))
    reverberant=lw+10.*log10(max(reverberant_power,1e-15))
    total=lw+10.*log10(max(direct_power+reverberant_power,1e-15))
    rt=float(metrics["eyring_rt60_s"][band_index])
    critical=.057*sqrt(max(q*float(metrics["volume_m3"])/max(rt,1e-9),0.))
    return {"direct_spl_db":direct,"reverberant_spl_db":reverberant,"total_spl_db":total,
            "boundary_gain_db":boundary_gain,
            "critical_distance_m":critical,"directivity_q":q,"warn_beyond_critical":r>critical}


def band_rir_metrics(rir: np.ndarray, fs: int, direct_index: int=0) -> list[dict[str,float]]:
    """Measure C50, C80, D50 and Schroeder RT60 for octave-band-filtered RIRs."""
    h=np.asarray(rir,dtype=float)
    if len(h)<32: raise ValueError("RIR is too short for octave-band metrics")
    rows=[]; arrival=max(0,int(direct_index))
    for center in BANDS_HZ:
        low=center/np.sqrt(2.); high=min(center*np.sqrt(2.),fs*.49)
        sos=butter(4,[low,high],btype="bandpass",fs=fs,output="sos")
        filtered=sosfiltfilt(sos,h); energy=filtered**2; total=float(energy.sum())+1e-15
        row={"frequency_hz":center}
        for window,label in ((.050,"c50_db"),(.080,"c80_db")):
            split=min(len(h),arrival+int(window*fs)); early=float(energy[arrival:split].sum())+1e-15
            late=float(energy[split:].sum())+1e-15; row[label]=10.*log10(early/late)
        split=min(len(h),arrival+int(.050*fs)); row["d50"]=(float(energy[arrival:split].sum())+1e-15)/total
        decay=np.cumsum(energy[::-1])[::-1]; decay_db=10.*np.log10(np.maximum(decay/total,1e-15))
        times=np.arange(len(h))/float(fs); mask=(decay_db<=-5.)&(decay_db>=-35.)
        if np.count_nonzero(mask)>=8:
            slope=np.polyfit(times[mask],decay_db[mask],1)[0]; rt60=-60./slope if slope<0 else float("nan")
        else: rt60=float("nan")
        row["rt60_measured_s"]=float(rt60); rows.append(row)
    return rows


def first_order_reflections(room_polygon_m, source_xyz, listener_xyz, height_m, wall_absorption=.2, c=343.):
    """Estimate first-order image paths and levels relative to the direct path."""
    room=np.asarray(room_polygon_m,dtype=float); source=np.asarray(source_xyz,dtype=float); listener=np.asarray(listener_xyz,dtype=float)
    direct=float(np.linalg.norm(source-listener)); rows=[]; cross=lambda a,b:float(a[0]*b[1]-a[1]*b[0])
    for index in range(room.shape[1]):
        a=room[:,index]; edge=room[:,(index+1)%room.shape[1]]-a; length=float(np.linalg.norm(edge))
        normal=np.array([edge[1],-edge[0]])/length; image_xy=source[:2]-2.*float((source[:2]-a)@normal)*normal
        ray=listener[:2]-image_xy; den=cross(ray,edge)
        if abs(den)<1e-12: continue
        t=cross(a-image_xy,edge)/den; u=cross(a-image_xy,ray)/den
        if not (1e-7<t<1.-1e-7 and -1e-7<=u<=1.+1e-7): continue
        image=np.r_[image_xy,source[2]]; path=float(np.linalg.norm(image-listener))
        hit_z=source[2]+t*(listener[2]-source[2])
        if not 0.<=hit_z<=height_m: continue
        amplitude=np.sqrt(max(0.,1.-wall_absorption))*direct/max(path,1e-9)
        hit_xy=image_xy+t*ray
        rows.append({"surface":"wall {}".format(index),"reflection_point_m":[float(hit_xy[0]),float(hit_xy[1]),float(hit_z)],
                     "time_ms":1000.*path/c,"level_relative_db":20.*log10(max(amplitude,1e-12)),"path_length_m":path})
    for surface,mirror_z,alpha in (("floor",-source[2],.15),("ceiling",2.*height_m-source[2],.15)):
        image=np.array([source[0],source[1],mirror_z]); path=float(np.linalg.norm(image-listener))
        amplitude=np.sqrt(1.-alpha)*direct/max(path,1e-9)
        point_z=0. if surface=="floor" else height_m
        fraction=(point_z-image[2])/(listener[2]-image[2])
        point=image+fraction*(listener-image)
        rows.append({"surface":surface,"reflection_point_m":[float(point[0]),float(point[1]),float(point_z)],"time_ms":1000.*path/c,
                     "level_relative_db":20.*log10(max(amplitude,1e-12)),"path_length_m":path})
    return sorted(rows,key=lambda row:row["time_ms"])
