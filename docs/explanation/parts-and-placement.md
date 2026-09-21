# Parts, instances and placement

One bracket design might appear four times in an assembly and be printed in an
orientation unlike any of those installed positions. Keeping those facts
separate is central to CadKit's model.

A **Part** is the manufacturing definition: its builder, material, quantity
and export orientation. A **Component** is an installed instance: its name,
placed geometry, appearance and link to the Part. An **Assembly** organizes
instances into a hierarchy. Hardware may be a component without being a
printable Part; a fit coupon may be a Part without being installed anywhere.

## Three coordinate contexts

| Context | What the coordinates mean | Where the transform belongs |
| --- | --- | --- |
| Design | The part's own datums and dimensions | In the CadQuery body and its local features |
| Installed | The part's position in the complete object | In component placement, or a design assembly's resolved frames |
| Manufacturing | The orientation used for an individual exported part | In the Part's print rotation and bed normalization |

All use millimetres. Moving an installed lid upward should not also move its
print export above the bed. Rotating a part for printing should not turn the
assembled lid upside down.

In the base API, `Part.build(for_print=False)` returns the authored shape.
`Part.build()` applies X, Y and Z rotations in order, then translates Z so the
lowest point lies on the bed. It does not center X or Y. If a builder already
returns print-oriented geometry, adding another `print_rotation` would apply
that choice twice.

`cadkit.design.Part.build()` always returns design geometry. Its `as_part()`
adapter supplies the base Part's manufacturing behavior. The same word
`build` therefore has a different default at these two boundaries; use the
namespace and returned type to make the intended operation clear.

## A tree is not always a transform hierarchy

Base `cadkit.Assembly` objects organize shapes already placed in world
coordinates. Nesting a Component under a subassembly does not transform it
again. This lets an existing CadQuery assembly retain its placement logic
while gaining a useful inspection tree.

`cadkit.design.Assembly` resolves local frames through a directed placement
graph, including nested assemblies and their motion. It applies the resulting
transform to each native body and adapts the result to the base assembly
contract. Exporting a named pose changes installed geometry while leaving
manufacturing definitions unchanged.

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

In the base API, manufacturing quantities are explicit and independent of
the number of displayed components. A spare or a chosen production set can
make those counts differ. The design adapter instead counts manufactured
instances in its assembly snapshot. Hardware quantities come from declared
sites and stack members, or purchased inventory, rather than printable Part
counts.

This distinction also explains why STL and assembled STEP serve different
purposes: the first commonly describes a part ready for manufacturing, while
the latter records installed components for assembly review.

See [Export parts and run checks](../how-to/export-and-check.md) and
[Nest assemblies and name poses](../how-to/nested-assemblies.md) for practical
examples.
