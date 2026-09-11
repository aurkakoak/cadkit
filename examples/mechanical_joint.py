"""Two bolted plates: daily-use example for desktop, MCP and pre-print review.

Run from CadKit: PYTHONPATH=examples python -m cadkit.cli --project mechanical_joint:PROJECT mechanics
Desktop: npm --prefix desktop start -- --project-dir examples --project mechanical_joint:PROJECT
The two M3x12 bolts each use two ISO7089 washers and one ISO4032 nut.
Printed geometry is explicitly authored; hardware never silently cuts holes.
"""
import cadquery as cq
from cadkit import (Project, Part, Component, Joint, Interface, Fastening,
                    FastenerSpec, HardwareItem, FastenerSite, AccessEnvelope)

POSITIONS = ((-8, 0), (8, 0))
WASHER = FastenerSpec("plain_washer", "M3")
WASHER_THICKNESS = 0.55  # ISO7089 M3 catalogue thickness


def plate(z):
    body = cq.Solid.makeBox(32, 18, 3).translate((-16, -9, z))
    for x, y in POSITIONS:
        body = body.cut(cq.Solid.makeCylinder(1.7, 3, (x, y, z)))
    return body


def components(**options):
    return [Component("top", plate(0.55), "Plates", part="top"),
            Component("base", plate(3.55), "Plates", part="base")]


def tool_envelope():
    return cq.Compound.makeCompound([cq.Solid.makeCylinder(2.5, 20, (x, y, -23)) for x, y in POSITIONS])


PROJECT = Project(
    "mechanical-joint",
    (Part("top", lambda: plate(0.55), "Plates"), Part("base", lambda: plate(3.55), "Plates")),
    components,
    joints=(Joint("plate-joint", ("top", "base"), interfaces=("plate-contact",), fastenings=("plate-bolts",)),),
    interfaces=(Interface("plate-contact", ("top", "base"), "contact"),),
    fastenings=(Fastening(
        "plate-bolts", ("top", "base"), joint="plate-joint",
        sites=tuple(FastenerSite(f"mount-{i+1}", (x,y,0)) for i,(x,y) in enumerate(POSITIONS)),
        hardware=(HardwareItem("screw", FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=12)),
                  HardwareItem("head-washer", WASHER, 0),
                  HardwareItem("nut-washer", WASHER, 6.55),
                  HardwareItem("nut", FastenerSpec("hex_nut", "M3-0.5"), 7.10)),
        grip_mm=7.10, thread_depth_mm=2.4, min_engagement_mm=2.4,
        hole_depth_mm=14, insertion_distance_mm=20,
        access=(AccessEnvelope("driver", tool_envelope, ("top", "base")),),
        description="Two M3×12 screws, four washers and two nuts clamp the plates.",
    ),),
)
