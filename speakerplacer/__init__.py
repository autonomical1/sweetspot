"""Wall-mounted speaker placement optimizer."""
from .room import make_room, feet_to_m, meters_to_ft, default_listener
from .optimize import optimize_speakers, optimize_layout, OptimizationResult
from .scoring import ScoreWeights
from .speaker_types import SpeakerType, DEFAULT_SPEAKER_TYPES, parse_speaker_layout
from .specs import SpeakerSpec
__all__=["make_room","feet_to_m","meters_to_ft","default_listener","optimize_speakers","optimize_layout","OptimizationResult","ScoreWeights","SpeakerType","DEFAULT_SPEAKER_TYPES","parse_speaker_layout","SpeakerSpec"]
