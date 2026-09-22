"""Bypass seats derived from the authoritative core and nacelle surfaces."""

from functools import lru_cache

import cadquery as cq

from ...geometry import lower_half, revolve
from ...profiles import ShellProfile
from .specifications import BypassSupport


def seat_stations(spec: BypassSupport, core: ShellProfile, nacelle: ShellProfile):
    """Include every profile break so tapered contact faces remain exact."""
    return tuple(
        sorted(
            set(core.stations_between(spec.station, spec.end))
            | set(nacelle.stations_between(spec.station, spec.end))
        )
    )


@lru_cache(maxsize=None)
def front_support_body(
    spec: BypassSupport,
    core: ShellProfile,
    nacelle: ShellProfile,
) -> cq.Shape:
    """Three lower ribs bridge two collars; the leading face is local X=0."""
    stations = seat_stations(spec, core, nacelle)
    outer = tuple((x - spec.station, nacelle.inner_radius_at(x)) for x in stations)
    inner = tuple((x - spec.station, core.outer_radius_at(x)) for x in stations)
    domain = revolve(outer + tuple(reversed(inner)))
    inner_collar = revolve(
        tuple((x, radius + spec.collar_wall) for x, radius in inner) + tuple(reversed(inner))
    )
    outer_collar = revolve(
        outer + tuple((x, radius - spec.collar_wall) for x, radius in reversed(outer))
    )
    # Extend a rib to the outer contact surface, then trim it to the bypass.
    rib_reach = max(radius for _, radius in outer)
    rib_blank = cq.Solid.makeBox(
        spec.thickness,
        spec.rib_width,
        rib_reach,
        (0, -spec.rib_width / 2, 0),
    )
    ribs = [
        rib_blank.rotate((0, 0, 0), (1, 0, 0), angle).intersect(domain) for angle in spec.rib_angles
    ]
    return lower_half(inner_collar.fuse(outer_collar, *ribs))


@lru_cache(maxsize=None)
def rear_support_body(
    spec: BypassSupport,
    core: ShellProfile,
    nacelle: ShellProfile,
) -> cq.Shape:
    """A continuous lower seat across the narrowing aft bypass duct."""
    stations = seat_stations(spec, core, nacelle)
    outer = tuple((x - spec.station, nacelle.inner_radius_at(x)) for x in stations)
    inner = tuple((x - spec.station, core.outer_radius_at(x)) for x in reversed(stations))
    return lower_half(revolve(outer + inner))
