# Author models people can change

For new designs, substantial extensions and source reviews. Respect existing
consumer conventions; a small edit does not authorise restructuring the project.

## Ownership

| Decision | Owner |
| --- | --- |
| Independent inputs and shared mating profiles | The part or nearest common subsystem that needs them |
| Derived dimensions | Expressions/properties beside their source inputs |
| Local body and owned features | Pure builder and Part definition |
| Manufacturing | The Part's process declaration |
| Installed layout | Assembly frames, ports and connections |
| Project entry | Composition and `as_project()` |
| Evidence | Checks on authored/resolved geometry, not a parallel copied model |

Keep small models in one file. As a project grows, colocate subsystem dimensions,
parts, assembly and checks under `assemblies/<subsystem>/`; promote parts to
project-level `parts/` only for reuse across subsystems. Two instances of one
part do not require a new package. Do not create empty folders or a global bucket
for unrelated dimensions.

Dependencies flow from inputs to parts to assemblies to the project. Pass shared
data explicitly; a part should not import its containing project for dimensions.
Prefer imports from owning modules over re-export-only barrels. Namespace
packages need no `__init__.py`. File layout need not mirror the CAD assembly graph:
choose assembly ownership according to placement and physical interfaces.

## Inputs and geometry

Use [`ck.Dimensions`](api.md#design-inputs) for coherent configurable inputs and
publish that same configuration's `parameters()`. Derived properties are not
independent controls. An input changing only metadata does not control geometry;
use `measured=True` for measured Parameter records. Rebuild changed configurations
instead of retaining cached geometry from mutable inputs.

Name physical dimensions and units, derive mating shapes from one shared profile,
and distinguish modelling tolerances from manufacturing allowances. Geometric
station tables need named fields or an explained schema. Axis vectors, halves
and origins need no artificial constant names. Record measured or deliberately
tuned values honestly rather than inventing parametric relationships.

## Declarations and boundaries

Use `ck.Part`, process declarations and Assembly methods directly. Pure shape
builders, part factories and meaningful assembly constructors are useful;
generic wrappers combining registration, manufacture and placement hide the edit
path and create a second authoring language. Share immutable inputs and processes.

A nested assembly publishes ports for placement, `export_feature` for shared
mount roles and `export_component` for contact/clearance participants. Consumers
use these exports rather than mutating internals or depending on private paths.
See [assemblies](declarative-assemblies.md) for syntax and coordinate semantics.
Static Joint evidence does not create motion; use motion connections and attach
the components that move with them.

Direct CadQuery, imported geometry and fixed layouts remain valid boundaries.
Record datum, units and native/mesh provenance near the code. Keep domain-specific
design rules with the consumer; repeated registration/export infrastructure belongs
in CadKit.

## Worked example

The shaft-support package separates unit design from project composition. Read
only the files relevant to the edit; the complete package is bundled:

- [Run and modify](examples/shaft_support/README.md)
- [Project](examples/shaft_support/project.py)
- [Dimensions](examples/shaft_support/assemblies/bearing_unit/dimensions.py)
- [Parts](examples/shaft_support/assemblies/bearing_unit/parts.py)
- [Assembly](examples/shaft_support/assemblies/bearing_unit/assembly.py)
- [Checks](examples/shaft_support/assemblies/bearing_unit/checks.py)
- Package files: [root](examples/shaft_support/__init__.py), [assemblies](examples/shaft_support/assemblies/__init__.py), [bearing unit](examples/shaft_support/assemblies/bearing_unit/__init__.py)

## Review a substantial design

Trace a controlling dimension through body, mating features, placement and checks.
A reader should find each responsibility without hidden side effects or copied
inputs. For a configurable subsystem, rebuild a representative input change and
verify the intended geometric effect and fit, using consumer checks or a focused
native comparison. Tests of names or file layout do not establish that behaviour.
