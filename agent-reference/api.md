# Consumer API

An additive, experimental authoring API now lives under `cadkit.design`.
See [declarative authoring](declarative.md) for explicitly owned manufacturing
features and rigid assembly connections. The existing API below remains supported.

CadKit 0.1 uses ordinary Python builders. Machine datums, purchased interfaces,
motion states and specialized fabrication stay in the consumer. Keep imports
and registry construction cheap; generate geometry inside builders.

## Project and geometry

```python
import cadquery as cq
from cadkit import Assembly, Component, Part, Project, Parameter, Check

THICKNESS = 6

def plate():
    return cq.Workplane("XY").box(30, 20, THICKNESS).val()

def components(*, include_hardware=True):
    return [Component("plate", plate().translate((0, 0, 40)),
                      "frame", part="plate", explode=(0, 0, 15))]

def assembly(*, include_hardware=True):
    return Assembly("machine", (
        Assembly("frame", tuple(components(include_hardware=include_hardware))),
    ))

PROJECT = Project(
    name="example", parts=(Part("plate", plate, "frame", material="PETG"),),
    components=components, assembly=assembly,
    parameters=(Parameter("thickness", THICKNESS, "mm", "Plate thickness",
                          "my_cad/project.py", measured=False),),
)
```

Builders return a `cq.Workplane`, `cq.Shape`, or explicit `cadkit.geometry.Mesh`.
Workplanes are reduced with `.val()`; for multiple solids, return an explicit
compound rather than relying on an entire Workplane stack being exported.
All installed geometry uses world millimetres. Assemblies organize components;
they do not apply transforms. Apply every placement exactly once in the consumer.

| Contract | Fields and behavior |
| --- | --- |
| `Part` | Required `name`, zero-argument `builder`, `group`; optional `quantity=1`, `material="PETG"`, `description=""`, `production=True`, `expected_solids=1`, `print_rotation=(0,0,0)`, Markdown `notes=""` |
| `Component` | Required `name`, built `model`, `group`; optional RGB `color`, visual `material="printed"`, `part=None`, `explode=(0,0,0)` |
| `Assembly` | `name`, tuple of child Components/Assemblies, optional `description` |
| `Project` | `name`, tuple of Parts, `components` callable; optional `parameters`, `checks`, `description`, `views` dictionary and `assembly` callable |
| `Parameter` | `name`, `value`, `unit`, `description`, `source`, `measured=False`; descriptive metadata, not a setter or live UI control |

`Part.build(for_print=False)` returns authored geometry. The default
`Part.build()` rotates around world X, then Y, then Z in degrees, and translates
only Z so its lowest point touches the bed. It does not center X/Y. Do not wrap
an already print-oriented legacy export function and apply its rotation again.
Set `expected_solids` to the intentional count, or `None` only when variable
solid count is meaningful. Registration does not replace physical fit tests.

Part names are safe artifact stems; preserve existing names when they qualify.
Quantities are positive integers for manufacturing totals, separate from the
number of visible Component instances. Set `production=False` for optional
variants or coupons; `build all` selects only production Parts. Explicitly
named builds can include optional Parts. Slicer quantity overrides allow zero.

`Component.part` must name its Part when it represents one. Hardware can have
no Part. Component material is a rendering category; Part material is the
manufacturing material. Stable sibling names and hierarchy yield stable desktop
paths. Renaming or reparenting creates new identities. Don't store generated
MCP IDs in a registry: discover them from the running app.

The `components` callable and every named `views` callable must accept
`include_hardware=True`, because CLI assembly/preview/render commands pass it.
Define `views={"service": service_components}` for `--view service`. The
desktop uses `Project.get_assembly()` for the default model; it does not expose
a named-view selector. Without `assembly=`, CadKit groups default components
by `Component.group`. A custom assembly builder and the flat component builder
must describe the same installed model. Derive them from a shared builder.

## Checks

`Check(name, builder, required_contact=False, tolerance_mm3=1e-5,
contact_pair=None, max_gap_mm=0.001)` evaluates intersection geometry returned
by `builder`. An empty intersection passes a forbidden-overlap check. Set
`required_contact=True` for required interference. For true surface contact,
also provide `contact_pair=lambda: (shape_a, shape_b)`; touching native B-reps
can have zero intersection volume. The gap criterion is native-only. Exceptions
are failures. Failed overlaps export witness STLs, plus a JSON report.

Keep existing motion-sweep, interface, manufacturing and domain tests. A
`Project` with no registered Checks produces a vacuously passing `cadkit check`;
that is not evidence that the model has been checked for collisions.

## Reusable primitives and boundaries

`cadkit.geometry` offers `annulus`, `rounded_rect_prism`, `capsule`,
`polar_points`, transforms, booleans, extrusion, and `normalized_to_bed`.
`cadkit.fits` offers `Bore`, `Countersink` and `fit_coupon`. Adopt these where
their coordinate and tolerance conventions match the consumer; adapting to
CadKit does not require rewriting working CadQuery geometry.

Native shapes remain native. `import_mesh(path)` explicitly enters the mesh
boundary; spatial convex hulls and booleans involving meshes also use Manifold.
Mesh Parts export STL, not nominally editable STEP. Native STEP assembly output
has a companion omission manifest for meshes. Complete meshes remain available
to the desktop and Blender. Preserve vendor attribution in the consumer.

Use [contracts](contracts.md) for file schemas and [workflows](workflows.md) for
commands. The installed wheel's Python source is available for API inspection
when these references do not answer a question; record such documentation gaps.

## Mechanical contracts (0.2)

`Project.joints`, `Project.interfaces` and `Project.fastenings` are first-class
collections. See [mechanics](mechanics.md) for constructors, located cq_warehouse
hardware, validation, app and MCP contracts. Existing projects default to empty
collections; `describe` remains lazy.
