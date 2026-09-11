"""Explicit fit allowances and measured hardware interfaces for printed parts."""

from dataclasses import dataclass
import cadquery as cq
from .geometry import cylinder, difference, translate


@dataclass(frozen=True)
class Bore:
    nominal_diameter: float
    diametral_allowance: float = 0.2

    def __post_init__(self):
        if self.nominal_diameter <= 0 or self.diameter <= 0:
            raise ValueError("Nominal and effective bore diameters must be positive")

    @property
    def diameter(self):
        return self.nominal_diameter + self.diametral_allowance

    def cutter(self, height, *, at=(0, 0, 0)):
        return translate([cylinder(h=height, d=self.diameter)], at)


@dataclass(frozen=True)
class Countersink:
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
    """Ordered bore ladder; map positions to allowances in the part's notes."""
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
