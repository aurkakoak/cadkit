"""Bearing-unit inputs and their mating dimensions; all lengths are millimetres."""
from dataclasses import dataclass

import cadkit as ck


@dataclass(frozen=True, kw_only=True)
class Dimensions(ck.Dimensions):
    shaft_diameter: float = ck.input(
        default=8.0, unit="mm", description="Nominal shaft diameter", gt=0,
    )
    radial_clearance: float = ck.input(
        default=0.2, unit="mm", description="Gap from the shaft surface to each journal bore", gt=0,
    )
    support_span: float = ck.input(
        default=70.0, unit="mm", description="Centre-to-centre support distance along the shaft", gt=0,
    )
    support_thickness: float = ck.input(
        default=12.0, unit="mm", description="Support thickness along the shaft axis", gt=0,
    )
    support_wall: float = ck.input(
        default=6.0, unit="mm", description="Material around the journal bore", gt=0,
    )
    shaft_overhang: float = ck.input(
        default=10.0, unit="mm", description="Shaft extension beyond each support's outer face", gt=0,
    )
    base_margin: float = ck.input(
        default=8.0, unit="mm", description="Base margin beyond the support footprint", gt=0,
    )
    base_thickness: float = ck.input(
        default=6.0, unit="mm", description="Base thickness", gt=0,
    )

    def validate(self):
        if self.support_span <= self.support_thickness:
            raise ValueError("Support centres must be farther apart than their thickness")

    @property
    def bore_diameter(self):
        return self.shaft_diameter + 2 * self.radial_clearance

    @property
    def support_width(self):
        return self.bore_diameter + 2 * self.support_wall

    @property
    def support_height(self):
        return self.support_width

    @property
    def shaft_axis_height(self):
        """Height above the support's bottom face, not above the entire assembly."""
        return self.support_height / 2

    @property
    def shaft_length(self):
        return self.support_span + self.support_thickness + 2 * self.shaft_overhang

    @property
    def base_length(self):
        return self.support_span + self.support_thickness + 2 * self.base_margin

    @property
    def base_width(self):
        return self.support_width + 2 * self.base_margin
