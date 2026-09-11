# Provenance

CadKit was extracted while migrating the sibling Grinder project to CadQuery.
The part registry and bed-orientation approach are based on Brewer's Python
pipeline. The slicer report parser and Bambu profile resolver began with
Brewer's `scripts/slice_report.py`; subsequent changes add a reusable package
entry point, manifest-driven selection and optional retained slice artifacts.
The geometry helpers build on both projects' ring, rounded-profile, capsule,
polar-layout, export and clearance-check conventions.

Blender's runner is project independent; it consumes component metadata rather
than carrying Brewer-specific scene construction. Grinder remains a separate
consumer. Brewer was initially read as a reference; it is now a separate CadKit
consumer used to exercise mechanical contracts against a real assembly.

No third-party CAD models are distributed in this package. Consumer projects
must retain their own source-model licenses and attribution.

Catalogue fasteners build on the Apache-2.0-licensed `cq_warehouse` dependency,
pinned to commit `daa46507ecc429c0e2dce11d9d5ffd09b12a42af`. CadKit adapts placement
and validates declared stacks; a plain-washer compatibility adapter builds an
annulus from the provider dimensions. Supplier-specific reference envelopes
and their qualifications remain in consumer projects.
