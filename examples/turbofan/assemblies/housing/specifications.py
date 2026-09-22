"""Housing layout and contour data; axial positions and radii are millimetres."""

from dataclasses import dataclass

from ...profiles import FRONT_NACELLE, REAR_NACELLE


@dataclass(frozen=True, kw_only=True)
class HousingLayout:
    inlet: float = 0.0
    front_shell: float = FRONT_NACELLE.start
    rear_shell: float = REAR_NACELLE.start
    nozzle: float = REAR_NACELLE.end + 1.0  # Axial gap between shell and nozzle.

    @property
    def front_cover(self) -> float:
        return self.front_shell

    @property
    def rear_cover(self) -> float:
        return self.rear_shell

    @property
    def nozzle_cover(self) -> float:
        return self.nozzle


@dataclass(frozen=True, kw_only=True)
class InletLip:
    """Named (axial position, radius) points on the rounded intake section."""

    rear_outer: tuple[float, float] = (18.0, 71.0)
    forward_outer: tuple[float, float] = (7.0, 71.0)
    outer_arc_mid: tuple[float, float] = (0.0, 68.0)
    nose_inner: tuple[float, float] = (1.5, 65.0)
    inner_arc_mid: tuple[float, float] = (4.0, 63.2)
    throat: tuple[float, float] = (8.0, 64.0)
    rear_inner: tuple[float, float] = (18.0, 65.0)
    collar_start: float = 17.8
    collar_length: float = 5.2
    collar_outer_radius: float = 68.0
    collar_inner_radius: float = 65.0


@dataclass(frozen=True, kw_only=True)
class NozzleSection:
    length: float = 22.0
    inlet_outer_radius: float = REAR_NACELLE.stations[-1].outer_radius
    inlet_inner_radius: float = REAR_NACELLE.stations[-1].inner_radius
    outlet_outer_radius: float = 28.0
    outlet_wall: float = 2.5

    @property
    def polygon(self) -> tuple[tuple[float, float], ...]:
        return (
            (0, self.inlet_outer_radius),
            (self.length, self.outlet_outer_radius),
            (self.length, self.outlet_outer_radius - self.outlet_wall),
            (0, self.inlet_inner_radius),
        )


HOUSING_LAYOUT = HousingLayout()
INLET_LIP = InletLip()
NOZZLE_SECTION = NozzleSection()
