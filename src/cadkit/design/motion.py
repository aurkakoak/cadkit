"""Explicit scalar degrees of freedom about the attachment frame's positive Z."""
from dataclasses import dataclass
import math
import cadquery as cq


@dataclass(frozen=True)
class Rigid:
    """A connection whose parent and child datums coincide without motion.

    Args:
        kind: Relationship label; retain its default value, `rigid`.
    """
    kind: str = "rigid"

    def location(self, position=0):
        """Return the native relative Location for the given position in zero."""
        if position != 0:
            raise ValueError("Rigid connections have no motion coordinate")
        return cq.Location()

    def describe(self):
        return {"kind": self.kind}


@dataclass(frozen=True)
class Revolute:
    """One rotation about the attachment frame's positive Z axis.

    Args:
        position: Default angle in degrees.
        limits: Optional inclusive `(minimum, maximum)` angles in degrees.

    Positions outside declared limits are rejected. This is a scalar placement
    relationship, not a general constraint solver or a collision-free motion proof.
    """
    position: float = 0
    limits: tuple[float, float] | None = None

    def __post_init__(self):
        _validate(self.position, self.limits)
        if self.limits is not None:
            object.__setattr__(self, "limits", tuple(self.limits))

    @property
    def kind(self):
        return "revolute"

    def location(self, position=None):
        """Return the native relative Location for the given position in degrees."""
        position = self.position if position is None else position
        _validate(position, self.limits)
        return cq.Location((0, 0, 0), (0, 0, 1), position)

    def describe(self):
        return {"kind": self.kind, "position": self.position, "limits": self.limits, "unit": "deg"}


@dataclass(frozen=True)
class Slider(Revolute):
    """One translation along the attachment frame's positive Z axis.

    Args:
        position: Default displacement in millimetres.
        limits: Optional inclusive `(minimum, maximum)` displacements in millimetres.
    """
    @property
    def kind(self):
        return "slider"

    def location(self, position=None):
        """Return the native relative Location for the given position in millimetres."""
        position = self.position if position is None else position
        _validate(position, self.limits)
        return cq.Location((0, 0, position))

    def describe(self):
        return {"kind": self.kind, "position": self.position, "limits": self.limits, "unit": "mm"}


def _validate(position, limits):
    if not isinstance(position, (int, float)) or not math.isfinite(position):
        raise ValueError("Motion position must be finite")
    if limits is not None:
        if len(limits) != 2 or not all(math.isfinite(v) for v in limits) or limits[0] > limits[1]:
            raise ValueError("Motion limits must be ordered finite bounds")
        if not limits[0] <= position <= limits[1]:
            raise ValueError(f"Motion position {position} is outside limits {limits}")
