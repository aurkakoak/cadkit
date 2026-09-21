# Adopt an existing CadQuery model

Use this guide when you already have working CadQuery geometry and want CadKit
exports, a desktop viewer and agent access. You need a
[CadKit Python environment](install.md#set-up-a-python-project-for-the-cli).

## Wrap the builder

Keep the existing geometry function. Define a `Part`, then place its instance in
an assembly. This complete example can be saved as `project.py`:

```python
import cadquery as cq
import cadkit as ck


def plate():
    # Replace this body with your existing CadQuery builder.
    return cq.Workplane("XY").box(60, 40, 4)


PLATE = ck.Part(
    "plate", body=plate, manufacture=ck.FDM("PETG"), group="structure",
)
assembly = ck.Assembly("mounting-plate")
assembly.fix(assembly.add("plate", PLATE), at=ck.Frame((0, 0, 20)))
PROJECT = assembly.as_project()
```

The `Part` describes what to manufacture; its body builder takes no arguments.
`assembly.add()` creates one instance linked to that definition. `fix()` supplies
its installed frame without changing the local geometry or manufacturing pose.

Builders may return a CadQuery Workplane or Shape. Return a single shape or an
explicit compound for several solids; do not rely on several items in a
Workplane stack being exported together. Keep the builder lazy: pass `plate`,
not `plate()`. Set `expected_solids` for an intentional multiple-solid definition.
An explicit `cadkit.geometry.Mesh` body is also supported, with STL output and
reported STEP omissions; native manufacturing features require native geometry.

## Check the integration

Run from the directory containing `project.py`:

```sh
uv run cadkit --project project:PROJECT describe
uv run cadkit --project project:PROJECT inspect plate
uv run cadkit --project project:PROJECT build plate
```

`describe` lists the registry without building the geometry. `inspect` builds
the print-oriented part and reports its geometry. `build` writes STL, native
STEP and a manifest to `build/cadquery`.

Open the same project in the desktop using the
[launch command for your platform](install.md#open-your-own-project).
The viewer shows the plate centered at Z=20; the part export rests on the print
bed. Those placements serve different purposes.

## Adapt more than one part

Add one `Part` per manufacturing definition. Call `assembly.add()` for every
installed instance, with distinct names such as `left-bracket` and
`right-bracket` referring to the same definition. Manufacturing quantities follow
instance counts; use `as_project(quantities={"bracket": 4})` for an explicit total,
including any spares.

Put uninstalled coupons and optional variants in
`as_project(extra_parts=(COUPON,))`, with `production=False` on the definition.
They remain discoverable and can be exported by name.

Apply installed transforms once through fixed frames or connections. If your
existing exporter rotates a part for printing, use the original design builder
for the `Part` and put that rotation in `ck.FDM("PETG", print_rotation=(...))`.
See [nested assemblies](nested-assemblies.md) for reusable units and named poses.

## Preserve geometric evidence

Before switching exporters, retain a representative export and run the project's
existing tests. Compare native validity, solid count, dimensions and the interfaces
that matter to your design. Also inspect the assembly visually. Matching volume
and bounds alone do not establish matching geometry.

Keep custom fabrication commands where CadKit does not cover their output format.
Add named features when they help express manufacturing intent or a relationship;
adoption does not require rewriting your CadQuery body builders.

See [Parts and placement](../explanation/parts-and-placement.md) for the model,
and the [Project reference](../reference/project.md) for inventory and checks.
