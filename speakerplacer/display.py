"""Pure geometry and photometry helpers for screen/projector planning."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
from typing import Any

import yaml


# Generic planning placeholders used when a user has not supplied a product
# spec. These make every normal layout include an explicit display estimate.
DEFAULT_SCREEN_SPEC = {
    "diag_in": 100., "aspect_ratio": "16:9", "material": "matte_white",
    "gain": 1., "half_gain_angle_deg": 45., "border_width_m": .05,
    "thickness_m": .03, "standoff_from_wall_m": .05,
    "bottom_edge_height_m": .61, "image_fit": "fit_width",
}
DEFAULT_PROJECTOR_SPEC = {
    "model": "generic_placeholder", "native_resolution": "3840x2160",
    "native_aspect": "16:9", "lumens_ansi": 3000., "eco_mode_factor": .75,
    "native_contrast": 1000., "throw_ratio_min": 1.4, "throw_ratio_max": 2.2,
    "lumens_loss_at_tele_pct": .15, "lens_shift_vertical_min": -.5,
    "lens_shift_vertical_max": .5, "lens_shift_horizontal_min": -.2,
    "lens_shift_horizontal_max": .2, "lens_shift_convention": "center_fraction",
    "keystone_max_v_deg": 5., "keystone_max_h_deg": 5.,
    "body_width_m": .35, "body_height_m": .15, "body_depth_m": .30,
    "noise_dba_1m": 32., "noise_dba_eco_1m": 28.,
    "mount_type": "ceiling_inverted", "min_distance_m": 2.,
    "max_distance_m": 8., "ventilation_clearance_m": .20,
}


def _ratio(value: Any) -> float:
    if isinstance(value,str) and ":" in value:
        a,b=map(float,value.split(":",1)); return a/b
    return float(value)


@dataclass(frozen=True)
class ScreenGeometry:
    width_m: float
    height_m: float
    image_width_m: float
    image_height_m: float
    aspect_ratio: float


def screen_geometry(spec: dict[str, Any]) -> ScreenGeometry:
    """Resolve physical screen and inscribed image dimensions from user specs."""
    if "width_m" in spec and "height_m" in spec:
        width, height = float(spec["width_m"]), float(spec["height_m"])
    elif "diag_in" in spec:
        aspect = _ratio(spec.get("aspect_ratio", 16./9.))
        diagonal = float(spec["diag_in"])*.0254
        width, height = diagonal*aspect/math.hypot(aspect, 1.), diagonal/math.hypot(aspect, 1.)
    else:
        raise ValueError("screen needs width_m and height_m, or diag_in and aspect_ratio")
    if width <= 0 or height <= 0: raise ValueError("screen dimensions must be positive")
    aspect = _ratio(spec.get("aspect_ratio", width/height))
    if aspect <= 0: raise ValueError("screen aspect_ratio must be positive")
    image_aspect=_ratio(spec.get("image_aspect_ratio",aspect))
    if image_aspect<=0: raise ValueError("image_aspect_ratio must be positive")
    fit = str(spec.get("image_fit", "fit_height" if image_aspect<aspect else "fit_width"))
    if fit == "fit_width": image_w, image_h = width, width/image_aspect
    elif fit == "fit_height": image_h, image_w = height, height*image_aspect
    elif fit == "constant_height": image_h, image_w = min(height,width/image_aspect), min(height,width/image_aspect)*image_aspect
    else: raise ValueError("image_fit must be fit_width, fit_height, or constant_height")
    if image_w > width+1e-9 or image_h > height+1e-9:
        raise ValueError("image aspect and fit mode do not fit inside the physical screen")
    return ScreenGeometry(width,height,image_w,image_h,aspect)


def solve_display_positions(room_polygon_m, facing, screen_spec, projector_spec,
                            room_height_m, screen_pos=None, projector_pos=None):
    """Place the screen on the selected wall and keep the projector inside it."""
    import numpy as np
    from matplotlib.path import Path as PolygonPath
    from .viewer3d import front_wall_index,wall_frame

    room=np.asarray(room_polygon_m,dtype=float)
    image_spec=dict(screen_spec)
    if "image_aspect_ratio" not in image_spec and projector_spec.get("native_aspect"):
        image_spec["image_aspect_ratio"]=projector_spec["native_aspect"]
    geometry=screen_geometry(image_spec)
    wall_index=front_wall_index(room,facing); start,tangent,inward=wall_frame(room,wall_index)
    forward=-inward; right=np.array([forward[1],-forward[0]])
    wall_length=float(np.linalg.norm(room[:,(wall_index+1)%room.shape[1]]-start))
    border=float(screen_spec.get("border_width_m",0.)); clearance=float(screen_spec.get("clearance_m",0.))
    offset=float(screen_spec.get("fixed_x_offset_m",0.))
    screen_along=wall_length/2.+offset
    if screen_pos is not None:
        requested_x,z=map(float,screen_pos)
        screen_along=float((np.array([requested_x,0.])-start)@tangent) if facing in ("north","south") else float((np.array([0.,requested_x])-start)@tangent)
        bottom=z-geometry.height_m/2.
    else: bottom=float(screen_spec.get("bottom_edge_height_m",.61))
    half_screen=geometry.width_m/2.+border+clearance
    standoff=float(screen_spec.get("standoff_from_wall_m",0.))
    if standoff<0.: raise ValueError("room invalid for screen: standoff_from_wall_m cannot move the screen outside the room")
    if screen_along-half_screen<0. or screen_along+half_screen>wall_length:
        raise ValueError("room invalid for screen: front wall is {:.2f} m long but screen plus border/clearance needs {:.2f} m; reduce screen size or edit the room, then retry".format(wall_length,2.*half_screen))
    if bottom<0. or bottom+geometry.height_m+border>float(room_height_m):
        raise ValueError("room invalid for screen: screen vertical bounds {:.2f}..{:.2f} m exceed floor/ceiling 0..{:.2f} m; change screen height or room height, then retry".format(bottom,bottom+geometry.height_m+border,room_height_m))
    screen_center_xy=start+tangent*screen_along+inward*standoff
    screen_center=np.r_[screen_center_xy,bottom+geometry.height_m/2.]
    if projector_pos is not None:
        projector=np.asarray(projector_pos,dtype=float)
        if projector.shape!=(3,): raise ValueError("projector position must be X/Y/Z")
        requested=[projector]
    else:
        ratio_min=float(projector_spec.get("throw_ratio_min",1.4)); ratio_max=float(projector_spec.get("throw_ratio_max",2.2))
        distance_min=max(ratio_min*geometry.image_width_m,float(projector_spec.get("min_distance_m",0.)))
        distance_max=min(ratio_max*geometry.image_width_m,float(projector_spec.get("max_distance_m",np.inf)))
        if distance_min>distance_max:
            raise ValueError("room invalid for projector: legal throw distance is empty (screen requires {:.2f}..{:.2f} m, projector allows {:.2f}..{:.2f} m); change screen/projector specs and retry".format(ratio_min*geometry.image_width_m,ratio_max*geometry.image_width_m,float(projector_spec.get("min_distance_m",0.)),float(projector_spec.get("max_distance_m",np.inf))))
        preferred=float(np.clip(projector_spec.get("throw_m",(ratio_min+ratio_max)*.5*geometry.image_width_m),distance_min,distance_max))
        distances=np.unique(np.r_[preferred,np.arange(distance_min,distance_max+.010,.025),distance_min,distance_max])
        shift_min=float(projector_spec.get("lens_shift_horizontal_min",0.)); shift_max=float(projector_spec.get("lens_shift_horizontal_max",0.))
        shift_limit=max(abs(shift_min),abs(shift_max))*geometry.image_width_m
        lateral_offsets=np.unique(np.r_[np.arange(-shift_limit,shift_limit+.005,.05),0.]) if shift_limit else np.array([0.])
        requested=[np.r_[screen_center_xy-forward*distance+right*lateral,screen_center[2]]
                   for distance in distances for lateral in lateral_offsets]
    body_w=float(projector_spec.get("body_width_m",.35)); body_h=float(projector_spec.get("body_height_m",.15)); body_d=float(projector_spec.get("body_depth_m",.30))
    vent=float(projector_spec.get("ventilation_clearance_m",0.)); path=PolygonPath(room.T)
    legal=[]
    for point in requested:
        actual_throw=float(np.linalg.norm(point[:2]-screen_center_xy))
        if projector_pos is None and not (distance_min-1e-9<=actual_throw<=distance_max+1e-9): continue
        if point[2]-body_h/2.-vent<0. or point[2]+body_h/2.+vent>room_height_m: continue
        corners=[point[:2]+right*sx*(body_w/2.+vent)+forward*sy*(body_d/2.+vent)
                 for sx,sy in ((-1,-1),(-1,1),(1,1),(1,-1))]
        samples=[]
        for i,a in enumerate(corners):
            b=corners[(i+1)%4]; count=max(2,int(np.ceil(np.linalg.norm(b-a)/.05)))
            samples.extend(a+(b-a)*t for t in np.linspace(0.,1.,count))
        if all(path.contains_point(sample,radius=-1e-8) for sample in samples):
            legal.append(point)
    if not legal:
        raise ValueError("room invalid for projector: no position keeps the projector body and ventilation clearance inside the room while preserving its throw range; reduce the screen/projector size, change throw specs, or edit the room and retry")
    if projector_pos is not None: projector=legal[0]
    else:
        target_distance=float(np.clip(projector_spec.get("throw_m",(float(projector_spec.get("throw_ratio_min",1.4))+float(projector_spec.get("throw_ratio_max",2.2)))*.5*geometry.image_width_m),distance_min,distance_max))
        projector=min(legal,key=lambda point:abs(float(np.linalg.norm(point[:2]-screen_center_xy))-target_distance)+.1*abs(float((point[:2]-screen_center_xy)@right)))
    return {"screen_geometry":geometry,"screen_center_m":screen_center.tolist(),
            "projector_position_m":projector.tolist(),"forward_xy":forward.tolist(),
            "right_xy":right.tolist(),"wall_index":wall_index,"wall_start_m":start.tolist(),
            "wall_tangent_xy":tangent.tolist(),"wall_inward_xy":inward.tolist(),
            "screen_bottom_m":bottom,
            "projector_horizontal_shift_m":float((projector[:2]-screen_center_xy)@right)}


def throw_feasibility(image_width_m: float, distance_m: float,
                      throw_ratio_min: float, throw_ratio_max: float) -> dict[str, float | bool]:
    """Evaluate throw ratio and nearest feasible distance without changing inputs."""
    if min(image_width_m,distance_m,throw_ratio_min) <= 0 or throw_ratio_max < throw_ratio_min:
        raise ValueError("image width, distance, and throw-ratio range must be positive and ordered")
    ratio=distance_m/image_width_m
    nearest=min(max(distance_m,throw_ratio_min*image_width_m),throw_ratio_max*image_width_m)
    return {"implied_throw_ratio":ratio,"throw_ratio_min":throw_ratio_min,"throw_ratio_max":throw_ratio_max,
            "feasible":throw_ratio_min-1e-9<=ratio<=throw_ratio_max+1e-9,
            "nearest_feasible_distance_m":nearest,"nearest_feasible_image_width_m":distance_m/min(max(ratio,throw_ratio_min),throw_ratio_max),
            "zoom_position":min(1.,max(0.,(ratio-throw_ratio_min)/(throw_ratio_max-throw_ratio_min))) if throw_ratio_max>throw_ratio_min else 0.}


def horizontal_viewing_angle_deg(eye_xyz, screen_center_xyz, right_xy, image_width_m: float) -> float:
    """Horizontal image angle based on vectors to both physical image edges."""
    import numpy as np
    eye=np.asarray(eye_xyz,dtype=float); center=np.asarray(screen_center_xyz,dtype=float)
    right=np.asarray(right_xy,dtype=float); right=right/max(float(np.linalg.norm(right)),1e-12)
    left=center-np.r_[right,0.]*image_width_m/2.; right_edge=center+np.r_[right,0.]*image_width_m/2.
    a=left-eye; b=right_edge-eye
    return float(np.degrees(np.arccos(np.clip(a@b/max(float(np.linalg.norm(a)*np.linalg.norm(b)),1e-12),-1.,1.))))


def screen_brightness(lumens_ansi: float, gain: float, image_width_m: float,
                      image_height_m: float, derate: float=1.) -> dict[str,float]:
    """Return idealized screen luminance in foot-lamberts and nits."""
    if min(lumens_ansi,gain,image_width_m,image_height_m,derate)<=0:
        raise ValueError("lumens, gain, image dimensions, and derate must be positive")
    area_ft2=image_width_m*image_height_m/(.3048**2)
    fl=lumens_ansi*derate*gain/area_ft2
    return {"image_area_ft2":area_ft2,"foot_lamberts":fl,"nits":fl*3.426}


def pixel_visibility_distance_m(image_height_m: float, vertical_pixels: int) -> float:
    """Distance at which pixel pitch subtends one arcminute."""
    if image_height_m<=0 or vertical_pixels<=0: raise ValueError("image height and pixel count must be positive")
    return (image_height_m/vertical_pixels)/math.tan(math.radians(1./60.))


def lens_shift_and_keystone(image_center_z_m: float, lens_z_m: float,
                            image_height_m: float, throw_distance_m: float,
                            inverted: bool=False, keystone_max_deg: float=0.,
                            shift_min: float=-math.inf, shift_max: float=math.inf) -> dict[str,float | bool]:
    """Normalize vertical shift and estimate residual tilt/keystone."""
    if image_height_m<=0 or throw_distance_m<=0: raise ValueError("image height and throw distance must be positive")
    raw=(image_center_z_m-lens_z_m)/image_height_m
    required=-raw if inverted else raw
    excess=max(shift_min-required,required-shift_max,0.)
    tilt=math.degrees(math.atan(excess*image_height_m/throw_distance_m))
    return {"required_vertical_shift":required,"allowed_min":shift_min,"allowed_max":shift_max,
            "lens_shift_feasible":excess<=1e-9,"keystone_angle_deg":tilt,
            "keystone_allowed":tilt<=keystone_max_deg+1e-9}


def load_spec(path: str | Path) -> dict[str, Any]:
    """Read a YAML spec mapping."""
    data=yaml.safe_load(Path(path).expanduser().read_text(encoding="utf-8")) or {}
    if not isinstance(data,dict): raise ValueError("spec YAML must contain a mapping")
    return data


def parse_unit_overrides(tokens: list[str], kind: str) -> dict[str, Any]:
    """Parse simple comma-separated CLI overrides; dimensional keys are normalized once."""
    out={}
    for token in tokens:
        if "=" not in token: raise ValueError("{} override must be key=value".format(kind))
        key,value=token.split("=",1); key=key.strip(); value=value.strip()
        if key=="diag_in": out[key]=float(value)
        elif key.endswith("_in"):
            normalized=key[:-3]+"_m"; normalized={"bottom_m":"bottom_edge_height_m","standoff_behind_m":"standoff_behind_m"}.get(normalized,normalized)
            out[normalized]=float(value)*.0254
        elif key.endswith("_ft"):
            out[key[:-3]+"_m"]=float(value)*.3048
        elif key.endswith("_m"):
            out[key]=float(value)
        elif key in ("aspect","aspect_ratio","throw_ratio") and ":" in value:
            a,b=map(float,value.split(":",1))
            if key=="throw_ratio": out["throw_ratio_min"],out["throw_ratio_max"]=a,b
            else: out["aspect_ratio"]=a/b
        else:
            try: out[key]=float(value)
            except ValueError: out[key]=value
    return out


def init_spec_templates(directory: str | Path) -> tuple[Path,Path]:
    """Write commented templates; values are generic placeholders, not products."""
    root=Path(directory); root.mkdir(parents=True,exist_ok=True)
    screen=root/"screen.yaml"; projector=root/"projector.yaml"
    screen.write_text("""# Generic screen template. Fill in measured/user-supplied values.\n# Units are encoded in field names. Targets are conventions marked verify.\ndiag_in: 120\naspect_ratio: 16:9\nmaterial: matte_white  # matte_white | alr | ats\ngain: 1.0\nhalf_gain_angle_deg: 45\nborder_width_m: 0.05\nthickness_m: 0.03\nstandoff_from_wall_m: 0.05\nbottom_edge_height_m: 0.61\nimage_fit: fit_width\ncurvature: flat\n# ATS only: transmission_loss_db: {125: 1, 250: 2, 500: 3, 1000: 4, 2000: 5, 4000: 6}\n# ATS only: standoff_behind_m: 0.15\n# Optional: fixed_x_offset_m: 0.0\n""",encoding="utf-8")
    projector.write_text("""# Generic projector constraints. Do not treat these as a real product.\nmodel: generic_placeholder\nnative_resolution: 3840x2160\nnative_aspect: 16:9\nlumens_ansi: 3000\neco_mode_factor: 0.75\nnative_contrast: 1000\nthrow_ratio_min: 1.4\nthrow_ratio_max: 2.2\nlumens_loss_at_tele_pct: 0.15\nlens_shift_vertical_min: -0.5\nlens_shift_vertical_max: 0.5\nlens_shift_horizontal_min: -0.2\nlens_shift_horizontal_max: 0.2\nlens_shift_convention: center_fraction\nkeystone_max_v_deg: 5\nkeystone_max_h_deg: 5\nfixed_lens_offset_m: 0.0\nthrow_reference: lens_front\nlens_offset_x_m: 0.0\nlens_offset_z_m: 0.0\nbody_width_m: 0.35\nbody_height_m: 0.15\nbody_depth_m: 0.30\nnoise_dba_1m: 32\nnoise_dba_eco_1m: 28\nallowed_mounts: [ceiling_inverted, rear_shelf, table, floor_front]\nmount_drop_min_m: 0.10\nmount_drop_max_m: 0.50\nmin_distance_m: 2.0\nmax_distance_m: 8.0\nventilation_clearance_m: 0.20\n""",encoding="utf-8")
    return screen,projector


