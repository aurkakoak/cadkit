# Adopt an existing CadQuery project

The useful outcome is one authoritative consumer model connected to CadKit's
shared tooling. Preserve geometry and behavior while changing integration.

## Establish the baseline

Identify the existing registry, geometry builders, assembly placements, motion
states, print orientations, quantities, materials and optional variants. Inventory
all user-facing commands and downstream outputs, including specialized fabrication
and rendering. Record the starting commit, environment, test commands and outcomes.
Retain representative native geometry and rendered views before replacing exporters.

Use the consumer's existing tests first. Classify pre-existing failures separately.
Do not weaken checks just because the integration uses different abstractions.

## Define parts and their placement

Install the supplied CadKit package using [installation](install.md). Introduce
an importable `PROJECT = assembly.as_project(...)` using [the API contract](api.md).
Reuse existing local body builders and express installed placement as fixed Frames
or connections. Preserve one authoritative definition for each manufactured part.

Map manufacturing definitions to Parts and add installed instances to an Assembly.
Preserve stable names and intentional quantity differences through `quantities`.
Use `extra_parts` for uninstalled coupons and variants; carry their production flag,
notes, groups and expected solid counts. Describe exposed parameters with units
and provenance without moving their source of truth.

Switch shared export, preview, Blender and slicing commands to CadKit where
behavior matches. Retain consumer-specific commands for capabilities outside
the current API, such as 2D fabrication formats, bespoke render substitutions or
specialized motion exports. Document the boundary instead of dropping a feature.
Keep existing entry points as wrappers where that avoids breaking normal use.

## Verify equivalence

| Concern | Useful evidence |
| --- | --- |
| Geometry | Native validity, solid count, bounds, volume and symmetric-difference volume or appropriate distance checks, with stated tolerances |
| Manufacturing | Per-Part material, quantities, optional status, orientation and bed contact |
| Assemblies | Instance count, names, installed transforms, hardware, both default and named views, and existing motion/interface tests |
| Export | Native STEP round-trip checks, explicit mesh omissions, STL fidelity, complete manifest selection and specialized artifacts |
| Blender | Complete component/material coverage, units, normal and exploded placement, and inspected images |
| Slicing | Exact manifest/quantity/group selection, actual profiles, retained artifacts and estimates |
| Desktop/MCP | Load consumer through its own Python; tree/Part mapping, visibility/solo, selection, a known measurement and screenshot |

File hashes identify artifacts; they do not prove geometric equivalence because
equivalent STEP/STL serialization can differ. Bounds and volume alone also do
not prove equal shape. Keep numerical and visual evidence complementary.

Run existing tests after integration and add only tests that cover changed
boundaries or previously untested requirements. A mock slicer validates command
wiring and reporting; label it as a mock and distinguish it from a real slicer
run. Desktop mocks are likewise not evidence that the actual consumer loaded.

## Report adoption gaps

Keep an adoption report in the consumer with the release ID and manifest hash,
starting commit, environment, baseline and final commands/results, parity checks,
retained custom adapters and unresolved limitations. Record failed commands and
documentation/API gaps when they happen, including workarounds and whether they
required reading framework internals or maintainer help.

During a frozen-release evaluation, keep the supplied release unchanged. If it
blocks a requirement, finish independent work and report a minimal reproduction.
A revised release starts an explicitly recorded retry; don't silently patch an
installed package and call that a successful adoption of the original release.
