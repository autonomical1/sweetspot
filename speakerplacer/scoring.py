"""Acoustic and stereo geometry score terms, each expressed in dB-like units."""
from dataclasses import dataclass, asdict
from functools import lru_cache
import numpy as np
from scipy.signal import butter, sosfiltfilt
@dataclass
class ScoreWeights:
    clarity: float=1.0
    off_axis: float=1.0
    early_reflection: float=1.0
    geometry: float=2.0
    def to_dict(self): return asdict(self)

def direct_arrival(rir,fs):
    h=np.abs(np.asarray(rir)); peak=float(h.max()) if len(h) else 0
    indices=np.flatnonzero(h>=peak*.5)
    return int(indices[0]) if len(indices) else int(np.argmax(h))

def clarity_score(rir,fs,direct_index=None,window_ms=50.):
    h=np.asarray(rir,dtype=float); i=direct_arrival(h,fs) if direct_index is None else direct_index
    j=min(len(h),i+max(1,int(window_ms*fs/1000))); e1=float(h[i:j]@h[i:j]); e2=float(h[j:]@h[j:])
    return float(10*np.log10(max(e1,1e-15)/max(e2,1e-15)))

def band_clarity_score(rir,fs,frequency_band_hz,direct_index=None,window_ms=50.):
    """C50-style score after zero-phase filtering to a speaker's useful band."""
    low,high=frequency_band_hz
    if high >= fs/2: raise ValueError("frequency band upper limit must be below Nyquist")
    sos=butter(4,[low,high],btype="bandpass",fs=fs,output="sos")
    h=np.asarray(rir,dtype=float)
    filtered=sosfiltfilt(sos,h) if len(h)>32 else h
    return clarity_score(filtered,fs,direct_index,window_ms)

def off_axis_score(normal,source,listener,reference_deg=30.):
    n=np.asarray(normal); v=np.asarray(listener)-np.asarray(source); d=np.linalg.norm(n)*np.linalg.norm(v)
    if d==0:return -1e6
    angle=np.degrees(np.arccos(np.clip(n@v/d,-1,1))); return float(-(angle/reference_deg)**2)

def early_reflection_score(rir,fs,direct_index=None,window_ms=5.):
    h=np.asarray(rir,dtype=float); i=direct_arrival(h,fs) if direct_index is None else direct_index
    j=min(len(h),i+max(1,int(window_ms*fs/1000))); reflected=float(h[i+1:j]@h[i+1:j]); direct=float(h[i]**2)
    return float(-10*np.log10(1+reflected/max(direct,1e-15)))

def angle_to_facing(source,listener,facing):
    v=np.asarray(source)-np.asarray(listener); axis={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing]
    return float(np.degrees(np.arctan2(v[0]*axis[1]-v[1]*axis[0],axis@v)))

def score_terms(rir,fs,normal,source,listener):
    i=direct_arrival(rir,fs)
    return {"clarity_db":clarity_score(rir,fs,i),"off_axis_db":off_axis_score(normal,source,listener),"early_reflection_db":early_reflection_score(rir,fs,i)}


def rectangular_room_frame(room_polygon):
    """Return room axes; irregular convex rooms use a bounding-box acoustic proxy."""
    from .room import validate_polygon
    p=validate_polygon(room_polygon)
    if p.shape[1]==4:
        origin=p[:,0]; e1=p[:,1]-origin; e2=p[:,3]-origin
        lx=float(np.linalg.norm(e1)); ly=float(np.linalg.norm(e2))
        if lx>0 and ly>0:
            ux=e1/lx; uy=e2/ly
            if abs(float(ux@uy))<=1e-6 and np.allclose(p[:,2],origin+e1+e2,atol=1e-6):
                return origin,ux,uy,lx,ly
    lo=p.min(axis=1); hi=p.max(axis=1); lx=float(hi[0]-lo[0]); ly=float(hi[1]-lo[1])
    if lx<=0 or ly<=0: raise ValueError("room must have nonzero width and length")
    return lo,np.array([1.,0.]),np.array([0.,1.]),lx,ly


