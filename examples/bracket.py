"""Minimal CadKit project: local geometry, print intent and installed frames."""

import cadkit as ck
from cadkit.geometry import rounded_rect_prism, translate, cylinder
from cadkit.fits import Bore, Countersink

THICKNESS = 6
HOLE = Bore(4, 0.3)
SINK = Countersink(HOLE.diameter, 8.5)
POSITIONS = ((-20, 0), (20, 0))


def plate():
    body = rounded_rect_prism(60, 24, THICKNESS, 4).val()
    tools = []
    for x, y in POSITIONS:
        tools.extend(
            [
                HOLE.cutter(THICKNESS + 0.2, at=(x, y, -0.1)),
                SINK.cutter(THICKNESS, at=(x, y)),
            ]
        )
    return body.cut(*tools).clean()


PLATE = ck.Part(
    "plate", body=plate, manufacture=ck.FDM("PETG"), group="structure",
    description="M4 countersunk mounting plate",
)
SHAFT = ck.Purchased(
    "fastener-shaft", body=lambda: cylinder(h=10, d=4),
    representation="envelope", description="M4 shaft envelope; no head geometry.",
)

ASSEMBLY = ck.Assembly("bracket")
ASSEMBLY.fix(ASSEMBLY.add("plate", PLATE, group="printed", explode=(0, 0, 15)))
for index, xy in enumerate(POSITIONS):
    fastener = ASSEMBLY.add(
        f"fastener-{index}", SHAFT, group="hardware", color=(0.6, 0.6, 0.65),
        material="metal", explode=(0, 0, 30),
    )
    ASSEMBLY.fix(fastener, at=ck.Frame((*xy, -4)))

PROJECT = ASSEMBLY.as_project(
    parameters=(
        ck.Parameter("THICKNESS", THICKNESS, "mm", "Plate thickness", "bracket.py"),
    ),
    checks=(
        ck.Check(
            "shaft-fits-hole",
            lambda: plate().intersect(translate([cylinder(h=8, d=4)], (-20, 0, -1))),
        ),
    ),
)
