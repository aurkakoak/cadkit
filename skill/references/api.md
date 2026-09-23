# CadKit API

Use `import cadkit as ck` for parts, manufacturing features, frames, assemblies
and mechanical evidence. Machine datums, purchased interfaces, motion states and
specialized fabrication stay in the consumer. Keep imports and graph construction
cheap; generate geometry inside lazy body builders.

## Project and geometry

```python
from dataclasses import dataclass
from functools import partial
import cadquery as cq
import cadkit as ck


@dataclass(frozen=True, kw_only=True)
class PlateDimensions(ck.Dimensions):
    width: float = ck.input(
        default=30.0, unit="mm", description="Plate width", gt=0,
    )
    depth: float = ck.input(
        default=20.0, unit="mm", description="Plate depth", gt=0,
    )
    thickness: float = ck.input(
        default=6.0, unit="mm", description="Plate thickness", gt=0,
    )


def plate_body(dimensions):
    # The origin is the centre of the bottom face.
    return cq.Workplane("XY").box(
        dimensions.width, dimensions.depth, dimensions.thickness,
        centered=(True, True, False),
    ).val()


dimensions = PlateDimensions()
PLATE = ck.Part(
    "plate", body=partial(plate_body, dimensions),
    manufacture=ck.FDM("PETG"), group="frame",
)
assembly = ck.Assembly("example")
instance = assembly.add(PLATE)
assembly.fix(instance)
PROJECT = assembly.as_project(parameters=dimensions.parameters(scope="plate"))
```

Builders return one valid `cq.Workplane`, `cq.Shape`, or explicit
`cadkit.geometry.Mesh`. For multiple native solids, return an explicit compound
rather than relying on an entire Workplane stack being exported. Bodies use
local design coordinates. The assembly resolves and applies each installed
transform once, including nested assemblies. All linear coordinates use millimetres.

| Contract | Fields and behavior |
| --- | --- |
| `Dimensions` | Frozen, keyword-only dataclass base for typed inputs, common validation, a custom `validate()` hook and `parameters(scope="")` metadata |
| `input` | Dataclass field declaration with optional `default`, `unit`, `description` and numeric `gt`, `ge`, `lt`, `le` bounds |
| `Part` | Required `name`, zero-argument `body`, `manufacture`; optional named `features`, `ports`, native `finalize`, `group="parts"`, `description=""`, `notes=""`, `production=True`, `expected_solids=1` |
| `FDM` | Explicit `material`, `print_rotation=(0,0,0)` or keyword `print_frame`; print transform is independent of installed placement |
| `Purchased` | Local body, ports and explicit features; supplier identity, description, qualified representation and per-instance quantity; omitted from printable inventory |
| `Assembly` | Named graph; `add` reusable definitions, `fix` roots, `connect` remaining instances, then `as_project` |
| `Parameter` | `name`, `value`, `unit`, `description`, `source`, `measured=False`; descriptive metadata, not a setter or live UI control |
| `Project` | Compiled snapshot returned by `as_project`, used by the CLI, desktop, inspection and exporters |

`Part.build()` returns local design geometry. `Part.build_for_print()` applies
the declared X, Y, Z rotations in degrees, or explicit fabrication Frame, and
translates only Z so the lowest point touches the bed. It does not center X/Y.
Do not rotate an already print-oriented body a second time. Set `expected_solids`
to the intentional count, or `None` only when variable solid count is meaningful.
Registration does not replace physical fit tests.

Part names are safe artifact stems. Quantities default to installed instance
counts. Supply extra definitions with `as_project(extra_parts=(COUPON,))` and
explicit manufacturing totals with `quantities={"plate": 4}`. Overrides must name
registered parts and be positive integers. Set `production=False` for optional
variants or coupons; `build all` selects only production parts. Explicitly named
builds can include optional parts. Slicer quantity overrides allow zero.

`assembly.add(definition)` infers the instance name from the definition. Use
`add("left-plate", PLATE)` or `add(name="left-plate", part=PLATE)` for an alias;
repeated definitions need unique instance names. Names are not automatically
numbered.

`Part.group` is the manufacturing group and also the default display group for
its instances. An explicit `group` on `add` overrides display only. Nested leaves
keep their own groups unless their containing instance overrides the group.
The `color`, `material` and `explode` arguments also control display; an instance's
visual material is not its manufacturing material. Stable sibling
names and hierarchy yield stable desktop paths. Renaming or reparenting creates
new identities. Discover MCP IDs from the running app instead of storing them
in source definitions.

Use `name_pose("service", {...})` to supply named views to CLI
`--view service`. The desktop shows the Project's selected pose and has no
named-view selector; `assembly.pose(...).as_project()` selects a pose explicitly.
The inspector's Motion controls preview revolute joints without changing the
Project. They expose signed rpm, limits and coupling-aware playback; reset before
measuring or rendering. Never rewrite Parts just to animate a viewer.
Geometry, graph hardware and interfaces resolve from that pose. Visibility and
explosion never alter manufacturing quantities.

