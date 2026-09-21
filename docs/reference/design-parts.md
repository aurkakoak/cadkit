# Declarative parts and frames

```python
from cadkit import design as d
```

This is the implemented **experimental** authoring namespace. Definitions use
local native CadQuery geometry; an [assembly](design-assemblies.md) supplies
installed placement. The stable registry remains available in
[`cadkit.project`](project.md).

::: cadkit.design.parts.Part
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - build
        - as_part
        - describe

## Feature protocol

Built-in [manufacturing features](design-features.md) and
[mount roles](design-mounts.md) satisfy this protocol. A custom feature must
return valid native geometry and describe its own manufacturing intent.

::: cadkit.design.parts.Feature
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

## Manufacturing processes

::: cadkit.design.parts.FDM
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.parts.LaserCut
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - validate

## Purchased components

::: cadkit.design.purchased.Purchased
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

::: cadkit.design.frames.Frame
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
corners = d.PointPattern(((-20, -12), (20, -12), (20, 12), (-20, 12)))
```

::: cadkit.design.frames.PointPattern
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.design.frames.PolarPattern
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - points
