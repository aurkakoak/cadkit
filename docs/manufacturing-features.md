# Declarative manufacturing features

`cadkit.design.Part` owns a native CadQuery body, named manufacturing features,
and a manufacturing process. CadQuery constructs the bespoke structural form;
Cadkit features describe the physical function, apply its geometry, and report
subsequent operations such as tapping and installing inserts. The same part
builds identically regardless of assembly placement or print orientation.

```python
from cadkit import design as d

block = d.Part(
    "motor-block", body=block_blank, manufacture=d.FDM("PETG"),
    features={
        "bearing": d.BearingSeat(
            nominal_diameter=22, allowance=0.15, depth=7,
            at=d.Frame((0, 0, 20), z=(0, 0, -1)),
        ),
        "motor-threads": d.TappedHole(
            "M3-0.5", pilot_diameter=2.5, depth=8, thread_depth=6,
            pattern=d.PointPattern(((-10, 0), (10, 0))),
            at=d.Frame((0, 0, 20), z=(0, 0, -1)),
        ),
    },
)
```

`build()` returns native CadQuery geometry. `describe()` provides named features
and a combined `operations` list that traces every secondary operation back to
its feature. It does not build the geometry. Tapped holes export the pilot, not
modeled thread helices; the finished interface and tapping operation remain
explicit. Supplied threads in purchased components have no tapping operation.

## Coordinate and dimension rules

All dimensions are millimetres. `Hole`, `CounterboredHole`, `CountersunkHole`,
`TappedHole`, `BearingSeat`, `DBore`, `Slot`, and `NutPocket` use an entry-face
`Frame`; local **+Z points into the material**. Their blind floor is exactly at
`depth`. The cutter extends 0.1 mm beyond the entry face for robust booleans.
A hole with `through=True` also extends 0.1 mm beyond the declared exit face;
its depth remains an authored dimension, never an inferred bounding box.

`CounterboredHole(..., recess=d.Counterbore(diameter, depth))` and
`CountersunkHole(..., head_diameter=..., included_angle=90)` put the head seat
at the entry. `Slot(length, width, depth)` includes the semicircular ends in
its overall length and aligns along local X. `DBore(..., flat=...)` truncates
the circular opening at local X=flat; flat is the signed distance from the
shaft axis. `SealGroove(mean_radius, section_radius, at=...)` is a toroidal
cut with its ring lying in local XY.

Features reject empty cuts. Every patterned site and every separately declared
recess must intersect material. Part errors name the part and feature that
failed. CadQuery geometry and finalizers remain available for custom forms,
but should not duplicate a named feature's cut.

`BearingSeat` records nominal diameter and diametral allowance independently.
A `clearance` fit permits nonnegative allowance, a `press` fit nonpositive
allowance, and a `transition` fit accepts either. These explicit dimensions do
not claim a material-specific process capability.

## Shared connections

`InsertMount` and `ThreadedMount` generate explicitly owned matching roles.
Mount roles use a shared mating plane whose **+Z points from the receiving part
toward the clamped part**. Receiver pockets therefore cut negative local Z;
clearance holes cut positive local Z. This convention keeps both sides and
hardware in one coordinate system.

```python
mount = d.ThreadedMount(
    pattern=d.PointPattern(((-10, 0), (10, 0))),
    screw=screw_spec,
    clearance_diameter=3.4,
    pilot_diameter=2.5, thread_depth=6, hole_depth=8,
    minimum_engagement=3,
)
cover_role = mount.clearance_side(thickness=4, head_recess=d.Counterbore(6, 2))
base_role = mount.threaded_side()
```

The resulting connection derives a 2 mm grip, screw placements, purchased
hardware, thread size and engagement requirements from those roles. The
receiver's tapping step belongs to the base part. For a purchased motor,
`threaded_side(supplied=True)` declares the supplied interface without cutting
the envelope. Unknown supplier hole or thread depths remain `None` and remain
unverified; they are never filled with guessed dimensions.

A milled/printed slot uses `clearance_side(slot_length=..., slot_angle=...)`.
`slot_radial=True` rotates each slot along the pattern radius. A scalloped
opening made with repeated drilling uses `drill_offsets=((x1,y1),(x2,y2))`;
its nominal fastening axis remains at the pattern site.

## Clamped stacks

Intermediate roles contribute physical layer lengths and matched geometry:

```python
gear_role = mount.middle_side(thickness=6, head_recess=d.Counterbore(6, 1.7))
spacer_role = mount.middle_side(offset=4.3, thickness=41.7, supplied=True)
cover_role = mount.clearance_side(
    offset=46, thickness=3, head_recess=d.Counterbore(6, 1),
)
assembly.connect(
    "cover-stack", mount,
    through=cover.feature("stack"), into=base.feature("threads"),
    via=(gear.feature("stack"), spacer.feature("stack")),
)
```

Each role's `at` is the **same mating datum**, expressed in that part's local
coordinates. `offset` is the axial start of its material relative to that datum.
A recessed middle role ends at the recessed contact plane: in this example,
the gear contributes 4.3 mm before the spacer. The cover's screw seat is 48 mm
from the receiver, so that is the grip. Stack validation rejects undeclared
gaps, overlapping axial layers and a screw head seated on an interior layer.
Purchased spacers use `supplied=True`; manufactured layers generate their
clearances from the same shared pattern.

## Reinforcement and sheet stock

`Boss(diameter, depth, at=..., limit=...)` adds a cylindrical reinforcement. Its
optional `limit` is a native CadQuery shape or builder describing a bespoke
outer envelope. Features apply in declaration order, so a boss can deliberately
restore material after an earlier cut and then receive its own mounting pocket.
A boss must add valid material and join the part. `InsertBoss` combines a barrel
and insert pocket when the two operations can be kept together.

`Counterbore(..., entry_extension=...)` explicitly extends the access opening
outward beyond the nominal entry face. This preserves a screw's authored seat
and a stack's grip while clearing surrounding material above that face.

`LaserCut(material, thickness)` describes a sheet-stock part and checks that its
native XY blank matches the declared thickness. Whether its entire profile is
constant through that thickness remains explicitly unverified.

## Automatic bounded fit contracts

Every bound insert/thread connection also derives its installed-fit interfaces.
These contracts follow the same resolved frames as the parts and hardware,
including nested motion and embedded assemblies.

For a purchased insert, declare the documented outside dimension separately
from the receiving pilot:

```python
pocket = d.InsertPocket(
    diameter=4.0, depth=6.7,
    insert_outer_diameter=4.6,
)
```

The resulting press-fit region is limited to the insert diameter and length;
its permitted overlap is the insert/pilot annulus. Without an explicit insert
outside diameter, Cadkit makes no automatic press-fit exemption. Screw/insert
thread regions use the declared nominal thread and installed engagement span.

For a generated tapped receiver, the permitted overlap is limited to the
nominal thread minus the pilot, inside the declared threaded depth. A screw
that intrudes beyond this region still produces a collision finding. For an
explicitly modeled supplier envelope, Cadkit bounds intrusion to the known
installed screw protrusion; unknown blind-hole and usable thread depths remain
unverified. Detailed supplier geometry with unknown thread data receives no
such automatic exemption.

Graph construction, descriptions and interface extraction do not query
hardware providers or build parts. Interface regions build native geometry
only when measured. These nominal checks do not establish compliance,
retention, preload or process capability.

## Closures inside one part

Some hardware closes a split clamp or retains a shaft inside a single printed
part. `Assembly.attach` binds these fastenings to named features without
inventing a second part or a placement joint:

```python
assembly.attach(
    "clamp-closure",
    d.CaptiveNutFastening(screw_spec, nut_spec, nut_thickness=1.6),
    through=clamp.feature("closing-hole"), nut=clamp.feature("captive-nut"),
)
assembly.attach(
    "shaft-retention",
    d.SetScrew(set_screw_spec),
    thread=pinion.feature("radial-thread"), stop=pinion.feature("shaft-d-bore"),
)
```

The captive-nut recipe accepts a `Hole` and an opposing `NutPocket`. Their
frames determine the nut's position and grip; their axes and thread designations
must agree. The set-screw recipe accepts a `TappedHole` and a `DBore`. It derives
the tip by intersecting the pilot axis with the finite D-flat plane, then places
the screw's drive end one screw-length upstream. The screw must fit inside the
declared threaded span. `FastenerSpec("set_screw", "M2-0.4", length_mm=2)` uses
the pinned provider's ISO 4026 catalogue model.

Attachments contribute purchased quantities, located hardware and bounded
thread interfaces in every owning-part pose. They do not change manufactured
geometry. A fastening can reference one physical component; joints and contact
interfaces still require distinct participants. Actual shaft-flat contact,
clamp preload and set-screw retention remain unverified by nominal geometry.