def evaluate_display(screen_spec: dict[str, Any], projector_spec: dict[str, Any],
                     screen_center_xyz, seats, projector_position_xyz=None,
                     target_fl: float=16., ambient_lux: float=0., derate: float=1.,
                     right_xy=(1.,0.)) -> dict[str, Any]:
    """Resolve/evaluate one screen-projector pair and per-seat display geometry."""
    import numpy as np
    image_spec=dict(screen_spec)
    if "image_aspect_ratio" not in image_spec and projector_spec.get("native_aspect"):
        image_spec["image_aspect_ratio"]=projector_spec["native_aspect"]
    screen=screen_geometry(image_spec); center=np.asarray(screen_center_xyz,dtype=float)
    seats=[np.asarray(seat,dtype=float) for seat in seats]
    if center.shape!=(3,) or not seats or any(s.shape!=(3,) for s in seats):
        raise ValueError("screen center and at least one 3D seat position are required")
    ratio_min=float(projector_spec.get("throw_ratio_min",1.4)); ratio_max=float(projector_spec.get("throw_ratio_max",2.2))
    if projector_position_xyz is None:
        distance=float(projector_spec.get("throw_m",((ratio_min+ratio_max)/2.)*screen.image_width_m))
        projector=np.array([center[0],center[1]-distance,center[2]])
        position_source="solved at mid-zoom on screen centerline"
    else:
        projector=np.asarray(projector_position_xyz,dtype=float)
        if projector.shape!=(3,): raise ValueError("projector position must be an XYZ triple")
        position_source="user supplied"
    throw=float(np.linalg.norm(projector[:2]-center[:2]))
    feasible=throw_feasibility(screen.image_width_m,throw,ratio_min,ratio_max)
    native=str(projector_spec.get("native_resolution","3840x2160"))
    try: px_w,px_h=(int(v) for v in native.lower().split("x",1))
    except (ValueError,AttributeError): raise ValueError("native_resolution must have WIDTHxHEIGHT form")
    lumens=float(projector_spec.get("lumens_ansi",3000.)); eco=float(projector_spec.get("eco_mode_factor",.75))
    tele_loss=float(projector_spec.get("lumens_loss_at_tele_pct",.15)); zoom=float(feasible["zoom_position"])
    lamp_factor=eco*float(derate)*(1.-zoom*tele_loss)
    brightness=screen_brightness(lumens,float(screen_spec.get("gain",1.)),screen.image_width_m,screen.image_height_m,lamp_factor)
    horizontal=[]; vertical=[]; distances=[]; seat_fl=[]
    right=np.asarray(right_xy,dtype=float); right/=max(float(np.linalg.norm(right)),1e-12)
    top=center.copy(); top[2]+=screen.image_height_m/2.
    for seat in seats:
        horizontal.append(horizontal_viewing_angle_deg(seat,center,right,screen.image_width_m))
        delta=top-seat; vertical.append(float(np.degrees(np.arctan2(delta[2],np.linalg.norm(delta[:2])))))
        distances.append(float(np.linalg.norm(seat-center)))
        viewing_off_axis=abs(float(np.degrees(np.arctan2(float((seat[:2]-center[:2])@right),max(float(np.linalg.norm(seat[:2]-center[:2])),1e-12)))))
        half_gain=float(screen_spec.get("half_gain_angle_deg",45.)); exponent=math.log(.5)/math.log(max(math.cos(math.radians(half_gain)),1e-9)) if half_gain<90. else 0.
        gain_factor=max(0.,math.cos(math.radians(viewing_off_axis)))**exponent
        seat_fl.append(brightness["foot_lamberts"]*gain_factor)
    ambient_nits=max(0.,float(ambient_lux))*float(screen_spec.get("gain",1.))/math.pi
    white=brightness["nits"]; contrast=(white+ambient_nits)/(white/max(float(projector_spec.get("native_contrast",1000.)),1.)+ambient_nits)
    pixel_distance=pixel_visibility_distance_m(screen.image_height_m,px_h)
    lens=np.asarray([projector[0]+float(projector_spec.get("lens_offset_x_m",0.)),
                    projector[1]+float(projector_spec.get("lens_offset_y_m",0.)),
                    projector[2]+float(projector_spec.get("lens_offset_z_m",0.))])
    shift=lens_shift_and_keystone(center[2],lens[2],screen.image_height_m,throw,
        str(projector_spec.get("mount_type","ceiling_inverted"))=="ceiling_inverted",
        float(projector_spec.get("keystone_max_v_deg",0.)),
        float(projector_spec.get("lens_shift_vertical_min",-.5)),
        float(projector_spec.get("lens_shift_vertical_max",.5)))
    noise=float(projector_spec.get("noise_dba_1m",32.)); eco_noise=float(projector_spec.get("noise_dba_eco_1m",noise))
    noise_rows=[(eco_noise if eco<1. else noise)-20.*math.log10(max(float(np.linalg.norm(lens-seat)),.1)) for seat in seats]
    return {"screen":{"geometry":{"width_m":screen.width_m,"height_m":screen.height_m,
                    "image_width_m":screen.image_width_m,"image_height_m":screen.image_height_m,
                    "aspect_ratio":screen.aspect_ratio},"center_m":center.tolist(),"center_ft":(center/.3048).tolist(),
                    "material":screen_spec.get("material","matte_white"),"gain":float(screen_spec.get("gain",1.)),
                    "diag_in":float(screen_spec.get("diag_in",math.hypot(screen.width_m,screen.height_m)/.0254)),
                    "transmission_loss_db":{str(k):float(v) for k,v in screen_spec.get("transmission_loss_db",{}).items()}},
            "projector":{"position_m":projector.tolist(),"position_ft":(projector/.3048).tolist(),"position_source":position_source,
                    "throw_distance_m":throw,"native_resolution":native,"lumens_effective":lumens*lamp_factor,
                    **feasible,"brightness":brightness,"effective_contrast":contrast,
                    "ambient_lux":float(ambient_lux),"lens_position_m":lens.tolist(),"lens_position_ft":(lens/.3048).tolist(),
                    "lens_shift":shift,"noise_at_seats_dba":noise_rows,
                    "body_width_m":float(projector_spec.get("body_width_m",.35)),
                    "body_height_m":float(projector_spec.get("body_height_m",.15)),
                    "body_depth_m":float(projector_spec.get("body_depth_m",.30))},
            "per_seat":[{"index":i,"viewing_angle_deg":horizontal[i],"vertical_top_angle_deg":vertical[i],
                          "distance_m":distances[i],"distance_in_screen_heights":distances[i]/screen.image_height_m,
                          "pixels_unresolved":distances[i]>=pixel_distance,"foot_lamberts":seat_fl[i],
                          "nits":seat_fl[i]*3.426} for i in range(len(seats))],
            "pixel_unresolved_distance_m":pixel_distance,"target_fl":float(target_fl),
            "brightness_status":"PASS" if brightness["foot_lamberts"]>=target_fl else "WARN"}
