"""Local desktop worker. JSON lines over stdio; stdout is protocol-only.

Each process owns one immutable build revision and its original CAD geometry.
The Electron host builds in a new process, retaining the old process on failure.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from math import dist
from pathlib import Path
import sys
import time
import traceback
from urllib.parse import quote
from uuid import uuid4

import numpy as np
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from .cli import load_project
from .export import build
from .geometry import Mesh, mesh, shape
from .project import Assembly


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def bounds(model):
    if isinstance(model, Mesh):
        lo, hi = model.triangles().bounds
        return [lo.tolist(), hi.tolist()]
    b = model.BoundingBox()
    return [[b.xmin, b.ymin, b.zmin], [b.xmax, b.ymax, b.zmax]]


class Session:
    def __init__(self, project, notify=lambda message: None):
        self.project = project
        self.notify = notify
        self.revision = str(uuid4())
        self.models = {}
        self.metadata = {}
        self.snapshot = None

    def scene(self):
        if self.snapshot is not None:
            return self.snapshot
        try:
            from ocp_tessellate.convert import to_ocpgroup, tessellate_group
        except ImportError as exc:
            raise RuntimeError(
                "Install CadKit's desktop extra in this Python environment: pip install -e '../cadkit[desktop]'"
            ) from exc

        started = time.monotonic()
        self.notify("Building assembly geometry…")
        assembly = self.project.get_assembly()
        parts = {part.name: part for part in self.project.parts}

        def visit(node, parent=""):
            path = parent + "/" + quote(node.name, safe="")
            if isinstance(node, Assembly):
                children = [visit(child, path) for child in node.children]
                return (
                    {
                        "version": 3,
                        "name": node.name,
                        "id": path,
                        "parts": [c[0] for c in children],
                    },
                    {
                        "id": path,
                        "name": node.name,
                        "kind": "assembly",
                        "description": node.description,
                        "children": [c[1] for c in children],
                    },
                )
            self.notify(f"Preparing {node.name}…")
            model = shape(node.model)
            if model is None:
                raise ValueError(f"{node.name}: no geometry")
            if node.part is not None and node.part not in parts:
                raise ValueError(f"{node.name}: unknown Part {node.part!r}")
            self.models[path] = model
            color = "#" + "".join(f"{round(v * 255):02x}" for v in node.color)
            if isinstance(model, Mesh):
                triangles = model.triangles()
                geometry = {
                    "vertices": np.asarray(triangles.vertices).ravel(),
                    "normals": np.asarray(triangles.vertex_normals).ravel(),
                    "triangles": np.asarray(triangles.faces).ravel(),
                    "triangles_per_face": [len(triangles.faces)],
                    "face_types": [10],
                    "edges": [],
                    "segments_per_edge": [],
                    "edge_types": [],
                    "obj_vertices": [],
                }
                visual = {
                    "shape": geometry,
                    "state": [1, 0],
                    "type": "shapes",
                    "subtype": "solid",
                    "color": color,
                    "alpha": 1,
                }
            else:
                group, instances = to_ocpgroup(
                    model.wrapped, names=[node.name], colors=[color]
                )
                meshes, converted, _ = tessellate_group(
                    group,
                    instances,
                    kwargs={"deviation": 0.1, "angular_tolerance": 0.2},
                )
                visual = converted["parts"][0]

                def expand(item, item_path):
                    item["id"] = item_path
                    if "parts" in item:
                        for index, child in enumerate(item["parts"]):
                            expand(child, item_path + f"/shape-{index}")
                    elif "ref" in item.get("shape", {}):
                        item["shape"] = meshes[item["shape"]["ref"]]

                expand(visual, path)
            visual.update(version=3, id=path, name=node.name)
            bb = bounds(model)
            info = {
                "id": path,
                "name": node.name,
                "kind": "component",
                "group": node.group,
                "part": node.part,
                "material": parts[node.part].material if node.part else node.material,
                "color": color,
                "geometry": "mesh" if isinstance(model, Mesh) else "native",
                "bounds": bb,
                "size": [b - a for a, b in zip(*bb)],
                "volume_mm3": float(
                    model.manifold.volume()
                    if isinstance(model, Mesh)
                    else model.Volume()
                ),
            }
            self.metadata[path] = info
            return visual, info

        visuals, tree = visit(assembly)
        if not self.models:
            raise ValueError("The project contains no installed components")
        all_bounds = [bounds(model) for model in self.models.values()]
        lo = np.min([bb[0] for bb in all_bounds], axis=0)
        hi = np.max([bb[1] for bb in all_bounds], axis=0)
        visuals["bb"] = {
            key: float(value)
            for key, value in zip(
                ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax"), [*lo, *hi]
            )
        }
        self.snapshot = {
            "revision": self.revision,
            "project": self.project.describe(),
            "tree": tree,
            "components": list(self.metadata.values()),
            "shapes": visuals,
            "build_seconds": round(time.monotonic() - started, 2),
        }
        return self.snapshot

    def measure(self, revision, ids):
        if revision != self.revision:
            raise ValueError(
                "This selection belongs to an older build. Select the objects again."
            )
        if len(ids) != 2 or ids[0] == ids[1]:
            raise ValueError("Select two different objects")
        if any(path not in self.models for path in ids):
            raise ValueError("Unknown component selection")
        a, b = (self.models[path] for path in ids)
        centers = [np.mean(bounds(model), axis=0).tolist() for model in (a, b)]
        native = not any(isinstance(model, Mesh) for model in (a, b))
        points = None
        if native:
            result = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
            result.Perform()
            if not result.IsDone() or result.NbSolution() == 0:
                raise ValueError("OpenCascade could not calculate a distance")
            minimum = result.Value()
            points = [
                list(p.Coord())
                for p in (result.PointOnShape1(1), result.PointOnShape2(1))
            ]
        else:
            # Bound the search above the greatest possible separation to avoid a
            # clipped result. Native shapes are tessellated only at this boundary.
            limit = (
                float(
                    np.linalg.norm(
                        np.max([bounds(a)[1], bounds(b)[1]], axis=0)
                        - np.min([bounds(a)[0], bounds(b)[0]], axis=0)
                    )
                )
                + 1
            )
            minimum = mesh(a).manifold.min_gap(mesh(b).manifold, limit)
        return {
            "revision": self.revision,
            "ids": ids,
            "minimum_mm": float(minimum),
            "method": "native" if native else "mesh",
            "points": points,
            "center_distance_mm": dist(*centers),
            "center_delta_mm": [v - u for u, v in zip(*centers)],
        }

    def export_part(self, name, output_dir):
        part = self.project.select([name])[0]
        destination = Path(output_dir).resolve()
        manifest = build(self.project, [part], destination)
        return {"directory": str(destination), "manifest": manifest}

    def export_parts(self, revision, names, output_dir):
        if revision != self.revision:
            raise ValueError("This request belongs to an older build")
        if not names or len(names) != len(set(names)):
            raise ValueError("Choose distinct Parts to export")
        parts = self.project.select(names)
        destination = Path(output_dir).resolve()
        manifest = build(self.project, parts, destination)
        return {"directory": str(destination), "manifest": manifest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    protocol = sys.stdout

    def emit(message):
        protocol.write(
            json.dumps(
                message, default=json_default, separators=(",", ":"), allow_nan=False
            )
            + "\n"
        )
        protocol.flush()

    with redirect_stdout(sys.stderr):
        session = Session(
            load_project(args.project),
            lambda message: emit({"event": "progress", "message": message}),
        )
        for line in sys.stdin:
            request = {}
            try:
                request = json.loads(line)
                method = request["method"]
                if method not in {"scene", "measure", "export_part", "export_parts"}:
                    raise ValueError(f"Unknown method: {method}")
                result = getattr(session, method)(**request.get("params", {}))
                emit({"id": request["id"], "result": result})
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                emit({"id": request.get("id"), "error": str(exc)})


if __name__ == "__main__":
    main()
