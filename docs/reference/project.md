# Project model

```python
import cadkit as ck

assembly = ck.Assembly("fixture")
plate = ck.Part("plate", body=plate_body, manufacture=ck.FDM("PETG"))
assembly.fix(assembly.add("plate", plate))
PROJECT = assembly.as_project()
```

Create a Project with [`Assembly.as_project()`](design-assemblies.md#cadkit.Assembly.as_project).
It takes a snapshot of the authored graph for the CLI, desktop, validation and
exporters. Geometry stays lazy; all coordinates use millimetres.

## Manufacturing inventory

Installed manufactured definitions become project parts with quantities inferred
from their instance counts. Add uninstalled coupons and variants using
`extra_parts=(COUPON,)`; override production totals with
`quantities={"plate": 4}`. Quantity overrides must name registered definitions and
be positive integers. Slicer selection can independently override a quantity to
zero to omit a part from that slice job.

A Part's `group`, `description`, `notes`, `production` and `expected_solids`
metadata travel into the compiled inventory. `production=False` excludes a part
from `build all`, while explicit selection can still export it. Multiple-solid
coupons should state their intended `expected_solids` count. Definition names
are unique artifact stems; reuse the same definition for repeated instances.

`parameters`, `checks` and `description` are keyword arguments to `as_project()`.
Use assembly interfaces and connections for supported mechanical requirements;
custom installed contracts can be supplied with `joints`, `interfaces` and
`fastenings` for static assemblies. These contracts use project coordinates and
cannot be combined with motion edges. Declare moving hardware and interfaces on
the assembly graph so they follow the selected pose.

## Project inspection and output

::: cadkit.Project
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      show_signature: false
      inherited_members: true
      members:
        - get_assembly
        - get_components
        - select
        - describe
        - mechanical_descriptions
        - validate_mechanics

Project parts are resolved manufacturing records used by output tooling.
Author geometry through [`Part`](design-parts.md#cadkit.Part); use its `build()`
for local geometry and `build_for_print()` for print orientation and bed contact.
Installed component records returned by project methods carry resolved world
geometry, stable paths and definition metadata for inspection and exports.

## Parameters

::: cadkit.Parameter
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

Parameters describe source inputs and their units. They are not setters or live
UI controls; edit the source and rebuild to change a dimension.

## Checks

::: cadkit.Check
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

`Check` runs through [run_checks](export.md#cadkit.export.run_checks).
For automatic collision scans and hardware engagement, use
[mechanical validation](mechanics.md). An empty set of custom checks cannot
establish that a design has been physically validated.
