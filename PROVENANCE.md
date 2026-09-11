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
consumer. Brewer was read as a reference and was not changed.

No third-party CAD models are distributed in this package. Consumer projects
must retain their own source-model licenses and attribution.
