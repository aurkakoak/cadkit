# CadKit API

Use `import cadkit as ck` for parts, manufacturing features, frames, assemblies
and mechanical evidence. Machine datums, purchased interfaces, motion states and
specialized fabrication stay in the consumer. Keep imports and graph construction
cheap; generate geometry inside lazy body builders.

## Project and geometry

```python
import cadquery as cq
import cadkit as ck

THICKNESS = 6


def plate():
    return cq.Workplane("XY").box(30, 20, THICKNESS).val()


PLATE = ck.Part("plate", body=plate, manufacture=ck.FDM("PETG"), group="frame")
assembly = ck.Assembly("example")
instance = assembly.add("plate", PLATE, group="frame", explode=(0, 0, 15))
assembly.fix(instance, at=ck.Frame((0, 0, 40)))
PROJECT = assembly.as_project(
    parameters=(ck.Parameter("thickness", THICKNESS, "mm", "Plate thickness",
                             "my_cad/project.py", measured=False),),
)
```

Builders return one valid `cq.Workplane`, `cq.Shape`, or explicit
`cadkit.geometry.Mesh`. For multiple native solids, return an explicit compound
rather than relying on an entire Workplane stack being exported. Bodies use
local design coordinates. The assembly resolves and applies each installed
transform once, including nested assemblies. All linear coordinates use millimetres.

| Contract | Fields and behavior |
| --- | --- |
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

`Part.group` is the manufacturing group. The `group`, `color`, `material` and
`explode` arguments to `assembly.add()` control installed display independently;
an instance's visual material is not its manufacturing material. Stable sibling
names and hierarchy yield stable desktop paths. Renaming or reparenting creates
new identities. Discover MCP IDs from the running app instead of storing them
in source definitions.

Use `name_pose("service", {...})` to supply named views to CLI
`--view service`. The desktop shows the Project's selected pose and has no
named-view selector; `assembly.pose(...).as_project()` selects a pose explicitly.
Geometry, graph hardware and interfaces resolve from that pose. Visibility and
explosion never alter manufacturing quantities.

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

For static assemblies, `as_project(joints=..., interfaces=..., fastenings=...)`
accepts additional installed contracts in project coordinates. These cannot be
combined with motion edges; moving contracts belong on the graph so their
geometry and metadata follow the same pose. `Project.joints`, `interfaces` and
`fastenings` expose the compiled collections. See [mechanics](mechanics.md) for
contract constructors, hardware, validation and app/MCP evidence.