def room_modes(room_polygon, band_hz=(30.,200.), c=343.):
    """Enumerate rectangular-room modes f_nm = c/2 sqrt((n/Lx)^2+(m/Ly)^2)."""
    _,_,_,lx,ly=rectangular_room_frame(room_polygon)
    high=float(band_hz[1]); modes=[]
    nmax=int(np.ceil(2*high*lx/c)); mmax=int(np.ceil(2*high*ly/c))
    for n in range(nmax+1):
        for m in range(mmax+1):
            if n==0 and m==0: continue
            freq=(c/2.)*np.sqrt((n/lx)**2+(m/ly)**2)
            if band_hz[0] <= freq <= high: modes.append((float(freq),n,m))
    return sorted(modes)


def room_modes_3d(room_polygon, height_m, band_hz=(20.,250.), c=343., coincidence_hz=1., coincidence_fraction=.02):
    """Enumerate shoebox (n,m,l) modes and flag near-coincident frequencies."""
    _,_,_,lx,ly=rectangular_room_frame(room_polygon)
    if height_m<=0 or c<=0: raise ValueError("height and sound speed must be positive")
    high=float(band_hz[1]); modes=[]
    limits=(int(np.ceil(2*high*lx/c)),int(np.ceil(2*high*ly/c)),int(np.ceil(2*high*height_m/c)))
    for n in range(limits[0]+1):
        for m in range(limits[1]+1):
            for l in range(limits[2]+1):
                if n==m==l==0: continue
                frequency=float(c/2.*np.sqrt((n/lx)**2+(m/ly)**2+(l/height_m)**2))
                if band_hz[0]<=frequency<=high:
                    mode_type="axial" if sum(value>0 for value in (n,m,l))==1 else "tangential" if sum(value>0 for value in (n,m,l))==2 else "oblique"
                    modes.append({"n":n,"m":m,"l":l,"frequency_hz":frequency,"type":mode_type,"near_coincident":False,"coincident_with":[]})
    modes.sort(key=lambda item:item["frequency_hz"])
    for i,row in enumerate(modes):
        matches=[]
        for j,other in enumerate(modes):
            if i==j: continue
            delta=abs(row["frequency_hz"]-other["frequency_hz"])
            if delta<=max(float(coincidence_hz),float(coincidence_fraction)*row["frequency_hz"]):
                matches.append({"n":other["n"],"m":other["m"],"l":other["l"],"frequency_hz":other["frequency_hz"]})
        row["near_coincident"]=bool(matches); row["coincident_with"]=matches
    return modes


def bonello_mode_counts(modes, band_hz=(20.,250.)):
    """Count 3D modes in contiguous 1/3-octave bands for Bonello screening."""
    low,high=map(float,band_hz)
    if low<=0 or high<=low: raise ValueError("band_hz must be positive and increasing")
    ratio=2.**(1./3.); centers=[]; center=low*ratio**.5
    while center/ratio**.5<high:
        centers.append(center); center*=ratio
    half=ratio**.5
    rows=[]
    for center in centers:
        count=sum(1 for mode in modes if center/half<=mode["frequency_hz"]<center*half)
        rows.append({"center_hz":center,"mode_count":count})
    nonempty=[row["mode_count"] for row in rows if row["mode_count"]>0]
    return rows,all(b>=a for a,b in zip(nonempty,nonempty[1:]))


def modal_step_for_damping(room_polygon, absorption, q_scale=20., requested_step_hz=1., band_hz=(30.,200.), floor_hz=.25):
    """Choose at most half the narrowest modal half-bandwidth, with 0.25 Hz floor.

    With Q=q_scale/sqrt(absorption), the resonance half-width is approximated
    by f/(2Q); resolving half of that gives step=f/(4Q). The explicit floor
    avoids excessive work for unrealistically narrow modes in this simple model.
    """
    q=float(q_scale)/np.sqrt(max(float(absorption),.01))
    frequencies=[f for f,_,_ in room_modes(room_polygon,band_hz)]
    if not frequencies: return max(float(floor_hz),float(requested_step_hz))
    damping_limit=min(frequencies)/(4.*q)
    automatic=max(float(floor_hz),damping_limit)
    return max(float(floor_hz),min(float(requested_step_hz),automatic))


