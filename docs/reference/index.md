# Reference

Use this section to look up exact names, arguments, defaults, units, and output
contracts. Python signatures and descriptions below are generated from the
library source using [mkdocstrings](https://mkdocstrings.github.io/python/).
The pages choose the public objects to show; they do not import CAD geometry
or run builders while building the documentation.

## Python API

Use `import cadkit as ck` to define parts, frames, features and assemblies.
`PROJECT = assembly.as_project()` supplies the CLI, desktop and exporters with
manufacturing inventory, installed geometry, parameters and checks.

| Topic | Objects and operations |
| --- | --- |
| [Project model](project.md) | Compiled `Project`, inventory, quantities, `Parameter` and `Check` |
| [Parts and frames](design-parts.md) | `Part`, `Feature`, `FDM`, `LaserCut`, `Purchased`, `Frame`, patterns |
| [Assemblies and motion](design-assemblies.md) | Instances, placement, connections, poses and composition |
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
