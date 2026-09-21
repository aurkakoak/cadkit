# CadQuery and CadKit

CadQuery describes geometry in Python. CadKit gives that geometry a project
structure: which bodies are manufactured parts, where their instances belong,
which hardware connects them, what should be checked, and what should be
exported. A useful CadKit project can start with one ordinary CadQuery builder.

That division keeps the shape construction familiar. You can keep an existing
Workplane chain, a carefully chosen datum or a bespoke boolean operation.
CadKit does not require a second modelling language for the shape itself.

## From a body to a project

Import CadKit with `import cadkit as ck`. A `ck.Part` owns a body builder,
manufacturing metadata and any named features or attachment frames. An
`ck.Assembly` contains instances of those definitions. Fix an instance at a
frame or connect it to another instance, then call `assembly.as_project()` to
create the Project consumed by the CLI, desktop and exporters.

A part can own its clearance holes; another can own the matching insert pockets.
A shared mount recipe defines their common pattern, and the assembly binds the
two roles. The connection derives placement, hardware and mechanical declarations
from those inputs. Bespoke geometry can stay entirely in the body builder;
named features are useful when their intent and relationships matter.

| Concern | Where it belongs |
| --- | --- |
| Custom shape | A lazy body builder, optionally followed by owned features |
| Installed placement | Fixed instance frames or connections between local datums |
| Manufacturing quantity | Instance counts, with explicit totals and extra parts at `as_project()` |
| Mechanical requirements | Connections, contact/clearance interfaces, access envelopes and custom checks |
| Supplied geometry | `Purchased` definitions with explicit supplier identity and representation |

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

Assembly placement is a directed calculation. Each instance has a fixed frame
or one placement parent. Revolute and slider connections add explicit motion
coordinates; couplings calculate one coordinate from another. This supports
predictable composition, but does not solve arbitrary closed-loop constraints.

Native bodies support named manufacturing features. An explicit Mesh body can
participate in the same assembly and manufacturing inventory, but native-only
feature operations are unavailable for meshes. Mesh exports and STEP omissions
remain explicit.

CadKit also leaves process decisions explicit. It does not choose an unknown
material, infer a screw length from a picture, predict a printer's fit allowance
or execute a secondary operation. Those inputs belong to the project and its
physical verification.

See [Adopt an existing model](../how-to/adopt-cadquery.md) for wrapping a working
CadQuery builder, or follow the [tutorial](../tutorials/index.md) to add features
incrementally.
