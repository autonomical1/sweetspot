"""Perimeter speaker candidates and reflection across a facing axis."""
from dataclasses import dataclass
import numpy as np
from .room import validate_polygon
@dataclass
class Candidate:
    position: np.ndarray
    normal: np.ndarray
    wall_index: int
    wall_t: float

def generate_candidates(polygon, spacing_m=.25, margin_m=.3, nudge_m=.05):
    p=validate_polygon(polygon); out=[]
    for i in range(p.shape[1]):
        a,b=p[:,i],p[:,(i+1)%p.shape[1]]; edge=b-a; length=np.linalg.norm(edge)
        if length<=2*margin_m: continue
        tangent=edge/length; normal=np.array([-tangent[1],tangent[0]])
        ds=np.arange(margin_m,length-margin_m+1e-9,spacing_m)
        if not len(ds) or length-margin_m-ds[-1] > spacing_m*.5: ds=np.append(ds,length-margin_m)
        out.extend(Candidate(a+tangent*d+nudge_m*normal,normal,i,float(d/length)) for d in ds)
    return out

def facing_wall_index(polygon, facing):
    p=validate_polygon(polygon); direction={"north":np.array([0.,1.]),"south":np.array([0.,-1.]),"east":np.array([1.,0.]),"west":np.array([-1.,0.])}[facing]
    scores=[]
    for i in range(p.shape[1]):
        e=p[:,(i+1)%p.shape[1]]-p[:,i]; e=e/np.linalg.norm(e); inward=np.array([-e[1],e[0]])
        scores.append(float(np.dot(-inward,direction)))
    return int(np.argmax(scores))

def mirror_candidate(candidate, listener, facing, polygon, candidates, tolerance=.14, margin_m=.3, nudge_m=.05):
    """Reflect across facing axis; preserve a continuous mirrored location on its wall."""
    axis=np.array([0.,1.]) if facing in ("north","south") else np.array([1.,0.])
    origin=np.asarray(listener); target=origin+(2*np.outer(axis,axis)-np.eye(2)).dot(candidate.position-origin)
    p=validate_polygon(polygon); i=candidate.wall_index; a=p[:,i]; edge=p[:,(i+1)%p.shape[1]]-a; length=np.linalg.norm(edge); tangent=edge/length
    inward=np.array([-tangent[1],tangent[0]]); distance=float(np.dot(target-a,inward)); along=float(np.dot(target-a,tangent))
    if abs(distance-nudge_m)>max(.02,tolerance) or not margin_m-1e-9<=along<=length-margin_m+1e-9: return None
    return Candidate(target,inward,i,along/length)
