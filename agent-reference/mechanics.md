# Joints, interfaces and fastenings

CadKit 0.2 makes mechanical intent part of the Project contract. These three
collections are discoverable in Python, CLI JSON, the desktop Connections tab
and MCP. Declarations describe the consumer's geometry; they do not silently
cut or reposition printed parts.

| Concept | Responsibility |
| --- | --- |
| `Joint` | Related installed components, rigid/revolute/slider behaviour, world frame, position/limits, and links to interfaces/fastenings |
| `Interface` | A pair's required contact or clearance, or permitted overlap within a bounded region and volume limit |
| `Fastening` | Located hardware stacks through two or more components, with engagement, bottom clearance and access requirements |

Component references can be exact URL-encoded assembly paths or unique component
names. Unknown or ambiguous references fail validation; use full paths when names
repeat. Joint and fastening links use declaration names, which also serve as IDs.
A Joint is declared intent, not a constraint solver: position/limits do not move
the authored geometry. Rotation units are degrees; translation and geometry use mm.

## Catalogue hardware and placement

`FastenerSpec(kind, size, standard=..., length_mm=...)` uses pinned cq_warehouse
catalogue geometry with simplified threads. Use explicit thread pitch, e.g.
`M3-0.5`, for screws/nuts; washers use `M3`. Supported families include socket-head,
button-head and hex-head screws, hex nuts, plain washers and heat-set inserts.
Countersunk screws are rejected until their distinct length/seat convention is
supported. Material/process choices and supplier insert dimensions remain explicit.

A `Fastening` has:

- `sites`: `FastenerSite(name, origin, axis)` for every installed location.
- `hardware`: ordered `HardwareItem(name, spec, offset_mm)` entries along each site's axis.
- `components`: all clamped/connected participants; shared fasteners across three
  components are one fastening, not two overlapping pairwise sets.
- `kind`: `through`, `tapped` or `insert`; optional `joint` links the relationship.
- Declared `grip_mm`, `thread_depth_mm`, `min_engagement_mm`, `hole_depth_mm`,
  `min_tip_clearance_mm`, and tapped receiver `thread_size` for validation.
- `access`: `AccessEnvelope(name, envelope, obstacles)` for explicit world-space
  swept insertion/tool solids checked against specified installed components.

The site's +Z axis is the insertion direction. Screw origin is its under-head
seat; the shaft points +Z and head -Z. Washers and nuts start at local Z=0.
Offsets share this datum. `hole_depth_mm` is the bottom/obstruction position
from that datum, not the blind-hole depth measured from a different face.
`grip_mm` locates the start of the receiving thread; it includes intervening
washers/spacers. Nonzero screw offsets affect the actual tip and threaded span.

The independent `examples/mechanical_joint.py` shows two plates held by two M3×12
screws, four washers and two nuts. Its same sites can place explicit hole cutters:

```python
from cadkit import FastenerSpec, FastenerSite

screw = FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=12)
site = FastenerSite("left", (-8, 0, 0), (0, 0, 1))
cutter = site.place(screw.clearance_cutter(8, fit="Normal", allowance_mm=0.1))
# Explicitly cut the consumer shape when that design change is intended:
# plate = plate.cut(cutter)
```

`dimensions()`, `clearance_diameter()` and `catalogue()` expose provider data.
Allowance is a diameter adjustment separate from the nominal catalogue size.
The cq_warehouse revision is pinned in pyproject.toml. Its plain-washer geometry
is incompatible with CadQuery 2.8; a narrow adapter constructs a valid annulus
from the provider's d1/d2/h dimensions. Other families retain provider geometry.

Supplier-specific factories are supported by `FastenerSpec(factory=...)` with
manufacturer, part_number and representation. Mark a simplified supplier model
`representation="envelope"`; it is not a complete supplier CAD model. The screw
factory uses the provider convention (shaft -Z), then CadKit normalizes it.
A custom factory returns a native `cq.Shape`. Authoritative catalogue attributes
such as `thread_diameter` and `thread_pitch` allow thread-size compatibility checks;
`thread_length` describes the usable threaded span when available. Missing
attributes remain unverified rather than inferred from an approximate solid.

For non-fastener reference geometry, mark known packaging approximations with
`Component(metadata={"representation": "envelope"})`. Overlaps involving these
or fastener envelopes are possible interference, not confirmed collisions;
interface checks retain the nominal result as evidence and remain unverified.
Collision coverage is partial whenever approximate geometry participates.

