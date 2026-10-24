"""Shared room/layout contract (docs/API.md sections 1-2)."""
from typing import Literal

from pydantic import BaseModel, Field

Vec3 = list[float]
SurfaceKind = Literal["wall", "floor", "ceiling", "door", "window", "opening"]
Material = Literal["drywall", "glass", "brick", "carpet", "hardwood", "tile", "curtain", "unknown"]
Role = Literal["L", "R", "C", "LFE", "Ls", "Rs"]


class Dimensions(BaseModel):
    width: float
    length: float
    height: float = 2.7


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
    rotation_y: float = 0.0


class Listener(BaseModel):
    position: Vec3
    facing: list[float]  # unit vector [fx, fz]; north = [0, -1]


class Room(BaseModel):
    schema_version: int = 1
    room_id: str
    session_id: str | None = None
    source: Literal["rectangle", "roomplan"] = "rectangle"
    dimensions: Dimensions
    surfaces: list[Surface]
    objects: list[RoomObject] = Field(default_factory=list)
    listener: Listener
    budget: float | None = None
    captured_room: dict | None = None


class Speaker(BaseModel):
    role: Role
    position: Vec3
    aim: Vec3


class Screen(BaseModel):
    wall_id: str
    center: Vec3
    width: float
    height: float


class Layout(BaseModel):
    speakers: list[Speaker]
    screen: Screen | None = None


class LayoutResult(BaseModel):
    layout: Layout
    metrics: dict = Field(default_factory=dict)
