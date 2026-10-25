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
    rectangular=False
    if p.shape[1]==4:
        origin=p[:,0]; e1=p[:,1]-origin; e2=p[:,3]-origin
        rectangular=(abs(float(e1@e2))<=1e-6*np.linalg.norm(e1)*np.linalg.norm(e2) and
                     np.allclose(p[:,2],origin+e1+e2,atol=1e-6) and np.allclose(p[:,3],origin+e2,atol=1e-6))
    if not rectangular:
        # Use the polygon centroid, falling back to a tiny inward offset from
        # an edge when a concave room's area centroid lies outside the room.
        from matplotlib.path import Path
        nxt=np.roll(p,-1,axis=1); cross=p[0]*nxt[1]-nxt[0]*p[1]
        area2=float(np.sum(cross))
        centroid=np.array([np.sum((p[0]+nxt[0])*cross),np.sum((p[1]+nxt[1])*cross)])/(3.*area2)
        path=Path(p.T)
        if path.contains_point(centroid): return centroid
        vertex_mean=np.mean(p,axis=1)
        if path.contains_point(vertex_mean): return vertex_mean
        for i in range(p.shape[1]):
            edge=p[:,(i+1)%p.shape[1]]-p[:,i]; length=float(np.linalg.norm(edge))
            if length<=0: continue
            inward=np.array([-edge[1],edge[0]])/length
            for offset in (.01,.05,.15,.3):
                candidate=(p[:,i]+p[:,(i+1)%p.shape[1]])/2.+offset*inward
                if path.contains_point(candidate): return candidate
        raise ValueError("could not find an interior listener position; provide --listener X Y")
    if facing=="north": return np.array([(lo[0]+hi[0])/2,lo[1]+(hi[1]-lo[1])/3])
    if facing=="south": return np.array([(lo[0]+hi[0])/2,hi[1]-(hi[1]-lo[1])/3])
    if facing=="east": return np.array([lo[0]+(hi[0]-lo[0])/3,(lo[1]+hi[1])/2])
    if facing=="west": return np.array([hi[0]-(hi[0]-lo[0])/3,(lo[1]+hi[1])/2])
    raise ValueError("facing must be north, south, east, or west")
