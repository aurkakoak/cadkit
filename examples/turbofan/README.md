# TF-300: an educational turbofan

A 300 mm cutaway engine with a swept fan, eight compressor and turbine rotors,
two independently rotating spools, removable upper covers and a display stand.
It demonstrates how to keep a substantial CadKit model readable: inputs own
design decisions, parts own local geometry, and assembly connections own motion.

## Open and build

Run this example with CadKit 0.5.3 or later.
Prepare and activate a Python environment with the desktop extra, following
the [installation guide](../../docs/how-to/install.md). Copy this entire
`turbofan/` folder into your model directory and run these commands from the
directory containing it. Pass the same interpreter to the desktop:

```sh
cadkit-desktop --project-dir "$PWD" --project turbofan.project:PROJECT \
  --python "$(command -v python)"
python -m cadkit.cli --project turbofan.project:PROJECT describe
python -m cadkit.cli --project turbofan.project:PROJECT check --output-dir build/checks
python -m cadkit.cli --project turbofan.project:PROJECT validate-assembly --output build/validation.json
python -m cadkit.cli --project turbofan.project:PROJECT build all --output-dir build/parts
```

From the CadKit repository root, use `examples.turbofan.project:PROJECT` instead.
No repository internals, project-specific launcher or `__init__.py` files are
needed. These folders are Python namespace packages; imports name the module
that owns each definition.

`PROJECT` installs all 39 parts. Hide the three upper covers under **housing** for the cutaway reveal,
or open `turbofan.project:OPEN_PROJECT` to install only the 36 uncovered parts.
Both projects retain the three covers as optional manufacturing definitions.
`build all` exports the 36 production parts; request each optional cover by name
to export it too. Display visibility never changes production selection.

The named views `lp-45deg`, `hp-30deg` and `spools-turned` turn the indicated
spools. The fan, two LP compressor stages and two LP turbine stages follow the
LP shaft. Three HP compressor stages and the HP turbine follow the concentric
sleeve. The housing and stand stay fixed.

## Find the decision you want to change

```text
turbofan/
├── project.py                  # Entry points, configuration and evidence.
├── assembly.py                 # Five subsystems and the two spool connections.
├── interfaces.py               # Contact and clearance between subsystems.
├── checks.py                   # Full-turn envelopes and shaft interference.
├── dimensions.py               # Shared shaft fits and engine axis height.
├── profiles.py                 # Shared nacelle and core mating surfaces.
├── geometry.py                 # Pure construction helpers for the +X axis.
├── appearance.py               # Display colours.
├── parts/
│   └── rotor.py                # Rotor family used by both spools.
└── assemblies/
    ├── low_pressure/           # Fan, split shaft, LP rotors and end fittings.
    ├── high_pressure/          # Concentric sleeve and HP rotors.
    ├── housing/                # Inlet, nacelle halves and exhaust nozzle.
    ├── core/                   # Bearings, guides, combustor and bypass seats.
    └── stand/                  # Base, saddles and socket dimensions.
```

Each subsystem's `parts.py` exposes its part factory. Its `assembly.py` places
those parts, declares their internal relationships and exports selected ports
and contact participants. Its other files contain that subsystem's geometry
and specifications. Root `parts/rotor.py` exists
because both spools use the same rotor family; the distinctive fan stays in
`low_pressure/fan.py`.

The installed model contains five nested `ck.Assembly` instances. Root
`assembly.py` fixes the stand, housing and core, then connects each spool to its
core journal. Subsystem ports expose the attachment datums; exported components
let `interfaces.py` describe contacts between their leaves without reaching into
private instance trees. Each unit uses direct `add`, `fix` and `connect` calls.
`add(part)` inherits the definition's name and display group; geometry factories
return definitions without registering or placing them.

| Change | Start here |
| --- | --- |
| Fan blade shape | Named `FAN_SECTIONS` in `assemblies/low_pressure/fan.py` |
| Compressor or turbine stage | `RotorStage` records in that spool's `dimensions.py` |
| Shaft running or keyed fit | `ShaftFit` in root `dimensions.py` |
| Nacelle or core contour | `ShellStation` tables in root `profiles.py` |
| Base and saddle sizes | `StandDimensions` in `assemblies/stand/dimensions.py` |
| Spool placement and motion | Connections in root `assembly.py` |
| Parts within a subsystem | That subsystem's `assembly.py` |

## Inputs and local coordinates

Lengths are millimetres and angles are degrees. The engine runs along **+X**,
from the inlet toward the exhaust. Its axis is 108 mm above the base. Parts are
built around their own shaft axis, leading face or bottom centre; only the
subsystem assembly puts them at an engine station. Root assembly places the
subsystems. Manufacturing orientation is separate. Use
`assembly.locations(names="path")` to inspect the final leaf transforms without
building geometry; `locations()` reports the five immediate subsystem transforms.

Independent inputs use frozen `ck.Dimensions` dataclasses. Ordinary properties
derive mating dimensions: the same `ShaftFit` determines a shaft, its keyed
bores and its plain bearings. The nacelle and core profiles are also shared by
the supports that seat against them.

Create a variant in a sibling file, for example `my_engine.py`:

```python
from dataclasses import replace

from turbofan.dimensions import EngineDimensions, LOW_PRESSURE_FIT
from turbofan.assemblies.low_pressure.dimensions import Dimensions
from turbofan.project import make_project

PROJECT = make_project(
    engine=EngineDimensions(axis_height=112),
    lp_fit=replace(LOW_PRESSURE_FIT, radial_clearance=0.3),
    low_pressure=Dimensions(fan_blade_count=18),
    covers=False,
)
```

Open it with `--project my_engine:PROJECT`. Raising the engine also changes the
saddle heights. The keyed clearance updates both the circular bore and its
flat. Blade count changes the fan geometry. The project's parameter metadata
comes from these same inputs; it describes source values, not live UI controls.

Blade sections and shell stations are drawing data with named fields, rather
than a claim that every contour has a useful scalar adjustment. After changing
them, run the checks and inspect the resulting surfaces.

## What the evidence establishes

Five geometry checks cover full-turn rotor clearance against the installed
stationary engine and interference between the shafts and their coupling.
The conservative swept envelopes use the actual native blade bounds, keeping
blade and hub axial spans distinct. Contact and clearance interfaces also
measure the saddle seats, core supports, cover seams and journals.

This is an educational display model, not an operating engine. All parts are
native solids with PLA print orientations, but the model has not been printed
or mechanically tested. Keyed fits and plain bearings need printer calibration;
rotor retention, bearing loads and cover attachment are not established by
clearance checks. The revolute connections express intended motion, not a
simulation of torque or friction.
