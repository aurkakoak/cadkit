# Validation and evidence

A solid can be valid CAD geometry and still be a poor fit, impossible to
assemble or too weak to use. CadKit keeps these questions separate so that a
successful export does not imply more than the checks actually established.

## Geometry, intent and physical behavior

Geometry checks can establish facts such as a native shape being valid, two
solids intersecting, or a measured gap being below a threshold. Mechanical
declarations add intent: a particular contact is required, a local overlap is
expected around an insert, or a screw needs a specified engagement length.

Without that intent, the validator cannot distinguish a desired press fit
from an accidental collision. Without geometry or authoritative dimensions,
intent alone cannot establish that the connection works.

For example, an `Interface` can permit overlap in a bounded insert region.
That permission applies to the stated region and overlap limit. It does not
excuse a screw intersecting a wall elsewhere. Keeping exceptions local makes
the remaining collision findings useful.

## What the different checks answer

| Evidence | Useful conclusion | Still outside that conclusion |
| --- | --- | --- |
| Native validity and solid count | The exported shape satisfies those geometry checks | Functional correctness or manufacturability |
| Whole-object minimum distance | The closest separation in the current pose | Which selected face fits; a zero gap can include overlap |
| A declared overlap or contact check | The tested relation meets its geometric criterion | Undeclared interfaces and other poses |
| Assembly validation | Covered collisions and declared mechanical requirements were evaluated | General strength, preload, material behavior or all assembly sequences |
| Tool access envelope | The declared swept shape clears the listed obstacles | Every possible tool or insertion path |
| Slicer result | That slicer and those profiles produced artifacts and available estimates | A successful physical print or packed-plate timing |

`cadkit check` runs only the registered checks. An empty check list passes
without supplying collision evidence. Assembly validation adds a native
collision scan and evaluates declared joints, interfaces, fastenings and
access. Its report also identifies missing coverage.

## Why incomplete is a separate result

Reports distinguish `pass`, `fail` and `incomplete`. An unknown supplier thread
depth, an approximate envelope or unsupported geometry should not become a
fabricated measurement just to produce a green result. A collision involving
an approximate envelope is possible interference rather than confirmed detail
geometry; missing evidence stays visible.

The CLI exits with a failure for confirmed assembly failures. It currently
returns zero for an incomplete report, so an automated manufacturing gate must
read the report status and coverage. A shell exit code alone is insufficient.

Current-pose validation also differs from motion validation. A revolute joint
within its stated limits is not proof that it can travel between those limits
without collision. A hardware insertion preview is presentation, not an
assembly-sequence test. Keep domain-specific motion and physical tests in the
project alongside CadKit checks.

## Evidence follows the artifact

Build manifests record the selected part set, quantities, hashes and available
assembly review. Selected-part reviews retain the surrounding assembly as
context and include the selected parts' fastening hardware. An uninstalled
coupon has no demonstrated installed fit merely because it can be exported.

A confirmed failure blocks reviewed exports unless a specific override reason
is supplied. The override is retained with the report; it is a recorded
decision, not changed evidence. The slicer wrapper checks that STL hashes still
match their manifest so its estimates refer to the reviewed artifacts.

Physical fit still needs physical evidence. A coupon printed with the intended
material, orientation and settings can justify a process allowance. Record
those conditions with the measurement so that a later printer or material
change does not silently inherit an unsupported assumption.

See [Export parts and run checks](../how-to/export-and-check.md) to obtain the
reports and [Use catalogue fasteners and fit coupons](../how-to/fasteners-and-fit.md)
to collect a simple physical fit measurement.
