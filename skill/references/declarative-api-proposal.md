# Declarative API proposal (historical)

This page preserves the discussion draft from 12 September 2026. For the
implemented API and current usage, start with [declarative authoring](declarative.md).
Code labeled **proposed** below records the original API design; its names and
signatures are design sketches. Existing consumer builders and dimensions in
those examples are inputs, so the snippets are not drop-in migrations.

## Current implementation

The `cadkit.design` namespace implements manufacturing features, assembly
composition and motion, and generated mechanical contracts. The original rigid
retainer example has grown into the following capabilities:

| Implemented capabilities | Current guide |
| --- | --- |
| Immutable part definitions, CadQuery bodies, feature ownership, manufacturing metadata and existing Project adapters | [Declarative authoring](declarative.md) |
| Holes, counterbores, countersinks, tapped holes, bearing seats, slots, D-bores, nut pockets, seal grooves, bosses, FDM and sheet-stock metadata | [Manufacturing features](manufacturing-features.md) |
| Insert and threaded mounts, layered stacks, bounded fit contracts, captive-nut fastenings and set screws | [Manufacturing features](manufacturing-features.md#shared-connections) |
| Named ports, repeated and nested assemblies, rigid/revolute/slider placement, affine motion coupling, named poses, purchased inventory, contact regions, tool access and existing-project embedding | [Declarative assemblies](declarative-assemblies.md) |

[`examples/insert_mount.py`](examples/insert_mount.py) is a complete runnable
example using the implemented API. The namespace remains experimental; the
proposal below is broader than the current interface. Placement uses a directed
graph, and feature-specific desktop editing and a general constraint solver
remain outside the current implementation.

## Original design boundary

The intended boundary is: **CadQuery describes shape. Cadkit describes a physical
design: what each part requires to be made, and how its instances connect.** The
desktop, CLI and agent tools inspect and operate on that same design.

## Responsibility and vocabulary

| Responsibility | Owner |
| --- | --- |
| Sketches, profiles, extrusions, fillets, booleans, native solids | CadQuery |
| Manufacturing features such as clearance holes, insert pockets and bearing seats | Cadkit, implemented using CadQuery |
| Material, process, fabrication orientation and secondary operations | Cadkit |
| Local attachment frames, part instances, joints and subassembly composition | Cadkit, using CadQuery geometry and transforms |
| Catalogue hardware and its manufacturing interfaces | Cadkit with supplier/catalogue adapters |
| Machine-specific outlines, mechanisms and interface specifications | Consumer Python packages, using both libraries |
| Inspection, edits, exports, validation and presentation | Cadkit over the common design model |

There should be little reason for new code to use `ck.cylinder` or `ck.extrude`.
`ck.InsertPocket` earns its existence by knowing its manufacturing meaning,
producing the corresponding CadQuery geometry, and carrying its requirements.
Existing generic geometry helpers can remain available during migration.

Current Cadkit also supports Manifold mesh geometry. Under this boundary it needs
an explicit interoperability surface: vendor mesh references and mesh fabrication
assets retain their representation and provenance. They cannot silently acquire
the capabilities or validation status of native CadQuery parts. Existing Grinder
mesh artifacts need continued support during migration.

The core concepts should stay small:

- **Part**: an immutable manufacturing definition in local coordinates, with a
  lazy CadQuery body builder, ordered named features and a manufacturing plan.
- **Feature**: a named physical operation or interface on a part. It can generate
  geometry, expose attachment ports and declare checks and process steps.
- **Port**: a named local frame with optional interface requirements. It describes
  an attachment datum, independently of a particular assembly placement.
- **Instance**: a reference to a part or subassembly, with identity in an assembly.
- **Connection**: binds instance ports, defines relative placement or motion and
  can instantiate hardware. A named assembly contains instances and connections.

Specialized objects such as `InsertMount` are reusable recipes built from those
concepts. Applications should be able to author such recipes in ordinary Python.

## Comparison 1: Grinder's motor mounting holes

Today, `grinder/cadquery/src/grinder_cad/native/motor_mount.py:48` calculates four
hole positions, constructs bore and countersink cutters, then subtracts them:

```python
# Current, abbreviated; variables come from Grinder's configuration.
for index in inclusive_range(0, 3):
    hole_angle = motor_mount_pattern_angle + index * 90
    hole_center = vec([
        motor_mount_pcd / 2 * cos(hole_angle),
        motor_mount_pcd / 2 * sin(hole_angle),
    ])
    pieces.append(Bore(motor_mount_hole_d, 0).cutter(
        motor_carrier_h + 2 * epsilon,
        at=vec([hole_center[0], hole_center[1], -epsilon]),
    ))
    pieces.append(Countersink(
        motor_countersink_throat_d, motor_countersink_d,
    ).cutter(motor_carrier_h, at=hole_center, overlap=epsilon))
```

Proposed: retain the carrier's bespoke outline as CadQuery, and describe its
manufacturing features. This excerpt covers the four motor holes only; the pilot
bore, clamp holes and existing design requirements still need declarations.

```python
# PROPOSED API
import cadquery as cq
import cadkit as ck

motor_carrier = ck.Part(
    name="motor-carrier",
    body=carrier_blank,  # Lazy callable returning a CadQuery Workplane/Shape.
    features={
        "motor-screws": ck.HolePattern(
            pattern=ck.PolarPattern(
                radius=motor_mount_pcd / 2,
                # The downward frame reverses local Y; retain the authored XY sites.
                angles=tuple(-(motor_mount_pattern_angle + 90*i) for i in range(4)),
            ),
            at=ck.Frame(origin=(0, 0, motor_carrier_h), z=(0, 0, -1), x=(1, 0, 0)),
            hole=ck.ClearanceHole(
                diameter=motor_mount_hole_d,
                depth=motor_carrier_h,
                countersink=ck.Countersink(
                    throat_diameter=motor_countersink_throat_d,
                    head_diameter=motor_countersink_d,
                    angle=90,
                ),
            ),
        ),
    },
    manufacture=carrier_manufacturing_plan,
)
```

This first step is intentionally modest. It preserves independently authored
diameters rather than inventing a standard screw match for Grinder's reduced-head
hardware. A hole feature carries its name and purpose through geometry, inspection
and fabrication. Cutter overshoot is an implementation detail with a documented
tolerance policy; it does not change the designed hole depth.

The GUI can select `motor-carrier/features/motor-screws` and display the pattern,
diameter, seat, source parameters and resulting checks. Four anonymous cylinders
do not provide that information. Generic hole features do not invent a BOM;
hardware enters through an explicitly specified connection.

## Comparison 2: Brewer's retainer fastening

Today, Brewer has at least three related definitions:

1. Retainer clearances and recesses in `parts/brew_head.py:192`.
2. Housing insert bosses and pockets earlier in that file.
3. Hardware sites, stack offsets and engagement in `mechanics.py:116`.

For example:

```python
# Current geometry, abbreviated from parts/brew_head.py.
points = polar_points(head.bearing_retainer_fastener_radius, angles)
retainer = retainer.cut(
    cylinders_at(points, fab.m3_clearance_diameter, height + 0.2, z=-0.1)
).cut(
    cylinders_at(points, fab.m3_head_diameter, 1.4, z=height - 1.2)
)

# Current mechanical declaration, abbreviated from mechanics.py.
Fastening(
    "bearing-retainer-screws", ("bearing_retainer", "outer_housing"),
    sites=retainer_sites, kind="insert", grip_mm=1.2,
    thread_depth_mm=5.7, min_engagement_mm=3,
    hole_depth_mm=1.2 + DESIGN.manufacturing.heatset_m3_standard_depth,
    hardware=(HardwareItem("screw", _screw("M3-0.5", 6)),
              HardwareItem("insert", M3_STANDARD_INSERT, 1.2)),
)
```

Proposed: define a common mount recipe. Dimensions below reuse the current
Brewer inputs; no new hardware or manufacturing material is being recommended.

```python
# PROPOSED API
retainer_mount = ck.InsertMount(
    pattern=ck.PolarPattern(
        radius=head.bearing_retainer_fastener_radius,
        angles=(45, 135, 225, 315),
    ),
    screw=ck.SocketHeadScrew(thread="M3-0.5", length=6),
    insert=M3_STANDARD_INSERT,  # Existing supplier-specific specification.
    clearance_diameter=fab.m3_clearance_diameter,
    pocket=ck.InsertPocket(
        diameter=fab.heatset_m3_hole_diameter,
        depth=fab.heatset_m3_standard_depth,
    ),
    minimum_engagement=3,
)

retainer = ck.Part(
    name="bearing-retainer",
    body=retainer_blank,
    features={
        "housing-mount": retainer_mount.clearance_side(
            at=ck.Frame(),
            thickness=head.bearing_retainer_height,
            head_recess=ck.Counterbore(
                diameter=fab.m3_head_diameter,
                depth=head.bearing_retainer_height - 1.2,
            ),
        ),
    },
    manufacture=retainer_manufacturing_plan,
)

housing = ck.Part(
    name="outer-housing",
    body=housing_blank,
    features={
        "retainer-mount": retainer_mount.insert_side(
            at=ck.Frame(origin=(0, 0, head.bearing_z + head.bearing_width)),
        ),
    },
    manufacture=housing_manufacturing_plan,
)

brew_head = ck.Assembly("brew-head")
shell = brew_head.add("housing", housing)
ring = brew_head.add("retainer", retainer)
brew_head.fix(shell)
brew_head.connect(
    "bearing-retainer", retainer_mount,
    through=ring.feature("housing-mount"),
    into=shell.feature("retainer-mount"),
)
```

`retainer_blank` is the existing ring, tabs and motor relief before its mounting
holes. `housing_blank` retains the housing and supporting bosses, with these
insert pockets removed from its builder. Migration requires that refactor; passing
the already-drilled builder would not establish feature ownership. Other holes
and contracts remain part of their own explicit migration.

The mount convention must be documented: both role frames lie on the mating plane,
with +Z pointing from the housing into the retainer and +X establishing clocking.
The clearance side occupies positive Z; the insert pocket enters negative Z.
Connecting the roles aligns these frames. A primitive `HolePattern` instead uses
its frame's +Z as the cutting direction, as specified by that feature's API.

From this one recipe and its two role bindings Cadkit should derive:

- Clearance and recess geometry in the retainer, insert pockets in the housing.
- Attachment frames, installed retainer placement and four located hardware sets.
- Under-head seat, grip and available engagement from the bound features.
- The declared interface regions and geometric checks against the final solids.
- Insert-installation steps, plus references for user-authored assembly order.
- BOM entries and source links back to the recipe and participating features.

It cannot infer appropriate support bosses, material strength or every assembly
obstacle from this declaration. Bosses are either explicit CadQuery geometry or
an explicitly requested `InsertBoss` feature. Tool access and insertion order need
their own declared context. A common specification removes duplication; independent
measurements of the resulting geometry must still catch incorrect application.

**Ownership recommendation:** a part explicitly opts into every feature that
changes it. An assembly connects those features and instantiates hardware. Reusing
a part in another assembly therefore preserves its manufacturing definition.

An alternative is `assembly.screw(cover, housing, cut=True)`, which automatically
adds holes to whichever instances it encounters. That is attractive for short
examples but makes part identity, reuse and exports depend on assembly context.
If in-context design is added later, it should produce an explicit named part
variant. A connection should never mutate a shared part definition.

The example selects screw length explicitly. Changing thickness recomputes the
stack and can reveal an unsuitable screw. Automatic size selection, if added,
needs a declared catalogue and selection policy; there should be no invisible
change to purchased hardware.

## Comparison 3: assembly placement and motion

Brewer currently computes carriage translations and applies the head rotation to
each moving shape in `assembly.py:34`. Grinder constructs installed components
and then classifies their names into subassemblies in `assembly.py:14`.

Proposed assemblies should directly express the mechanism using local ports:

```python
# PROPOSED API; these definitions already expose the named local ports.
brew_head = ck.Assembly("brew-head")
shell = brew_head.add("housing", housing)
rotating = brew_head.add("rotating-stage", rotating_stage)
slide = brew_head.add("carriage", carriage)

brew_head.fix(shell)
azimuth = brew_head.connect(
    "azimuth", ck.Revolute(position=35),
    parent=shell.port("bearing-axis"),
    child=rotating.port("bearing-axis"),
)
radial = brew_head.connect(
    "radial", ck.Slider(limits=(head.radial_min, head.radial_max),
                        position=head.radial_default),
    parent=rotating.port("rail-axis"),
    child=slide.port("rail-axis"),
)

home = brew_head.pose({azimuth: 0, radial: head.radial_min})
extended = brew_head.pose({azimuth: 90, radial: head.radial_max})
```

Ports are explicit local coordinate frames. A port can be authored from design
datums or resolved by a CadQuery selector inside its geometry builder. Automatic
identification of the intended bearing face is not assumed. The slider moves
along its port Z axis; a radial rail port is oriented accordingly. Revolute motion
is about port Z. Both include X orientation to define the zero position.

`rotating_stage` is itself an assembly and exports its public bearing and rail
ports. Its rotor, gear and slip-ring carrier follow its pose together. Hardware
attached within it follows the same transforms. Exposed subassembly ports avoid
forcing its callers to refer to its private instance paths.

Start with directed placement: one grounded root, one placement parent per moving
instance, explicit rigid/revolute/slider connections. Given parent placement
`T_parent`, local port frames `F_parent` and `F_child`, and relative motion `M(q)`:

```text
T_child = T_parent * F_parent * M(q) * inverse(F_child)
```

Rigid connections have a fixed relative transform. Insert-mount role frames above
align with identity relative transform. Additional physical relationships may
validate an already placed pair without also controlling placement; two bolt
patterns on the same cover must not create competing placement parents.

Closed-loop mechanisms, gears and belt couplings need explicit further support.
The simple tree model must report unsupported placement cycles rather than
pretend to solve them. Joint limits constrain permitted poses; a pose is not a
sweep or proof of collision-free movement.

## Manufacturing means more than a print rotation

A part needs a process plan in addition to its intended final shape. Suggested
initial scope is FDM plus explicit secondary operations, with a protocol that
can accommodate machining, sheet processes and bought components later.

```python
# PROPOSED API: explicit project inputs, not material or machine defaults.
retainer_manufacturing_plan = ck.FDM(
    material=prototype_material,
    setup=ck.PrintSetup(
        bed=ck.Frame(),  # Part-local datum mapped to the printer's XY bed.
        profile=prototype_print_profile,
    ),
)

# An example secondary operation on another part:
tapped_hole = ck.TappedHole(
    thread="M2-0.4",
    pilot_diameter=1.6,
    depth=2.7,
    method="tap-after-printing",
)
```

These inputs express real differences:

- An insert pocket contributes an empty pocket to the printable solid and an
  install-insert step. The insert is a purchased instance in the assembly.
- A tap-after-printing hole contributes its pilot geometry to the printable
  solid, and records the tapping operation and intended finished thread. Export
  must identify which stage it represents; printed pilot geometry is not evidence
  that a thread has been made.
- Nominal size, intentional clearance/interference and process compensation are
  separate values. Increasing a pilot for printer compensation must not change
  the advertised thread identity.
- Print placement transforms the fabrication output only. Joint locations use
  the part's design frame and remain unchanged.
- A purchased part carries a specification, local ports and representation
  fidelity. It contributes to procurement, not to the print queue.

For an assembly order, default manufacturing counts should come from selected
instances of manufactured part definitions. A separate order specifies assembly
count, spares and standalone coupons. View visibility and exploded presentation
must never alter the order. Identical shape alone is insufficient to merge parts:
material, secondary operations and deliberate part identities can differ.

## Ordinary Python and extension points

Declarative authoring should mean structured Python objects with explicit
relationships. Geometry bodies stay ordinary functions. Typed configuration
dataclasses can be passed into part/assembly factory functions; the tool edits
those inputs and rebuilds. It need not symbolically interpret arbitrary Python.

Every custom feature should have the same small contract as built-in features:
accept explicit inputs, apply an ordered operation to a CadQuery body, and return
the new body plus named ports, manufacturing requirements and check definitions.
Its contribution should carry a stable authored key and its source inputs.

A custom feature must either supply those semantic outputs or identify itself as
geometry-only. A shape becoming a named feature does not establish a fit or prove
manufacturability. Dependencies between features are explicit and acyclic;
assembly placement cannot be a hidden input to a supposedly reusable part.

This permits consumer-defined constructs such as a measured motor interface or
a replaceable wet-path cartridge. Cadkit supplies the authoring protocol and
generally reusable mechanical features; the machine-specific definitions stay in
Brewer and Grinder.

## Evaluation and collaboration

The evaluation order should be observable:

1. Resolve parameters and feature recipes in part-local coordinates.
2. Build CadQuery bodies and apply their ordered features.
3. Resolve the exposed ports and evaluate assembly placement for a pose.
4. Instantiate connection hardware and manufacturing operations.
5. Validate final geometry and requirements; produce a common resolved model.
6. Derive desktop scenes, CLI reports, native exports and fabrication jobs.

All consumers use the same evaluated revision. Semantic keys such as
`brew-head/retainer/features/housing-mount` survive ordinary rebuilds; geometric
face indices are not the public identity. A resolved feature should expose its
parameters, provenance, generated surfaces/volumes and dependent connections.
Geometric references are refreshed each build rather than presumed persistent.

For humans and agents this enables selecting a recess, seeing which fastener
requires it, editing an authored dimension, and reviewing the affected geometry,
hardware and checks before applying a source change. Arbitrary Python remains
readable and editable as code; unrestricted functions do not promise visual
parameter editing. Structured source metadata can make the supported edits precise.

Validation should distinguish malformed declarations, incompatible ports,
placement failures, measured geometric failures and missing manufacturing
evidence. Native clearance/interference checks are independent of recipe inputs;
thread engagement can additionally depend on catalogue facts. A known schema
does not establish material strength, printer calibration or a feasible complete
assembly sequence.

## Original implementation plan and design decisions

The draft proposed Brewer's bearing-retainer connection as the first end-to-end
example. This list records that original implementation plan:

1. Local part definitions, named features and ports; preserve exact authored
   geometry and current manufacturing orientation.
2. One `InsertMount` recipe, explicit part roles and derived hardware/checks.
3. Rooted rigid assembly placement through the recipe's ports.
4. Adapt the resolved result to the existing desktop/export interfaces.
5. Add a revolute/slider example and prove hardware follows the changed pose.

Useful acceptance cases include changing a bolt-circle radius once and observing
both parts and hardware update; changing recess depth and observing recomputed
engagement; reusing one subassembly twice with correct independent transforms and
BOM counts; changing print setup without changing installed geometry; and
detecting a role applied to an incompatible or incorrectly oriented body. Preserve
consumer-specific fit checks and compare native volume/bounds/export geometry
against the baseline when the intended geometry is unchanged.

The first discussions should resolve these choices:

- **Recommended:** parts own geometry-changing features; connections bind them.
  An optional later in-context API must name the generated part variants.
- **Recommended:** begin with deterministic directed placement and explicit
  non-placing relationships. Add a broader constraint solver only for demonstrated
  mechanisms that require it.
- **Recommended:** features represent manufacturing intent and process steps,
  while bespoke geometry remains CadQuery code.

The examples deliberately use plain constructors and named bindings. We can
adjust naming, decorators or builder syntax after these ownership and evaluation
rules are agreed; those rules determine whether the API remains coherent as the
machines grow.
