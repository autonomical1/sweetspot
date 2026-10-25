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
    height_m: float | None = None
    surface: str = "wall"

def generate_candidates(polygon, spacing_m=.25, margin_m=.3, nudge_m=.001):
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

def mirror_candidate(candidate, listener, facing, polygon, candidates, tolerance=.14, margin_m=.3, nudge_m=.001):
    """Reflect across facing axis; preserve a continuous mirrored location on its wall."""
    axis=np.array([0.,1.]) if facing in ("north","south") else np.array([1.,0.])
    origin=np.asarray(listener); target=origin+(2*np.outer(axis,axis)-np.eye(2)).dot(candidate.position-origin)
    p=validate_polygon(polygon); i=candidate.wall_index; a=p[:,i]; edge=p[:,(i+1)%p.shape[1]]-a; length=np.linalg.norm(edge); tangent=edge/length
    inward=np.array([-tangent[1],tangent[0]]); distance=float(np.dot(target-a,inward)); along=float(np.dot(target-a,tangent))
    if abs(distance-nudge_m)>max(.02,tolerance) or not margin_m-1e-9<=along<=length-margin_m+1e-9: return None
    return Candidate(target,inward,i,along/length,candidate.height_m)


def snap_wall_candidate_to_bay(candidate, polygon, spacing_m, thickness_m=.0381, width_m=0., margin_m=.3, nudge_m=.001):
    """Snap a wall point to a stud-bay center and reject cutouts that do not fit.

    Studs are indexed from the wall's first room vertex; this is a planning
    convention, since real framing must be measured on site. ``width_m`` is
    the speaker cutout/enclosure width parallel to the wall.
    """
    if spacing_m is None:
        return candidate
    spacing=float(spacing_m); thickness=float(thickness_m); width=float(width_m)
    if spacing<=thickness or thickness<0 or width<0:
        raise ValueError("bay spacing must exceed nonnegative stud thickness")
    clear=spacing-thickness
    if width>clear+1e-9:
        raise ValueError("speaker cutout {:.3f} m exceeds {:.3f} m clear bay; needs header".format(width,clear))
    p=validate_polygon(polygon); i=int(candidate.wall_index)
    a,b=p[:,i],p[:,(i+1)%p.shape[1]]; edge=b-a; length=float(np.linalg.norm(edge)); tangent=edge/length
    along=float((np.asarray(candidate.position)-a)@tangent)
    # Wall origin is a stud line; bay centers are half a spacing from it.
    snapped=(round(along/spacing-.5)+.5)*spacing
    half_width=width/2.
    if snapped-half_width<margin_m or snapped+half_width>length-margin_m:
        raise ValueError("nearest stud bay center does not leave the required wall-end clearance")
    inward=np.array([-tangent[1],tangent[0]])
    return Candidate(a+tangent*snapped+nudge_m*inward,inward,i,snapped/length,candidate.height_m)


def ceiling_bay_centers(room_polygon_m, spacing_m, thickness_m=.0381, footprint_m=.22, margin_m=.15):
    """Return rectangular joist-bay center grid that fits the speaker cutout."""
    p=validate_polygon(room_polygon_m); spacing=float(spacing_m); thickness=float(thickness_m)
    if spacing<=thickness or footprint_m>spacing-thickness:
        raise ValueError("ceiling speaker cutout exceeds clear joist bay; needs header")
    origin=p.min(axis=1); lo=origin+margin_m+footprint_m/2.; hi=p.max(axis=1)-margin_m-footprint_m/2.
    x=origin[0]+spacing/2.+np.arange(max(0,int(np.ceil((lo[0]-origin[0]-spacing/2.)/spacing))),int(np.floor((hi[0]-origin[0]-spacing/2.)/spacing))+1)*spacing
    y=origin[1]+spacing/2.+np.arange(max(0,int(np.ceil((lo[1]-origin[1]-spacing/2.)/spacing))),int(np.floor((hi[1]-origin[1]-spacing/2.)/spacing))+1)*spacing
    return [np.array([xx,yy]) for xx in x for yy in y]


def generate_horizontal_surface_candidates(room_polygon_m, room_height_m, model, spacing_m=.25, margin_m=.15):
    """Sample subwoofer centers on floor and ceiling surfaces in 3D."""
    p=validate_polygon(room_polygon_m); origin=p[:,0]; u=p[:,1]-origin; v=p[:,3]-origin
    lu=float(np.linalg.norm(u)); lv=float(np.linalg.norm(v)); u/=lu; v/=lv
    mx=float(model.width_m)/2.+margin_m; my=float(model.depth_m)/2.+margin_m
    xs=np.arange(mx,lu-mx+1e-9,spacing_m); ys=np.arange(my,lv-my+1e-9,spacing_m)
    result=[]
    for surface,z in (("floor",float(model.height_m)/2.),("ceiling",float(room_height_m)-float(model.height_m)/2.)):
        normal=np.array([0.,1.])
        for x in xs:
            for y in ys:
                result.append(Candidate(origin+x*u+y*v,normal,0,.5,z,surface))
    for x,y in ((mx,my),(lu-mx,my),(mx,lv-my),(lu-mx,lv-my)):
        if x<=lu-mx and y<=lv-my:
            result.append(Candidate(origin+x*u+y*v,np.array([0.,1.]),0,.5,float(model.height_m)/2.,"corner"))
    return result
