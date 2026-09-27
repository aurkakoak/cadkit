# Modelling

Use `cadkit --project module:PROJECT describe` to discover definitions, parameters,
source locations and checks; `inspect PART` examines one definition. Run commands
from the consumer root with its configured Python. Geometry belongs in Python
builders, not generated STEP/STL/Blender output. Parameters describe source
inputs; they are not live UI setters. Rebuild after changing the source.

## Choose the relevant authoring reference

| Change | Reference |
| --- | --- |
| New design, substantial extension or structure review | [Authoring](authoring.md) |
| Part, process, quantity, input or check syntax | [API](api.md) |
| Feature ownership and shared mounts | [Parts and features](declarative.md) |
| Holes, fits, seals, bosses or layered mounts | [Manufacturing features](manufacturing-features.md) |
| Placement, nested interfaces, motion or named poses | [Assemblies](declarative-assemblies.md) |
| Export schema, units or native/mesh boundary | [Contracts](contracts.md) |

A Part is a local manufacturing definition; `Assembly.add()` creates an installed
instance. Keep local body, print orientation and installed placement distinct,
applying each transform once. Compose with frames/connections and compile through
`as_project()`. Preserve material, quantities, variants and native/mesh provenance.
An edit to one definition can affect every instance.

Encode the physical requirement: intersection checks for forbidden collisions or
required interference; `contact_pair` for true surface contact, which can have
zero intersection volume. Run relevant CadKit checks and consumer regressions.
A valid solid or an empty passing check set does not establish fit or readiness.

For visual verification and explaining changes, use [shared review](interaction.md).
For exports or slicing, use [fabrication](workflows.md) when requested. Report
remaining unknown interfaces and approximation limits; geometry checks do not
establish physical validation.
