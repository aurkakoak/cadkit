"""Inputs shared by the shafts, their mating parts and the display stand."""

from dataclasses import dataclass

import cadkit as ck


@dataclass(frozen=True, kw_only=True)
class ShaftFit(ck.Dimensions):
    shaft_diameter: float = ck.input(
        default=8.8,
        unit="mm",
        description="D-shaft major diameter",
        gt=0,
    )
    shaft_flat: float = ck.input(
        default=3.6,
        unit="mm",
        description="Axis-to-flat distance toward +Y",
        gt=0,
    )
    radial_clearance: float = ck.input(
        default=0.25,
        unit="mm",
        description="Allowance at both the keyed bore's circle and flat",
        gt=0,
    )
    journal_clearance: float = ck.input(
        default=0.45,
        unit="mm",
        description="Radial allowance in the plain bearing",
        gt=0,
    )

    def validate(self):
        if self.shaft_flat >= self.shaft_radius:
            raise ValueError("The shaft flat must lie inside its circular envelope")

    @property
    def shaft_radius(self) -> float:
        return self.shaft_diameter / 2

    @property
    def bore_radius(self) -> float:
        return self.shaft_radius + self.radial_clearance

    @property
    def bore_diameter(self) -> float:
        return 2 * self.bore_radius

    @property
    def bore_flat(self) -> float:
        return self.shaft_flat + self.radial_clearance

    @property
    def bearing_radius(self) -> float:
        return self.shaft_radius + self.journal_clearance


@dataclass(frozen=True, kw_only=True)
class EngineDimensions(ck.Dimensions):
    axis_height: float = ck.input(
        default=108.0,
        unit="mm",
        description="Engine axis above the bottom of the display base",
        gt=0,
    )
    concentric_clearance: float = ck.input(
        default=0.65,
        unit="mm",
        description="Radial gap between the LP shaft and HP sleeve",
        gt=0,
    )


LOW_PRESSURE_FIT = ShaftFit()
HIGH_PRESSURE_FIT = ShaftFit(shaft_diameter=14.8, shaft_flat=6.4)

# Bearing entry planes measured downstream from the inlet; shafts expose
# matching local journal datums so the assembly does not repeat these stations.
LOW_PRESSURE_FRONT_JOURNAL = 57.0
LOW_PRESSURE_REAR_JOURNAL = 276.0
HIGH_PRESSURE_FRONT_JOURNAL = 111.0
HIGH_PRESSURE_REAR_JOURNAL = 232.5

# Minimum accepted gap is this far below each designed nominal clearance, in mm.
MEASUREMENT_ALLOWANCE = 0.01
