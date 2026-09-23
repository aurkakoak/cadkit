# Command-line interface

The Python package installs three commands: `cadkit`, `cadkit-slice`, and
`cadkit-slice-build`. In a uv project, prefix them with `uv run`.

## Project selection

```sh
uv run cadkit --project enclosure:PROJECT list
```

`--project MODULE:ATTRIBUTE` goes **before** the subcommand. Its default is
`project:PROJECT`; omitting `:ATTRIBUTE` also selects `PROJECT`. The module
must be importable in the active Python environment. Run from the directory
containing the module or install your package into that environment.

`doctor` and `blender` do not load a project. Other commands import the selected
Project; geometry is built only where the command needs it.

## Inspection

| Command | Options | Result |
| --- | --- | --- |
| `describe` | None | JSON metadata, parameters, checks and mechanical declarations; no geometry build |
| `list` | `--json` | All manufacturing Parts, including optional Parts |
| `inspect PART` | None | Build one Part in print orientation and report geometry, volume and bounds as JSON |
| `doctor` | None | Python/CadQuery versions and discovered external executable paths |
| `mechanics` | None | Resolve installed relationships and hardware BOM as JSON |
| `bom` | None | Resolved hardware BOM as JSON |

`bom` currently reports fastening hardware. Purchased-component quantities are separately available through `assembly.purchased_bom()` and
project design metadata.

## Fabrication and validation

| Command | Options and defaults | Result |
| --- | --- | --- |
| `build [PART ...]` | No Parts means `all`; `--group GROUP`; `--output-dir build/cadquery`; `--validation-override REASON` | Validated STL/native STEP plus build manifest, quantities and groups |
| `check [NAME ...]` | No names means every registered Check; `--output-dir build/checks/clearance-failures` | Check report and failing intersection witnesses |
| `validate-assembly` | `--parts PART ...`; `--no-collision-scan`; `--output build/assembly-validation.json` | Installed mechanics report, optionally scoped to a print set |

`all` selects production Parts. An optional Part can be built by its explicit
name. Fabrication placement is applied once: the declared X/Y/Z rotations or
explicit print frame, then a Z translation to the bed. Exporting a subset replaces the manifest with exactly that subset.

A confirmed mechanical failure blocks `build`. An explicit override reason
of 3–1000 characters is retained with the artifacts. An `incomplete` report
continues to describe missing evidence; it is not a passing clearance proof.
`check` only runs explicitly registered Checks, so an empty check set gives
no collision coverage. See [mechanical validation](mechanics.md).

## Assembly and presentation

These commands accept `--view NAME`, `--exploded`, and `--printed-only`.
Named views come from the Project. `--printed-only` selects installed instances
of manufactured Parts and excludes Purchased definitions and generated fastening
hardware. It does not add uninstalled coupons or change manufacturing quantities.

| Command | Additional options and defaults | Result |
| --- | --- | --- |
| `assembly` | `--output build/assembly/full-machine.step` | Installed native STEP plus a JSON manifest listing omitted meshes |
| `preview` | `--screenshot FILE`; `--no-interact` | CQ viewer, optionally a saved image |
| `render-assets` | `--output-dir render/exports` | Component STL files and `scene.json` for Blender |
| `blender` | `--assets render/exports/scene.json`; `--output render/project.blend`; `--render IMAGE`; `--animation`; `--blender blender`; `--samples 64`; `--width 1200`; `--height 1200`; `--camera Overview` (`Front`, `Rear`) | Background Blender scene build and optional rendering |

`blender` reads an existing render manifest. It does not accept the three
assembly-view flags; generate the intended assets with `render-assets` first.

## Slicing

Prefer a build manifest so the slicer consumes the exact validated artifact set:

```sh
uv run cadkit-slice-build \
  --manifest build/cadquery/manifest.json \
  --slicer prusa-slicer --slicer-kind prusa --profile print/prusa.ini
```

`cadkit-slice-build` defaults to `build/cadquery/manifest.json`. It verifies
stored STL hashes, rejects an unreviewed failed assembly report, and supplies
that manifest's file list. Unless overridden, quantities and groups come from
`quantities.json` and `subassemblies.json` beside the manifest.

For separately managed STL files, use `cadkit-slice FILE.stl [FILE.stl ...]`.
Both commands accept these slicer options:

| Option | Default / meaning |
| --- | --- |
| `--slicer` | `prusa-slicer`; executable name or path |
| `--slicer-kind` | `prusa`; choose `prusa`, `orca`, or `bambu` |
| `--profile` | Complete PrusaSlicer INI |
| `--machine-profile` | Bambu/Orca machine JSON |
| `--process-profile` | Bambu/Orca process JSON |
| `--filament-profile` | Bambu/Orca filament JSON |
| `--filament-price-per-kg` | Optional numeric price override |
| `--currency` | `GBP`; report currency label |
| `--quantity-file` | `print/quantities.json` for direct `cadkit-slice` |
| `--group` | `all`; restrict estimates to a subassembly |
| `--group-file` | `print/subassemblies.json` for direct `cadkit-slice` |
| `--work-dir` | `build/slicer-work` |
| `--output-json` | `build/print-estimate.json` |
| `--output-markdown` | `build/print-estimate.md` |
| `--artifact-dir` | Optional directory retaining G-code/3MF outputs |
| `--extra-args` | Additional slicer arguments as one shell-style argument string |

Quantity overrides are nonnegative integers; zero omits that Part's contribution.
Estimates sum separately sliced Parts multiplied by quantities, not packed
build-plate time. These commands create files and estimates; they do not send
a job to a printer.

## Exit status

For `cadkit`:

| Code | Meaning |
| --- | --- |
| `0` | Command completed; `validate-assembly` may still report `incomplete` |
| `1` | A named Check failed, or `validate-assembly` reported `fail` |
| `2` | Argument/import/handled operational error, including a blocked `build` |

Read the report as well as the exit code. Unexpected exceptions can also make
a process fail; they must not be interpreted as an empty or passing report.

## Python entry points

::: cadkit.cli.load_project
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.cli.main
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
