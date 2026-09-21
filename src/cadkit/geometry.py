"""Functional CadQuery geometry, including reusable fit and layout primitives.

Analytic B-reps stay analytic. Only explicitly imported meshes and spatial
convex hulls use Manifold; that boundary is retained in export metadata.
"""

from __future__ import annotations
import math
from itertools import combinations
from pathlib import Path
import cadquery as cq
import numpy as np
import manifold3d as m3d
import trimesh
from scipy.spatial import ConvexHull

TOLERANCE = 0.025
EMPTY = None


class Mesh:
    """An explicit Manifold triangle-mesh boundary in an otherwise native CAD model.

    Args:
        manifold (manifold3d.Manifold): Valid Manifold solid.

    Obtain one using `import_mesh` or `mesh`. Meshes can be shown, measured
    approximately, transformed, and exported as STL. They do not become analytic
    STEP solids. Translation and rotation return new Mesh wrappers.
    """
    def __init__(self, manifold):
        if manifold.status() != m3d.Error.NoError:
            raise ValueError(f"Invalid manifold mesh: {manifold.status()}")
        self.manifold = manifold

    def triangles(self):
        """Return a trimesh.Trimesh using the manifold vertices and triangles without reprocessing."""
        mesh = self.manifold.to_mesh()
        return trimesh.Trimesh(
            mesh.vert_properties[:, :3], mesh.tri_verts, process=False
        )

    def translate(self, vector):
        return Mesh(self.manifold.translate(tuple(vector)))

    def rotate(self, origin, end, degrees):
        matrix = trimesh.transformations.rotation_matrix(
            math.radians(degrees), np.subtract(end, origin), origin
        )
        return Mesh(self.manifold.transform(matrix[:3]))


def shape(value):
    """Unwrap a Workplane's first value; preserve Shapes, Meshes, and `None`.

    Args:
        value (object): CadQuery Workplane, native Shape, Mesh, or empty sentinel.

    Returns:
        (object): `.val()` for a Workplane, otherwise the original object.

    This does not combine a Workplane stack. Return an explicit compound from
    builders that intentionally contain multiple solids.
    """
    if isinstance(value, cq.Workplane):
        return value.val()
    return value


def _items(values):
    return [shape(v) for v in values if v is not None]


def mesh(value):
    """Convert native geometry to the explicit Manifold mesh representation.

    Args:
        value (object): Native Shape, Workplane, Mesh, or `None` for an empty mesh.

    Returns:
        (Mesh): Existing Mesh unchanged or newly tessellated geometry. Native
            tessellation uses 0.025 mm linear and 0.08 rad angular tolerance.
    """
    value = shape(value)
    if isinstance(value, Mesh):
        return value
    if value is None:
        return Mesh(m3d.Manifold())
    vertices, triangles = value.tessellate(TOLERANCE, 0.08)
    tm = trimesh.Trimesh([v.toTuple() for v in vertices], triangles, process=True)
    return Mesh(
        m3d.Manifold(
            m3d.Mesh(
                np.asarray(tm.vertices, dtype=np.float32),
                np.asarray(tm.faces, dtype=np.uint32),
            )
        )
    )


