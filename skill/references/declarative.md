# Parts and features

`import cadkit as ck` imports CadKit's authoring objects. CadQuery owns native
geometry. A `ck.Part` owns its lazy body builder and an ordered dictionary of
named manufacturing features. Shared `InsertMount` and `ThreadedMount` recipes
supply matched roles on participating parts. A `ck.Assembly` binds features and
local ports, owns nested composition and motion, and compiles geometry,
manufacturing inventory and mechanical evidence for the desktop and exporters.
See the complete runnable example in
[`examples/insert_mount.py`](examples/insert_mount.py).

```python
import cadkit as ck

# MOUNT is one shared InsertMount; COVER and BASE explicitly own its two roles.
assembly = ck.Assembly("fixture")
base = assembly.add("base", BASE)
cover = assembly.add("cover", COVER)
assembly.fix(base, at=ck.Frame((0, 0, 40)))
assembly.connect("mount", MOUNT,
    through=cover.feature("mount"), into=base.feature("mount"))
PROJECT = assembly.as_project()
```

Part and feature definitions are immutable. Adding a connection never edits a
part. Each moving instance gets one placement parent; disconnected or cyclic
placement fails explicitly. Both mount role frames lie on the mating plane with
+Z pointing from the receiver into the clamped part. Their X axes define the
same clocking. A rigid connection aligns those frames. A fixed assembly datum
can translate and rotate both the parts and their hardware.

`Part.build()` returns local design geometry. `Part.build_for_print()` applies
fabrication orientation and Z-only bed normalization. `FDM(material,
print_rotation)` records the process; the optional keyword `print_frame` supplies
an explicit design-to-fabrication frame instead of Euler rotations. Material can
be `"unspecified"`; no material is inferred.

`Assembly.as_project()` takes a snapshot and derives manufacturing quantities
from instances. Supply extra definitions with `extra_parts`, quantity totals with
`quantities`, and project evidence with `parameters` and `checks`. Later graph
edits cannot change a previously created Project.

Native builders return one valid CadQuery shape or an explicit compound. Feature
application verifies that every hole site intersects the body. A blind pocket's
overshoot extends through its open end only; its nominal bottom stays fixed.
Optional `Part.finalize` applies a final native geometry operation, such as an
outer-face partition for reliable STEP export. It does not alter the authored
feature metadata; final geometry still needs the project's checks.

Part descriptions contain named features, frames, manufacturing information and
secondary operations with feature provenance. Installed component metadata exposes
the same information to the desktop and agent tools. Feature-specific editing and
face selection are not currently available in the desktop UI.

`InsertMount` uses `ck.FastenerSpec` for supplier identity and catalogue geometry.
It derives grip, hardware offsets and bottom depth from the part role, then
checks engagement and other mechanical requirements. Screw lengths and pocket
dimensions stay explicit. Supplied access envelopes and bounded interfaces remain
authoritative: aligned frames alone do not establish physical contact, allowable
interference, stock thickness or load capacity.

See [Manufacturing features](manufacturing-features.md) for holes, fits, slots,
D-bores, seals, bosses, tapping, insert installation and layered mounts. See
[Assemblies](declarative-assemblies.md) for ports, nested assemblies,
revolute/slider joints, gear/rack coupling, named poses, purchased inventory,
bounded interfaces and driver access.

Placement is directed and deterministic; it is not a general constraint solver.
The framework does not infer material, select an unrequested screw length,
execute secondary operations or certify a physical fit. Purchased envelopes and
unknown thread depths stay qualified evidence. Explicit Mesh bodies can use the
same Part, Purchased and assembly graph. Native-only features and finishing
operations require a native body; meshes export STL with explicit STEP omissions.
