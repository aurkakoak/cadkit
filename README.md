# CadKit

![CadKit desktop showing a CAD model](docs/assets/cadkit-desktop.png)

```python
# project.py
import cadquery as cq
from cadkit import design as d

plate = d.Part(
    "plate",
    body=lambda: cq.Workplane("XY").rect(60, 24).extrude(6),
    manufacture=d.FDM("PETG"),
    features={
        "mounting-holes": d.Hole(
            diameter=4.3, depth=6, through=True,
            pattern=d.PointPattern(((-20, 0), (20, 0))),
        ),
    },
)

assembly = d.Assembly("bracket")
assembly.fix(assembly.add("plate", plate))
PROJECT = assembly.as_project()
```

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
uv add "cadkit[desktop] @ git+https://github.com/aurkakoak/cadkit.git@v0.2.0"
# Save the example above as project.py.
uv run cadkit --project project:PROJECT build all
```

**Agent skill:**

```sh
npx skills add aurkakoak/cadkit --skill cadkit
```

[Documentation](https://aurkakoak.github.io/cadkit/docs/) ·
[Run from source](docs/how-to/install.md) · [Release process](docs/contributing/releases.md)
