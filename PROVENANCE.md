# Provenance

CadKit is an independent framework for inspectable CadQuery projects. It provides
part registries, bed orientation, geometry helpers, validation, exports, rendering
and slicer integration. Its reusable primitives include rings, rounded profiles,
capsules, polar layouts and clearance checks.

The Blender runner consumes component metadata. Slicing uses manifest-driven
selection, profile resolution and optional retained artifacts. Project-specific
models, scene construction, printer profiles and supplier qualifications belong
to the projects using the framework.

No third-party CAD models are distributed in this package. Consumer projects
must retain their own source-model licenses and attribution.

Catalogue fasteners build on the Apache-2.0-licensed `cq_warehouse` dependency,
pinned to commit `daa46507ecc429c0e2dce11d9d5ffd09b12a42af`. CadKit adapts placement
and validates declared stacks; a plain-washer compatibility adapter builds an
annulus from the provider dimensions. Supplier-specific reference envelopes
and their qualifications remain in consumer projects.
