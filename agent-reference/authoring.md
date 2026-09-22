# Author models people can change

Use this guidance for new designs, substantial extensions and source reviews.
CadKit's default is explicit Python design intent: shared inputs feed local parts;
assemblies compose those parts; checks inspect the resolved design. Existing
consumer conventions and explicit user choices take precedence. Improve the
code you touch without turning a small geometry edit into an unsolicited rewrite.

## Put each decision with its owner

| Responsibility | Owner | Keep out |
| --- | --- | --- |
| Independent dimensions, fits, station data | A cohesive design specification or the part that alone needs it | A second copy of a mating profile or datum |
| Derived dimensions | Expressions/properties next to their source inputs | Independent literals for dimensions that must track one another |
| Local body and owned features | Pure builder and `ck.Part` definition | Installed offsets, global registration and viewer state |
| Manufacturing | The part's `ck.FDM` or other process declaration | Placement of its installed instances |
| Installed layout and relationships | `ck.Assembly`, frames, ports and connections | Reshaping the definition to bake in each instance's location |
| Project entry point | Composition and `as_project()` | An entire machine's body builders |
| Evidence | Checks against the authored/resolved geometry | A parallel model rebuilt from copied dimensions |

Keep a small model in one file when its responsibilities remain clear. For a
growing project, use subsystem colocation as the default:

```text
project.py                     # Compose the complete machine.
parts/                         # Parts reused across different subsystems.
assemblies/
    fan/
        __init__.py            # The subsystem's public interface.
        dimensions.py          # Fan inputs, profiles and derived dimensions.
        parts/                 # Fan-specific definitions; parts.py also works.
        assembly.py            # Local placement and relationships.
        checks.py              # Fan requirements and their geometric evidence.
    casing/
        ...
```

Keep inputs and checks near the subsystem that owns them. Shared mating data
belongs at the nearest common owner and is passed explicitly to its consumers;
do not collect every dimension in a global configuration file. Promote a part to
project-level `parts/` when it is needed across subsystems. Do not create empty
folders or move a part merely because it has two instances within one subsystem.
Avoid miscellaneous `utils.py` collections with unrelated responsibilities.

A subsystem publishes its construction function and the configuration its
callers need through `__init__.py`; a nested CadKit Assembly publishes attachment
ports. Other subsystems should not import its private parts or mutate its
internal instances. Dependencies run from inputs to parts to assemblies to the
project. A part must not import its containing project to discover dimensions.
File organization does not require every folder to become a nested CAD assembly:
choose graph ownership according to real placement and interface relationships.

## Describe relationships, not a collection of coordinates

Name editable dimensions by their physical meaning and document units. Derive
the bore from shaft diameter and radial allowance; derive placement from the
support datum. Keep one profile definition when a shell and its supports share
that surface.

For a configurable unit, use `@dataclass(frozen=True, kw_only=True)` on a
`ck.Dimensions` subclass. Declare each `float`, `int`, `bool` or `str` input with
`ck.input(default=..., unit=..., description=...)`, adding `gt`, `ge`, `lt` or
`le` for numeric bounds. Common type, finite-value and range checks run at
construction. Put cross-field requirements in `validate()`, not `__post_init__`;
keep derived dimensions as ordinary properties. Keep this configuration beside
the subsystem that owns it, not in a machine-wide collection of every input.

