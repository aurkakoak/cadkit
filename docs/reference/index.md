# Reference

Use this section to look up exact names, arguments, defaults, units, and output
contracts. Python signatures and descriptions below are generated from the
library source using [mkdocstrings](https://mkdocstrings.github.io/python/).
The pages choose the public objects to show; they do not import CAD geometry
or run builders while building the documentation.

## Choose a namespace

| Namespace | Purpose | Status |
| --- | --- | --- |
| `cadkit` / `cadkit.project` | Part registry, installed Components, project metadata and checks | Stable 0.2 contract |
| `cadkit.design` | Local parts with owned features, frames, mounts and resolved assemblies | Experimental, implemented API |
| `cadkit.fasteners` / `cadkit.mechanics` | Catalogue hardware and installed mechanical contracts | Stable 0.2 contract |
| `cadkit.geometry`, `fits`, `math` | Optional geometry and dimensional helpers | Public helpers |
| `cadkit.export`, `preflight`, `viewer`, `cache` | Validation, outputs and supporting utilities | Public helpers |

`cadkit.Part` and `cadkit.design.Part` are different classes. Likewise,
`cadkit.Assembly` groups already placed geometry, while `cadkit.design.Assembly`
resolves local definitions through connection datums. Declarative
`assembly.as_project()` produces the stable Project consumed by the CLI and app.

## Python API

| Topic | Objects and operations |
| --- | --- |
| [Project model](project.md) | `Project`, `Part`, `Component`, `Assembly`, `Parameter`, `Check` |
| [Declarative parts and frames](design-parts.md) | `Part`, `Feature`, `FDM`, `LaserCut`, `Purchased`, `Frame`, patterns |
| [Declarative assemblies and motion](design-assemblies.md) | Placement, connections, poses, composition and adapters |
| [Manufacturing features](design-features.md) | Holes, slots, pockets, seats, bosses and finishing intent |
| [Mounts and attachments](design-mounts.md) | Insert/threaded stacks, captive nuts and set screws |
| [Fasteners](fasteners.md) | Catalogue specifications, hardware items and located sites |
| [Mechanical validation](mechanics.md) | Joints, interfaces, fastenings, access and reports |
| [Geometry, fits and math](geometry.md) | Native helpers, the explicit mesh boundary and allowances |
| [Export and utilities](export.md) | Fabrication, assembly outputs, viewer, preflight and caching |

## Commands and file contracts

- [CLI](cli.md): commands, defaults, outputs and exit status.
- [Desktop and MCP](desktop.md): launch arguments, revision-scoped tools and coordinates.
- [Files and schemas](contracts.md): manifests, validation reports and units.
