# Render a project with Blender

You need an importable CadKit project, its Python environment and a separate
Blender installation. Run these commands from the project directory. Geometry
remains authored in Python; Blender receives a presentation scene.

## Export the scene

```sh
uv run cadkit --project project:PROJECT render-assets --output-dir render/exports
```

The output includes component meshes and `scene.json`, with installed
placement, materials and optional explosion offsets. Add `--printed-only` to
exclude hardware, or `--view service` to select a named project view.

## Make a still image

```sh
uv run cadkit blender \
  --assets render/exports/scene.json \
  --output render/model.blend \
  --render render/model.png
```

If Blender is not on `PATH`, add `--blender /absolute/path/to/blender`. Use
`--samples 8` for a quick preview before a longer render. The Blender command
does not take `--project`; it consumes the exported scene manifest.

Open the image and check that all intended components, materials and placements
are present. CadKit converts scene millimetres to Blender metres once; avoid
adding a second unit conversion in a custom Blender script.

## Make an exploded view

Give components explicit `explode` offsets in your project, then export:

```sh
uv run cadkit --project project:PROJECT render-assets \
  --exploded --output-dir render/exploded
uv run cadkit blender \
  --assets render/exploded/scene.json \
  --output render/exploded.blend \
  --render render/exploded.png
```

For an animation, add `--animation` and choose an `.mp4` render path; this also
requires FFmpeg. Exploded offsets are presentation instructions, not evidence
of a feasible assembly sequence.

See the [CLI reference](../reference/cli.md) for render options.