## Design inputs

Each instance field in a `ck.Dimensions` subclass must use `ck.input` and be
annotated `float`, `int`, `bool` or `str`. All constructor arguments are keyword
arguments. Omit `default` for a required input. A `float` field also accepts an
integer value, excluding booleans; the other field types are checked strictly.
Numeric values must be finite. Numeric bounds are checked during construction,
followed by the class's `validate()` method for cross-field rules. Override that
method when needed; overriding `__post_init__` is rejected.

Derived dimensions are ordinary properties and do not appear in generated
parameter metadata. Profile tables and other structured shape data remain
separate named records. Use `dataclasses.replace(dimensions, width=40.0)` to
create and validate a variant, then pass it to the body and assembly builders
and compile the corresponding metadata. There is no automatic dependency
tracking or live editing of an existing Project.

`dimensions.parameters(scope="plate")` returns `ck.Parameter` records named
`plate.width`, `plate.depth` and `plate.thickness`, with their current values,
units, descriptions and the declaring class's source file when available.
Scope is a metadata prefix; it does not rename a part or an assembly path.
Unit strings label values without converting them. Supply lengths in millimetres
and angles in the units required by the API using them.

Direct `ck.Parameter(name, value, unit, description, source, measured=False)`
records are also accepted by `as_project(parameters=...)`. Use them for measured
or externally supplied metadata that is not owned by a Dimensions configuration;
set `measured=True` for measurements. Neither form wires a value into geometry:
the builders must consume the authored input. See [authoring](authoring.md) for
dimension ownership and subsystem organization.

## Checks

Pass custom checks as `assembly.as_project(checks=(check, ...))`.
`Check(name, builder, required_contact=False, tolerance_mm3=1e-5,
contact_pair=None, max_gap_mm=0.001)` evaluates intersection geometry returned
by `builder`. An empty intersection passes a forbidden-overlap check. Set
`required_contact=True` for required interference. For true surface contact,
also provide `contact_pair=lambda: (shape_a, shape_b)`; touching native B-reps
can have zero intersection volume. The gap criterion is native-only. Exceptions
are failures. Failed overlaps export witness STLs, plus a JSON report.

Keep useful motion-sweep, interface, manufacturing and domain tests. A
Project with no registered Checks produces a vacuously passing `cadkit check`;
that is not evidence that the model has been checked for collisions.

## Reusable primitives and boundaries

`cadkit.geometry` offers `annulus`, `rounded_rect_prism`, `capsule`,
`polar_points`, transforms, booleans, extrusion, and `normalized_to_bed`.
`cadkit.fits` offers `Bore`, `Countersink` and `fit_coupon`. Use these where their
coordinate and tolerance conventions match the consumer; wrapping a model in
CadKit does not require rewriting working CadQuery geometry.

Native shapes remain native. `import_mesh(path)` explicitly enters the mesh
boundary; spatial convex hulls and booleans involving meshes also use Manifold.
Part and Purchased bodies can be meshes, with fixed frames, ports and nested
assembly placement. Native-only features and native finishing operations reject
mesh bodies clearly. Mesh parts export STL; native STEP assembly output has a
companion omission manifest for meshes. Complete meshes remain available to the
desktop and Blender. Preserve vendor attribution in the consumer.

Use [contracts](contracts.md) for file schemas and [workflows](workflows.md) for
commands. The installed wheel's Python source is available for API inspection
when these references do not answer a question; record such documentation gaps.

## Mechanical contracts

Assembly connections derive hardware, joints and fastenings from the same part
features. Declare contact and clearance with `assembly.interface()`, and tool
access with `assembly.access()` or `driver_access()`.

A subsystem publishes selected leaf participants with
`export_component("foot", foot_instance)`. Its parent uses
`unit_instance.component("foot")` in `interface(left=..., right=...)`, alongside
direct owned leaves or exports from another nested instance. Re-export a nested
component reference to expose it through another level. References follow poses
and remain scoped to the installed occurrence when a definition is reused.
Only export the leaves callers need; use ports for placement. Optional interface
regions remain in the declaring assembly's coordinates. See
[assemblies](declarative-assemblies.md#contacts-across-subsystems).

For static assemblies, `as_project(joints=..., interfaces=..., fastenings=...)`
accepts additional installed contracts in project coordinates. These cannot be
combined with motion edges; moving contracts belong on the graph so their
geometry and metadata follow the same pose. `Project.joints`, `interfaces` and
`fastenings` expose the compiled collections. See [mechanics](mechanics.md) for
contract constructors, hardware, validation and app/MCP evidence.
