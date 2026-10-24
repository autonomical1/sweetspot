"""Room polygon construction and coordinate helpers."""
import numpy as np
FT_TO_M = 0.3048

def feet_to_m(value_ft: float) -> float: return float(value_ft) * FT_TO_M
def meters_to_ft(value_m: float) -> float: return float(value_m) / FT_TO_M

def make_room(length_ft: float, width_ft: float) -> np.ndarray:
    """Build a 2xN CCW rectangle in metres from feet at the input boundary."""
    length, width = feet_to_m(length_ft), feet_to_m(width_ft)
    if length <= 0 or width <= 0: raise ValueError("Room dimensions must be positive")
    return np.array([[0., length, length, 0.], [0., 0., width, width]])

def validate_polygon(polygon):
    p=np.asarray(polygon,dtype=float)
    if p.ndim!=2 or p.shape[0]!=2 or p.shape[1]<3 or not np.isfinite(p).all(): raise ValueError("polygon must be a finite 2xN array, N >= 3")
    area=.5*np.sum(p[0]*np.roll(p[1],-1)-p[1]*np.roll(p[0],-1))
    if area<=1e-10: raise ValueError("polygon must be non-degenerate and counterclockwise")
    return p

def default_listener(polygon, facing="north"):
    p=validate_polygon(polygon); lo=p.min(axis=1); hi=p.max(axis=1)
    if facing=="north": return np.array([(lo[0]+hi[0])/2,lo[1]+(hi[1]-lo[1])/3])
    if facing=="south": return np.array([(lo[0]+hi[0])/2,hi[1]-(hi[1]-lo[1])/3])
    if facing=="east": return np.array([lo[0]+(hi[0]-lo[0])/3,(lo[1]+hi[1])/2])
    if facing=="west": return np.array([hi[0]-(hi[0]-lo[0])/3,(lo[1]+hi[1])/2])
    raise ValueError("facing must be north, south, east, or west")
