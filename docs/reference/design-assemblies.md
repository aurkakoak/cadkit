# Assemblies and motion

```python
import cadkit as ck
assembly = ck.Assembly("enclosure")
```

An assembly graph places local Part, Purchased and nested Assembly
definitions. Instances must be grounded or connected to a grounded parent;
a geometry output rejects unresolved placements. Multiple fixed roots are
allowed. Names identify instances, connections and ports; keep them stable
when you want the app to preserve selection across rebuilds.

## Assembly

The core sequence is `add` → `fix` / `connect` → `as_project`. `connect`
places a child, while `fasten` adds secondary hardware between already placed
parts. `attach` adds hardware to existing named features without assigning
placement. None of these operations implicitly cuts a different part.

::: cadkit.Assembly
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
        - describe

## Instance handles

Get an Instance from `assembly.add(...)`. References created by `feature()`
and `port()` belong to that assembly; they cannot be used with another owner.
For a nested assembly, expose a port with `export_port` first.

::: cadkit.Instance
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

::: cadkit.Rigid
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - location

::: cadkit.Revolute
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - location

::: cadkit.Slider
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - location

## Pose snapshots

::: cadkit.AssemblyPose
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      members: false

The pose object exposes `locations`, `components`, `models`, `joints`,
`fastenings`, `interfaces`, `as_assembly`, `as_cq_assembly`, `as_project`,
and `describe`. Their placement/filter options match the Assembly methods above;
the pose itself is already selected.

## Project output

`as_project()` captures the assembly for the CLI, desktop and exporters. Named
poses become available to commands with `--view`. Use `extra_parts` for uninstalled
manufacturing definitions, `quantities` for explicit totals, and `parameters` and
`checks` for project evidence. See [Project model](project.md) for their semantics.

Compose reusable subsystems by passing an Assembly to `add()`. Export its public
attachment datums with `export_port()` and connect the resulting instance just as
you would a Part. Nested placements and mechanical relationships resolve in the
selected pose.
