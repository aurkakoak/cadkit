# Assemblies and motion

`cadkit` composes local native or explicit mesh geometry. A `Part`
owns a local body builder, manufacturing process, named features and named `Frame`
ports. `Purchased` supplies the same geometry/port contract with supplier metadata
and a quantity; it is excluded from printable parts. An `Assembly` owns instances
of either definition, or instances of other assemblies.

## Placement and motion

Every instance has one placement parent or an explicit fixed frame. Each
connection aligns a parent's local datum and the child's local datum. A revolute
joint adds a rotation about the datum's positive Z axis; a slider adds a translation
along positive Z. Positions are degrees and millimetres respectively.

```python
import cadkit as ck

head = ck.Assembly("tool-head")
housing = head.add("housing", housing_definition)
rotor = head.add("rotor", rotor_definition)
head.fix(housing)
azimuth = head.connect(
    "azimuth", ck.Revolute(position=35, limits=(-180, 180)),
    parent=housing.port("bearing-axis"),
    child=rotor.port("bearing-axis"),
)

head.name_pose("home", {azimuth: 0})
turned = head.pose({azimuth: 90})
```

Geometry is built in part coordinates and transformed once at resolution. Changing
assembly pose does not modify the part definition or its print orientation. Cycles,
ungrounded instances, foreign references, multiple parents and invalid motion
limits raise errors before export.

A nested assembly publishes only the datums its callers need:

```python
stage.export_port("bearing-axis", stage.instances["rotor"].port("bearing-axis"))
rotating = head.add("rotating-stage", stage)
head.connect("azimuth", ck.Revolute(position=35),
             parent=housing.port("bearing-axis"),
             child=rotating.port("bearing-axis"))
```

The path `rotating-stage/radial` addresses a joint inside the nested assembly.
Repeated nested assemblies have independent scoped paths. An exported moving
port resolves using the nested pose before the outer attachment is placed.

`couple` declares an affine relationship explicitly:

```python
head.couple("azimuth-gears", driver="azimuth", driven="pinion-angle",
            ratio=-main_teeth / pinion_teeth, offset=180 / pinion_teeth)
```

The driven coordinate is computed from its driver and cannot be set independently
in a pose. Coupling cycles, multiple drivers and derived limit violations fail.
This is a directed kinematic graph; it does not solve closed-loop constraints.

## Fastenings and ownership

Parts own named sides of shared mount recipes. A connection consumes those sides
and derives placement, hardware, grip, engagement and mechanical metadata:

```python
head.connect("retainer", mount,
             through=retainer.feature("housing-mount"),
             into=housing.feature("retainer-mount"))
```

`fasten` binds an additional connection on already placed parts. It validates that
the installed feature datums coincide and does not add a competing placement
parent. Intermediate clamped layers use `middle_side` and `via=(...)`; each layer
explicitly owns its manufacturing feature and axial interval.

Tool access is attached to the connection's receiver datum. The complete swept
envelope and obstacle instances are explicit:

```python
head.access("retainer-driver", connection=retainer_connection,
            envelope=driver_swept_envelope, obstacles=(housing,))
```

`driver_access(name, connection=..., diameter=..., length=..., obstacles=...)`
derives straight outward tool probes from the shared pattern and screw seats.

Contact and clearance interfaces are local assembly declarations. Optional bounded
regions move with their containing assembly. They constrain checks; they do not
alter geometry.

## One graph for the desktop and exports

`as_project()` takes a recursive snapshot for the CadKit desktop, CLI,
validation and export APIs. Named poses become views. Geometry, generated hardware,
joints, contact regions and access envelopes resolve from the same selected pose.
Later edits to the source graph cannot alter an existing snapshot.

- `components()` returns installed components with unique relative paths.
- `models(kind="manufactured", names="leaf")` supplies CadQuery Workplanes for
  existing native callers; duplicate leaf names require `names="path"`.
- `as_assembly()` preserves the authored hierarchy for Cadkit inspection.
- `as_cq_assembly()` produces the same installed hierarchy as a native CadQuery
  assembly. `kind="manufactured", include_hardware=False` selects printable bodies.
- `purchased_bom()` counts purchased instances, including explicitly declared sets.
- `describe()` exposes the definitions, datums, features and relationships without
  building the part bodies.

Compose a subsystem by adding its Assembly definition to the parent. Publish
attachment datums with `export_port`, and use the returned instance's `port()`
for outer connections. Compile the containing graph with `as_project()` so
hardware and mechanical paths have the correct root and nested identity.

The compiled manufacturing inventory counts installed Parts independently of
poses and visibility. `extra_parts=(COUPON,)` adds uninstalled definitions;
`quantities={"bracket": 6}` selects an explicit manufacturing total. Definition
groups control manufacturing folders; instance groups control display.
