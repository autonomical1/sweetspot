"""pyroomacoustics 2D image-source simulation backend."""
import numpy as np
from .room import validate_polygon

def simulate_rir(room_polygon, source, listener, absorption=.2, fs=16000, max_order=10):
    """Return mono RIR and sample rate; requires pyroomacoustics with 2D support."""
    p=validate_polygon(room_polygon)
    if not 0<=absorption<=1: raise ValueError("absorption must be in [0, 1]")
    try: import pyroomacoustics as pra
    except ImportError as exc: raise RuntimeError("pyroomacoustics is required; install requirements.txt") from exc
    try:
        room=pra.Room.from_corners(p,fs=fs,max_order=max_order,materials=pra.Material(absorption))
        room.add_source(np.asarray(source,dtype=float))
        room.add_microphone(np.asarray(listener,dtype=float))
        room.compute_rir()
        # pyroomacoustics applies a global delay equal to half its fractional-delay filter length.
        delay=int(pra.constants.get("frac_delay_length")) // 2
        rir=np.asarray(room.rir[0][0],dtype=float)[delay:]
    except Exception as exc: raise RuntimeError("pyroomacoustics failed to compute a 2D RIR via Room.from_corners; verify 2D support/API in the installed version") from exc
    if rir.ndim!=1 or not len(rir) or not np.isfinite(rir).all(): raise RuntimeError("Invalid RIR returned by pyroomacoustics")
    return rir,fs
