"""Runnable declarative example, using CadQuery bodies and qualified insert envelopes.

PYTHONPATH=src:examples python -m cadkit.cli --project insert_mount:PROJECT describe
"""
import cadquery as cq
from cadkit import FastenerSpec
import cadkit as ck


def insert_envelope(spec):
    model = cq.Workplane("XY").circle(2.3).circle(1.5).extrude(spec.length_mm).val()
    model.thread_diameter, model.thread_pitch = 3, .5
    return model


MOUNT = ck.InsertMount(
    pattern=ck.PolarPattern(8, (0, 180)),
    screw=FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=6),
    insert=FastenerSpec("heat_set_insert", "M3-0.5", length_mm=5.7,
                        factory=insert_envelope, representation="envelope",
                        description="Example envelope; choose and calibrate the purchased insert."),
    clearance_diameter=3.4,
    pocket=ck.InsertPocket(diameter=4, depth=6.7),
    minimum_engagement=3,
)

COVER = ck.Part(
    name="cover", body=lambda: cq.Workplane("XY").rect(30, 20).extrude(2.4),
    manufacture=ck.FDM("unspecified"),
    features={"mount": MOUNT.clearance_side(thickness=2.4, head_recess=ck.Counterbore(6.2, 1.2))},
)
BASE = ck.Part(
    name="base", body=lambda: cq.Workplane("XY").rect(30, 20).extrude(-8),
    manufacture=ck.FDM("unspecified"), features={"mount": MOUNT.insert_side()},
)

DESIGN = ck.Assembly("insert-mount")
base = DESIGN.add("base", BASE)
cover = DESIGN.add("cover", COVER)
DESIGN.fix(base)
DESIGN.connect("cover-mount", MOUNT, through=cover.feature("mount"), into=base.feature("mount"))
PROJECT = DESIGN.as_project()