The generated hierarchy is `Hardware / fastening / site / item`; every instance
has its own stable component ID and spec/fastening metadata. Hardware is excluded
from printable Parts. BOM counts come from actual sites and stack members,
not solid counts or `Part.quantity`. An unlocated fastening can declare
`quantity`, but its geometric coverage remains unverified. The BOM covers
**declared fastenings**, not unmodelled screws elsewhere in the consumer.

Hardware declarations currently target the default authored assembly pose.
The `include_hardware` option controls its visibility/export inclusion. Named
views or explicit pose options omit nominal hardware to avoid incorrect
placements. Declare pose-dependent builders before relying on hardware in
alternative configurations; joint position metadata does not perform that work.

## Interfaces and validation

`Interface` supports `contact`, `clearance`, `press_fit`, `threaded` and `mesh`
intent. `max_overlap_mm3 > 0` requires a callable `region` returning a valid
native solid; collisions outside it remain errors. `min_clearance_mm` and
`max_gap_mm` bound separation. Contact defaults to a maximum 0.001 mm gap.
Regional contact checks apply to the declared domain; do not use a broad whole
component exemption for a local thread or bearing fit.

Validation combines:

- Automatic native collision scanning, with bounds filtering and aggregate coverage.
- Declared interface contact, clearance, overlap region and volume limits.
- Joint references and stated positions against limits.
- Screw thread compatibility, usable engagement, receiver placement and tip clearance.
- Explicit access envelopes against their obstacle sets.

Mesh/native computation failures and missing motion, assembly sequence, material
or strength evidence are reported as unverified. A passing clearance check is not
proof of general assemblability. An access envelope establishes only its declared
path and obstacles. Reports distinguish `pass`, `fail` and `incomplete`, with
per-finding evidence and coverage; `incomplete` is not a green readiness result.

```sh
cadkit --project my_cad.project:PROJECT mechanics
cadkit --project my_cad.project:PROJECT bom
cadkit --project my_cad.project:PROJECT validate-assembly
cadkit --project my_cad.project:PROJECT validate-assembly --parts bracket base
cadkit --project my_cad.project:PROJECT build bracket base
```

`mechanics` resolves installed IDs; ordinary `describe` keeps declarations lazy.
`validate-assembly` writes `build/assembly-validation.json` and exits 1 on
confirmed failures (0 with explicit incomplete status when evidence is missing).
`--no-collision-scan` evaluates declarations only and records incomplete coverage.

Projects with mechanical declarations validate before CLI Part builds. Desktop
exports always review the installed assembly, even without declarations. Selected
Parts retain checks affecting their installed instances **and their fastenings'
hardware**, including hardware-to-hardware collisions, while retaining the complete
surrounding assembly as context. Uninstalled coupons have no demonstrated installed fit. A failed review
prevents export; intentional exceptions need `--validation-override "reason"`
(or the app's reason field). Reports and overrides are retained in
`assembly-validation.json` and the build manifest. Never change the expected
interface merely to suppress a failing check.

Slicer manifests retain the review. The build slicer wrapper rejects modified
STLs whose hashes no longer match their exports. Native export validity and
assembly validation answer different questions; existing consumer regression
tests and domain-specific checks remain necessary.

## Desktop and MCP

Connections exposes all three concepts, their participants and linked contracts.
Selecting a fastening shows its hardware stack and quantities. Hardware visibility
has All, Selected and Hidden modes, composed with normal eye controls and solo.
Assembly preview scrubs hardware along declared insertion offsets. It is
presentation only; reset it to the installed pose before native measurement.
Dark/light themes, annotations and screenshot capture work in this view.

Use `get_state` first. Its `mechanics` contains resolved joints/interfaces/
fastenings and `hardware_bom`; `selectedConnection`, `hardwareView`, `presentation`
and `mechanicalReport` describe the actual UI. `cadkit://mechanics` exposes that
model as an MCP resource. All geometry-dependent operations require the revision.

| MCP tool | Arguments beyond revision |
| --- | --- |
| `inspect_connection` | `kind`: joint/interface/fastening; `id` from mechanics |
| `select_connection` | Same, plus optional `focus` |
| `mechanical_report` | Optional `parts`, `scan_collisions` (default true) |
| `set_hardware_view` | Optional `mode`: all/selected/hidden; `previewProgress`: 0..1 |

`mechanical_report` updates the app's findings. Inspect responses include related
collision findings, validation scope and `not_checked` when the entity has no
relevant results. Slicing uses the same backend review; `slice_parts` and
`prepare_parts` accept an explicit `validation_override` reason when warranted.
A failed or in-progress rebuild cannot launch a new export from stale geometry.
Reports reset on a successful new build; stable connection selection can survive.
