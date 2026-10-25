"""Shared room/layout contract (docs/API.md sections 1-2)."""
from typing import Literal

from pydantic import BaseModel, Field

Vec3 = list[float]
SurfaceKind = Literal["wall", "floor", "ceiling", "door", "window", "opening"]
Material = Literal["drywall", "glass", "brick", "carpet", "hardwood", "tile", "curtain", "unknown"]
Role = Literal["L", "R", "C", "LFE", "Ls", "Rs", "Lss", "Rss", "Lrs", "Rrs",
               "Ltf", "Rtf", "Ltr", "Rtr", "Ltm", "Rtm", "LFE2"]


class Dimensions(BaseModel):
    width: float
    length: float
    height: float = 9.0  # feet


class Surface(BaseModel):
    id: str
    kind: SurfaceKind
    polygon: list[Vec3]
    material: Material = "drywall"
    absorption: dict[str, float] = Field(default_factory=dict)


class RoomObject(BaseModel):
    id: str
    category: str
    center: Vec3
    size: Vec3
    rotation_y: float = 0.0  # degrees about +y; world = center + R_y(rotation_y) * local


class Frame(BaseModel):
    """Room frame -> scan world frame: world_ft = R_y(yaw_deg) * room_ft + offset (see docs/API.md)."""
    yaw_deg: float = 0.0
    offset: Vec3 = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class Listener(BaseModel):
    position: Vec3
    facing: list[float]  # unit vector [fx, fz]; north = [0, -1]; positions are decimal feet


class Room(BaseModel):
    schema_version: int = 1
    units: Literal["ft"] = "ft"
    room_id: str
    session_id: str | None = None
    source: Literal["rectangle", "roomplan"] = "rectangle"
    dimensions: Dimensions
    surfaces: list[Surface]
    objects: list[RoomObject] = Field(default_factory=list)
    listener: Listener
    budget: float | None = None
    warnings: list[str] = Field(default_factory=list)  # e.g. converter notes such as 'no sofa detected'
    frame: Frame | None = None  # scanned rooms only; None = the room frame is the only frame
    captured_room: dict | None = None


class Speaker(BaseModel):
    role: Role
    position: Vec3
    aim: Vec3
    yaw_deg: float | None = None
    pitch_deg: float | None = None
    size: dict[str, float] | None = None
    mount: Literal["on_wall", "in_wall", "on_ceiling", "floor", "stand"] | None = None
    model_id: str | None = None
    distance_ft: float | None = None
    receiver_delay_ms: float | None = None
    receiver_trim_db: float | None = None
    compliance: dict | None = None


class Screen(BaseModel):
    wall_id: str
    center: Vec3
    width: float
    height: float


class Layout(BaseModel):
    speakers: list[Speaker]
    screen: Screen | None = None
    preset: str | None = None
    standard: str | None = None
    stage: Literal["quick", "refining", "refined"] | None = None
    seats: list[dict] | None = None
    projector: dict | None = None


class LayoutResult(BaseModel):
    layout: Layout
    metrics: dict = Field(default_factory=dict)
