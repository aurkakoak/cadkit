# CadKit

CadKit is a Python tooling framework for people and LLMs building real objects
with CadQuery. A small project contract connects named parts, parameters,
assembly components, joints, interfaces, fastenings and fit checks to fabrication
and presentation tools.
Geometry builders remain ordinary Python functions returning CadQuery
Workplanes or Shapes. CadKit does not replace CadQuery or interpret OpenSCAD.

For a consumer project, start with [installation](docs/install.md), then the
[migration guide](docs/migration.md), [API](docs/api.md), and
[workflow commands](docs/workflows.md). A local trial release includes the
Python wheel, desktop sources, documentation and a portable `cadkit` skill.
See [building and evaluating a trial](docs/trials.md) for the release process.
The development-checkout commands below are for working on CadKit itself.

Grinder and Brewer are separate consumer projects. Brewer also exercises the
mechanical contracts on real heat-set, tapped and through-bolted connections.

The optional [desktop application](desktop/README.md) adds an Electron/React
interface with three-cad-viewer, nested assembly visibility, Part inspection,
native distance measurements and live rebuilds. Dark mode is the default.
Its local MCP server lets external agents inspect the live selection, control
visibility and camera views, draw annotations and arrows, and capture PNGs.
The Print panel connects Part exports to Bambu Studio, OrcaSlicer or PrusaSlicer,
with profile selection, background jobs and material/time/cost reports.
The application is maintained in its own `desktop/` folder; the Python worker
is an optional framework adapter. From Grinder, run `make desktop-setup` once,
then `make desktop`.

## Start a project

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . pytest
PYTHONPATH=examples .venv/bin/cadkit --project bracket:PROJECT describe
PYTHONPATH=examples .venv/bin/cadkit --project bracket:PROJECT build all
PYTHONPATH=examples .venv/bin/cadkit --project bracket:PROJECT check
PYTHONPATH=examples .venv/bin/cadkit --project bracket:PROJECT preview
```

[`examples/bracket.py`](examples/bracket.py) is a complete independent project,
including countersunk holes, print metadata, hardware placement and a fit check.
Copy it into your own Python package, name its `Project`, and replace its builders.
Keep this repository separate from consumers and install it with `pip install -e
../cadkit`. Python 3.11 or newer is required; CadQuery is pinned to 2.8.0.

## The contract

| Type | Responsibility |
| --- | --- |
| `Project` | One discoverable registry; validates unique part and check names |
| `Part` | Pure geometry builder, group, material, quantity, print rotation, expected solid count |
| `Component` | Named installed geometry, color, material, optional part association, explosion offset |
| `Assembly` | Nested installed components and subassemblies with stable paths |
| `Joint` | Mechanical relationship, frame, motion limits and linked contracts |
| `Interface` | Bounded contact, clearance or permitted interference between components |
| `Fastening` | Located cq_warehouse hardware stacks, quantities and assembly requirements |
| `Parameter` | Value, units, description, source file and measured/assumed provenance |
| `Check` | Forbidden intersection, required overlap, or native surface contact within a stated gap |

`Part.build(for_print=False)` retains authored coordinates. The default
`Part.build()` applies its print rotation and drops its lowest point to Z=0.
Assembly placement is independent: changing print orientation cannot move the
installed assembly. Use one builder for both paths.

`cadkit describe` emits versioned JSON for agents. `list` is concise text;
`list --json` and `inspect PART` expose metadata and measured geometry.
A failed part validation or geometric check exits nonzero. Check reports record
intersection volumes or contact gaps and export collision witnesses.

See [mechanical contracts](docs/mechanics.md) and
[`examples/mechanical_joint.py`](examples/mechanical_joint.py) for catalogue
hardware, assembly validation, the Connections UI and MCP operations.

## Workflow

```sh
cadkit --project my_cad.project:PROJECT build all
cadkit --project my_cad.project:PROJECT assembly --output build/machine.step
cadkit --project my_cad.project:PROJECT render-assets
cadkit blender --output render/machine.blend --render render/output/machine.png
cadkit --project my_cad.project:PROJECT render-assets --exploded --output-dir render/exploded_exports
cadkit blender --assets render/exploded_exports/scene.json --output render/exploded.blend --animation
```

The CQ viewer uses CadQuery's bundled VTK viewer and shows native solids plus
mesh references. `cadkit preview --screenshot build/preview.png --no-interact`
provides a visual smoke check. `cadkit.viewer.show_components(...,
show_object=show_object)` also supports CQ-editor's injected callback, for
native solids; mesh components are explicitly identified as available in the
CQ viewer and Blender. CQ-editor is an optional separate installation.

Blender consumes a versioned `scene.json` plus component STLs. The reusable
runner handles mm-to-m conversion, collections, materials, studio lighting,
three cameras and an editable exploded animation. Add `--render output.mp4`
with `--animation` to render/encode the animation; FFmpeg is required for MP4.
The runner needs Blender but does not import CadQuery. Python failures produce
a nonzero Blender exit code. `doctor` reports available external tools.

## Fabrication

Every native part exports STEP and STL after solid validation. Every build
writes `manifest.json`, bounds, volume, solid count, SHA-256 file hashes,
quantities and non-overlapping groups. The manifest lists the exact output set;
stale files and calibration coupons never join a production slice by globbing.

The explicitly tagged `Mesh` type supports attributed vendor meshes and their
boolean modifications with Manifold. Meshes export STL; they are not presented
as editable STEP solids. STEP assembly export writes a companion JSON listing
omitted mesh components. The CQ viewer and Blender show the complete assembly.

`geometry` includes analytic rings, rounded plates, capsules, polar layouts,
profile booleans and normalized bed placement. `fits` provides explicit bore
allowances, angle-derived countersinks and ordered calibration coupons. Fit
allowances are inputs to measure and tune, not claims about a specific printer.
Spatial convex hulls use tessellated meshes; native circular 2D hulls keep
analytic arcs. The default mesh linear tolerance is 0.025 mm.

```sh
cadkit-slice-build --slicer prusa-slicer --slicer-kind prusa --profile my-printer.ini \
  --artifact-dir build/sliced
cadkit-slice-build --slicer BambuStudio --slicer-kind bambu \
  --machine-profile machine.json --process-profile process.json \
  --filament-profile filament.json --artifact-dir build/sliced
```

The slicer adapter supports Bambu Studio, OrcaSlicer and PrusaSlicer, flattens
Bambu profile inheritance/includes, parses G-code or G-code 3MF metadata and
reports material, time and cost in JSON and Markdown. Printer profiles are
explicit local inputs. `--group` selects a subassembly; `--quantity-file`
overrides the generated quantities. Zero quantities represent unused variants.
Use `cadkit-slice` for an explicit STL list without a build manifest. Sliced
artifacts are retained only when `--artifact-dir` is supplied. No command sends
a print job to a printer.

See [the agent guide](docs/agent-guide.md) for a repeatable modelling loop and
[the schema notes](docs/contracts.md) for interoperability details.

## Development

```sh
.venv/bin/python -m pytest tests -q
```

The framework has no Grinder or Brewer imports, paths, geometry or printer
presets. Consumer adapters own those decisions. Regression tests cover analytic
geometry, coplanar boundary cleanup, print/assembly independence, invalid solids,
contact semantics, slicer parsing and profile inheritance.
