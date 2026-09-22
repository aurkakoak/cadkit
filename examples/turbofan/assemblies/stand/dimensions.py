"""Display-stand inputs in millimetres, with X measured from the engine intake."""

from dataclasses import dataclass

import cadkit as ck

# Fixed stations of the 300 mm display layout, not a second engine profile.
BASE_CENTRE_X = 150.0
FRONT_SADDLE_X = 57.0
REAR_SADDLE_X = 249.0


@dataclass(frozen=True, kw_only=True)
class StandDimensions(ck.Dimensions):
    base_length: float = ck.input(
        default=320.0,
        unit="mm",
        description="Base length along the engine axis",
        gt=0,
    )
    base_width: float = ck.input(
        default=150.0,
        unit="mm",
        description="Base width across the engine",
        gt=0,
    )
    base_thickness: float = ck.input(
        default=8.0,
        unit="mm",
        description="Base thickness above its bottom face",
        gt=0,
    )
    corner_radius: float = ck.input(
        default=9.0,
        unit="mm",
        description="Radius of the base's four plan-view corners",
        gt=0,
    )
    saddle_thickness: float = ck.input(
        default=8.0,
        unit="mm",
        description="Saddle thickness along the engine axis",
        gt=0,
    )
    saddle_width: float = ck.input(
        default=40.0,
        unit="mm",
        description="Saddle width across the nacelle",
        gt=0,
    )
    socket_clearance: float = ck.input(
        default=0.25,
        unit="mm",
        description="Clearance on each side of the saddle tenon",
        gt=0,
    )
    socket_floor: float = ck.input(
        default=3.0,
        unit="mm",
        description="Base material below each saddle socket",
        gt=0,
    )

    def validate(self):
        if self.corner_radius >= min(self.base_length, self.base_width) / 2:
            raise ValueError("Base corner radius must fit within its length and width")
        if self.socket_floor >= self.base_thickness:
            raise ValueError("Socket floor must leave a recess in the base")
        if self.socket_width >= self.base_width:
            raise ValueError("Saddle sockets must fit inside the base width")
        for station in (FRONT_SADDLE_X, REAR_SADDLE_X):
            if abs(station - BASE_CENTRE_X) + self.socket_length / 2 >= self.base_length / 2:
                raise ValueError("Saddle sockets must fit inside the base length")

    @property
    def socket_length(self) -> float:
        return self.saddle_thickness + 2 * self.socket_clearance

    @property
    def socket_width(self) -> float:
        return self.saddle_width + 2 * self.socket_clearance
