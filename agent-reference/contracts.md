# Contracts, units and failure behavior

All geometry and placement coordinates use millimetres. Angles in modelling
helpers and explosion rotations use degrees. CadQuery's tessellation angular
tolerance is in radians. Blender is the only boundary that scales to metres.

`Project.describe()` returns schema version 1, the project name, description,
units, part metadata, discoverable parameters and named checks. Part names must
be safe filename stems. Manufacturing quantities are positive integers in the
compiled inventory; slicer overrides also accept zero for unselected alternatives.

Manufacturing metadata includes X/Y/Z `print_rotation` angles in degrees. A
supplied fabrication frame also appears as `print_frame` (`origin`, `x`, `z`);
the angles describe that frame's orientation. Apply the frame or the rotations,
then Z bed normalization, once. Exported part files already include that
fabrication placement. Installed assembly frames are independent.

A build manifest has schema version 1, project name, CadQuery version,
tessellation settings and a `parts` array. Each entry has the Part metadata,
`geometry` (`brep` or `mesh`), `valid`, `solid_count`, `volume_mm3`, `bounds_mm`,
relative output filenames and SHA-256 hashes. Bounds include min, max and size.
A partial build replaces the manifest with exactly the requested set. Existing
files outside that set are not silently added to subsequent slicing.

Render `scene.json` has schema version 1, units, an `exploded` flag and a
`components` array. Component STLs always contain installed coordinates;
`explosion_mm` is a separate presentation translation. The Blender runner
applies it once, or animates between zero and the supplied offset. The manifest
also supplies the name, group, color, material, geometry kind and part link.

Check reports contain the named outcomes, intersection volume, required-contact
flag, optional gap and maximum-gap tolerance, error details and collision
witness paths. Exceptions are failures, never interpreted as empty clearance.
Geometry with no volumetric intersection can still have exact surface contact.

Native STEP assembly export preserves names and colors without fusing all
components. Vendor mesh components are listed in a companion omission manifest;
their complete installed geometry remains available in the viewer and render
assets. CadKit deliberately does not turn STL triangles into nominally editable
STEP faces.
