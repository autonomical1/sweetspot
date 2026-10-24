"""Built-in speaker profiles and a small extension point for custom specifications."""
from dataclasses import dataclass
from typing import Optional, Tuple, Union

@dataclass(frozen=True)
class SpeakerSpec:
    """Placement and acoustic assumptions for one speaker role.

    `wall_role` is front, rear, side, or any. `target_mode` is fan, center,
    surround, rear, or omni. A frequency band activates band-limited C50 scoring.
    """
    name: str
    wall_role: str = "front"
    target_mode: str = "fan"
    frequency_band_hz: Optional[Tuple[float, float]] = None
    directivity_scale: float = 1.0

    def __post_init__(self):
        if self.wall_role not in ("front", "rear", "side", "any"):
            raise ValueError("wall_role must be front, rear, side, or any")
        if self.target_mode not in ("fan", "center", "surround", "rear", "omni"):
            raise ValueError("unsupported target_mode")
        if self.frequency_band_hz is not None:
            low, high = self.frequency_band_hz
            if low <= 0 or high <= low: raise ValueError("frequency band must be positive and increasing")
        if self.directivity_scale < 0: raise ValueError("directivity_scale must be nonnegative")

BUILTIN_SPEAKERS = {
    "regular": SpeakerSpec("regular", "front", "fan", None, 1.0),
    "center": SpeakerSpec("center", "front", "center", None, 1.0),
    "bass": SpeakerSpec("bass", "any", "omni", (20.0, 120.0), 0.0),
    "subwoofer": SpeakerSpec("subwoofer", "any", "omni", (20.0, 120.0), 0.0),
    "surround": SpeakerSpec("surround", "side", "surround", None, 0.5),
    "rear": SpeakerSpec("rear", "rear", "rear", None, 0.5),
}

def resolve_speaker_spec(spec: Union[str, SpeakerSpec]) -> SpeakerSpec:
    if isinstance(spec, SpeakerSpec): return spec
    try: return BUILTIN_SPEAKERS[str(spec).lower()]
    except KeyError as exc: raise ValueError("Unknown speaker type {!r}; choose from {}".format(spec, ", ".join(BUILTIN_SPEAKERS))) from exc
