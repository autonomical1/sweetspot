"""Deterministic rectangular-room placement for offline development."""
import math


def _clamp(value: float, upper: float) -> float:
    return min(max(value, 1.0), max(1.0, upper - 1.0))


def _metrics() -> dict:
    return {"score": 0.5, "reflections": [], "treatment_patches": [], "sub_modes": {}, "warnings": ["stub engine"]}


def optimize(room: dict, options: dict | None = None) -> dict:
    dims = room["dimensions"]
    width, length, height = (dims[key] for key in ("width", "length", "height"))
    listener = room["listener"]["position"]
    fx, fz = room["listener"]["facing"]
    magnitude = math.hypot(fx, fz) or 1.0
    fx, fz = fx / magnitude, fz / magnitude
    left = (fz, -fx)
    distance = min(width, length) * 0.3

    def point(forward: float, side: float, y: float) -> list[float]:
        return [_clamp(listener[0] + fx * forward + left[0] * side, width),
                _clamp(y, height),
                _clamp(listener[2] + fz * forward + left[1] * side, length)]

    front = distance * math.cos(math.radians(30))
    side = distance * math.sin(math.radians(30))
    rear = distance * math.cos(math.radians(110))
    rear_side = distance * math.sin(math.radians(110))
    positions = {"L": point(front, side, 3.6), "R": point(front, -side, 3.6),
                 "C": point(distance, 0, 3.6), "Ls": point(rear, rear_side, 5),
                 "Rs": point(rear, -rear_side, 5)}
    horizontal = abs(fx) >= abs(fz)
    wall_id = ("wall_e" if fx > 0 else "wall_w") if horizontal else ("wall_s" if fz > 0 else "wall_n")
    wall_distance = (width - listener[0] if fx > 0 else listener[0]) if horizontal else (length - listener[2] if fz > 0 else listener[2])  # noqa: E501  # preserve behavior while retaining the existing expression
    positions["LFE"] = point(max(1.0, wall_distance - 1), max(1.0, min(width, length) / 3), 3.6)
    screen_width = 2 * wall_distance * math.tan(math.radians(18))
    center = [width if fx > 0 else 0.0, 4.5, listener[2]] if horizontal else [listener[0], 4.5, length if fz > 0 else 0.0]  # noqa: E501  # preserve behavior while retaining the existing expression
    speakers = [{"role": role, "position": positions[role], "aim": listener} for role in ("L", "R", "C", "LFE", "Ls", "Rs")]  # noqa: E501  # preserve behavior while retaining the existing expression
    return {"layout": {"speakers": speakers, "screen": {"wall_id": wall_id, "center": center,
            "width": screen_width, "height": screen_width * 9 / 16}}, "metrics": _metrics()}


def score(room: dict, layout: dict) -> dict:
    return {"metrics": _metrics()}
