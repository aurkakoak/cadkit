"""Bearing-unit solids and manufacturing definitions; no installed positions."""
from dataclasses import dataclass
from functools import partial

import cadquery as cq
import cadkit as ck

from .dimensions import Dimensions


def base_body(dimensions: Dimensions):
    """The base's origin is the centre of its bottom face."""
    return cq.Workplane("XY").box(
        dimensions.base_length,
        dimensions.base_width,
        dimensions.base_thickness,
        centered=(True, True, False),
    )


def support_blank(dimensions: Dimensions):
    """An unbored block, centred in X/Y with its bottom at local Z=0."""
    return cq.Workplane("XY").box(
        dimensions.support_thickness,
        dimensions.support_width,
        dimensions.support_height,
        centered=(True, True, False),
    )


def shaft_body(dimensions: Dimensions):
    """The shaft starts at its left end and extends along local +X."""
    return cq.Solid.makeCylinder(
        dimensions.shaft_diameter / 2,
        dimensions.shaft_length,
        (0, 0, 0),
        (1, 0, 0),
    )


@dataclass(frozen=True)
class ShaftSupportParts:
    base: ck.Part
    support: ck.Part
    shaft: ck.Part


def make_parts(dimensions: Dimensions) -> ShaftSupportParts:
    # This entry frame cuts the bore and later locates the shaft's journal.
    # Feature +Z points into the block, which is assembly +X here.
    journal_entry = ck.Frame(
        (-dimensions.support_thickness / 2, 0, dimensions.shaft_axis_height),
        z=(1, 0, 0),
        x=(0, 1, 0),
    )
    base = ck.Part(
        "base",
        body=partial(base_body, dimensions),
        manufacture=ck.FDM("PETG"),
        group="stationary",
        ports={
            "left-support": ck.Frame(
                (-dimensions.support_span / 2, 0, dimensions.base_thickness)
            ),
            "right-support": ck.Frame(
                (dimensions.support_span / 2, 0, dimensions.base_thickness)
            ),
        },
    )
    support = ck.Part(
        "support",
        body=partial(support_blank, dimensions),
        manufacture=ck.FDM("PETG", print_rotation=(0, 90, 0)),
        group="stationary",
        features={
            "journal": ck.Hole(
                diameter=dimensions.bore_diameter,
                depth=dimensions.support_thickness,
                at=journal_entry,
                through=True,
            ),
        },
        ports={"base": ck.Frame()},
    )
    shaft = ck.Part(
        "shaft",
        body=partial(shaft_body, dimensions),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="rotating",
        ports={
            "journal": ck.Frame(
                (dimensions.shaft_overhang, 0, 0), z=(1, 0, 0), x=(0, 1, 0)
            ),
        },
    )
    return ShaftSupportParts(base=base, support=support, shaft=shaft)
