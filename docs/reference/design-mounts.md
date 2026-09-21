# Mounts and attachments

```python
from cadkit import design as d
from cadkit import FastenerSpec
```

These **experimental** recipes share hardware dimensions between explicitly
owned part features. Use the same mount object to create every matching role,
then bind those roles with an [assembly connection](design-assemblies.md).
Matching values on two separate mount objects are not enough.

## Mating-datum convention

Mount role frames coincide at the receiver/clamped-part interface. **+Z points
out of the receiver toward the clamped parts.** Receiver pockets extend into
negative Z; clamped layers occupy positive Z. This convention is different
from standalone Hole and InsertPocket features, whose +Z points into material.

The outermost clearance role defines the screw seat. Its Z position is
`offset + thickness - head_recess.depth` (zero recess when absent). Layers
passed through `via=` must continuously cover the grip without gaps or overlaps.
Each intermediate instance needs its own placement.

## Insert mount

::: cadkit.design.mounts.InsertMount
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      inherited_members:
        - clearance_side
        - middle_side
      members:
        - clearance_side
        - middle_side
        - insert_side
        - describe

## Threaded mount

::: cadkit.design.mounts.ThreadedMount
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      inherited_members:
        - clearance_side
        - middle_side
      members:
        - clearance_side
        - middle_side
        - threaded_side
        - describe

## Pocket and recess dimensions

::: cadkit.design.mounts.Counterbore
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.mounts.InsertPocket
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - feature

::: cadkit.design.mounts.InsertBoss
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

## Resulting role

::: cadkit.design.mounts.MountFeature
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      members:
        - seat
        - apply
        - describe

## Hardware attachments without placement

Use `assembly.attach()` for individually named features within an already
placed part or set of parts. These recipes derive hardware positions from
the features. They do not invent receiving geometry or a placement relationship.

::: cadkit.design.attachments.CaptiveNutFastening
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - describe

::: cadkit.design.attachments.SetScrew
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - describe
