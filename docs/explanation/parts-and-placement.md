# Parts, instances and placement

One bracket design might appear four times in an assembly and be printed in an
orientation unlike any of those installed positions. Keeping those facts
separate is central to CadKit's model.

A **Part** is a manufacturing definition: a local body, manufacturing process,
features and attachment ports. An **instance** places a definition in an
**Assembly**. A **Purchased** definition represents supplied hardware or reference
geometry and contributes to the purchased BOM. A fit coupon can be a Part without
being installed anywhere.

## Three coordinate contexts

| Context | What the coordinates mean | Where the transform belongs |
| --- | --- | --- |
| Design | The part's own datums and dimensions | In the CadQuery body and its local features |
| Installed | The part's position in the complete object | In fixed frames and assembly connections |
| Manufacturing | The orientation used for an individual exported part | In `FDM.print_rotation` or `FDM.print_frame`, then bed normalization |

All use millimetres. Moving an installed lid upward should not also move its
print export above the bed. Rotating a part for printing should not turn the
assembled lid upside down.

`Part.build()` returns local design geometry. `Part.build_for_print()` applies
X, Y and Z rotations in order, then translates Z so the lowest point lies on the
bed. It does not center X or Y. Start with the design body and declare print
rotation once in `FDM`, or use its `print_frame` for an explicit fabrication
frame; a builder that already returns print-oriented geometry
would apply that rotation twice.

## Assembly frames compose

An Assembly resolves local frames through a directed placement graph, including
nested assemblies and their motion. Each instance is fixed or connected to one
placement parent. The resolved transform places each body once. Reusing a nested
assembly creates independent instances of its parts and scoped motion coordinates.

`assembly.as_project()` takes a snapshot for the CLI, desktop and exporters.
Exporting a named pose changes installed geometry while leaving manufacturing
definitions unchanged. Later source-graph edits do not modify an existing Project;
compile it again after editing the graph.

Feature frames also have a specific purpose. An individual hole's entry frame
has +Z pointing into the material. Shared mount roles use +Z from the receiver
toward the clamped part. These conventions are not interchangeable; the
[feature reference](../reference/design-features.md) states the convention
for each constructor.

## Names and quantities carry different meanings

A manufacturing name such as `bracket` identifies an artifact. Instance names
such as `left-bracket` and `right-bracket` identify locations. Stable names and
parentage give the desktop stable paths, so a rebuild can preserve selection,
visibility and attached notes. Renaming or reparenting creates a new identity.

Manufacturing quantities default to the number of installed instances. Pass
`quantities={"bracket": 6}` to `as_project()` to make a different production total,
for example four installed brackets and two spares. Extra definitions such as
coupons enter through `extra_parts=(COUPON,)`. Set `production=False` on an
optional definition so it is built only when selected explicitly. Visibility,
explosion and named poses do not alter manufacturing quantities.

`Part.group` controls manufacturing selections and output folders. An instance's
`group` controls display organization independently. Hardware quantities come
from declared fastening sites and stack members, or purchased inventory.

This distinction also explains why STL and assembled STEP serve different
purposes: the first commonly describes a part ready for manufacturing, while
the latter records installed components for assembly review.

See [Export parts and run checks](../how-to/export-and-check.md) and
[Nest assemblies and name poses](../how-to/nested-assemblies.md) for practical
examples.