def modal_response(room_polygon, sources, listener, absorption=.2, band_hz=(30.,200.), step_hz=1., q_scale=20., c=343., source_gains_db=None, surface_absorption=None):
    """Complex coherent modal pressure versus frequency for same-signal sources.

    Q = q_scale / sqrt(absorption) is a configurable approximate damping map.
    """
    if step_hz<=0 or absorption<0: raise ValueError("step_hz must be positive and absorption nonnegative")
    listener_array=np.asarray(listener,dtype=float); was_single=listener_array.ndim==1
    if was_single: listener_array=listener_array[None,:]
    room_array=np.asarray(room_polygon,dtype=float)
    wall_alpha=np.full(4,float(absorption)) if surface_absorption is None else np.asarray(surface_absorption,dtype=float)
    if wall_alpha.shape!=(4,) or np.any((wall_alpha<0)|(wall_alpha>1)): raise ValueError("surface_absorption must contain four wall coefficients in [0,1]")
    origin,ux,uy,lx,ly,frequencies,basis=_modal_basis(
        room_array.shape,room_array.tobytes(),listener_array.shape,listener_array.tobytes(),
        float(absorption),tuple(band_hz),float(step_hz),float(q_scale),float(c),
        tuple(float(value) for value in wall_alpha),surface_absorption is not None)
    def local(point):
        delta=np.asarray(point,dtype=float)-origin
        return float(delta@ux),float(delta@uy)
    source_points=[local(source) for source in sources]
    gains=np.ones(len(source_points)) if source_gains_db is None else 10.**(np.asarray(source_gains_db,dtype=float)/20.)
    pressure=np.zeros((len(listener_array),len(frequencies)),dtype=complex)
    for n,m,psi_l,denominator in basis:
        psi_s=sum(gain*np.cos(n*np.pi*x/lx)*np.cos(m*np.pi*y/ly) for (x,y),gain in zip(source_points,gains))
        numerator=psi_l[:,None]*psi_s
        pressure += numerator/denominator
    return frequencies.copy(),(pressure[0] if was_single else pressure)


@lru_cache(maxsize=128)
def _modal_basis(room_shape, room_bytes, listener_shape, listener_bytes, absorption,
                 band_hz, step_hz, q_scale, c, wall_alpha_values, has_surface_absorption):
    """Reuse room modes, seat shapes, and frequency denominators across candidates."""
    room=np.frombuffer(room_bytes,dtype=float).reshape(room_shape)
    listener_array=np.frombuffer(listener_bytes,dtype=float).reshape(listener_shape)
    origin,ux,uy,lx,ly=rectangular_room_frame(room)
    listener_points=np.asarray([(float((point-origin)@ux),float((point-origin)@uy)) for point in listener_array])
    modes=room_modes(room,band_hz,c)
    frequencies=np.arange(float(band_hz[0]),float(band_hz[1])+step_hz*.5,step_hz)
    q=q_scale/np.sqrt(max(float(absorption),.01))
    wall_alpha=np.asarray(wall_alpha_values,dtype=float)
    alpha_x=float(np.mean(wall_alpha[[1,3]])); alpha_y=float(np.mean(wall_alpha[[0,2]]))
    basis=[]
    for f_nm,n,m in modes:
        psi_l=np.cos(n*np.pi*listener_points[:,0]/lx)*np.cos(m*np.pi*listener_points[:,1]/ly)
        weights=[]; participating=[]
        if n: weights.append((n/lx)**2); participating.append((n/lx)**2*alpha_x)
        if m: weights.append((m/ly)**2); participating.append((m/ly)**2*alpha_y)
        alpha_mode=(sum(participating)/sum(weights)) if participating else absorption
        mode_q=q_scale/np.sqrt(max(float(alpha_mode),.01)) if has_surface_absorption else q
        denominator=f_nm**2-frequencies[None,:]**2+1j*frequencies[None,:]*f_nm/mode_q
        basis.append((n,m,psi_l,denominator))
    return origin,ux,uy,lx,ly,frequencies,basis


def modal_score(frequencies, pressure, null_db=10.):
    """Return fixed-resolution flatness and fraction of the band in deep nulls."""
    response_db=20*np.log10(np.maximum(np.abs(pressure),1e-15))
    score_frequencies=np.asarray(frequencies,dtype=float)
    if len(frequencies)>1:
        # Score on a common 0.25 Hz grid so callers' sampling choices do not
        # alter the statistical weight of different parts of the band.
        grid=np.arange(float(frequencies[0]),float(frequencies[-1])+.125,.25)
        response_db=np.interp(grid,score_frequencies,response_db)
        score_frequencies=grid
    mean=float(np.mean(response_db))
    flatness=-float(np.std(response_db))
    null_penalty=-float(np.mean(response_db < mean-null_db))
    return {"flatness":flatness,"null_penalty":null_penalty,"mean_level_db":mean,"response_db":response_db,"frequencies_hz":score_frequencies}
