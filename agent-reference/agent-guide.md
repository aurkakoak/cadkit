# Building with CadKit

1. Read the consumer's assembly definitions and `PROJECT` compilation and run `describe`. Inspect part names,
   units, measured dimensions, source locations, optional variants and checks.
2. Follow the [authoring principles](authoring.md). Keep machine datums and
   purchased interfaces in the consumer. Use CadKit's geometry, fits, features
   and export primitives where their semantics match; domain-specific pure
   geometry helpers belong alongside the parts that use them. Do not recreate
   part registration, placement or export machinery in a consumer wrapper.
3. Write a pure builder returning `cq.Workplane`, `cq.Shape`, or an explicitly
   mesh-backed `cadkit.geometry.Mesh`. Name independent design inputs, derive
   related fits and datums, and label profile data with fields and units. Change
   geometry at its source rather than editing generated STEP, STL, or Blender files.
   Group configurable scalar inputs in `ck.Dimensions` with `ck.input` metadata;
   use `parameters(scope=...)` to publish that same configuration. Derived
   properties are calculations, not additional editable inputs.
4. Define a `Part` with its local body, manufacturing process and print orientation.
   Add instances to an `Assembly`, then fix or connect them using local frames.
   Compile with `as_project()`. Quantities follow instances unless overridden;
   pass uninstalled optional variants and coupons through `extra_parts`.
5. Encode the physical requirement. Use intersection checks for forbidden
   collisions and required interference. Use a `contact_pair` for true surface
   contact; exact B-reps can touch with zero intersection volume.
6. Run `inspect PART`, relevant checks, and the project's regression tests.
   Inspect the preview or Blender image, especially after transforms or hulls.
   A valid B-rep alone does not prove fit, correct geometry or useful orientation.
   Review the code's edit path: the changed input should drive body, mating
   features, placement and checks where intended, without copied dimensions.
7. Export the selected print set and slice with explicit machine/process/filament
   profiles. Treat reported costs and durations as estimates. Check material
   choices against `Part.manufacture.material`; one slicer run uses one filament profile.
8. Report the artifacts, validation evidence, remaining measured interfaces and
   any mesh/STEP limitations. Do not claim a model has been physically validated
   from a successful geometry check or slicer run.

Discovery commands:

```sh
cadkit --project my_cad.project:PROJECT describe
cadkit --project my_cad.project:PROJECT list --json
cadkit --project my_cad.project:PROJECT inspect part-name
cadkit --project my_cad.project:PROJECT check specific-interface
cadkit doctor
```

The versioned JSON is for discovery and reports. It does not execute commands or
change a parameter implicitly. Edit the identified Python source, then launch a
fresh build process so derived dimensions and geometry caches are recalculated.