Pass that same configuration to the builders and to
`dimensions.parameters(scope="bearing")` at project compilation. Generated
`ck.Parameter` records carry the input metadata and source location; do not
handwrite a duplicate parameter-registration list. Scope only prefixes metadata
names, such as `bearing.shaft_diameter`; it does not rename assembly objects.
The unit string is a label, not a conversion. Use `dataclasses.replace` for a
validated variant and build it again. There are no live setters or automatic
dependency updates. See [API](api.md#design-inputs) for an executable pattern.

An input that only changes parameter metadata is not an editable geometry
control. Label measured/report-only values accordingly. Direct `ck.Parameter`
records remain appropriate for measurements or externally supplied metadata;
use `measured=True` for measured values.

Geometric data may contain numbers. A blade station table should identify radius,
chord, angle and units with named fields or an explained data schema. Numerical
origins, axis vectors, halves and full turns need no artificial constant names.
Distinguish a modelling tolerance from a manufacturing allowance. Explain any
deliberately tuned dimension instead of implying a relationship that is untrue.

## Keep the framework visible

Write `ck.Part`, process declarations, `Assembly.add`, `fix` and `connect`
explicitly. A pure blade builder, reusable part factory or function that returns
a meaningful assembly is useful abstraction. A generic `add(...)` that creates
a part, updates registries, picks manufacture, converts colours and places the
instance introduces a second authoring language. Do not add that layer merely
to shorten repeated declarations. Share immutable inputs and process objects
instead. Use keyword arguments and named data for repeated part families.

Bodies have a stated local datum. Assembly frames place them once; print frames
are independent. Use ports for meaningful mating datums and connections for
relationships. `production=False` controls default manufacturing selection;
installed presence, viewer visibility and manufacturing quantity are separate.
Use local `assembly.interface()` declarations for mechanical evidence where
supported. Static `ck.Joint` records describe evidence; actual motion requires
connections such as `ck.Revolute` and components attached to the moving unit.

Nested assemblies publish ports for placement. Current `assembly.interface()`
participants must be leaf instances of that same assembly: an exported port is
not a reference to a nested contact participant. Keep interacting leaves at a
common owner when appropriate; record a genuine composition gap rather than
hiding it behind paths or an invented wrapper API. See [assemblies](declarative-assemblies.md).

## A worked example, available with this skill

The shaft-support example colocates one bearing unit's design and checks, with
project composition outside it. Its two support instances reuse one local Part;
there is no cross-subsystem reuse requiring a root `parts/` folder yet. Read the
files relevant to the edit; they form one ordinary Python package:

- [Package](../examples/shaft_support/__init__.py)
- [Assembly package](../examples/shaft_support/assemblies/__init__.py)
- [Bearing unit's public interface](../examples/shaft_support/assemblies/bearing_unit/__init__.py)
- [Unit dimensions](../examples/shaft_support/assemblies/bearing_unit/dimensions.py)
- [Unit parts](../examples/shaft_support/assemblies/bearing_unit/parts.py)
- [Unit assembly](../examples/shaft_support/assemblies/bearing_unit/assembly.py)
- [Unit checks](../examples/shaft_support/assemblies/bearing_unit/checks.py)
- [Project](../examples/shaft_support/project.py)
- [Run and modify it](../examples/shaft_support/README.md)

This is the recommended default; use a different layout when an existing
convention or a concrete design need justifies it. The public
[project-structure guide](../docs/explanation/project-structure.md) explains the
same defaults for human readers.

## Review the edit a person will make next

Before presenting a substantial generated design as complete, inspect its source
as well as the model. Can a reader find the controlling dimension, trace its
geometric effect and locate each part's manufacture and assembly placement? Are
mating surfaces derived from the same data? Do repeated definitions reuse parts
without sharing unintended placement state? Does a meaningful input change
preserve the intended fit and update the relevant checks?

For an example or a configurable subsystem, validate a representative dimension
change, not only the default values. Rebuild from the changed inputs; avoid caches
that retain geometry after mutable configuration changes. Use existing consumer
checks or a focused native comparison rather than tests that only check names,
file layout or formatting.

Direct CadQuery bodies, imported geometry and fixed layouts remain supported
escape hatches. State the datum, units and the reason for the boundary near that
code, keep it local, and preserve native/mesh provenance. Do not invent idealized
parametric relationships for vendor geometry. Repeated infrastructure needs
across projects are candidates for CadKit itself; consumer-specific design rules
stay with the design.
