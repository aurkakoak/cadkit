# CadQuery and CadKit

CadQuery describes geometry in Python. CadKit gives that geometry a project
structure: which bodies are manufactured parts, where their instances belong,
which hardware connects them, what should be checked, and what should be
exported. A useful CadKit project can start with one ordinary CadQuery builder.

That division keeps the shape construction familiar. You can keep an existing
Workplane chain, a carefully chosen datum or a bespoke boolean operation.
CadKit does not require a second modelling language for the shape itself.

## Two ways to describe a project

The base API, imported from `cadkit`, accepts explicit builders and already
placed geometry. A `Part` names a manufacturing definition. A `Component`
holds one installed shape. A `Project` collects those definitions along with
parameters, checks and mechanical declarations. This is the smallest adapter
for an existing CadQuery model: the application remains responsible for its
own placement calculations.

The experimental `cadkit.design` API gives parts named features and local
attachment frames. A part can own its clearance holes; another can own the
matching insert pockets. A shared mount recipe defines their common pattern,
and the assembly binds the two roles. The connection can derive placement,
hardware and mechanical declarations from the same inputs.

Both approaches use the same desktop and export system. Calling
`design_assembly.as_project()` produces an adapter to the Project contract.
This is why adopting CadKit does not require moving an entire project to the
design API at once.

| Concern | Base API | `cadkit.design` |
| --- | --- | --- |
| Custom shape | A zero-argument builder | A body builder, then owned features |
| Installed placement | Apply transforms in component builders | Fix instances or connect local frames |
| Manufacturing quantity | Set `Part.quantity` | Derive counts from assembly instances |
| Mechanical declarations | Supply joints, interfaces and fastenings | Derive supported contracts from features and connections; add explicit interfaces where needed |
| Current status | Existing supported contract | Experimental authoring namespace |

## Why a feature belongs to a part

A manufactured part needs a complete definition even when it is exported alone.
Putting a mounting hole in the part's feature list makes that ownership
explicit. Adding an assembly connection does not secretly alter its shape.
The same part therefore has the same geometry in a normal view, a service pose
and a manufacturing export.

Features also carry information a solid alone cannot communicate. A tapped
hole contains a pilot in the exported shape and a secondary tapping operation
in its description. A purchased threaded receiver can declare an interface
without pretending that CadKit manufactures it. A screw envelope can be useful
for layout while remaining identified as incomplete supplier geometry.

## Deliberate scope

Design assembly placement is a directed calculation. Each instance has a fixed
frame or one placement parent. Revolute and slider connections add explicit
motion coordinates; couplings calculate one coordinate from another. This
supports predictable composition, but does not solve arbitrary closed-loop
constraints.

CadKit also leaves process decisions explicit. It does not choose an unknown
material, infer a screw length from a picture, predict a printer's fit allowance
or execute a secondary operation. Those inputs belong to the project and its
physical verification.

See [Adopt an existing model](../how-to/adopt-cadquery.md) for the base API,
or follow the [tutorial](../tutorials/index.md) to add features incrementally.
