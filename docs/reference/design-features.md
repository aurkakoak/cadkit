# Manufacturing features

```python
from cadkit import design as d
```

These **experimental** objects belong in `d.Part(features={...})`. Features
run in dictionary insertion order. Dimensions and allowances use millimetres;
angles use degrees. `apply(body)` returns a valid native Shape and `describe()`
returns metadata; Part calls both at the appropriate boundary.

For entry-based cuts, `at.origin` is the entry face and **+Z points into the
material**. A downward cut from the top of a 10 mm block uses
`d.Frame(origin=(0, 0, 10), z=(0, 0, -1))`. This differs from the
[mating-datum convention used by mounts](design-mounts.md).

A pattern repeats the feature at local XY sites. `None` means one site at
`(0, 0)`. Every cutting site must actually remove material; missed bodies and
invalid results raise a feature-named error. A through cut needs an explicit
depth that spans the material.

## Round holes

::: cadkit.design.manufacturing.Hole
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.manufacturing.CounterboredHole
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.manufacturing.CountersunkHole
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - recess_depth

CounterboredHole uses [`d.Counterbore`](design-mounts.md#cadkit.design.mounts.Counterbore).
CountersunkHole produces a recess without requiring a rendered countersunk
fastener; that hardware kind is currently unsupported.

## Threaded pilots and bearing seats

::: cadkit.design.manufacturing.TappedHole
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.manufacturing.BearingSeat
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - diameter

## Slots and nut traps

::: cadkit.design.manufacturing.Slot
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.manufacturing.NutPocket
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

## Shaft bores and seals

::: cadkit.design.manufacturing.DBore
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.manufacturing.SealGroove
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

## Reinforcement

::: cadkit.design.manufacturing.Boss
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

See [InsertBoss](design-mounts.md#cadkit.design.mounts.InsertBoss) for a boss
that also owns its insert pocket and installation intent.
