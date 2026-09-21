# Project model

```python
from cadkit import Project, Part, Component, Assembly, Parameter, Check
```

These are the stable 0.2 contracts. A Part is a manufacturing definition; a
Component is one already positioned instance. Both builders and assembly
callables stay lazy. All geometry uses millimetres.

For definitions with owned holes and connection datums, see
[declarative parts](design-parts.md). Their adapters preserve this contract.

::: cadkit.project.Project
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - get_assembly
        - get_components
        - select
        - describe
        - mechanical_descriptions
        - validate_mechanics

::: cadkit.project.Part
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - build
        - describe

::: cadkit.project.Component
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - placed

::: cadkit.project.Assembly
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - components

::: cadkit.project.Parameter
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members: false

::: cadkit.project.Check
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members: false

`Check` runs through [run_checks](export.md#cadkit.export.run_checks).
For automatic collision scans and hardware engagement, use
[mechanical validation](mechanics.md).
