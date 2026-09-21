# CadKit Desktop

A desktop workbench for inspecting real CadKit projects. Electron hosts a
TypeScript/React interface and three-cad-viewer. A local Python worker owns the
original CadQuery geometry. The application starts in dark mode; the theme
switch updates the viewport too and remembers the choice.

## Install the app

The release pipeline builds macOS Apple Silicon and Intel DMG/ZIP downloads,
and a Windows x64 installer, with Python and CAD dependencies included.
See [installation](install.md) and [release builds](releases.md).
Opening the installed app creates an editable bracket project in the app's
user-data directory. Existing edits survive later launches and upgrades.

Open your own project from the command line, for example on macOS:

```sh
/Applications/CadKit.app/Contents/MacOS/CadKit \
  --project-dir /path/to/project --project project:PROJECT
```

Use the installed `CadKit.exe` with the same arguments on Windows. Installed
apps use their bundled Python by default. `--python /path/to/python` selects
a custom environment if your project requires additional packages; install
`cadkit[desktop]` and those packages there first. A consumer with a `src/`
package layout must be installed in that custom environment or supplied
through `PYTHONPATH` with the `--python` override.

For a supplied trial source bundle, follow its `docs/install.md` to install
the Python wheel and copy a writable desktop runtime.

## Run Grinder

From the sibling Grinder checkout, after its usual `make setup`:

```sh
make desktop-setup  # once: Python extra, npm packages, Electron runtime
make desktop
```

Source checkouts require Node 22.12+ and the project's Python environment.

## Run another project

Install CadKit's desktop extra into that project's virtual environment, then:

```sh
cd /path/to/cadkit/desktop
npm ci
npm run setup
npm start -- --project-dir /path/to/project \
  --project my_package.project:PROJECT \
  --python /path/to/project/.venv/bin/python
```

`--project` is an importable `cadkit.Project` reference. The default is
`project:PROJECT`. In source checkouts, the default Python is `.venv/bin/python`
in the project folder (`.venv/Scripts/python.exe` on Windows), falling back to
`python3` on Unix or `python` on Windows.
Opening a project executes its Python builders, just like the CadKit CLI.

## Inspect

- Click an object in the viewport or tree to see its Part and installed bounds.
- Toggle an assembly, subassembly or object with its eye button. The crosshair
  beside a tree row toggles solo for that branch. Click the active crosshair
  again to restore the previous visibility; switching solo targets keeps that
  original state. Eye changes during solo are temporary. **Show all** exits
  solo and reveals everything. The inspector's isolate buttons work the same way.
- **Parts** lists manufacturing definitions, including optional parts and
  coupons that are not installed in the assembly. **Export** asks for a
  folder and exports the Part in print orientation, with STL and native STEP
  where available. Each Part has a separate subfolder and manifest.
- Shift-click two objects, or use the A/B selectors, to measure minimum distance.
  Native shapes are measured by OpenCascade in installed world coordinates.
  Closest-point markers and a dimension line appear in the viewport.
- Measurements involving a mesh use Manifold; curved native shapes are
  tessellated at this boundary. These results are labelled approximate and
  do not invent analytic faces or closest-point markers. A zero gap means
  touching or overlapping, not a validated clearance check.
- Bounding-box centre distance and signed centre deltas are separately labelled.
- Python edits trigger background rebuilds. Stable object paths preserve
  visibility and selection, and the camera remains in place. A failed build
  retains the previous geometry and measurement worker. Measurements are
  revision-scoped and recalculated after a successful rebuild.

This version measures whole objects. Face/edge/axis selection, persistent
annotations and a project picker remain future work.
Blender continues through the CadKit CLI.

## Mechanical connections

The Connections tab exposes first-class Joints, Interfaces and Fastenings.
Inspect participants, catalogue hardware, BOM quantities and validation findings.
Hardware has All/Selected/Hidden visibility and a reversible assembly preview.
Measurements use installed geometry; return the preview to zero before measuring.
Run assembly checks here or review the selected Part set before printing.
Known failures require an explicit override reason, stored with exported artifacts.
Unverified coverage remains visible. See [mechanical contracts](mechanics.md)
for modelling, validation limits, and the four dedicated MCP tools.

## MCP: connect an external agent

Open the app, then click the **plug icon** to copy its MCP client configuration.
It contains the paths and project reference of this running session. Paste it
into your MCP client's server settings. The installed app uses its own executable
with `--mcp`; no separate Node installation is needed. A source-checkout
configuration looks like:

```json
{
  "mcpServers": {
    "cadkit": {
      "command": "node",
      "args": [
        "/path/to/cadkit/desktop/electron/mcp.mjs",
        "--project-dir", "/path/to/project",
        "--project", "my_package.project:PROJECT"
      ]
    }
  }
}
```

Use Node 22.12+. The process speaks standard MCP over stdio through the
[official TypeScript SDK](https://ts.sdk.modelcontextprotocol.io/server).
It attaches to the **open app**, so it sees the user's actual selection, camera
and build. It does not launch another model or embed an agent. The connection
survives app restarts; calls made while the app is closed return a useful error.
One app owns each project-directory/project-reference pair.

| Tool | Purpose |
| --- | --- |
| `get_state` | Project, Parts, assembly tree, component IDs, selection, visibility, camera, annotations and current measurement |
| `inspect` | Selected objects or explicit component/assembly IDs or a Part name; bounds, volume and manufacturing metadata |
| `select` | Set up to two selected components, select a Part, or clear selection |
| `visibility` | Show, hide or isolate objects and entire assembly branches |
| `highlight` | Coloured bounds independent of the user's selection |
| `camera` | Preset orientation, fit visible objects, zoom, or restore an exact camera pose |
| `measure` | Native solid clearance or labelled mesh approximation; optionally display it in the UI |
| `annotate`, `clear_annotations` | Markdown cards, markers and arrows attached to assembly items or placed in world/screen coordinates |
| `screenshot` | PNG image content of the viewport or app window, including annotations |
| `slicer_settings` | Current locally configured executable and profiles |
| `prepare_parts` | Export print-oriented STLs and open them in the slicer |
| `slice_parts`, `slice_status`, `cancel_slice` | Start and monitor headless jobs, inspect estimates/artifacts, or cancel |
| `open_in_slicer` | Open a completed job for review |

`cadkit://state` exposes the same state as an MCP JSON resource. Responses omit
triangle buffers. Read `get_state` first and use its stable IDs and `revision`
for geometry-dependent commands. Stale revisions and unknown IDs are rejected
before changing the view. Camera poses use world coordinates and a unit
quaternion. `fit` frames currently visible objects; isolate a branch first to
focus on it. `zoom` is absolute, not a multiplier.

Example tool arguments, substituting the live revision and component IDs:

```json
{"revision":"…", "ids":["/machine/frame/left", "/machine/frame/right"], "show":true}
```

The measurement returns the minimum distance, method, world closest points
(native shapes), and bounding-box centre deltas. A `show:false` call leaves the
UI selection alone. To draw a labelled arrow toward a model feature:

```json
{"revision":"…", "id":"fit-check", "text":"Check this fit", "space":"world", "from":[40,0,80], "point":[20,0,50], "color":"#f1c789"}
```

Screen annotations use `[x,y,0]`, with x/y from 0 to 1 and the origin at the
viewport's top left. World annotations track camera motion. IDs replace
existing annotations; the eraser icon clears them. Use `target` instead of
`point` to attach a note to a component or assembly's bounds:

```json
{"revision":"…", "id":"bore-note", "target":"/machine/clamp/gate", "text":"**Fit check**\n\n- Verify the bore\n- Allow `0.2 mm` clearance", "offset":[48,-96]}
```

The note is shared with that item's assembly-tree row. Its note icon opens
the same Markdown card inline. Empty rows reveal an add-note icon on hover or
keyboard focus; the inspector also has an add-note action. Cards support
editing, colour selection and deletion. Drag their grip to reposition them,
or focus the grip and use arrow keys (Shift for larger steps).

Cards show a four-line preview and an ellipsis to expand longer notes.
Markdown supports headings, emphasis, lists, task lists, tables, code and web
links, up to 8,000 characters. Raw HTML is omitted and images are represented
by their alt text; notes do not fetch remote images. Web links open externally
only on user click. The editor has a Markdown preview and Ctrl/Cmd+Enter saves.

`offset` is a pixel displacement of the card from the anchor and overrides
`from`. Without either, the app places the card near its anchor. Attached
notes with no explicit `point` or `from` follow their stable target IDs across
rebuilds and disappear if the target is removed. Explicit coordinate notes and
extra highlights clear after a successful rebuild. Notes are session-only;
they do not modify Python Part definitions or survive closing the app.
Selection, visibility and camera remain stable.

The app bridge uses a private local socket (a named pipe on Windows) with a
random authentication token. Discovery is scoped to the current user and
project; on Unix its directory is 0700 and discovery/socket files are 0600.
No HTTP listener is opened. MCP exposes validated operations, not arbitrary
JavaScript, shell commands or filesystem access. Slicer paths are selected in
native app dialogs and cannot be changed through MCP. Release CI tests the
packaged worker, renderer and MCP entry on each target platform. Slicer
integrations still require testing with the user's installed slicer and profiles.

## Print

Use **Print…** in a Part inspector, or the printer icon for a production set.
Select Parts individually or by group. Choose Bambu Studio, OrcaSlicer or
PrusaSlicer, its executable, profiles and build plate. Bambu/Orca use machine, process and
filament JSON files; Prusa uses a complete INI. Profiles and optional price/kg
and currency persist in the app's local settings. Bambu profile inheritance
and includes are resolved by the existing CadKit adapter.

**Open in slicer** exports the selected Parts in their print poses and opens
the STLs for manual setup. **Slice** exports a fresh manifest and runs the
configured CLI in the background. The view remains interactive. The Jobs
section shows progress, filament mass, time, cost and per-Part totals, with
actions to cancel, show files or open the resulting G-code/3MF.

Each job uses a single filament profile for all selected Parts; choose a
matching material set (for example, slice a TPU liner separately from PETG).
Registry quantities multiply separate Part estimates, not packed-plate time.
Missing estimates display as unavailable. No action submits to a printer.
An active job retains its chosen profiles and revision if settings or geometry
change. A rebuild during the initial export can fail that job; retry it with
the new revision. Cancellation stops slicing; an export already underway may
finish writing its files before cancellation takes effect.

Artifacts, reports, the original job request, flattened profiles and failure logs stay under
`PROJECT/build/desktop-slices/JOB_ID/`. The live job list lasts for the app
session; files remain after exit. Jobs from an earlier build are labelled.

## Model contract

`Part` describes a manufacturing definition. `Component` is an installed
instance with an optional `part` reference. `Assembly` contains components and
other assemblies:

```python
from cadkit import Assembly

def assembly_tree(**options):
    return Assembly("machine", (
        Assembly("drive", (motor_component, carrier_component)),
        Assembly("frame", (left_tube, right_tube)),
    ))

# Supply assembly=assembly_tree alongside the existing components builder.
```

All current component geometry already uses world coordinates. Assembly nodes
organize that geometry; they do not apply a second placement transform. Sibling
names must be unique. Paths are escaped names scoped by parent assembly; rename
or reparent an object and it receives a new identity. Projects without an
assembly builder get a tree from their existing component groups.

The React interface is independent of Python model classes. `cadkit.desktop`
exposes JSON-line requests: `scene`, `measure`, `export_part`, and `export_parts`.
Electron owns the processes, file watching, local MCP bridge, slicer jobs and
native dialogs. The renderer receives
only a narrow preload API. Rebuilds start a new worker so changed Python modules
cannot survive in an import cache; the old worker is replaced only on success.

## Development and checks

```sh
npm run build  # TypeScript checking + Vite bundle
npm run test:runtime  # Bundled Python selection and first-launch project checks
CADKIT_TEST_PYTHON=/path/to/project/.venv/bin/python npm test
PYTHONPATH=../src /path/to/project/.venv/bin/python -m pytest ../tests -q
```

Build on the target OS and architecture with `npm run bundle:python`, then
`npm run package -- --mac --arm64`, `--mac --x64`, or `--win --x64`.
Run `npm run smoke:package -- /path/to/packaged/executable` to verify the actual
app archive, default project, bundled CAD worker, renderer and MCP startup.
The Python bundle is a complete standalone installation; the build moves it
before testing to catch dependencies on its original location.

The desktop tests launch Electron against independent two-block fixtures. They
checks nested visibility, Part selection, native measurement, dark/light mode,
theme persistence, failed-build recovery and visibility after a live rebuild.
An actual MCP SDK client also tests UI/agent selection synchronization,
visibility, camera restoration, native clearance, annotations, PNG capture,
resources, stale requests, authentication, and slicing through a mock CLI.
Slicer checks cover print-pose export, quantities/cost, artifact opening,
failure reporting and process-tree cancellation. Mock figures are fixtures,
not estimates of real printing.
Linux tests need a graphical session (or an Xvfb display). The optional
`CADKIT_TEST_NO_SANDBOX=1` is only for isolated test environments that cannot
run Chromium's sandbox; the application itself does not disable the sandbox.

The 3D engine accounts for most of the frontend bundle. No remote services,
fonts or rendering servers are required at runtime.
