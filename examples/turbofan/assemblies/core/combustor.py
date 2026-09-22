"""Local combustor shell, seating bands and radial dilution holes."""

from functools import lru_cache
import math

import cadquery as cq

from ...geometry import annulus, lower_half, revolve
from ...profiles import ShellProfile
from .specifications import CombustorDetails


@lru_cache(maxsize=None)
def combustor_body(
    section: tuple[tuple[float, float], ...],
    details: CombustorDetails,
    core: ShellProfile,
    station: float,
) -> cq.Shape:
    """The inlet face is X=0; installed stations only sample shared seat radii."""
    shell = lower_half(revolve(section))
    bands = [
        lower_half(
            annulus(
                core.inner_radius_at(x),
                details.band_inner_radius,
                details.band_width,
                start=x - station,
            )
        )
        for x in details.band_stations
    ]
    body = shell.fuse(*bands).clean()
    for row in details.hole_rows:
        for angle in details.hole_angles:
            radians = math.radians(angle)
            direction = cq.Vector(0, math.cos(radians), math.sin(radians))
            hole = cq.Solid.makeCylinder(
                row.radius,
                details.hole_length,
                (
                    row.station - station,
                    details.hole_start_radius * direction.y,
                    details.hole_start_radius * direction.z,
                ),
                direction,
            )
            body = body.cut(hole)
    return body.clean()
