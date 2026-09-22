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

## Design inputs

Use a frozen, keyword-only dataclass derived from `ck.Dimensions` for a unit's
configurable inputs. Declare each instance field with `ck.input`, and express
derived dimensions as ordinary properties. Pass the same configuration to the
part and assembly builders that consume it.

```python
from dataclasses import dataclass, replace
import cadkit as ck


@dataclass(frozen=True, kw_only=True)
class BearingDimensions(ck.Dimensions):
    shaft_diameter: float = ck.input(
        default=8.0, unit="mm", description="Nominal shaft diameter", gt=0,
    )
    radial_clearance: float = ck.input(
        default=0.2, unit="mm", description="Gap between shaft and bore", ge=0,
    )
    support_span: float = ck.input(
        default=70.0, unit="mm", description="Distance between support centres", gt=0,
    )
    support_thickness: float = ck.input(
        default=12.0, unit="mm", description="Support thickness along the shaft", gt=0,
    )

    @property
    def bore_diameter(self):
        return self.shaft_diameter + 2 * self.radial_clearance

    def validate(self):
        if self.support_span <= self.support_thickness:
            raise ValueError("Support centres must be farther apart than their thickness")


dimensions = BearingDimensions()
parameters = dimensions.parameters(scope="bearing")
larger = replace(dimensions, shaft_diameter=10.0)
```

The field annotations are `float`, `int`, `bool` or `str`. CadKit validates their
types, finite numeric values and declared `gt`, `ge`, `lt` and `le` bounds when
constructing the configuration. Override `validate()` for relationships between
fields; do not replace `__post_init__`, which runs the common validation.
Omit `default` to require an input at construction. Profile tables and other
structured shape data remain separate named data.

`dimensions.parameters(scope="bearing")` returns a tuple of `Parameter`
records for the input fields, including their units, descriptions and source
file when available. Names include the scope, such as `bearing.shaft_diameter`.
Properties such as `bore_diameter` are derived values and are not independent parameters.
Pass the tuple to `assembly.as_project(parameters=parameters)`. A scope only
names metadata: it does not rename parts, instances or assembly paths.

The unit string labels the value; it does not convert it. Supply lengths in
millimetres and angles in the units expected by the consuming API. A configuration
does not track its consumers or update geometry automatically. Use
`dataclasses.replace` to create a validated variant, then run the builders again
and compile that variant's assembly and parameter metadata together.

::: cadkit.Dimensions
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - parameters
        - validate

::: cadkit.input
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Parameter metadata

::: cadkit.Parameter
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

Parameters describe source values and their units. They are not setters or live
UI controls. `Dimensions.parameters()` produces them from an authored
configuration. Direct `ck.Parameter(...)` records are also accepted by
`as_project(parameters=...)` for measurements, imported values or metadata owned
outside a Dimensions class. Use `measured=True` for measured values and describe
their source. Edit the source and rebuild to change the design.

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
