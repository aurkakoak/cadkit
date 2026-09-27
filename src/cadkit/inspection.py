"""Bounded 2D review geometry from installed native shapes, not a drawing export."""

from math import isfinite

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from .geometry import Mesh


def drawing(
    models, components, ids, *, plane="XY", mode="section", offset=0, tolerance=0.05
):
    axes = {"XY": (0, 1, 2), "XZ": (0, 2, 1), "YZ": (1, 2, 0)}
    if plane not in axes or mode not in {"section", "projection"}:
        raise ValueError("Choose XY, XZ or YZ and section or projection")
    if not isfinite(offset) or not isfinite(tolerance) or not 0.001 <= tolerance <= 1:
        raise ValueError("Use a finite offset and tolerance between 0.001 and 1 mm")
    if not ids or len(ids) > 100 or len(set(ids)) != len(ids):
        raise ValueError("Choose 1 to 100 distinct components")
    if any(id not in models for id in ids):
        raise ValueError("Unknown component selection")
    if any(isinstance(models[id], Mesh) for id in ids):
        raise ValueError(
            "2D review requires native shapes; use measure for mesh clearance"
        )
    u, v, normal = axes[plane]
    origin, direction = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    origin[normal], direction[normal] = offset, 1
    cut_plane = gp_Pln(gp_Pnt(*origin), gp_Dir(*direction))
    items, count = [], 0
    for id in ids:
        model = models[id]
        if mode == "section":
            section = BRepAlgoAPI_Section(model.wrapped, cut_plane, False)
            section.Build()
            if not section.IsDone():
                raise ValueError(f"Could not section {id}")
            model = cq.Shape.cast(section.Shape())
        lines = []
        for edge in model.Edges():
            points, _ = edge.sample(float(tolerance))
            if edge.IsClosed() and points:
                points.append(points[0])
            line = [[p.toTuple()[u], p.toTuple()[v]] for p in points]
            if len(line) < 2 or all(p == line[0] for p in line):
                continue
            count += len(line)
            if count > 100_000:
                raise ValueError(
                    "2D review exceeds 100000 points; select fewer components or increase tolerance"
                )
            lines.append(line)
        metadata = components[id]
        items.append({"id": id, "name": metadata["name"], "lines": lines})
    points = [p for item in items for line in item["lines"] for p in line]
    bounds = (
        [
            [min(p[a] for p in points) for a in (0, 1)],
            [max(p[a] for p in points) for a in (0, 1)],
        ]
        if points
        else None
    )
    return {
        "mode": mode,
        "plane": plane,
        "offset_mm": offset,
        "units": "mm",
        "axes": ["XYZ"[u], "XYZ"[v]],
        "normal_axis": "XYZ"[normal],
        "tolerance_mm": tolerance,
        "bounds": bounds,
        "components": items,
        "frame": "installed",
        "method": "native-section" if mode == "section" else "native-edges",
        "limitations": "Sampled curves; projection includes hidden edges. Use native measurements and mechanical checks to establish fit.",
    }
