# Design APIs that preserve responsibility

CadKit should make an understandable design straightforward to write. The
[authoring model](../explanation/project-structure.md) is a design constraint
for the framework, its examples and its agent skill. A shorter call is useful
when it preserves ownership and intent; hiding several decisions in one call
can make the resulting project harder to edit.

## Keep the contracts distinct

A `Part` owns local geometry, manufacturing and local features. An assembly
instance owns an installed occurrence. Frames and connections describe placement
and motion; manufacturing transforms describe fabrication. Compilation gives the
desktop, checks and exporters a consistent snapshot of that design.

Preserve these distinctions when adding conveniences:

- Creating a definition must not silently register or install an occurrence.
- A manufacturing-selection flag must not also control installation or visibility.
- A print orientation must not alter assembly placement.
- Reusing a definition must not share accidental pose or placement state.
- A mechanical declaration must identify the geometry it checks and follow its
  supported pose; metadata alone must not imply simulated motion or proven fit.

Arguments should name physical concepts, state coordinate context and units, and
make required decisions explicit. Validate contradictory ownership or placement
early. Do not infer physical relationships from names, display groups or colour.

## Make composition useful

Parts and subsystems should publish the datums and features their callers need.
The recommended consumer layout colocates subsystem parts, dimensions and
checks, with project-level parts reserved for reuse across subsystems. A
subsystem's Python interface, exported ports and exported contact participants
should let that organization work without callers reaching into private
implementation files.
Callers should not need private registries, duplicate geometry or knowledge of a
subsystem's implementation to place it or express a supported relationship.
Prefer extending an existing responsibility over adding a parallel authoring API.

Evaluate an API proposal with a complete consumer example. Can a person change
a controlling dimension, reuse a part, move a subsystem and inspect its fit
without rewriting unrelated code? Does the declaration remain understandable
without a consumer wrapper around every operation?

`add(part)` infers the instance name, and a manufactured instance inherits its
Part's group unless explicitly overridden. These defaults remove repetition
while keeping identity and manufacturing ownership clear. Aliases still name
distinct occurrences; a display override must not mutate a Part.

Nested contacts use explicit exported participants. `export_component` exposes
a leaf, and `instance.component(name)` binds it to a particular occurrence.
Preserve that identity through reuse, re-export, motion and project snapshots.
An interface region belongs to its declaring assembly's frame. Keep component
references distinct from placement ports and document geometry evidence limits.

## Keep escape hatches bounded

Ordinary CadQuery builders, explicit fixed frames, imported geometry and custom
checks allow designs outside a convenience primitive's scope. Preserve their
coordinate, provenance and validation contracts. A caller should be able to use
one specialized builder without replacing the rest of the framework.

Keep domain choices such as an engine's blade profile in its project. Promote a
consumer helper into CadKit when repeated usage demonstrates a general concept
with a clear owner and contract. Generalizing a single model's registration
shortcut is not sufficient evidence.

## Ship the usage, not just the constructor

An API change should include a readable usage example and corresponding human
and agent guidance. Test a meaningful variation of the example: a changed fit,
reused instance or different placement should exercise the relationship the API
promises. Also check that local geometry and fabrication remain independent of
installed placement. Tests of spelling or a preferred folder tree cannot show
that the API produces maintainable designs.

Review [documentation maintenance](documentation.md) for executable examples and
standalone skill generation.
