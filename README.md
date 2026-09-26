# CadKit

![CadKit desktop showing a CAD model](docs/assets/cadkit-desktop.png)

```python
# project.py
import cadquery as cq
import cadkit as ck

PLATE_LENGTH = 60
PLATE_WIDTH = 24
PLATE_THICKNESS = 6
MOUNT_EDGE_DISTANCE = 10
MOUNT_HOLE_DIAMETER = 4.3
MOUNT_X = PLATE_LENGTH / 2 - MOUNT_EDGE_DISTANCE


def plate_body():
    # Local datum: centre of the bottom face. Dimensions are millimetres.
    return cq.Workplane("XY").rect(PLATE_LENGTH, PLATE_WIDTH).extrude(PLATE_THICKNESS)


plate = ck.Part(
    "plate",
    body=plate_body,
    manufacture=ck.FDM("PETG"),
    features={
        "mounting-holes": ck.Hole(
            diameter=MOUNT_HOLE_DIAMETER, depth=PLATE_THICKNESS, through=True,
            pattern=ck.PointPattern(((-MOUNT_X, 0), (MOUNT_X, 0))),
        ),
    },
)

assembly = ck.Assembly("bracket")
installed_plate = assembly.add("plate", plate)
assembly.fix(installed_plate)
PROJECT = assembly.as_project()
```

CadKit favours explicit design intent: named inputs drive local parts, parts own
their manufacturing definitions, and assemblies own placement and relationships.
The [project-structure guide](docs/explanation/project-structure.md) shows how to
grow this into cohesive modules, with a runnable example and supported escape hatches.

## Install

**macOS and Linux** — arm64 and x86_64:

```sh
curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | sh
```

On macOS, open `~/Applications/CadKit.app`. On Linux, launch CadKit from the
application menu or run `~/.local/bin/cadkit-desktop`. Python and the CAD libraries
are included.

You can also download a DMG or Linux archive from [Releases](https://github.com/aurkakoak/cadkit/releases/latest).
Unsigned builds may show a macOS security warning.

**Python** — to run the example or use the CLI, install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv init --python 3.12 my-cad-project
cd my-cad-project
uv add "cadkit[desktop] @ git+https://github.com/aurkakoak/cadkit.git@v0.6.0"
# Save the example above as project.py.
uv run cadkit --project project:PROJECT build all
```

**Agent skill:**

```sh
npx skills add aurkakoak/cadkit --skill cadkit
```

[Documentation](https://aurkakoak.github.io/cadkit/docs/) ·
[Run from source](docs/how-to/install.md) · [Release process](docs/contributing/releases.md)
