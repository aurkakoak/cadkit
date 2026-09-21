"""Chapter 5: explicit rim contact and driver-access checks. Try SCREW_LENGTH = 4."""
import cadquery as cq

WIDTH = 80
DEPTH = 50
HEIGHT = 20
WALL = 2.4
LID_THICKNESS = 3
SCREW_LENGTH = 8
MOUNT_POINTS = ((-34, -19), (-34, 19), (34, -19), (34, 19))


def box_body():
    # The rim is Z=0; the box extends down from it.
    outside = cq.Workplane("XY").rect(WIDTH, DEPTH).extrude(-HEIGHT)
    cavity = (cq.Workplane("XY").rect(WIDTH - 2 * WALL, DEPTH - 2 * WALL)
              .extrude(-(HEIGHT - WALL)))
    shell = outside.cut(cavity)
    # Four pads join the walls; each will receive a blind insert pocket.
    pads = (cq.Workplane("XY").pushPoints(MOUNT_POINTS)
            .circle(4.5).extrude(-8))
    return shell.union(pads)


def lid_body():
    return cq.Workplane("XY").rect(WIDTH, DEPTH).extrude(LID_THICKNESS)


from cadkit import FastenerSpec
import cadkit as ck


def insert_envelope(spec):
    """A dimensioned placeholder, not a supplier-specific insert model."""
    model = (cq.Workplane("XY").circle(2.35).circle(1.5)
             .extrude(spec.length_mm).val())
    model.thread_diameter = 3
    model.thread_pitch = 0.5
    return model


MOUNT = ck.InsertMount(
    pattern=ck.PointPattern(MOUNT_POINTS),
    screw=FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=SCREW_LENGTH),
    insert=FastenerSpec(
        "heat_set_insert", "M3-0.5", length_mm=5.7, standard="tutorial-envelope",
        factory=insert_envelope, representation="envelope",
        description="Tutorial insert envelope; select and calibrate a real insert before printing.",
    ),
    clearance_diameter=3.4,
    pocket=ck.InsertPocket(diameter=4, depth=6.7, insert_outer_diameter=4.7),
    minimum_engagement=3,
)

BOX = ck.Part(
    "box", box_body, manufacture=ck.FDM("PETG"),
    features={"lid-mount": MOUNT.insert_side()},
)
LID = ck.Part(
    "lid", lid_body, manufacture=ck.FDM("PETG"),
    features={"lid-mount": MOUNT.clearance_side(thickness=LID_THICKNESS)},
)

DESIGN = ck.Assembly("enclosure")
box = DESIGN.add("box", BOX, color=(0.32, 0.58, 0.72))
lid = DESIGN.add("lid", LID, color=(0.86, 0.70, 0.40), explode=(0, 0, 20))
DESIGN.fix(box)
closure = DESIGN.connect(
    "lid-mount", MOUNT,
    through=lid.feature("lid-mount"), into=box.feature("lid-mount"),
)

# --8<-- [start:contact]
# Require the installed lid to touch the rim, without a material overlap.
DESIGN.interface(
    "lid-on-rim", left=box, right=lid,
    kind="contact", max_gap_mm=0.01,
)
# --8<-- [end:contact]
# --8<-- [start:access]
# Check a straight, 3 mm diameter driver against these two parts.
DESIGN.driver_access(
    "lid-driver", connection=closure,
    diameter=3, length=30, obstacles=(box, lid),
)
# --8<-- [end:access]

PROJECT = DESIGN.as_project()
