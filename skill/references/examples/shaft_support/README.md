# A shaft on two supports

This small assembly demonstrates how to keep a configurable CadKit model readable.
The two support instances share one manufactured Part. Their journal bores and
the shaft use the same dimensions, while assembly connections own their placement.

Copy the entire `shaft_support` folder into your model directory. With CadKit
installed in that directory's Python environment, run:

```sh
python -m cadkit.cli --project shaft_support.project:PROJECT describe
python -m cadkit.cli --project shaft_support.project:PROJECT check --output-dir /tmp/shaft-support-checks
python -m cadkit.cli --project shaft_support.project:PROJECT validate-assembly --output /tmp/shaft-support-validation.json
python -m cadkit.cli --project shaft_support.project:PROJECT build all --output-dir /tmp/shaft-support-parts
```

The example uses the installed public API and needs no framework checkout. When
running it directly from the CadKit repository root, use
`examples.shaft_support.project:PROJECT` instead.

The bearing unit's files live together under `assemblies/bearing_unit/`:

```text
shaft_support/
    project.py
    assemblies/
        bearing_unit/
            __init__.py
            dimensions.py
            parts.py
            assembly.py
            checks.py
```

Within that package, `dimensions.py` owns immutable inputs and derived mating
dimensions. Its frozen dataclass inherits `ck.Dimensions`: each `ck.input`
declares a default, unit, description and positive range once. CadKit validates
the input types, finite values and ranges; the local `validate()` method adds
the requirement that the support span exceed the support thickness. Ordinary
computed properties derive bore diameter, axis height and lengths from those
inputs. `parts.py` owns pure local body builders, the journal Hole,
attachment Frames and explicit manufacturing definitions. `assembly.py` places
their instances and declares motion, clearance and contact. `checks.py` owns
the unit's custom geometry checks. The package exposes configuration, assembly
and evidence factories; `project.py` uses that public interface to compile
`PROJECT` for the CLI and desktop.

These parts belong to this subsystem. If a part is later reused by several
different subsystems, move that shared definition into a project-level `parts/`
package. This example has one subsystem, so it needs no shared-parts directory.
Python package organization does not add levels to the installed CAD tree.

The base has its bottom at Z=0. A support's origin is the centre of its bottom
face. Its bore entry frame is also the shaft's placement datum. The shaft starts
at its own left end and runs along +X. One revolute connection places it from
the left support; a clearance interface checks its fit in each support. No body
builder knows either support's installed position.

Create another independent configuration without changing existing definitions:

```python
from shaft_support.assemblies.bearing_unit import Dimensions
from shaft_support.project import make_project

PROJECT = make_project(Dimensions(shaft_diameter=10, support_span=85))
```

The new shaft diameter enlarges both bores and the support walls' outer envelope.
The new span moves the supports and changes the shaft and base lengths. The
shaft's axis height and journal placement follow those dimensions. There is no
mutable parameter object or geometry cache to invalidate. Displayed Parameters
come from `dimensions.parameters(scope="bearing")`, which includes all eight
declared inputs and their source locations. The scope distinguishes this unit's
input names when a project collects parameters from several subsystems. Derived
properties are not independent inputs and are not automatically listed.
Parameter metadata describes the source values; it does not create editable UI
controls or update existing geometry. Build a new project from a new Dimensions
instance, or use `dataclasses.replace(dimensions, shaft_diameter=10)` to create
a validated variant of an existing configuration.

There are three manufacturing definitions and four installed instances: one
base, two supports and one shaft. Print orientation is separate from placement;
the shaft and support bores are vertical for fabrication. All four instances
share one assembly owner so their contact and clearance interfaces can refer to
the participating leaves directly.

The supports rest on the base; no fasteners or axial shaft retention are modelled.
The nominal radial clearance is a design input to calibrate for the chosen
printing process. The circular shaft looks identical in the `quarter-turn` pose,
although its frame rotates. Clearance checks establish this model's geometric
gaps; they do not establish bearing load capacity or printed fit.
