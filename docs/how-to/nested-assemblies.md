# Nest assemblies and name poses

Use this guide when a moving unit needs to be reused more than once. It uses
the experimental `cadkit.design` namespace and assumes a
[working Python environment](install.md#set-up-a-python-project-for-the-cli).

## Define the reusable unit

Save this as `motion.py`. The geometry represents a base and a pivoting arm;
the pivot is a placement datum, not a model of a bearing or fastener.

```python
import cadquery as cq
from cadkit import design as d

BASE = d.Part(
    "base", body=lambda: cq.Workplane("XY").box(
        30, 30, 4, centered=(True, True, False)),
    manufacture=d.FDM("PETG"),
    ports={"pivot": d.Frame((0, 0, 4))},
)
ARM = d.Part(
    "arm", body=lambda: cq.Workplane("XY").box(
        25, 8, 3, centered=(False, True, False)),
    manufacture=d.FDM("PETG"),
    ports={"pivot": d.Frame()},
)

unit = d.Assembly("pivot-unit")
base = unit.add("base", BASE)
arm = unit.add("arm", ARM)
unit.fix(base)
unit.connect(
    "swing", d.Revolute(position=0, limits=(-90, 90)),
    parent=base.port("pivot"), child=arm.port("pivot"),
)

machine = d.Assembly("two-arms")
left = machine.add("left", unit)
right = machine.add("right", unit)
machine.fix(left, at=d.Frame((-40, 0, 0)))
machine.fix(right, at=d.Frame((40, 0, 0)))
machine.name_pose("open", {"left/swing": 60, "right/swing": -60})

PROJECT = machine.as_project()
```

The parent's `pivot` is on the base's top face. The child's `pivot` is on the
arm's bottom face. Connecting them places the arm on the base, with rotation
about the shared frame's +Z axis. Revolute positions use degrees; a `Slider`
would translate along that axis in millimetres.

Each instance is either fixed or has one placement parent. Do not also fix
the connected arm: that would give it two placements.

## Export both configurations

```sh
uv run cadkit --project motion:PROJECT describe
uv run cadkit --project motion:PROJECT assembly --output build/home.step
uv run cadkit --project motion:PROJECT assembly --view open --output build/open.step
```

The installed arms move; their manufacturing definitions and print orientations
stay the same. Each manufactured definition has quantity two in the adapted
Project. Both instances share the unit's definition, but `left/swing` and
`right/swing` address separate motion coordinates.

The desktop shows the Project's default pose; it currently has no named-view
selector. To inspect the open pose there, change the final line to:

```python
PROJECT = machine.pose({"left/swing": 60, "right/swing": -60}).as_project()
```

Save and wait for a successful rebuild.

## Expose an attachment datum

When another assembly needs to attach to an internal part, expose only the
needed port. Before adding `unit` to `machine`, you could write:

```python
unit.export_port("arm-pivot", arm.port("pivot"))
```

An outer connection can now refer to `left.port("arm-pivot")` without reaching
into the unit's internal instance tree. To expose the tip instead, first add a
separate tip frame to `ARM.ports` in its definition.

Named poses and relationships describe placement. They do not prove the
mechanism is collision-free throughout its travel or that a physical pivot
exists. Add the intended hardware, interfaces and motion tests separately.

See [assembly reference](../reference/design-assemblies.md) for exported ports,
coupled motion and embedding into an existing Project.
