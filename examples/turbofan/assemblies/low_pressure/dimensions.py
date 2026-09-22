"""LP spool inputs and its fixed axial drawing stations, in millimetres."""

from dataclasses import dataclass

import cadkit as ck

from ...parts.rotor import RotorStage


@dataclass(frozen=True, kw_only=True)
class Dimensions(ck.Dimensions):
    fan_blade_count: int = ck.input(
        default=20,
        description="Number of repeated refined fan blades",
        ge=2,
    )
    coupling_tongue_width: float = ck.input(
        default=3.8,
        unit="mm",
        description="Square rear-shaft coupling tongue width",
        gt=0,
    )
    coupling_clearance: float = ck.input(
        default=0.25,
        unit="mm",
        description="Clearance at each square coupling side",
        gt=0,
    )

    @property
    def coupling_socket_width(self) -> float:
        return self.coupling_tongue_width + 2 * self.coupling_clearance


FRONT_SHAFT_START = 19.0
FRONT_SHAFT_LENGTH = 158.0
REAR_SHAFT_START = 178.0
REAR_SHAFT_LENGTH = 106.0
COUPLING_DEPTH = 10.0
COUPLING_ROOT_OVERLAP = 1.0
SPINNER_STATION = 8.0
TAILCONE_STATION = 282.0
FAN_STATION = 34.0
FAN_HUB_START = -12.0
FAN_HUB_LENGTH = 29.0
FAN_HUB_RADIUS = 15.0


FRONT_ROTOR_STAGES = (
    RotorStage(
        name="lp-compressor-1",
        station=75,
        tip_radius=34,
        blade_count=20,
        chord=9,
        stagger=33,
        sweep=3,
        hub_radius=15,
    ),
    RotorStage(
        name="lp-compressor-2",
        station=95,
        tip_radius=32,
        blade_count=22,
        chord=8,
        stagger=31,
        sweep=3,
        hub_radius=15,
    ),
)
REAR_ROTOR_STAGES = (
    RotorStage(
        name="lp-turbine-1",
        station=247,
        tip_radius=29.5,
        blade_count=24,
        chord=8,
        stagger=-29,
        sweep=3,
        hub_radius=15,
    ),
    RotorStage(
        name="lp-turbine-2",
        station=265,
        tip_radius=31,
        blade_count=26,
        chord=7,
        stagger=-31,
        sweep=3,
        hub_radius=15,
    ),
)


@dataclass(frozen=True, kw_only=True)
class Spacer:
    name: str
    station: float
    length: float
    outer_radius: float = 8.0


FAN_REAR_SPACER = Spacer(name="fan-rear-spacer", station=52.1, length=4.4)
STAGE_SPACER = Spacer(name="lp-stage-spacer", station=85.6, length=4.3)
