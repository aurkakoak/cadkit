# Geometry, fits and math

These helpers are optional. Existing CadQuery builders can continue using
CadQuery directly. Lengths are millimetres, angles are degrees unless an
external API explicitly says otherwise.

## Reusable native shapes

```python
from cadkit.geometry import annulus, rounded_rect_prism, capsule, polar_points
```

::: cadkit.geometry.annulus
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.rounded_rect_prism
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.capsule
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.polar_points
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.normalized_to_bed
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Explicit fit allowances

```python
from cadkit.fits import Bore, Countersink, fit_coupon
```

Allowance changes a diameter, not a radius. A nominal fit in the model is not
calibration of a printer, material or machining process.

::: cadkit.fits.Bore
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - diameter
        - cutter

::: cadkit.fits.Countersink
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - depth
        - cutter

::: cadkit.fits.fit_coupon
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Native and mesh boundaries

::: cadkit.geometry.shape
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.Mesh
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members:
        - triangles
        - translate
        - rotate

::: cadkit.geometry.mesh
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.import_mesh
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Booleans and transforms

These functional helpers accept lists of geometry and combine them before
transforming. Booleans involving a Mesh become meshes. Native solids remain
native otherwise; a spatial convex hull is another explicit mesh boundary.

::: cadkit.geometry.union
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.difference
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.intersection
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.translate
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.rotate
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.mirror
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.scale
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Lower-level primitives

The functional primitives return native faces or shapes, except where their
description states a mesh boundary. `facets` is not a general tessellation
control: circles and spheres ignore it; cylinders use it only for polygonal
prisms with at most twelve sides.

::: cadkit.geometry.circle
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.polygon
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.square
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.cube
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.cylinder
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.sphere
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.linear_extrude
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.rotate_extrude
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.offset
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.hull
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.geometry.projection
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Degree-based arithmetic

`cadkit.math` also re-exports Python's `pi`, `sqrt`, `floor`, and `ceil`.
`vec` arithmetic is elementwise; multiplication is not a dot or cross product.

::: cadkit.math.vec
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
      members: false

::: cadkit.math.sin
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.cos
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.tan
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.asin
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.acos
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.atan
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.atan2
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.norm
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.concat
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.sign
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.require
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.inclusive_range
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.math.concat_text
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