def import_mesh(path):
    """Load an existing mesh file into a validated Manifold representation.

    Args:
        path (str | Path): Mesh file recognized by trimesh.

    Returns:
        (Mesh): Explicit mesh geometry in the file's numerical units; no rescaling.

    Raises:
        FileNotFoundError: The file does not exist.
        ValueError: Manifold rejects the imported geometry.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Missing source mesh: {path}")
    tm = trimesh.load_mesh(path, process=True)
    return Mesh(
        m3d.Manifold(
            m3d.Mesh(
                np.asarray(tm.vertices, dtype=np.float32),
                np.asarray(tm.faces, dtype=np.uint32),
            )
        )
    )


def _planar_boolean(values, operation):
    """Unify 2D regions through a short prism so OCCT removes internal seams.

    Coplanar face fuse preserves split faces in OCCT. Offsetting those individual
    faces cuts artificial gaps, so restore one boundary before the next feature.
    """
    solids = []
    for value in values:
        pieces = [
            cq.Solid.extrudeLinear(f.outerWire(), f.innerWires(), cq.Vector(0, 0, 1))
            for f in value.Faces()
        ]
        solids.append(
            pieces[0].fuse(*pieces[1:]).clean() if len(pieces) > 1 else pieces[0]
        )
    if operation == "union":
        result = solids[0].fuse(*solids[1:], tol=1e-7).clean()
    elif operation == "difference":
        result = solids[0].cut(*solids[1:], tol=1e-7).clean()
    else:
        result = solids[0]
        for solid in solids[1:]:
            result = result.intersect(solid, tol=1e-7)
        result = result.clean()
    faces = [
        f.translate((0, 0, -1)) for f in result.Faces() if f.normalAt().z > 0.99999
    ]
    if not faces:
        return None
    return faces[0] if len(faces) == 1 else cq.Compound.makeCompound(faces)


def _planar(values):
    return all(not isinstance(v, Mesh) and not v.Solids() and v.Faces() for v in values)


def union(values):
    """Fuse all nonempty inputs, retaining the native/mesh boundary.

    Args:
        values (list): Shapes, Workplanes, Meshes, or `None`.

    Returns:
        (cq.Shape | Mesh | None): Native result when all inputs are native;
            mesh result when any is a Mesh. Empty input yields `None`.

    Planar native faces use planar booleans. `union` ignores `None` values;
    `difference` is empty if its first value is `None`; `intersection` is
    empty if any value is `None`.
    """
    values = _items(values)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    if any(isinstance(v, Mesh) for v in values):
        return Mesh(
            m3d.Manifold.batch_boolean(
                [mesh(v).manifold for v in values], m3d.OpType.Add
            )
        )
    if _planar(values):
        return _planar_boolean(values, "union")
    return values[0].fuse(*values[1:]).clean()


def difference(values):
    """Subtract subsequent inputs from the first, retaining the native/mesh boundary.

    Args:
        values (list): Shapes, Workplanes, Meshes, or `None`.

    Returns:
        (cq.Shape | Mesh | None): Native result when all inputs are native;
            mesh result when any is a Mesh. Empty input yields `None`.

    Planar native faces use planar booleans. `union` ignores `None` values;
    `difference` is empty if its first value is `None`; `intersection` is
    empty if any value is `None`.
    """
    if not values or values[0] is None:
        return None
    values = _items(values)
    if len(values) == 1:
        return values[0]
    if any(isinstance(v, Mesh) for v in values):
        return Mesh(
            m3d.Manifold.batch_boolean(
                [mesh(v).manifold for v in values], m3d.OpType.Subtract
            )
        )
    if _planar(values):
        return _planar_boolean(values, "difference")
    return values[0].cut(*values[1:]).clean()


def intersection(values):
    """Intersect all inputs, retaining the native/mesh boundary.

    Args:
        values (list): Shapes, Workplanes, Meshes, or `None`.

    Returns:
        (cq.Shape | Mesh | None): Native result when all inputs are native;
            mesh result when any is a Mesh. Empty input yields `None`.

    Planar native faces use planar booleans. `union` ignores `None` values;
    `difference` is empty if its first value is `None`; `intersection` is
    empty if any value is `None`.
    """
    if any(v is None for v in values):
        return None
    values = _items(values)
    if not values:
        return None
    if any(isinstance(v, Mesh) for v in values):
        return Mesh(
            m3d.Manifold.batch_boolean(
                [mesh(v).manifold for v in values], m3d.OpType.Intersect
            )
        )
    if _planar(values):
        return _planar_boolean(values, "intersection")
    result = values[0]
    for value in values[1:]:
        result = result.intersect(value)
    return result.clean()


def _xyz(value):
    return tuple(value) + (0,) * (3 - len(value))


def translate(values, v):
    """Union inputs and translate them in millimetres.

    Args:
        values (list): Input geometry.
        v (tuple): XY or XYZ displacement; omitted trailing coordinates are zero.

    Returns:
        (cq.Shape | Mesh | None): Transformed geometry, or `None` for empty input.
    """
    result = union(values)
    if result is None:
        return None
    moved = result.translate(_xyz(v))
    if hasattr(result, "_circles"):
        moved._circles = [(x + v[0], y + v[1], r) for x, y, r in result._circles]
    return moved


def rotate(values, a, v=None):
    """Union inputs and rotate about the origin using degrees.

    Args:
        values (list): Input geometry.
        a (float | tuple): One angle about `v`, or X/Y/Z angles applied in that order.
        v (tuple | None): Axis for a scalar angle; defaults to positive Z.

    Returns:
        (cq.Shape | Mesh | None): Rotated geometry.
    """
    result = union(values)
    if result is None:
        return None
    if isinstance(a, (int, float)):
        return result.rotate((0, 0, 0), v or (0, 0, 1), a)
    for axis, angle in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), a):
        if angle:
            result = result.rotate((0, 0, 0), axis, angle)
    return result


def mirror(values, v):
    """Union inputs and reflect about a plane through the origin.

    Args:
        values (list): Input geometry.
        v (tuple): Plane normal.

    Returns:
        (cq.Shape | Mesh | None): Reflected geometry.
    """
    result = union(values)
    if result is None:
        return None
    if isinstance(result, Mesh):
        normal = np.asarray(v, dtype=float)
        normal /= np.linalg.norm(normal)
        return Mesh(
            result.manifold.transform(
                np.c_[np.eye(3) - 2 * np.outer(normal, normal), np.zeros(3)]
            )
        )
    return result.mirror(tuple(v))


def scale(values, v):
    """Union inputs and scale about the origin.

    Args:
        values (list): Nonempty input geometry.
        v (float | tuple): Uniform factor or XYZ factors.

    Returns:
        (cq.Shape | Mesh): Scaled geometry. Nonuniform native scaling uses a
            general geometry transform rather than a rigid placement.
    """
    result = union(values)
    if isinstance(v, (int, float)):
        v = (v, v, v)
    if isinstance(result, Mesh):
        return Mesh(result.manifold.scale(tuple(v)))
    matrix = cq.Matrix(
        [[v[0], 0, 0, 0], [0, v[1], 0, 0], [0, 0, v[2], 0], [0, 0, 0, 1]]
    )
    return result.transformGeometry(matrix)


def circle(r=None, d=None, facets=None):
    """Return a native XY disk centred at the origin. Supply radius `r` or diameter `d` in millimetres; `d` wins. `facets` is accepted but unused."""
    radius = d / 2 if d is not None else r
    if radius is None or radius <= 0:
        raise ValueError("Circle radius must be positive")
    result = cq.Face.makeFromWires(
        cq.Wire.makeCircle(radius, cq.Vector(), cq.Vector(0, 0, 1))
    )
    result._circles = [(0, 0, radius)]
    return result


def polygon(points):
    """Return a native closed XY face from ordered 2D/3D points in millimetres."""
    return cq.Face.makeFromWires(
        cq.Wire.makePolygon([cq.Vector(*_xyz(p)) for p in points], close=True)
    )


def square(size, center=False):
    """Return a native XY rectangle. `size` is one length or an `(x, y)` pair in millimetres; `center=False` uses positive XY."""
    if isinstance(size, (int, float)):
        size = (size, size)
    x, y = size
    x0, y0 = (-x / 2, -y / 2) if center else (0, 0)
    return polygon([(x0, y0), (x0 + x, y0), (x0 + x, y0 + y), (x0, y0 + y)])


def cube(size, center=False):
    """Return a native box. `size` is one length or XYZ lengths in millimetres; `center=False` uses positive XYZ."""
    if isinstance(size, (int, float)):
        size = (size, size, size)
    if min(size) <= 0:
        raise ValueError("Box dimensions must be positive")
    result = cq.Solid.makeBox(*size)
    return result.translate(tuple(-x / 2 for x in size)) if center else result


def cylinder(
    h, r=None, d=None, d1=None, d2=None, r1=None, r2=None, center=False, facets=None
):
    """Return a native +Z cylinder or cone of height `h` in millimetres. Use `r`/`d`, or `r1`/`d1` and `r2`/`d2` for bottom/top. `center=True` centres Z. `facets <= 12` selects a polygonal prism; larger values retain analytic round geometry."""
    bottom = (
        d1 / 2
        if d1 is not None
        else r1 if r1 is not None else d / 2 if d is not None else r
    )
    top = d2 / 2 if d2 is not None else r2 if r2 is not None else bottom
    if h <= 0:
        raise ValueError("Cylinder height must be positive")
    if facets is not None and facets <= 12:
        pts = [
            (
                bottom * math.cos(i * 2 * math.pi / facets),
                bottom * math.sin(i * 2 * math.pi / facets),
            )
            for i in range(int(facets))
        ]
        result = linear_extrude([polygon(pts)], h)
    elif abs(bottom - top) < 1e-12:
        result = cq.Solid.makeCylinder(bottom, h)
    else:
        result = cq.Solid.makeCone(bottom, top, h)
    return result.translate((0, 0, -h / 2)) if center else result


def sphere(r=None, d=None, facets=None):
    """Return an analytic sphere centred at the origin. Supply `r` or `d` in millimetres; `d` wins. `facets` is accepted but unused."""
    return cq.Solid.makeSphere(
        d / 2 if d is not None else r, angleDegrees1=-90, angleDegrees2=90
    )


def linear_extrude(values, height, center=False, **kwargs):
    """Union planar inputs and extrude their faces along +Z by `height` millimetres. `center=True` centres Z. Extra keyword arguments are accepted but unused; twist and taper are not implemented."""
    result = union(values)
    if result is None:
        return None
    solids = [
        cq.Solid.extrudeLinear(f.outerWire(), f.innerWires(), cq.Vector(0, 0, height))
        for f in result.Faces()
    ]
    result = union(solids)
    return result.translate((0, 0, -height / 2)) if center else result


def rotate_extrude(values, angle=360, facets=None):
    """Revolve an XY profile about world Z after mapping its Y axis to Z. `angle` is in degrees; `facets` is accepted but unused."""
    profile = rotate(values, (90, 0, 0))
    return union(
        [
            cq.Solid.revolve(f.outerWire(), f.innerWires(), angle, (0, 0, 0), (0, 0, 1))
            for f in profile.Faces()
        ]
    )


def offset(values, r=None, delta=None):
    """Offset planar regions by `r` with arc joins or `delta` with intersection joins, in millimetres. Positive offsets expand outer boundaries and shrink holes."""
    profile = union(values)
    amount = r if r is not None else delta
    result = []
    for face in profile.Faces():
        outer = face.outerWire().offset2D(
            amount, "arc" if r is not None else "intersection"
        )
        for wire in outer:
            f = cq.Face.makeFromWires(wire)
            for hole in face.innerWires():
                for hw in hole.offset2D(-amount):
                    f = f.cut(cq.Face.makeFromWires(hw))
            result.append(f)
    return union(result)


def _circle_hull(circles):
    pieces = [translate([circle(r=r)], (x, y, 0)) for x, y, r in circles]
    centers = np.array([(x, y) for x, y, r in circles])
    if len(centers) >= 3 and np.linalg.matrix_rank(centers - centers[0]) == 2:
        pieces.append(polygon(centers[ConvexHull(centers).vertices]))
    for a, b in combinations(circles, 2):
        ax, ay, ar = a
        bx, by, br = b
        dx, dy = bx - ax, by - ay
        dist = math.hypot(dx, dy)
        if dist <= abs(ar - br) + 1e-10:
            continue
        ux, uy = dx / dist, dy / dist
        q = (ar - br) / dist
        t = math.sqrt(1 - q * q)
        normals = [(q * ux + s * t * uy, q * uy - s * t * ux) for s in (-1, 1)]
        n1, n2 = normals
        pieces.append(
            polygon(
                [
                    (ax + ar * n1[0], ay + ar * n1[1]),
                    (bx + br * n1[0], by + br * n1[1]),
                    (bx + br * n2[0], by + br * n2[1]),
                    (ax + ar * n2[0], ay + ar * n2[1]),
                ]
            )
        )
    return union(pieces)


def hull(values):
    """Return a convex hull. Circles use native tangent geometry; other planar curves are sampled. Spatial hulls cross to the Mesh representation."""
    values = _items(values)
    if not values:
        return None
    if all(hasattr(v, "_circles") for v in values):
        return _circle_hull([c for v in values for c in v._circles])
    if all(not isinstance(v, Mesh) and not v.Solids() for v in values):
        points = np.array(
            [
                p.toTuple()[:2]
                for v in values
                for edge in v.Edges()
                for p in edge.sample(64)[0]
            ]
        )
        return polygon(points[ConvexHull(points).vertices])
    # Spatial hulls used for imported mesh interfaces; record the mesh boundary.
    return Mesh(m3d.Manifold.batch_hull([mesh(v).manifold for v in values]))


def projection(values, cut=False):
    """Project tessellated input onto XY, or section at Z=0 with `cut=True`. Returns planar faces reconstructed from Manifold contours; this is not an analytic projection."""
    source = mesh(union(values)).manifold
    contours = source.slice(0).to_polygons() if cut else source.project().to_polygons()
    return union([polygon(contour) for contour in contours])


# Higher-level primitives that accept ordinary CadQuery objects.
def annulus(outer_diameter, inner_diameter, height):
    """Build a native ring from Z=0 along positive Z.

    Args:
        outer_diameter (float): Outer diameter in millimetres.
        inner_diameter (float): Inner diameter in millimetres.
        height (float): Ring height in millimetres.

    Returns:
        (cq.Workplane): Native annular prism centred on the origin in XY.
    """
    return (
        cq.Workplane("XY")
        .circle(outer_diameter / 2)
        .circle(inner_diameter / 2)
        .extrude(height)
    )


def rounded_rect_prism(length, width, height, radius, *, centered=True):
    """Build an XY rounded rectangle extruded from Z=0.

    Args:
        length (float): Overall X extent in millimetres.
        width (float): Overall Y extent in millimetres.
        height (float): Z height in millimetres.
        radius (float): Corner radius, at most half the smaller XY extent.
        centered (bool): Centre XY at the origin; if false, use positive XY extents.

    Returns:
        (cq.Workplane): Native rounded rectangular prism.
    """
    require_radius = min(length, width) / 2
    if not 0 < radius <= require_radius:
        raise ValueError("Corner radius exceeds half the smaller side")
    result = linear_extrude(
        [
            _circle_hull(
                [
                    (sx * (length / 2 - radius), sy * (width / 2 - radius), radius)
                    for sx in (-1, 1)
                    for sy in (-1, 1)
                ]
            )
        ],
        height,
    )
    return cq.Workplane("XY").newObject(
        [result if centered else result.translate((length / 2, width / 2, 0))]
    )


def capsule(center=(0, 0), diameter=5, travel=10, angle=0, height=10):
    """Build a rounded slot-shaped prism from two semicircular ends.

    Args:
        center (tuple): XY centre in millimetres.
        diameter (float): Width in millimetres.
        travel (float): Distance between end-circle centres in millimetres.
            Overall length is `travel + diameter`.
        angle (float): Long-axis angle in degrees from +X toward +Y.
        height (float): Extrusion from Z=0 along +Z, in millimetres.

    Returns:
        (cq.Shape): Native capsule prism.
    """
    dx = travel / 2 * math.cos(math.radians(angle))
    dy = travel / 2 * math.sin(math.radians(angle))
    return linear_extrude(
        [
            _circle_hull(
                [
                    (center[0] - dx, center[1] - dy, diameter / 2),
                    (center[0] + dx, center[1] + dy, diameter / 2),
                ]
            )
        ],
        height,
    )


def polar_points(radius, angles):
    """Return XY points on a circle, preserving the supplied angle order.

    Args:
        radius (float): Radius in millimetres.
        angles (tuple): Angles in degrees from +X toward +Y.

    Returns:
        (list[tuple]): XY pairs in millimetres.
    """
    return [
        (radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a)))
        for a in angles
    ]


def normalized_to_bed(model):
    """Translate geometry vertically so its lowest point touches Z=0.

    Args:
        model (object): Native Shape, Workplane, or Mesh.

    Returns:
        (cq.Shape | Mesh): Translated geometry; X/Y placement and rotation are preserved.
    """
    value = shape(model)
    if isinstance(value, Mesh):
        z = value.triangles().bounds[0, 2]
    else:
        z = value.BoundingBox().zmin
    return value.translate((0, 0, -z))
