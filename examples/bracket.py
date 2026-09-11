"""Minimal independent CadKit project: explicit datums, fits and assembly placement."""

from cadkit import Project, Part, Component, Parameter, Check
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


def components(*, include_hardware=True):
    items = [Component("plate", plate(), "printed", part="plate", explode=(0, 0, 15))]
    if include_hardware:
        for i, xy in enumerate(POSITIONS):
            items.append(
                Component(
                    f"fastener-{i}",
                    translate([cylinder(h=10, d=4)], (*xy, -4)),
                    "hardware",
                    (0.6, 0.6, 0.65),
                    "metal",
                    explode=(0, 0, 30),
                )
            )
    return items


PROJECT = Project(
    "bracket",
    (Part("plate", plate, "structure", description="M4 countersunk mounting plate"),),
    components,
    parameters=(
        Parameter("THICKNESS", THICKNESS, "mm", "Plate thickness", "bracket.py"),
    ),
    checks=(
        Check(
            "shaft-fits-hole",
            lambda: plate().intersect(translate([cylinder(h=8, d=4)], (-20, 0, -1))),
        ),
    ),
)
