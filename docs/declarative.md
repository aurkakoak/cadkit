# Experimental declarative authoring

`from cadkit import design as d` opts into the first implementation of the
[design proposal](declarative-api-proposal.md). Existing `cadkit.Part`,
`cadkit.Assembly`, Project loaders, viewers and exporters keep their existing API.
This namespace is experimental; it is not yet the whole proposed interface.

CadQuery owns native geometry. A `d.Part` owns its lazy CadQuery body builder and
an ordered dictionary of named features. An `InsertMount` recipe supplies the
clearance-side and insert-side features. A `d.Assembly` binds those features,
deriving rigid placement and the existing Fastening/Joint contracts. See the
complete runnable example in [`examples/insert_mount.py`](../examples/insert_mount.py).

```python
from cadkit import design as d

# MOUNT is one shared InsertMount; COVER and BASE explicitly own its two roles.
assembly = d.Assembly("fixture")
base = assembly.add("base", BASE)
cover = assembly.add("cover", COVER)
assembly.fix(base, at=d.Frame((0, 0, 40)))
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

`Part.build()` returns a native shape in design coordinates. `Part.as_part(group)`
adapts it to the existing manufacturing registry. `FDM(material, print_rotation)`
sets explicit manufacturing metadata and export orientation, with the existing
Z-only bed normalization. Material can be `"unspecified"`; no material is inferred.
`Assembly.as_project()` takes a snapshot and derives manufacturing quantities from
instances. Separate graph edits cannot stale a previously created Project.

Builders return one valid CadQuery shape or an explicit compound. Feature
application verifies that every hole site intersects the body. A blind pocket's
overshoot extends through its open end only; its nominal bottom stays fixed.
Optional `Part.finalize` applies a final native geometry operation, such as
Brewer's existing outer-face partition for reliable STEP export. It does not alter
the authored feature metadata; final geometry still needs the project's checks.

The resulting legacy Part's `describe()` includes a `design` object containing
named features, frames, manufacturing information and required insert-installation
operations. Design assembly components expose the same object as metadata to the
existing desktop worker and agent tools. There is no new feature-specific editor
or face-selection UI in this slice.

`InsertMount` reuses `cadkit.FastenerSpec` for supplier identity and catalogue
geometry. It derives grip, hardware offsets and bottom depth from the part role,
then delegates engagement and other mechanical checks to the existing engine.
Screw lengths and pocket dimensions stay explicit. Supplied access envelopes and
bounded interfaces remain authoritative: aligned frames alone do not establish
physical contact, allowable interference, stock thickness or load capacity.

Current limits: socket-head screws with heat-set inserts, polar patterns, rigid
placement of part instances, and FDM orientation metadata. Motion joints, nested
design assemblies, generalized port connections, profile selection and execution
of secondary manufacturing operations remain future work. Vendor meshes continue
through the existing API; this authoring namespace accepts native CadQuery solids.

```sh
PYTHONPATH=src:examples python -m cadkit.cli --project insert_mount:PROJECT describe
PYTHONPATH=src:examples python -m cadkit.cli --project insert_mount:PROJECT preview
PYTHONPATH=src python -m pytest tests -q
```

The example deliberately leaves supplier/process evidence incomplete. In Brewer,
the migrated connection retains the machine's existing bounded interfaces and
tool-access checks. A successful geometry build is not a completed manufacturing
review.
