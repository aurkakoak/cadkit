"""Stationary-core layout and named section data; lengths are millimetres."""

from dataclasses import dataclass

from ...dimensions import (
    HIGH_PRESSURE_FRONT_JOURNAL,
    HIGH_PRESSURE_REAR_JOURNAL,
    LOW_PRESSURE_FRONT_JOURNAL,
    LOW_PRESSURE_REAR_JOURNAL,
)
from ...profiles import CORE_LINER


@dataclass(frozen=True, kw_only=True)
class CoreLayout:
    liner: float = CORE_LINER.start
    combustor: float = 174.0
    front_support: float = 63.0
    rear_support: float = 266.0
    front_bearing: float = LOW_PRESSURE_FRONT_JOURNAL
    rear_bearing: float = LOW_PRESSURE_REAR_JOURNAL
    hp_front_bearing: float = HIGH_PRESSURE_FRONT_JOURNAL
    hp_rear_bearing: float = HIGH_PRESSURE_REAR_JOURNAL


@dataclass(frozen=True, kw_only=True)
class BearingSupport:
    """A three-arm bearing; angles are degrees from +Z about the +X axis."""

    name: str
    station: float
    outer_radius: float
    thickness: float = 4.0
    rim_wall: float = 2.5
    hub_wall: float = 3.0
    arm_width: float = 3.0
    arm_overlap: float = 1.0
    arm_angles: tuple[float, ...] = (0.0, 120.0, 240.0)


@dataclass(frozen=True, kw_only=True)
class GuideRow:
    """Lower guide vanes; angles are degrees from +Z about the +X axis."""

    name: str
    station: float
    outer_radius: float
    thickness: float = 3.0
    rim_wall: float = 2.2
    hub_radius: float = 11.0
    shaft_clearance: float = 0.75  # Gap beyond the HP shaft's circular envelope.
    vane_width: float = 1.8
    vane_overlap: float = 1.0
    vane_angles: tuple[float, ...] = (110.0, 135.0, 160.0, 185.0, 210.0, 235.0, 260.0)


@dataclass(frozen=True, kw_only=True)
class BypassSupport:
    """Engine stations and lower ribs, angled in degrees from +Z about +X."""

    station: float
    thickness: float = 4.0
    collar_wall: float = 2.0
    rib_width: float = 3.0
    rib_angles: tuple[float, ...] = (120.0, 180.0, 240.0)

    @property
    def end(self) -> float:
        return self.station + self.thickness


@dataclass(frozen=True, kw_only=True)
class CombustorHoleRow:
    station: float
    radius: float


@dataclass(frozen=True, kw_only=True)
class CombustorDetails:
    """Engine stations; radial hole angles run from +Y toward +Z in degrees."""

    band_stations: tuple[float, ...] = (178.0, 188.0, 208.0)
    band_width: float = 1.8
    band_inner_radius: float = 27.5
    hole_rows: tuple[CombustorHoleRow, ...] = (
        CombustorHoleRow(station=181.0, radius=2.0),
        CombustorHoleRow(station=192.0, radius=2.5),
        CombustorHoleRow(station=203.0, radius=3.0),
    )
    hole_angles: tuple[float, ...] = (205.0, 235.0, 265.0, 295.0, 325.0, 355.0)
    hole_start_radius: float = 22.0
    hole_length: float = 12.0


CORE_LAYOUT = CoreLayout()
FRONT_BEARING = BearingSupport(
    name="front-bearing-spider",
    station=CORE_LAYOUT.front_bearing,
    outer_radius=36.4,
)
REAR_BEARING = BearingSupport(
    name="rear-bearing-spider",
    station=CORE_LAYOUT.rear_bearing,
    outer_radius=33.3,
)
HP_FRONT_BEARING = BearingSupport(
    name="hp-front-bearing",
    station=CORE_LAYOUT.hp_front_bearing,
    outer_radius=32.8,
)
HP_REAR_BEARING = BearingSupport(
    name="hp-rear-bearing",
    station=CORE_LAYOUT.hp_rear_bearing,
    outer_radius=31.3,
)
GUIDE_ROWS = (
    GuideRow(name="lp-guide-1", station=86.0, outer_radius=35.0),
    GuideRow(name="diffuser-guide", station=106.0, outer_radius=33.5),
    GuideRow(name="hp-guide-1", station=132.5, outer_radius=30.25),
    GuideRow(name="hp-guide-2", station=151.0, outer_radius=28.05),
    GuideRow(name="turbine-guide", station=238.0, outer_radius=31.4),
)
FRONT_SUPPORT = BypassSupport(station=CORE_LAYOUT.front_support)
REAR_SUPPORT = BypassSupport(station=CORE_LAYOUT.rear_support)
COMBUSTOR_DETAILS = CombustorDetails()

# (Local axial station, radius), walking the outer wall then the inner return.
COMBUSTOR_SECTION = (
    (0.0, 28.0),
    (7.0, 29.0),
    (31.0, 29.0),
    (38.0, 27.0),
    (38.0, 24.5),
    (31.0, 26.5),
    (7.0, 26.5),
    (0.0, 25.5),
)
