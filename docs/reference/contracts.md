# Files, schemas and units

CadKit emits JSON alongside its geometry so downstream tools can use the exact
artifact set and review evidence. The contracts below describe current
`schema_version: 1` outputs. Extra fields may carry richer declarative metadata;
consumers should use named fields rather than positional ordering.

## Coordinate and unit conventions

| Value | Unit or convention |
| --- | --- |
| Model coordinates, bounds, distances | Millimetres |
| Volumes and overlap tolerances | Cubic millimetres |
| Modeling angles, print rotations, revolute coordinates | Degrees |
| Slider coordinates | Millimetres |
| Export tessellation angular tolerance | Radians |
| Rendering RGB | Three values from 0 to 1 |
| Blender scene geometry | Scaled from millimetres to metres by the Blender boundary |

Part builders require one native Workplane value, a Shape, an explicit compound,
or an explicit Mesh. Use a compound when multiple native solids are intended;
implicit multi-value Workplane stacks are rejected.

## Project description

`cadkit describe` and `Project.describe()` return:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `name`, `description` | Project identity and notes |
| `units` | `mm` |
| `views` | Named view keys |
| `parts` | Manufacturing metadata without builder callables |
| `parameters` | Name, value, unit, description, source and measured flag |
| `checks` | Names, required-contact flag, volume tolerance, gap-check flag and tolerance |
| `mechanics` | Joints, interfaces, fastenings and hardware BOM descriptions |

This description is lazy. It does not prove that builders succeed or that
registered checks pass. Compiled projects include their design graph and
manufacturing-operation metadata.

Each manufacturing record includes `print_rotation`: X/Y/Z angles in degrees.
When a definition supplies `FDM.print_frame`, those angles describe the frame's
orientation and the record also contains `print_frame` with `origin`, `x` and
`z` vectors. The frame is the design-to-fabrication transform before Z bed
normalization; it replaces the rotation transform rather than adding another
rotation. Exported geometry already includes fabrication placement.

The desktop part inspector shows the orientation and, when a frame is present,
its X/Y offset. Installed assembly placement remains independent of these fields.

## Fabrication build

`cadkit build` writes the following inside its output directory:

| File | Meaning |
| --- | --- |
| `NAME.stl` | Validated Part in print orientation |
| `NAME.step` | Native analytic Part; unavailable for explicit meshes |
| `manifest.json` | Exact selected Parts, geometry metadata, filenames and hashes |
| `quantities.json` | Part name → positive registry quantity |
| `subassemblies.json` | Group name → selected Part names |
| `assembly-validation.json` | Mechanical review when mechanics were declared or a report supplied |

The manifest contains `schema_version`, `project`, `cadquery_version`,
`units`, `tessellation`, and `parts`. Each Part entry combines its manufacturing
metadata with:

| Field | Meaning |
| --- | --- |
| `geometry` | `brep` or `mesh` |
| `valid` | Geometry validity outcome |
| `solid_count` | Native solids or connected manifold components |
| `volume_mm3` | Volume rounded to five decimal places |
| `bounds_mm` | `min`, `max`, and `size`, each an XYZ array |
| `files` | Format → relative filename, e.g. `stl` and `step` |
| `sha256` | Format → content digest for those exported files |
| `step_unavailable_reason` | Present when native STEP cannot be produced |

When present, `assembly_validation` embeds the reviewed mechanical report.
An override remains part of that evidence. A partial build replaces the
manifest with exactly its selected set; old files outside that set may remain
on disk and must not be included by globbing. `cadkit-slice-build` follows the
manifest and verifies stored STL hashes before slicing.

## Mechanical validation

Overall `status` is `pass`, `fail`, or `incomplete`. Individual findings use
`pass`, `fail`, or `unverified`. Each finding identifies:

| Field | Meaning |
| --- | --- |
| `id` | Finding identity |
| `concept`, `entity`, `code` | Mechanical category, declared object and check code |
| `status`, `severity` | Outcome and `info` / `warning` / `error` severity |
| `message` | Human-readable result |
| `component_ids` | Installed participants, when known |
| `evidence` | Measured values or missing-information details |

`summary` counts finding outcomes. A scoped print-set review adds `scope`
containing Part names, component/hardware IDs, fastening IDs and the complete
installed-assembly context. Global reference and coverage errors remain in a
scoped report. An accepted override adds:

```json
{
  "override": {
    "reason": "The explicitly recorded review decision",
    "status": "accepted_with_findings"
  }
}
```

A failed export gate persists its review and removes an old `manifest.json`
before stopping, so an old successful manifest cannot advertise the new failed
attempt. An incomplete report retains its missing evidence even when export
is allowed.

## Explicit Check reports

`cadkit check` writes `report.json` with `schema_version: 1`, a `checks` array
and aggregate `passed`. Each check contains its name and `passed`; successful
execution also records `required_contact` and `intersection_mm3`. Native
contact-pair checks add `gap_mm` and `max_gap_mm`.

Exceptions become failed entries with `error`. A failing volumetric
intersection writes `NAME.stl` and records its `witness` path. Old witnesses
for the checks being run are removed first. Touching native faces can have
zero intersection volume, which is why a `contact_pair` distance test exists.

## STEP assembly companion

`cadkit assembly --output assembly.step` also writes `assembly.json` with
`schema_version`, `units`, `mesh_components_omitted_from_step`, and `note`.
Names and colors are retained without fusing the installed instances.
Explicit meshes remain available in the app and render assets; they are not
converted into nominally editable STEP triangle faces.

## Render scene

`cadkit render-assets` writes component STLs plus `scene.json` with
`schema_version`, `units`, `exploded`, and `components`. Each component has
`name`, `file`, `group`, `part`, `color`, `material`, `explosion_mm`, and
`geometry`.

STLs contain installed coordinates. `explosion_mm` is a separate presentation
translation, applied once by the Blender runner or animated from zero.
Rendering geometry includes explicit meshes.
