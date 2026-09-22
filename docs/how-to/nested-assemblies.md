# Nest assemblies and name poses

Use this guide when a moving unit needs to be reused more than once. It assumes
a [working Python environment](install.md#set-up-a-python-project-for-the-cli).

## Define the reusable unit

Save this as `motion.py`. The geometry represents a base and a pivoting arm;
the pivot is a placement datum, not a model of a bearing or fastener.

```python
import cadquery as cq
import cadkit as ck

BASE = ck.Part(
    "base", body=lambda: cq.Workplane("XY").box(
        30, 30, 4, centered=(True, True, False)),
    manufacture=ck.FDM("PETG"),
    ports={"pivot": ck.Frame((0, 0, 4))},
)
ARM = ck.Part(
    "arm", body=lambda: cq.Workplane("XY").box(
        25, 8, 3, centered=(False, True, False)),
    manufacture=ck.FDM("PETG"),
    ports={"pivot": ck.Frame()},
)

unit = ck.Assembly("pivot-unit")
base = unit.add(BASE)
arm = unit.add(ARM)
unit.fix(base)
unit.connect(
    "swing", ck.Revolute(position=0, limits=(-90, 90)),
    parent=base.port("pivot"), child=arm.port("pivot"),
)

machine = ck.Assembly("two-arms")
left = machine.add("left", unit)
right = machine.add("right", unit)
machine.fix(left, at=ck.Frame((-40, 0, 0)))
machine.fix(right, at=ck.Frame((40, 0, 0)))
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
stay the same. Each manufactured definition has quantity two in the compiled
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

## Check contact between subsystems

Export a selected part with `export_component` when a parent needs to check its
contact with another subsystem. The parent gets that participant through the
installed unit's `component()` method. This is separate from exporting a port
for placement.

Save this complete example as `contacts.py`. Each support contains one pad;
the two reused supports meet along the pads' vertical side faces.

```python
import cadquery as cq
import cadkit as ck

PAD_WIDTH = 20
PAD_DEPTH = 12
PAD_HEIGHT = 4


def pad_body():
    # Local X starts at the left edge; the bottom face is Z=0.
    return cq.Workplane("XY").box(
        PAD_WIDTH, PAD_DEPTH, PAD_HEIGHT, centered=(False, True, False),
    )


pad = ck.Part("pad", body=pad_body, manufacture=ck.FDM("PETG"), group="supports")
unit = ck.Assembly("support")
foot = unit.add(pad)
unit.fix(foot)
unit.export_component("foot", foot)

pair = ck.Assembly("pair")
left = pair.add("left", unit)
right = pair.add("right", unit)
pair.fix(left)
pair.fix(right, at=ck.Frame((PAD_WIDTH, 0, 0)))
pair.interface(
    "shared-edge", left=left.component("foot"), right=right.component("foot"),
    kind="contact", description="The two pads meet at their side faces",
)
PROJECT = pair.as_project()
```

```sh
uv run cadkit --project contacts:PROJECT validate-assembly --output build/contact-review.json
```

The declaration resolves to `left/pad` and `right/pad`. The pads share one
manufacturing definition and inherit its `supports` display group, while each
reference identifies its own installed occurrence. References also follow
internal motion when a unit has moving parts.

The report passes the contact check with zero gap and overlap. Assembly sequence
remains unverified; this declaration checks the installed fit.

A containing assembly can re-export a nested component reference with
`export_component`, exposing only the participants its own parent needs. An
interface can combine these references with its directly owned leaf instances.
If it declares an overlap `region`, that region uses the declaring assembly's
coordinates and moves with that assembly, independently of either participant.

See [assembly reference](../reference/design-assemblies.md) for exported ports,
exported components, coupled motion and project compilation.
