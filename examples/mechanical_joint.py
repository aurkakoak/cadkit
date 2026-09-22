"""Two bolted plates: daily-use example for desktop, MCP and pre-print review.

Run from CadKit: PYTHONPATH=examples python -m cadkit.cli --project mechanical_joint:PROJECT mechanics
Desktop: npm --prefix desktop start -- --project-dir examples --project mechanical_joint:PROJECT
The two M3x12 bolts each use two ISO7089 washers and one ISO4032 nut.
Printed geometry is explicitly authored; hardware never silently cuts holes.

This fixed assembly uses explicit Joint, Interface and Fastening records as
installed-coordinate contracts passed to as_project(). The records describe
the placed native bodies; they do not position them. For a moving mechanism,
use assembly connections and local ports so contracts follow the selected pose.
"""
import cadquery as cq
import cadkit as ck

# Independent plate, hardware and access dimensions, in millimetres.
PLATE_WIDTH = 32
PLATE_DEPTH = 18
PLATE_THICKNESS = 3
MOUNT_PITCH = 16
SCREW_DIAMETER = 3
SCREW_LENGTH = 12
SCREW_THREAD = "M3-0.5"
HOLE_ALLOWANCE = 0.4  # Diametral clearance.
WASHER_THICKNESS = 0.55  # ISO7089 M3 catalogue thickness
SCREW_HEAD_HEIGHT = 3  # ISO4762 M3 catalogue head height
NUT_THREAD_DEPTH = 2.4
DRIVER_DIAMETER = 5
INSERTION_DISTANCE = 20
UNOBSTRUCTED_DEPTH = 14  # Declared free depth from the screw's under-head seat.

POSITIONS = ((-MOUNT_PITCH / 2, 0), (MOUNT_PITCH / 2, 0))
HOLE_DIAMETER = SCREW_DIAMETER + HOLE_ALLOWANCE
WASHER = ck.FastenerSpec("plain_washer", f"M{SCREW_DIAMETER}")

# All stack mates derive from the screw's under-head seat, with insertion +Z.
SCREW_SEAT_Z = 0
HEAD_WASHER_Z = SCREW_SEAT_Z
TOP_Z = HEAD_WASHER_Z + WASHER_THICKNESS
PLATE_CONTACT_Z = TOP_Z + PLATE_THICKNESS
BASE_Z = PLATE_CONTACT_Z
NUT_WASHER_Z = BASE_Z + PLATE_THICKNESS
NUT_Z = NUT_WASHER_Z + WASHER_THICKNESS
TOP_FRAME = ck.Frame((0, 0, TOP_Z))
BASE_FRAME = ck.Frame((0, 0, BASE_Z))

# Sweep the driver toward the screw head, stopping at its outer face.
DRIVER_END_Z = SCREW_SEAT_Z - SCREW_HEAD_HEIGHT
DRIVER_START_Z = DRIVER_END_Z - INSERTION_DISTANCE


def plate():
    body = cq.Solid.makeBox(PLATE_WIDTH, PLATE_DEPTH, PLATE_THICKNESS).translate(
        (-PLATE_WIDTH / 2, -PLATE_DEPTH / 2, 0)
    )
    for x, y in POSITIONS:
        body = body.cut(cq.Solid.makeCylinder(HOLE_DIAMETER / 2, PLATE_THICKNESS, (x, y, 0)))
    return body


def tool_envelope():
    return cq.Compound.makeCompound([
        cq.Solid.makeCylinder(DRIVER_DIAMETER / 2, INSERTION_DISTANCE, (x, y, DRIVER_START_Z))
        for x, y in POSITIONS
    ])


TOP = ck.Part("top", body=plate, manufacture=ck.FDM("PETG"), group="Plates")
BASE = ck.Part("base", body=plate, manufacture=ck.FDM("PETG"), group="Plates")
ASSEMBLY = ck.Assembly("mechanical-joint")
top = ASSEMBLY.add("top", TOP)
base = ASSEMBLY.add("base", BASE)
ASSEMBLY.fix(top, at=TOP_FRAME)
ASSEMBLY.fix(base, at=BASE_FRAME)

PROJECT = ASSEMBLY.as_project(
    joints=(ck.Joint(
        "plate-joint", ("top", "base"),
        interfaces=("plate-contact",), fastenings=("plate-bolts",),
    ),),
    interfaces=(ck.Interface("plate-contact", ("top", "base"), "contact"),),
    fastenings=(ck.Fastening(
        "plate-bolts", ("top", "base"), joint="plate-joint",
        sites=tuple(
            ck.FastenerSite(f"mount-{i+1}", (x, y, SCREW_SEAT_Z))
            for i, (x, y) in enumerate(POSITIONS)
        ),
        hardware=(
            ck.HardwareItem("screw", ck.FastenerSpec(
                "socket_head_cap_screw", SCREW_THREAD, length_mm=SCREW_LENGTH,
            )),
            ck.HardwareItem("head-washer", WASHER, HEAD_WASHER_Z - SCREW_SEAT_Z),
            ck.HardwareItem("nut-washer", WASHER, NUT_WASHER_Z - SCREW_SEAT_Z),
            ck.HardwareItem("nut", ck.FastenerSpec("hex_nut", SCREW_THREAD), NUT_Z - SCREW_SEAT_Z),
        ),
        grip_mm=NUT_Z - SCREW_SEAT_Z,
        thread_depth_mm=NUT_THREAD_DEPTH, min_engagement_mm=NUT_THREAD_DEPTH,
        hole_depth_mm=UNOBSTRUCTED_DEPTH, insertion_distance_mm=INSERTION_DISTANCE,
        access=(ck.AccessEnvelope("driver", tool_envelope, ("top", "base")),),
        description="Two M3×12 screws, four washers and two nuts clamp the plates.",
    ),),
)
