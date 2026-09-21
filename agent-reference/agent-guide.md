# Building with CadKit

1. Read the consumer's `Project` adapter and run `describe`. Inspect part names,
   units, measured dimensions, source locations, optional variants and checks.
2. Keep machine datums and purchased interfaces in the consumer. Keep geometric
   helpers, export machinery and tool adapters in CadKit. Do not put consumer
   assumptions into the framework.
3. Write a pure builder returning `cq.Workplane`, `cq.Shape`, or an explicitly
   mesh-backed `cadkit.geometry.Mesh`. Use named dimensions. Change geometry at
   its source rather than editing generated STEP, STL, or Blender files.
4. Register a `Part`, its intended material, quantity and print orientation.
   Add `Component` instances using the same builder in installed coordinates.
   Optional variants and calibration artifacts should be clearly labelled.
5. Encode the physical requirement. Use intersection checks for forbidden
   collisions and required interference. Use a `contact_pair` for true surface
   contact; exact B-reps can touch with zero intersection volume.
6. Run `inspect PART`, relevant checks, and the project's regression tests.
   Inspect the preview or Blender image, especially after transforms or hulls.
   A valid B-rep alone does not prove fit, correct geometry or useful orientation.
7. Export the selected print set and slice with explicit machine/process/filament
   profiles. Treat reported costs and durations as estimates. Check material
   choices against `Part.material`; one slicer run uses one filament profile.
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
