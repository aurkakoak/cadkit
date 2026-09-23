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

`assembly.add(part)` uses the definition's name for the instance. Use
`assembly.add("left-bracket", part)` when naming a location or repeating the same
definition. Names must be unique within the containing assembly; CadKit does
not invent numeric suffixes. The keyword form `add(name="left-bracket",
part=part)` is also supported.

An omitted display group inherits a manufactured Part's `group`; Purchased
instances default to `"Purchased"`. Supply
`group="service-parts"` on `add` to override that instance's display grouping
without changing the Part's manufacturing group. Nested leaves retain their
own groups when their containing instance has no group override.

::: cadkit.Assembly
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - add
        - fix
        - export_port
        - export_component
        - exported_components
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
        - motion_graph
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

Get an Instance from `assembly.add(...)`. A leaf instance exposes its local
`feature()` and `port()` references. A nested instance exposes the definition's
exported ports through `port()` and its exported contact participants through
`component()`. Each reference is bound to that installed occurrence.

::: cadkit.Instance
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      members:
        - feature
        - port
        - component

## Contact participants across subsystems

Use `unit.export_component("foot", foot_instance)` to expose a selected Part or
Purchased leaf. After adding the unit to a parent, `unit_instance.component("foot")`
returns a scoped `ComponentRef` for use in `assembly.interface(left=..., right=...)`.
Either side can be a direct leaf owned by the declaring assembly or a component
reference obtained from one of its nested instances.

Ports expose placement datums; components expose the geometry a contact or
clearance declaration concerns. Exporting a component does not place it, add
another occurrence or change its manufacturing definition. A higher-level unit
can re-export a component reference from one of its own nested instances.
Export names are unique. Multiple names may refer to the same leaf, but the two
participants of an interface must resolve to distinct leaves.

References resolve through the selected pose and remain distinct when the same
subsystem is reused. An interface's optional `region` is expressed in the
declaring assembly's coordinates; it does not follow one participant's motion
independently. Referencing a mesh or approximate purchased envelope preserves
the geometry backend's validation limits.

See [the nested-contact example](../how-to/nested-assemblies.md#check-contact-between-subsystems)
for a complete runnable project.

::: cadkit.ComponentRef
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      members: false

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
you would a Part. Export contact participants with `export_component()` for
interfaces declared by the parent. Nested placements and mechanical relationships
resolve in the selected pose.

`locations()` returns immediate-instance transforms. Use `locations(names="path")`
for scoped leaf transforms without building geometry, and `models(names="path")`
when a check needs the corresponding installed shapes.

## Viewer motion

`Assembly.motion_graph()` exports a geometry-free transform graph for the selected
pose. Matrices are column-major in millimetres. Nodes contain a constant matrix,
a scalar joint transform, an ordered matrix product, or an inverse; every reference
points to an earlier node. Component targets identify their world-transform node
and inverse captured transform. Multiply those together to obtain the display
transform for already-installed meshes. Couplings derive driven coordinates before
node evaluation; joint limits apply to every resolved coordinate.

Compiled joint metadata identifies `parent_components` and `child_components`.
The parent is stationary **relative to that joint**, but may move with an upstream
joint. Desktop mechanical descriptions also include each joint's
`moving_components`, including attached descendants and generated hardware.

The graph is a placement preview, not a dynamics or collision solver. Joints with
additional fastening constraints that cannot be represented by the placement graph
are disabled in the viewer. Author a pose in Python to validate those arrangements.
