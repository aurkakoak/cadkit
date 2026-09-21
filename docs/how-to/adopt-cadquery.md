# Adopt an existing CadQuery model

Use this guide when you already have working CadQuery geometry and want CadKit
exports, a desktop viewer and agent access. You need a
[CadKit Python environment](install.md#set-up-a-python-project-for-the-cli).

## Wrap the builder

Keep the existing geometry function. Register it as a `Part`, then describe
where an instance of that part appears in the assembly. This complete example
can be saved as `project.py`:

```python
import cadquery as cq
from cadkit import Component, Part, Project


def plate():
    # Replace this body with your existing CadQuery builder.
    return cq.Workplane("XY").box(60, 40, 4)


def components(*, include_hardware=True):
    return [
        Component(
            "plate", plate().val().translate((0, 0, 20)),
            group="structure", part="plate",
        ),
    ]


PROJECT = Project(
    "mounting-plate",
    parts=(Part("plate", plate, group="structure", material="PETG"),),
    components=components,
)
```

The `Part` describes what to manufacture; its builder takes no arguments.
The `Component` describes one installed instance. Its `part="plate"` connects
the selected object in the viewer to the manufacturing definition.

Builders may return a CadQuery Workplane or Shape. Return a single shape or an
explicit compound for several solids; do not rely on several items in a
Workplane stack being exported together. Keep the builder lazy: pass `plate`,
not `plate()`.

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
The viewer shows the plate at Z=20; the part export is normalized to the print
bed. Those are intentionally different placements.

## Adapt more than one part

Add one `Part` per manufacturing definition. Add a `Component` for every
installed instance, with distinct names such as `left-bracket` and
`right-bracket` referring to the same `part="bracket"`. Set `Part.quantity`
explicitly; the base `Project` API does not infer it from visible instances.

Apply installed transforms in your component builder exactly once. If your
existing exporter already rotates a part for printing, use the original design
builder for the `Part` and put that rotation in `print_rotation` instead.

Every component or named-view builder must accept `include_hardware=True`,
even if it has no hardware. CadKit passes that keyword when preparing views
and exports.

## Preserve the evidence from the old workflow

Before switching exporters, keep a representative old export and run the
project's existing tests. Compare native validity, solid count, dimensions and
the interfaces that matter to your design. Also inspect the assembly visually.
Matching volume and bounds alone do not establish matching geometry.

Keep custom fabrication commands where CadKit does not cover their output
format. You can adopt `cadkit.design` features later, one part at a time;
adoption does not require rewriting your CadQuery model.

See [Parts and placement](../explanation/parts-and-placement.md) for the model
behind this adapter, and the [Project reference](../reference/project.md) for
all registration fields.
