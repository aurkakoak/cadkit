# Declarative assemblies and motion

```python
from cadkit import design as d
assembly = d.Assembly("enclosure")
```

This **experimental** graph places local Part, Purchased and nested Assembly
definitions. Instances must be grounded or connected to a grounded parent;
a geometry output rejects unresolved placements. Multiple fixed roots are
allowed. Names identify instances, connections and ports; keep them stable
when you want the app to preserve selection across rebuilds.

## Assembly

The core sequence is `add` → `fix` / `connect` → `as_project`. `connect`
places a child, while `fasten` adds secondary hardware between already placed
parts. `attach` adds hardware to existing named features without assigning
placement. None of these operations implicitly cuts a different part.

::: cadkit.design.assembly.Assembly
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - add
        - fix
        - export_port
        - connect
        - fasten
        - attach
        - interface
        - access
        - driver_access
        - couple
        - name_pose
        - pose
        - locations
        - components
        - models
        - fastenings
        - joints
        - interfaces
        - purchased_bom
        - as_assembly
        - as_cq_assembly
        - as_project
        - embed
        - describe

## Instance handles

Get an Instance from `assembly.add(...)`. References created by `feature()`
and `port()` belong to that assembly; they cannot be used with another owner.
For a nested assembly, expose a port with `export_port` first.

::: cadkit.design.assembly.Instance
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      members:
        - feature
        - port

## Motion relationships

Parent and child datum frames coincide at zero motion. Motion applies around
or along the parent's positive Z. Coupling ratios and offsets are explicit:
CadKit does not infer gear ratios, solve arbitrary loops, or prove a motion
sweep free of collision.

::: cadkit.design.motion.Rigid
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - location

::: cadkit.design.motion.Revolute
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - location

::: cadkit.design.motion.Slider
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - location

## Pose snapshots

::: cadkit.design.assembly.AssemblyPose
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      members: false

The pose object exposes `locations`, `components`, `models`, `joints`,
`fastenings`, `interfaces`, `as_assembly`, `as_cq_assembly`, `as_project`,
`embed`, and `describe`. Their placement/filter options match the Assembly
methods above; the pose itself is already selected.

## Stable-project embedding

::: cadkit.design.assembly.Embedding
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      members: false

Embedding exposes `components(include_hardware=False, kind=None)`,
`models(kind=None)`, `parts()`, `joints()`, `fastenings()`,
`interfaces(hardware_root=None)`, and `purchased_bom()`. The placement and
pose are fixed by the `assembly.embed(at=..., pose=...)` call.
