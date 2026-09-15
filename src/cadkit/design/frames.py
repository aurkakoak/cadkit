"""Named manufacturing datums backed by CadQuery locations; millimetres."""
from dataclasses import dataclass
import math
import re
import cadquery as cq
from ..fasteners import vector


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise ValueError(f"Expected a stable name without path separators: {value!r}")
    return value


def positive(value, label):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be positive and finite")


@dataclass(frozen=True)
class Frame:
    origin: tuple = (0, 0, 0)
    z: tuple = (0, 0, 1)
    x: tuple = (1, 0, 0)

    def __post_init__(self):
        for key in ("origin", "z", "x"):
            object.__setattr__(self, key, vector(getattr(self, key), key, unit=key != "origin"))
        if abs(sum(a*b for a, b in zip(self.x, self.z))) > 1e-9:
            raise ValueError("Frame x and z axes must be perpendicular")

    @property
    def location(self):
        return cq.Location(cq.Plane(self.origin, xDir=self.x, normal=self.z))

    @classmethod
    def from_location(cls, location):
        plane = location.plane
        return cls(plane.origin.toTuple(), plane.zDir.toTuple(), plane.xDir.toTuple())

    def describe(self):
        return {"origin": self.origin, "z": self.z, "x": self.x}


@dataclass(frozen=True)
class PolarPattern:
    radius: float
    angles: tuple[float, ...]

    def __post_init__(self):
        positive(self.radius, "Pattern radius")
        angles = tuple(float(a) for a in self.angles)
        if not angles or not all(math.isfinite(a) for a in angles):
            raise ValueError("Pattern needs finite angles")
        if any(abs((a-b+180) % 360-180) < 1e-9 for i, a in enumerate(angles) for b in angles[:i]):
            raise ValueError("Pattern sites must be distinct")
        object.__setattr__(self, "angles", angles)

    @property
    def points(self):
        return tuple((self.radius*math.cos(math.radians(a)), self.radius*math.sin(math.radians(a)))
                     for a in self.angles)

    def describe(self):
        return {"kind": "polar", "radius": self.radius, "angles": self.angles}


@dataclass(frozen=True)
class PointPattern:
    """Explicit sites in a feature's local XY plane, in millimetres."""
    points: tuple[tuple[float, float], ...] = ((0, 0),)

    def __post_init__(self):
        points = tuple(tuple(float(v) for v in point) for point in self.points)
        if not points or any(len(point) != 2 or not all(math.isfinite(v) for v in point) for point in points):
            raise ValueError("Pattern needs finite XY points")
        if len(set(points)) != len(points):
            raise ValueError("Pattern sites must be distinct")
        object.__setattr__(self, "points", points)

    def describe(self):
        return {"kind": "points", "points": self.points}
