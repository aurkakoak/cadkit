"""Pure axial geometry: +X is downstream, +Y is the keyed shaft's flat side."""

from collections.abc import Iterable

import cadquery as cq
import cadkit as ck

# Extend boolean tools past a face; this is not a manufactured fit allowance.
CUTTER_OVERRUN = 0.1


def axis_frame(x: float = 0) -> ck.Frame:
    return ck.Frame((x, 0, 0), z=(1, 0, 0), x=(0, 1, 0))


def cylinder(radius: float, length: float, *, start: float = 0) -> cq.Solid:
    return cq.Solid.makeCylinder(radius, length, (start, 0, 0), (1, 0, 0))


def annulus(
    outer_radius: float,
    inner_radius: float,
    length: float,
    *,
    start: float = 0,
) -> cq.Shape:
    return cylinder(outer_radius, length, start=start).cut(
        cylinder(inner_radius, length + 2 * CUTTER_OVERRUN, start=start - CUTTER_OVERRUN)
    )


def revolve(points: Iterable[tuple[float, float]]) -> cq.Shape:
    """Turn an (axial position, radius) section around the local X axis."""
    return (
        cq.Workplane("XY")
        .polyline(list(points))
        .close()
        .revolve(
            360,
            (0, 0),
            (1, 0),
        )
        .val()
    )


def _half(shape: cq.Shape, *, upper: bool) -> cq.Shape:
    bounds = shape.BoundingBox()
    margin = CUTTER_OVERRUN
    bottom = 0 if upper else bounds.zmin - margin
    height = bounds.zmax + margin if upper else -bottom
    clip = cq.Solid.makeBox(
        bounds.xlen + 2 * margin,
        bounds.ylen + 2 * margin,
        height,
        (bounds.xmin - margin, bounds.ymin - margin, bottom),
    )
    return shape.intersect(clip).clean()


def lower_half(shape: cq.Shape) -> cq.Shape:
    return _half(shape, upper=False)


def upper_half(shape: cq.Shape) -> cq.Shape:
    return _half(shape, upper=True)


def d_shaft(radius: float, flat: float, length: float, *, start: float = 0) -> cq.Shape:
    margin = CUTTER_OVERRUN
    flat_cutter = cq.Solid.makeBox(
        length + 2 * margin,
        radius - flat + margin,
        2 * (radius + margin),
        (start - margin, flat, -radius - margin),
    )
    return cylinder(radius, length, start=start).cut(flat_cutter).clean()
