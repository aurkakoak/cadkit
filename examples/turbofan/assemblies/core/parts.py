"""Stationary manufactured parts, with geometry local to each leading face."""

from dataclasses import dataclass
from functools import partial

import cadkit as ck

from ...dimensions import ShaftFit
from ...geometry import axis_frame
from ...profiles import CORE_LINER, FRONT_NACELLE, REAR_NACELLE
from .bearings import bearing_blank
from .combustor import combustor_body
from .guides import guide_body
from .liner import liner_body
from .specifications import (
    COMBUSTOR_DETAILS,
    COMBUSTOR_SECTION,
    CORE_LAYOUT,
    FRONT_BEARING,
    FRONT_SUPPORT,
    GUIDE_ROWS,
    HP_FRONT_BEARING,
    HP_REAR_BEARING,
    REAR_BEARING,
    REAR_SUPPORT,
    GuideRow,
)
from .supports import front_support_body, rear_support_body


@dataclass(frozen=True)
class CoreParts:
    liner: ck.Part
    combustor: ck.Part
    front_bearing: ck.Part
    rear_bearing: ck.Part
    hp_front_bearing: ck.Part
    hp_rear_bearing: ck.Part
    front_support: ck.Part
    rear_support: ck.Part
    guides: tuple[tuple[GuideRow, ck.Part], ...]


def make_parts(lp_fit: ShaftFit, hp_fit: ShaftFit) -> CoreParts:
    liner = ck.Part(
        "core-cutaway",
        body=partial(liner_body, CORE_LINER),
        manufacture=ck.FDM("PLA", print_rotation=(90, 0, 0)),
        group="Static core",
        ports={"axis": axis_frame()},
        description="Lower core housing separating the core and bypass streams",
    )
    combustor = ck.Part(
        "combustor-liner",
        body=partial(
            combustor_body,
            COMBUSTOR_SECTION,
            COMBUSTOR_DETAILS,
            CORE_LINER,
            CORE_LAYOUT.combustor,
        ),
        manufacture=ck.FDM("PLA", print_rotation=(90, 0, 0)),
        group="Combustor",
        ports={"axis": axis_frame()},
        description="Perforated lower combustor with three core-seating bands",
    )
    front_bearing = ck.Part(
        FRONT_BEARING.name,
        body=partial(bearing_blank, FRONT_BEARING, lp_fit),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="Static core",
        features={
            "journal": ck.Hole(
                diameter=2 * lp_fit.bearing_radius,
                depth=FRONT_BEARING.thickness,
                at=axis_frame(),
                through=True,
            )
        },
        description="Front three-arm LP plain bearing",
    )
    rear_bearing = ck.Part(
        REAR_BEARING.name,
        body=partial(bearing_blank, REAR_BEARING, lp_fit),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="Static core",
        features={
            "journal": ck.Hole(
                diameter=2 * lp_fit.bearing_radius,
                depth=REAR_BEARING.thickness,
                at=axis_frame(),
                through=True,
            )
        },
        description="Rear three-arm LP plain bearing",
    )
    hp_front_bearing = ck.Part(
        HP_FRONT_BEARING.name,
        body=partial(bearing_blank, HP_FRONT_BEARING, hp_fit),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="Static core",
        features={
            "journal": ck.Hole(
                diameter=2 * hp_fit.bearing_radius,
                depth=HP_FRONT_BEARING.thickness,
                at=axis_frame(),
                through=True,
            )
        },
        description="Front three-arm HP sleeve bearing",
    )
    hp_rear_bearing = ck.Part(
        HP_REAR_BEARING.name,
        body=partial(bearing_blank, HP_REAR_BEARING, hp_fit),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="Static core",
        features={
            "journal": ck.Hole(
                diameter=2 * hp_fit.bearing_radius,
                depth=HP_REAR_BEARING.thickness,
                at=axis_frame(),
                through=True,
            )
        },
        description="Rear three-arm HP sleeve bearing",
    )
    front_support = ck.Part(
        "front-bypass-support",
        body=partial(
            front_support_body,
            FRONT_SUPPORT,
            CORE_LINER,
            FRONT_NACELLE,
        ),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="Static core",
        ports={"axis": axis_frame()},
        description="Three lower bypass ribs between the core and front nacelle",
    )
    rear_support = ck.Part(
        "rear-bypass-support",
        body=partial(
            rear_support_body,
            REAR_SUPPORT,
            CORE_LINER,
            REAR_NACELLE,
        ),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="Static core",
        ports={"axis": axis_frame()},
        description="Continuous lower core seat in the narrowing aft bypass",
    )
    guides = tuple(
        (
            row,
            ck.Part(
                row.name,
                body=partial(guide_body, row, hp_fit),
                manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
                group="Static core",
                ports={"axis": axis_frame()},
                description="Cutaway stationary guide-vane row",
            ),
        )
        for row in GUIDE_ROWS
    )
    return CoreParts(
        liner=liner,
        combustor=combustor,
        front_bearing=front_bearing,
        rear_bearing=rear_bearing,
        hp_front_bearing=hp_front_bearing,
        hp_rear_bearing=hp_rear_bearing,
        front_support=front_support,
        rear_support=rear_support,
        guides=guides,
    )
