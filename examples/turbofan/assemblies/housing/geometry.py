"""Local housing bodies: +X downstream, split plane Z=0 through the axis."""

from functools import lru_cache

import cadquery as cq

from ...geometry import annulus, lower_half, revolve, upper_half
from ...profiles import ShellProfile
from .specifications import InletLip, NozzleSection


@lru_cache(maxsize=None)
def inlet_body(profile: InletLip) -> cq.Shape:
    """The intake datum is X=0; the two arcs form the rounded leading lip."""
    lip = (
        cq.Workplane("XY")
        .moveTo(*profile.rear_outer)
        .lineTo(*profile.forward_outer)
        .threePointArc(profile.outer_arc_mid, profile.nose_inner)
        .threePointArc(profile.inner_arc_mid, profile.throat)
        .lineTo(*profile.rear_inner)
        .close()
        .revolve(360, (0, 0), (1, 0))
        .val()
    )
    collar = annulus(
        profile.collar_outer_radius,
        profile.collar_inner_radius,
        profile.collar_length,
        start=profile.collar_start,
    )
    return lip.fuse(collar).clean()


@lru_cache(maxsize=None)
def shell_body(profile: ShellProfile, *, upper: bool = False) -> cq.Shape:
    """The leading profile station becomes the local axial origin."""
    shell = revolve(profile.polygon(origin=profile.start))
    return upper_half(shell) if upper else lower_half(shell)


@lru_cache(maxsize=None)
def nozzle_body(section: NozzleSection, *, upper: bool = False) -> cq.Shape:
    """A conical outlet whose leading annular face is at local X=0."""
    shell = revolve(section.polygon)
    return upper_half(shell) if upper else lower_half(shell)
