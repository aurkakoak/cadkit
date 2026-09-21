# Parts and frames

```python
import cadkit as ck
```

Definitions own local geometry and manufacturing intent; an
[assembly](design-assemblies.md) supplies installed placement. `Part.build()`
returns local geometry. `Part.build_for_print()` applies the declared fabrication
orientation and moves the result onto the bed.

Bodies can be native CadQuery shapes or explicit `cadkit.geometry.Mesh` values.
Native-only manufacturing features, finishing callbacks and sheet validation
require native bodies. Mesh parts retain their provenance and export STL, with
explicit omission reporting for STEP.

Manufacturing groups, notes, production inclusion and expected solid counts belong
to the Part. See [Project inventory](project.md#manufacturing-inventory) for
uninstalled coupons, variants and quantity overrides.

::: cadkit.Part
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - build
        - build_for_print
        - describe

## Feature protocol

Built-in [manufacturing features](design-features.md) and
[mount roles](design-mounts.md) satisfy this protocol. A custom feature must
return valid native geometry and describe its own manufacturing intent.

::: cadkit.Feature
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

## Manufacturing processes

`FDM("PETG", print_rotation=(90, 0, 0))` applies explicit X/Y/Z angles for
fabrication. When the design-to-fabrication transform is already known, use
`FDM("PETG", print_frame=ck.Frame(...))` instead. A `print_frame` cannot be
combined with nonzero `print_rotation`. Both paths move the final lowest Z
point onto the bed without changing installed assembly geometry.

::: cadkit.FDM
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.LaserCut
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - validate

## Purchased components

::: cadkit.Purchased
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - build
        - describe

## Frame

A Frame specifies orientation with two perpendicular axes, rather than Euler
angles. Use `Frame(origin=(0, 0, 10), z=(0, 0, -1))` for a downward-facing entry
at Z=10. A frame is a datum; it does not itself move or cut the body.

::: cadkit.Frame
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - location
        - from_location
        - describe

## Patterns

Patterns live in a feature's local XY plane. For a rectangular four-hole
pattern, for example:

```python
corners = ck.PointPattern(((-20, -12), (20, -12), (20, 12), (-20, 12)))
```

::: cadkit.PointPattern
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.PolarPattern
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - points
