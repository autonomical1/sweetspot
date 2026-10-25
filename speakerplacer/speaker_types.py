"""Speaker role registry and CLI layout parsing."""
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Union, Sequence

@dataclass
class SpeakerType:
    name: str
    count: int
    allowed_walls: Union[str, Sequence[str]]
    angle_target_deg: Optional[float]
    angle_tol_deg: float
    symmetric: bool
    band_hz: Tuple[float, float]
    directivity: float
    score_weights: Dict[str, float] = field(default_factory=dict)
    scorer: str = "imaging"
    ref_deg: float = 30.0
    model_id: Optional[str] = None
    channel_name: Optional[str] = None
    elevation_range_deg: Optional[Tuple[float, float]] = None
    azimuth_range_deg: Optional[Tuple[float, float]] = None

    def __post_init__(self):
        if self.count < 0: raise ValueError("speaker count must be nonnegative")
        if self.angle_tol_deg < 0 or (self.angle_target_deg is not None and self.angle_target_deg < 0): raise ValueError("angle target and tolerance must be nonnegative")
        if self.ref_deg <= 0: raise ValueError("ref_deg must be positive")
        allowed=self.allowed_walls.split(",") if isinstance(self.allowed_walls,str) else list(self.allowed_walls)
        if not allowed or any(wall not in ("front", "back", "left", "right", "any") for wall in allowed):
            raise ValueError("allowed_walls must contain front, back, left, right, or any")
        if "any" in allowed and len(allowed)>1: raise ValueError("'any' cannot be combined with named walls")
        self.allowed_walls=",".join(allowed)
        if self.angle_target_deg is None and self.angle_tol_deg < 0: raise ValueError("angle tolerance must be nonnegative")
        if self.scorer not in ("imaging", "modal"): raise ValueError("scorer must be imaging or modal")
        if self.band_hz[0] <= 0 or self.band_hz[1] <= self.band_hz[0]: raise ValueError("band_hz must be positive and increasing")
        if self.elevation_range_deg is not None:
            low,high=map(float,self.elevation_range_deg)
            if not -90.<=low<high<=90.: raise ValueError("elevation_range_deg must be increasing within -90..90")
        if self.azimuth_range_deg is not None:
            low,high=map(float,self.azimuth_range_deg)
            if not -180.<=low<=high<=180.: raise ValueError("azimuth_range_deg must be ordered within -180..180")
        if self.symmetric and self.count % 2: raise ValueError("speaker type '{}' is symmetric and requires an even count".format(self.name))

DEFAULT_SPEAKER_TYPES = {
    "front": SpeakerType("front",2,"front",30.,5.,True,(200.,20000.),1.,{"clarity":1.,"off_axis":1.,"early_reflection":1.,"geometry":1.,"headroom":.2,"direct_level":.5},"imaging",30.,"generic_bookshelf_onwall"),
    "center": SpeakerType("center",1,"front",0.,5.,False,(200.,20000.),1.,{"clarity":1.,"off_axis":1.,"early_reflection":1.,"geometry":1.,"headroom":.2,"direct_level":.5},"imaging",30.,"generic_center_onwall"),
    "rear_surround": SpeakerType("rear_surround",2,"back",140.,10.,True,(200.,20000.),.7,{"clarity":1.,"off_axis":.7,"early_reflection":1.,"geometry":1.,"headroom":.2,"direct_level":.5},"imaging",45.,"generic_surround_wide"),
    "wide": SpeakerType("wide",2,"any",60.,10.,True,(200.,20000.),1.,{"clarity":1.,"off_axis":1.,"early_reflection":1.,"geometry":1.,"headroom":.2,"direct_level":.5},"imaging",30.,"generic_bookshelf_onwall"),
    "surround": SpeakerType("surround",2,"left,right",100.,10.,True,(200.,20000.),.7,{"clarity":1.,"off_axis":.7,"early_reflection":1.,"geometry":1.,"headroom":.2,"direct_level":.5},"imaging",45.,"generic_surround_wide"),
    "bass": SpeakerType("bass",2,"any",None,180.,False,(30.,200.),0.,{"flatness":1.,"null_penalty":1.,"spatial_variance":.2,"geometry":.5,"headroom":.2},"modal",180.,"generic_inwall_sub"),
}
DEFAULT_LAYOUT = [("front",2),("bass",2),("surround",2)]

def parse_speaker_layout(items, registry=None):
    """Parse CLI tokens like ['front:2', 'bass:2'] into configured type records."""
    registry=DEFAULT_SPEAKER_TYPES if registry is None else registry
    layout=[]
    for item in items:
        parts=item.split(":")
        if len(parts) not in (2,3): raise ValueError("speaker entries must use TYPE:COUNT[:MODEL], e.g. front:2:generic_inwall_lcr")
        name,count_text=parts[:2]; model_id=parts[2] if len(parts)==3 else None; name=name.lower()
        if name not in registry: raise ValueError("unknown speaker type '{}'; choose from {}".format(name,", ".join(registry)))
        try: count=int(count_text)
        except ValueError as exc: raise ValueError("speaker count in {!r} must be an integer".format(item)) from exc
        spec=registry[name]
        configured=SpeakerType(spec.name,count,spec.allowed_walls,spec.angle_target_deg,spec.angle_tol_deg,
                               spec.symmetric and not (spec.name=="bass" and count==1),spec.band_hz,
                               spec.directivity,dict(spec.score_weights),spec.scorer,spec.ref_deg,model_id or spec.model_id,spec.channel_name,spec.elevation_range_deg,spec.azimuth_range_deg)
        if count: layout.append(configured)
    return layout
