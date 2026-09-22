"""Minimal CadKit project: local geometry, print intent and installed frames."""

import cadkit as ck
from cadkit.geometry import rounded_rect_prism, cylinder, union
from cadkit.fits import Bore, Countersink

# Independent dimensions and fit allowances, in millimetres.
WIDTH = 60
DEPTH = 24
THICKNESS = 6
CORNER_RADIUS = 4
MOUNT_PITCH = 40
SHAFT_DIAMETER = 4
SHAFT_LENGTH = 10
HOLE_ALLOWANCE = 0.3  # Diametral clearance, not radial clearance.
COUNTERSINK_DIAMETER = 8.5
CUTTER_OVERTRAVEL = 0.1

HOLE = Bore(SHAFT_DIAMETER, HOLE_ALLOWANCE)
SINK = Countersink(HOLE.diameter, COUNTERSINK_DIAMETER)
POSITIONS = ((-MOUNT_PITCH / 2, 0), (MOUNT_PITCH / 2, 0))

# The plate rests on Z=0; each shaft's end meets its countersunk top face.
PLATE_BOTTOM_Z = 0
PLATE_TOP_Z = PLATE_BOTTOM_Z + THICKNESS
PLATE_FRAME = ck.Frame((0, 0, PLATE_BOTTOM_Z))
SHAFT_FRAMES = tuple(
    ck.Frame((x, y, PLATE_TOP_Z - SHAFT_LENGTH)) for x, y in POSITIONS
)


def plate():
    body = rounded_rect_prism(WIDTH, DEPTH, THICKNESS, CORNER_RADIUS).val()
    tools = []
    for x, y in POSITIONS:
        tools.extend(
            [
                HOLE.cutter(
                    THICKNESS + 2 * CUTTER_OVERTRAVEL,
                    at=(x, y, -CUTTER_OVERTRAVEL),
                ),
                SINK.cutter(THICKNESS, at=(x, y)),
            ]
        )
    return body.cut(*tools).clean()


PLATE = ck.Part(
    "plate", body=plate, manufacture=ck.FDM("PETG"), group="structure",
    description="M4 countersunk mounting plate",
)
SHAFT = ck.Purchased(
    "fastener-shaft", body=lambda: cylinder(h=SHAFT_LENGTH, d=SHAFT_DIAMETER),
    representation="envelope", description="M4 shaft envelope; no head geometry.",
)

ASSEMBLY = ck.Assembly("bracket")
plate_instance = ASSEMBLY.add("plate", PLATE, group="printed", explode=(0, 0, 15))
ASSEMBLY.fix(plate_instance, at=PLATE_FRAME)
for index, frame in enumerate(SHAFT_FRAMES):
    fastener = ASSEMBLY.add(
        f"fastener-{index}", SHAFT, group="hardware", color=(0.6, 0.6, 0.65),
        material="metal", explode=(0, 0, 30),
    )
    ASSEMBLY.fix(fastener, at=frame)


def shaft_plate_overlap():
    """Check the actual shaft definitions at their declared installed frames."""
    models = ASSEMBLY.models()
    shafts = union([models[f"fastener-{index}"] for index in range(len(SHAFT_FRAMES))])
    return models["plate"].val().intersect(shafts)

PROJECT = ASSEMBLY.as_project(
    parameters=(
        ck.Parameter("THICKNESS", THICKNESS, "mm", "Plate thickness", "bracket.py"),
    ),
    checks=(ck.Check("shaft-fits-hole", shaft_plate_overlap),),
)
