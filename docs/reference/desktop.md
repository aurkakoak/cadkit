# Desktop and MCP

The installed app is available for Linux and macOS, with its own Python and CAD
runtime. Its stable input is an importable [Project](project.md). The app builds
geometry in a Python worker; the viewport and MCP tools inspect that same live
session.

## Launch arguments

```sh
cadkit-desktop --project-dir /path/to/enclosure --project enclosure:PROJECT
```

On macOS, use the executable inside the installed application, for example:

```sh
"$HOME/Applications/CadKit.app/Contents/MacOS/CadKit" \
  --project-dir /path/to/enclosure --project enclosure:PROJECT
```

| Argument | Meaning |
| --- | --- |
| `--project-dir PATH` | Project directory used for imports, watching and session identity |
| `--project MODULE:ATTRIBUTE` | Importable Project reference; default `project:PROJECT` |
| `--python PATH` | Use a custom Python containing `cadkit-py[desktop]` and project dependencies |
| `--mcp` | Run the installed executable as the stdio MCP bridge to an already open app |

Launching an installed app without an explicit project opens its editable
starter project. Installed apps otherwise use bundled Python unless overridden.
A project using additional packages or a `src/` package layout may need a custom
Python environment with the project installed.

## Object identity and rebuilds

Part names identify manufacturing definitions. Component IDs identify installed
instances; one Part can have several instances or no installed instance.
Assembly paths use URL-encoded names and must be unique among siblings.
Renaming or reparenting an object changes its identity.

Python changes trigger a fresh worker. Only a successful build replaces the
current geometry and revision. A failed build keeps the last working model,
so visible geometry does not establish that an edit succeeded. Geometry tools
require the current revision returned by `get_state`.

## MCP connection

Open the app and use its **plug icon** to copy the configuration for that exact
session. The bridge uses standard MCP over stdio and attaches to an already
open app; it does not start a second project or launch the desktop.

The MCP resource `cadkit://state` returns the same JSON state as `get_state`.
Tool responses omit triangle buffers. The installed app's `--mcp` entry needs
no separate Node installation.

The tables below summarize the public schemas. The connected server's
`tools/list` response is the machine-readable schema for your installed version.
`revision` is a nonempty build-revision string, `ids` means live component or
assembly paths, and `parts` means manufacturing Part names.

## Inspection and selection tools

| Tool | Arguments | Behavior |
| --- | --- | --- |
| `get_state` | `{}` | Project/reference, build status/revision, tree, Parts, mechanics, selection, visibility, camera, notes and current measurement |
| `inspect` | Optional `ids` (up to 100) or `part` | Inspect explicit objects/Part or the current selection |
| `select` | `revision`; either `ids` (up to 2) or `part` | Change selection; empty IDs clear it |
| `visibility` | `revision`, `action`: `show` / `hide` / `isolate`, `ids=[]` | Show/hide objects or descendants; isolate toggles the selected set |
| `highlight` | `revision`, `ids` (up to 100), `color="#f1c789"` | Replace independent colored bounds; empty IDs clear highlights |
| `measure` | `revision`, exactly two `ids`, `show=true` | Whole-object minimum clearance; optionally selects the pair and shows the dimension |

Repeating `isolate` on the same expanded set restores previous visibility.
Switching isolate targets keeps the original state to restore. `show` with no
IDs exits isolation and reveals everything. Eye/show/hide changes made during
isolation are temporary.

Native measurements include closest points. A measurement involving meshes is
labelled approximate and has no invented analytic face information. A zero gap
can mean contact **or overlap**; use validation to distinguish them.

## Camera and annotations

| Tool | Arguments | Behavior |
| --- | --- | --- |
| `camera` | Optional `preset`, `fit`, `zoom`, or `pose` | Read/change the live camera; zoom is an absolute scale |
| `annotate` | `revision`, `id`, optional `text`, `target`, `point`, `from`, `offset`, `space`, `color` | Add or replace a Markdown annotation with the given ID |
| `clear_annotations` | Optional `id` | Remove one annotation or all when omitted |
| `screenshot` | `target="viewport"` (`viewport` / `window`), `max_width=1600` (320–2400) | PNG image of the live viewport or app including notes |

Camera presets are `iso`, `front`, `rear`, `left`, `right`, `top`, and `bottom`.
A camera pose has XYZ `position`, unit `quaternion` in `[x,y,z,w]` order, XYZ
`target`, and `zoom` between 0.001 and 10000. `fit` frames visible geometry.

Annotations require a `target` or `point`. `id` is 1–80 characters and `text`
is Markdown up to 8000 characters. Colors are six-digit hex strings. World
coordinates use millimetres; screen points use `[x,y,0]` with x/y in [0,1]
and the origin at the viewport's top left. Target annotations use world space.
`offset=[dx,dy]` is a screen-pixel displacement, each value between -5000 and
5000, and overrides `from`.

Target-only notes follow stable IDs across successful rebuilds. Explicit
coordinate notes and highlights clear on rebuild. All notes are session-only;
record durable design decisions in the project's source or documentation.

## Mechanical tools

| Tool | Arguments | Behavior |
| --- | --- | --- |
| `mechanical_report` | `revision`, optional `parts` (1–100), `scan_collisions=true` | Validate the installed model, optionally scoped to a print set |
| `inspect_connection` | `revision`, `kind`, `id` | Inspect a `joint`, `interface`, or `fastening` using its mechanics ID |
| `select_connection` | `revision`, `kind`, `id`, `focus=false` | Select and highlight relationship participants |
| `set_hardware_view` | `revision`, optional `mode` and `previewProgress` | `all`, `hidden`, or `selected` hardware; preview position from 0 to 1 |

Return hardware `previewProgress` to zero for installed-geometry measurements.
The preview is presentation, not a proof of an insertion path. Report status
and its limits are defined in [mechanical validation](mechanics.md).

## Slicing tools

| Tool | Arguments | Behavior |
| --- | --- | --- |
| `slicer_settings` | `{}` | Read configured executable, profiles and readiness |
| `prepare_parts` | `revision`, `parts` (1–100), optional `validation_override` | Export print-oriented STLs and open the slicer for manual setup |
| `slice_parts` | `revision`, `parts` (1–100), optional `validation_override` | Export and start a headless job using saved profiles; returns a job ID |
| `slice_status` | Optional job `id` | Read a job, or list jobs when omitted |
| `cancel_slice` | Job `id` | Cancel the running job and slicer process |
| `open_in_slicer` | Job `id` | Open completed artifacts for review |

Configure executable/profile paths in the app's Print panel; MCP cannot change
them. An override is an explicit 3–1000 character review reason preserved with
the exported validation report. Read the mechanical findings first.

A job uses one filament profile and retains its chosen revision and settings.
Registry quantities multiply separate Part estimates, not packed-plate time.
No tool submits a print. Job files persist under
`PROJECT/build/desktop-slices/JOB_ID/`; the live job list lasts for the session.

## Protocol boundaries

The MCP bridge uses a private, authenticated local socket scoped to the current
user, project directory and Project reference. It exposes the validated tools
above, not arbitrary Python, JavaScript, or shell execution.

The app's internal `python -m cadkit.desktop --project ...` worker uses one JSON
request per line and methods `scene`, `measure`, `mechanical_report`,
`export_part`, and `export_parts`. This worker protocol carries geometry for
the desktop and is an implementation boundary, not the supported external-agent
interface. External clients should use MCP.
