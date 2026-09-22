"""Three-arm plain-bearing blanks; the Part owns the journal hole."""

from functools import lru_cache

import cadquery as cq

from ...dimensions import ShaftFit
from ...geometry import annulus, cylinder
from .specifications import BearingSupport


@lru_cache(maxsize=None)
def bearing_blank(spec: BearingSupport, fit: ShaftFit) -> cq.Shape:
    """The front face is local X=0; the shaft runs along +X."""
    rim = annulus(spec.outer_radius, spec.outer_radius - spec.rim_wall, spec.thickness)
    hub_radius = fit.bearing_radius + spec.hub_wall
    hub = cylinder(hub_radius, spec.thickness)
    arm_start = hub_radius - spec.arm_overlap
    arm_end = spec.outer_radius - spec.arm_overlap
    arm = cq.Solid.makeBox(
        spec.thickness,
        spec.arm_width,
        arm_end - arm_start,
        (0, -spec.arm_width / 2, arm_start),
    )
    arms = [arm.rotate((0, 0, 0), (1, 0, 0), angle) for angle in spec.arm_angles]
    return rim.fuse(hub, *arms).clean()
