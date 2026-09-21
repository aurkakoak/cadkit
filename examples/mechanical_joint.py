"""Two bolted plates: daily-use example for desktop, MCP and pre-print review.

Run from CadKit: PYTHONPATH=examples python -m cadkit.cli --project mechanical_joint:PROJECT mechanics
Desktop: npm --prefix desktop start -- --project-dir examples --project mechanical_joint:PROJECT
The two M3x12 bolts each use two ISO7089 washers and one ISO4032 nut.
Printed geometry is explicitly authored; hardware never silently cuts holes.
"""
import cadquery as cq
import cadkit as ck

POSITIONS = ((-8, 0), (8, 0))
WASHER = ck.FastenerSpec("plain_washer", "M3")
WASHER_THICKNESS = 0.55  # ISO7089 M3 catalogue thickness


def plate():
    body = cq.Solid.makeBox(32, 18, 3).translate((-16, -9, 0))
    for x, y in POSITIONS:
        body = body.cut(cq.Solid.makeCylinder(1.7, 3, (x, y, 0)))
    return body


def tool_envelope():
    return cq.Compound.makeCompound([
        cq.Solid.makeCylinder(2.5, 20, (x, y, -23)) for x, y in POSITIONS
    ])


TOP = ck.Part("top", body=plate, manufacture=ck.FDM("PETG"), group="Plates")
BASE = ck.Part("base", body=plate, manufacture=ck.FDM("PETG"), group="Plates")
ASSEMBLY = ck.Assembly("mechanical-joint")
ASSEMBLY.fix(ASSEMBLY.add("top", TOP), at=ck.Frame((0, 0, WASHER_THICKNESS)))
ASSEMBLY.fix(ASSEMBLY.add("base", BASE), at=ck.Frame((0, 0, WASHER_THICKNESS + 3)))

PROJECT = ASSEMBLY.as_project(
    joints=(ck.Joint("plate-joint", ("top", "base"), interfaces=("plate-contact",), fastenings=("plate-bolts",)),),
    interfaces=(ck.Interface("plate-contact", ("top", "base"), "contact"),),
    fastenings=(ck.Fastening(
        "plate-bolts", ("top", "base"), joint="plate-joint",
        sites=tuple(ck.FastenerSite(f"mount-{i+1}", (x, y, 0)) for i, (x, y) in enumerate(POSITIONS)),
        hardware=(ck.HardwareItem("screw", ck.FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=12)),
                  ck.HardwareItem("head-washer", WASHER, 0),
                  ck.HardwareItem("nut-washer", WASHER, 6.55),
                  ck.HardwareItem("nut", ck.FastenerSpec("hex_nut", "M3-0.5"), 7.10)),
        grip_mm=7.10, thread_depth_mm=2.4, min_engagement_mm=2.4,
        hole_depth_mm=14, insertion_distance_mm=20,
        access=(ck.AccessEnvelope("driver", tool_envelope, ("top", "base")),),
        description="Two M3×12 screws, four washers and two nuts clamp the plates.",
    ),),
)
