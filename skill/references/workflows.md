# Build, view, render and slice

Run these from the consumer root after installing the consumer package and
CadKit. Substitute the consumer's import reference and use the same Python
environment throughout. `--project` is a global option before the subcommand.

```sh
.venv/bin/cadkit --project my_cad.project:PROJECT describe
.venv/bin/cadkit --project my_cad.project:PROJECT list --json
.venv/bin/cadkit --project my_cad.project:PROJECT inspect plate
.venv/bin/cadkit --project my_cad.project:PROJECT build all
.venv/bin/cadkit --project my_cad.project:PROJECT check
.venv/bin/cadkit --project my_cad.project:PROJECT assembly --output build/machine.step
.venv/bin/cadkit --project my_cad.project:PROJECT assembly --view service --output build/service.step
```

Builds default to `build/cadquery`. `build plate coupon --output-dir build/sample`
selects explicit Parts; `build all --group frame` filters production Parts.
Every completed build writes a manifest, quantities and non-overlapping groups.
A partial build replaces that directory's manifest with exactly the selected
set, even if older artifacts remain. Use separate output directories for sets
you need to retain. There is no successful new manifest for a failed build.

## Preview and desktop

```sh
.venv/bin/cadkit --project my_cad.project:PROJECT preview
.venv/bin/cadkit --project my_cad.project:PROJECT preview --screenshot build/preview.png --no-interact
```

This preview is the CadQuery/VTK viewer. `--no-interact` avoids the interactive
loop, but may still require a display/OpenGL environment. The Electron desktop
is launched separately as described in [installation](install.md); it uses
three-cad-viewer, with native geometry retained in its Python worker.

For MCP, launch the desktop then use its plug button's connection configuration.
The supplied `desktop/electron/mcp.mjs` is a standard stdio server requiring
Node and installed desktop npm dependencies. Read `get_state` for IDs and the
current revision before changing geometry-dependent view state. MCP sees the
actual open window; it does not create an independent CAD session. Measurement
is between whole components, with native distance or a labelled mesh
approximation. Parameters are descriptive today; edits still happen in Python.

The release's desktop reference documents all tools, Markdown annotations,
camera control, screenshots, solo visibility and slicing. The same document is
included as `references/desktop.md` in the packaged skill.

## Blender

```sh
.venv/bin/cadkit --project my_cad.project:PROJECT render-assets --output-dir render/exports
.venv/bin/cadkit blender --assets render/exports/scene.json --output render/model.blend --render render/output/model.png
.venv/bin/cadkit --project my_cad.project:PROJECT render-assets --exploded --output-dir render/exploded_exports
.venv/bin/cadkit blender --assets render/exploded_exports/scene.json --output render/exploded.blend --animation
```

`render-assets` supports `--view` and `--printed-only`. The latter selects only
installed manufactured parts, excluding purchased components and fastening
hardware. The scene manifest owns
installed component geometry and optional explosion offsets. Blender converts
mm to metres exactly once. `blender` does not require `--project`; it consumes
that manifest. Use `--blender /path/to/blender` when it is not on PATH.
`--samples 8` is useful for a smoke image. `--render output.mp4 --animation`
also requires FFmpeg. Native models should remain authored in Python; Blender
is presentation output. Consumer-specific render postprocessing can remain
as a documented adapter when the standard scene is insufficient.

## Slicing

Build the intended set first, then slice its explicit manifest:

```sh
.venv/bin/cadkit-slice-build --manifest build/cadquery/manifest.json \
  --slicer /path/to/prusa-slicer --slicer-kind prusa --profile /path/to/printer.ini \
  --artifact-dir build/sliced --output-json build/estimate.json --output-markdown build/estimate.md

.venv/bin/cadkit-slice-build --manifest build/cadquery/manifest.json \
  --slicer /path/to/BambuStudio --slicer-kind bambu \
  --machine-profile /path/to/machine.json --process-profile /path/to/process.json \
  --filament-profile /path/to/filament.json --artifact-dir build/sliced
```

For Orca use `--slicer-kind orca`. Bambu/Orca settings may inherit other profiles;
keep those files available so the adapter can flatten them. Extra slicer options
can be passed as `--extra-args='--curr-bed-type Textured PEI Plate'` when supported
by the installed slicer. The tool does not invent a printer or material profile.

The build's generated quantities/groups are defaults; `--quantity-file` and
`--group-file` override them, and `--group NAME` selects a group. A zero quantity
omits an alternative. Production Parts themselves have positive quantities.
`cadkit-slice` accepts explicit STL paths when there is no build manifest.
Use `cadkit-slice --help` for shared options; the build wrapper reads its
manifest before forwarding slicer arguments, including `--help`.

Each run uses one filament profile. Slice different materials separately.
Quantities multiply per-Part estimates; they do not simulate packed plates.
Retain outputs with `--artifact-dir`. CLI and desktop slicing never submit a
print job. The desktop Print panel saves its executable/profile choices locally
and provides background jobs, cancellation and artifact opening.

## Assembly review

Use [mechanical contracts](mechanics.md) for `mechanics`, `bom` and
`validate-assembly`, pre-export findings and review overrides. Hardware counts
are independent of the printable Part quantities and cover declared fastenings.
