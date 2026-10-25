"""Acoustic and stereo geometry score terms, each expressed in dB-like units."""
from dataclasses import dataclass, asdict
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
    """Return origin, orthogonal room axes, and side lengths for a rectangle."""
    from .room import validate_polygon
    p=validate_polygon(room_polygon)
    if p.shape[1]!=4: raise ValueError("modal scorer requires a four-corner rectangle")
    origin=p[:,0]; e1=p[:,1]-origin; e2=p[:,3]-origin
    lx=float(np.linalg.norm(e1)); ly=float(np.linalg.norm(e2))
    if lx==0 or ly==0: raise ValueError("rectangle sides must be nonzero")
    ux=e1/lx; uy=e2/ly
    if abs(float(ux@uy))>1e-6: raise ValueError("modal scorer requires a rectangular polygon")
    return origin,ux,uy,lx,ly


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


def modal_response(room_polygon, sources, listener, absorption=.2, band_hz=(30.,200.), step_hz=1., q_scale=20., c=343., source_gains_db=None):
    """Complex coherent modal pressure versus frequency for same-signal sources.

    Q = q_scale / sqrt(absorption) is a configurable approximate damping map.
    """
    origin,ux,uy,lx,ly=rectangular_room_frame(room_polygon)
    if step_hz<=0 or absorption<0: raise ValueError("step_hz must be positive and absorption nonnegative")
    def local(point):
        delta=np.asarray(point,dtype=float)-origin
        return float(delta@ux),float(delta@uy)
    lx_listener,ly_listener=local(listener)
    source_points=[local(source) for source in sources]
    gains=np.ones(len(source_points)) if source_gains_db is None else 10.**(np.asarray(source_gains_db,dtype=float)/20.)
    modes=room_modes(room_polygon,band_hz,c)
    frequencies=np.arange(float(band_hz[0]),float(band_hz[1])+step_hz*.5,step_hz)
    pressure=np.zeros(len(frequencies),dtype=complex)
    q=q_scale/np.sqrt(max(float(absorption),.01))
    for f_nm,n,m in modes:
        psi_l=np.cos(n*np.pi*lx_listener/lx)*np.cos(m*np.pi*ly_listener/ly)
        psi_s=sum(gain*np.cos(n*np.pi*x/lx)*np.cos(m*np.pi*y/ly) for (x,y),gain in zip(source_points,gains))
        numerator=psi_l*psi_s
        pressure += numerator/(f_nm**2-frequencies**2+1j*frequencies*f_nm/q)
    return frequencies,pressure


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
