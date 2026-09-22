"""Open stationary vane rows, each built from its own leading face at X=0."""

from functools import lru_cache

import cadquery as cq

from ...dimensions import ShaftFit
from ...geometry import annulus, lower_half
from .specifications import GuideRow


@lru_cache(maxsize=None)
def guide_body(spec: GuideRow, hp_fit: ShaftFit) -> cq.Shape:
    rim = lower_half(
        annulus(
            spec.outer_radius,
            spec.outer_radius - spec.rim_wall,
            spec.thickness,
        )
    )
    inner = lower_half(
        annulus(
            spec.hub_radius,
            hp_fit.shaft_radius + spec.shaft_clearance,
            spec.thickness,
        )
    )
    vane_start = spec.hub_radius - spec.vane_overlap
    vane_end = spec.outer_radius - spec.vane_overlap
    vane = cq.Solid.makeBox(
        spec.thickness,
        spec.vane_width,
        vane_end - vane_start,
        (0, -spec.vane_width / 2, vane_start),
    )
    vanes = [vane.rotate((0, 0, 0), (1, 0, 0), angle) for angle in spec.vane_angles]
    return rim.fuse(inner, *vanes).clean()
