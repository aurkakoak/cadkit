"""Explicit fit allowances and measured hardware interfaces for printed parts."""

from dataclasses import dataclass
import cadquery as cq
from .geometry import cylinder, difference, translate


@dataclass(frozen=True)
class Bore:
    """A nominal circular interface with an explicit diametral print allowance.

    Args:
        nominal_diameter: Mating diameter in millimetres.
        diametral_allowance: Added to diameter, not radius, in millimetres.
            Negative values make a smaller bore; final diameter must be positive.
    """
    nominal_diameter: float
    diametral_allowance: float = 0.2

    def __post_init__(self):
        if self.nominal_diameter <= 0 or self.diameter <= 0:
            raise ValueError("Nominal and effective bore diameters must be positive")

    @property
    def diameter(self):
        return self.nominal_diameter + self.diametral_allowance

    def cutter(self, height, *, at=(0, 0, 0)):
        """Return a native bore cutter along +Z.

        Args:
            height (float): Cutter height in millimetres.
            at (tuple): XYZ bottom position in millimetres.

        Returns:
            (cq.Shape): Cylindrical cutting solid.
        """
        return translate([cylinder(h=height, d=self.diameter)], at)


@dataclass(frozen=True)
class Countersink:
    """A standalone conical cutter described by its throat, head, and full angle.

    Args:
        through_diameter: Throat diameter in millimetres.
        head_diameter: Head diameter in millimetres, greater than the throat.
        included_angle: Full cone angle in degrees, strictly between 0 and 180.
    """
    through_diameter: float
    head_diameter: float
    included_angle: float = 90

    @property
    def depth(self):
        import math

        if (
            self.head_diameter <= self.through_diameter
            or self.through_diameter <= 0
            or not 0 < self.included_angle < 180
        ):
            raise ValueError(
                "Countersink requires head > throat > 0 and an included angle between 0 and 180"
            )
        return (self.head_diameter - self.through_diameter) / (
            2 * math.tan(math.radians(self.included_angle / 2))
        )

    def cutter(self, top_z, *, at=(0, 0), overlap=0.05):
        """Return a cone with its nominal mouth at an explicit world Z plane.

        Args:
            top_z (float): Nominal mouth plane in millimetres.
            at (tuple): XY position of the cone axis in millimetres.
            overlap (float): Extra cone height in millimetres to clear the entry face.

        Returns:
            (cq.Shape): Native conical cutter. This cutter does not include the throat hole.
        """
        return translate(
            [
                cylinder(
                    h=self.depth + overlap,
                    d1=self.through_diameter,
                    d2=self.head_diameter,
                )
            ],
            (*at, top_z - self.depth),
        )


def fit_coupon(
    nominal_diameter, allowances=(-0.1, 0, 0.1, 0.2, 0.3), *, height=6, wall=3
):
    """Build an ordered ladder of bores for testing real manufactured fit.

    Args:
        nominal_diameter (float): Nominal mating diameter in millimetres.
        allowances (tuple): Nonempty sequence of diametral allowances in millimetres.
        height (float): Positive block thickness in millimetres.
        wall (float): Positive surrounding wall allowance in millimetres.

    Returns:
        (cq.Shape): Native block at positive XYZ with bores ordered along +X.

    Record the position-to-allowance mapping in the Part's notes; geometry has
    no engraved labels. Print using the intended material and process settings.
    """
    if not allowances:
        raise ValueError("A fit coupon requires at least one allowance")
    pitch = nominal_diameter + max(allowances) + 2 * wall
    if wall <= 0 or height <= 0:
        raise ValueError("Coupon wall and height must be positive")
    block = (
        cq.Workplane("XY")
        .box(pitch * len(allowances), pitch, height, centered=(False, False, False))
        .val()
    )
    tools = [
        Bore(nominal_diameter, a).cutter(
            height + 0.2, at=(pitch * (i + 0.5), pitch / 2, -0.1)
        )
        for i, a in enumerate(allowances)
    ]
    return difference([block, *tools])
