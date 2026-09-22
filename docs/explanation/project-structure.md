# Structure a readable project

For a larger CadKit project, keep each subsystem’s dimensions, parts, assembly
and checks together. Reserve root `parts/` for definitions reused across
subsystems. This makes a design change easy to locate: a fan blade, its mating
shroud and its clearance checks belong near one another.

```text
turbofan/
├── project.py
├── dimensions.py              # Inputs shared across subsystems only.
├── parts/
│   └── bearing_carrier.py     # Reused by multiple subsystems.
└── assemblies/
    ├── fan/
    │   ├── dimensions.py
    │   ├── parts/
    │   │   ├── rotor.py
    │   │   └── shroud.py
    │   ├── assembly.py
    │   └── checks.py
    ├── compressor/
    └── nozzle/
```

A small model can start in one file. Within a subsystem, `parts.py` can hold a
few related definitions; use a `parts/` package when they need separate modules.
Move a part to root `parts/` when another subsystem actually reuses it. Two
instances within one subsystem do not require that move.

## Give each decision an owner

| Location | Responsibility |
| --- | --- |
| `dimensions.py` | Independent inputs, derived dimensions and named profile data |
| `parts.py` or `parts/` | Local geometry, owned features, ports and manufacturing definitions |
| `assembly.py` | Installed instances, placement and mechanical relationships |
| `checks.py` | The subsystem’s requirements and geometric evidence |
| `project.py` | Compose subsystems, collect evidence and compile `PROJECT` |

Dependencies flow from inputs to parts to assemblies to project composition.
Builders do not import their containing project or mutate its assembly. Checks
consume the resulting definitions and geometry; root-level checks cover
requirements spanning subsystems.

Keep shared inputs at their nearest common owner. A fan-only profile belongs
with the fan. A mounting pattern used by the fan and compressor is defined once
at their common owner and passed to both. Root `dimensions.py` should contain
only such shared inputs. Keep specialized geometry helpers beside their users;
avoid a root `utils.py` that collects unrelated responsibilities.

## Declare inputs once, derive the rest

Use a frozen, keyword-only dataclass derived from `ck.Dimensions`. Declare
independent scalar values with `ck.input`, including their units, descriptions
and bounds. Ordinary properties express relationships: for example,
`bore_diameter = shaft_diameter + 2 * radial_clearance`. Put cross-field rules
in `validate()`. The [design-input reference](../reference/project.md#design-inputs)
has a complete example.

Pass the same configuration to the relevant builders and generate metadata
with `dimensions.parameters(scope="fan")`. To make a variant, use
`dataclasses.replace`, rebuild from it and compile its metadata with the resulting
assembly. Parameters describe source values; they do not automatically change
geometry. Units label values without converting them.

Keep profile tables as named data with clear fields, units and coordinate
conventions. Name design choices and meaningful tolerances; numerical origins,
axis vectors and simple arithmetic factors need no artificial constant names.
Both mating geometry and its checks should use the same design inputs. A useful
check measures the resulting geometry rather than repeating its construction
formula.

## Make geometry and placement readable

Build each part around a useful local datum, such as a mounting face or shaft
axis. Keep `ck.Part` and `ck.FDM` visible where local geometry, features and
manufacturing intent are defined. Assembly code uses `add(part)` for instances,
`fix` for placed roots and `connect` for relationships between datums. Print
orientation remains separate from installed placement; production selection and
viewer visibility also have distinct meanings. See [parts and placement](parts-and-placement.md).

Import configuration and construction functions from their owning modules,
such as `fan.dimensions` and `fan.assembly`. Namespace packages need no
`__init__.py` files or modules that only re-export names. A reusable
`ck.Assembly` publishes attachment datums with `export_port` and selected contact
participants with `export_component`. Callers use those exports instead of
manipulating internal instances.

Source folders do not require an identical nested CAD graph. Choose assembly
boundaries for placement, reuse and mechanical relationships. A parent can
declare contact between exported parts in different subsystems through
`instance.component(name)`. See [nested contacts](../how-to/nested-assemblies.md#check-contact-between-subsystems)
for a complete example.

Pure geometry helpers and factories returning meaningful subassemblies keep code
reusable. Avoid a generic registration helper that secretly creates a Part,
chooses its manufacturing process, places it and controls visibility. Those
decisions should remain visible at CadKit call sites. Geometry builders should
stay lazy and free of file-writing or viewer side effects.

## Follow complete examples

The [turbofan example](../../examples/turbofan/README.md) applies this layout to
a complete sectional engine: housing, two rotating spools, stationary core and
display stand. Shared profiles define the shells and their mating supports;
explicit module imports connect the subsystems.

The [shaft-support example](../../examples/shaft_support/README.md) keeps its
bearing unit together under `assemblies/bearing_unit/`. Follow its
[dimensions](../../examples/shaft_support/assemblies/bearing_unit/dimensions.py)
through the [parts](../../examples/shaft_support/assemblies/bearing_unit/parts.py),
[assembly](../../examples/shaft_support/assemblies/bearing_unit/assembly.py) and
[checks](../../examples/shaft_support/assemblies/bearing_unit/checks.py), then see
how [project.py](../../examples/shaft_support/project.py) compiles them. Changing
the shaft diameter updates both support bores and their clearance evidence.

Existing CadQuery builders, imported geometry and custom checks remain useful
escape hatches. Keep each exception local and explain its datum, units and
reason. Preserve established project conventions when making a small change;
the layout above is a default for growth, not a reason for an unrelated rewrite.
See [validation and evidence](validation-and-evidence.md) for what checks establish.
