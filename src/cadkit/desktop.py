"""Local desktop worker. JSON lines over stdio; stdout is protocol-only.

Each process owns one immutable build revision and its original CAD geometry.
The Electron host builds in a new process, retaining the old process on failure.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from math import dist
import os
from pathlib import Path
import sys
import time
import traceback
from urllib.parse import quote
from uuid import uuid4

import numpy as np
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from .cli import load_project
from .export import build, export_render_assets
from .geometry import Mesh, mesh, shape
from ._project import Assembly
from .preflight import scoped_report
from .performance import Timings, measure, peak_rss_bytes
from .geometry_cache import GeometryCache


def configure_threads():
    """Allow worker-local OCCT tuning through CadQuery's supported API."""
    from cadquery.occ_impl.shapes import setThreads
    from OCP.OSD import OSD_ThreadPool

    value = os.environ.get("CADKIT_OCCT_THREADS")
    if value is not None:
        try:
            count = int(value)
        except ValueError:
            raise ValueError("CADKIT_OCCT_THREADS must be a positive integer") from None
        if count < 1:
            raise ValueError("CADKIT_OCCT_THREADS must be a positive integer")
        setThreads(count)
    return OSD_ThreadPool.DefaultPool_s().NbThreads()


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


def encode_scene(shapes):
    """Pack shared meshes using three-cad-viewer's upstream instanced format.

    Only display buffers are cast to the viewer's float32/uint32 types. Original
    CAD geometry and native measurements are untouched.
    """
    from ocp_tessellate.utils import numpy_to_buffer_json

    instances, refs = [], {}
    floats = {"vertices", "normals", "edges", "obj_vertices", "uvs"}

    def visit(node):
        result = dict(node)
        if "parts" in node:
            result["parts"] = [visit(child) for child in node["parts"]]
        if "shape" in node:
            geometry = node["shape"]
            def buffers():
                arrays = {name: np.asarray(values, dtype="<f4" if name in floats else "<u4")
                          for name, values in geometry.items()}
                for name in floats & arrays.keys():
                    if not np.isfinite(arrays[name]).all():
                        raise ValueError(f"Non-finite {name} in display geometry")
                return numpy_to_buffer_json(arrays)
            if node.get("type") != "shapes":
                # Edges/vertices have partial geometry records. The viewer
                # decodes those inline rather than as complete mesh instances.
                result["shape"] = buffers()
                return result
            key = id(geometry)
            if key not in refs:
                refs[key] = len(instances)
                instances.append(buffers())
            result["shape"] = {"ref": refs[key]}
        return result

    tree = visit(shapes)
    return {"instances": instances, "shapes": tree}


class Session:
    def __init__(self, project, notify=lambda message: None, *, timings=None, geometry_cache=None):
        self.project = project
        self.notify = notify
        self.revision = str(uuid4())
        self.models = {}
        self.components = {}
        self.metadata = {}
        self.snapshot = None
        self.wire_snapshot = None
        self.assembly = None
        self.scene_counts = {}
        self.mechanical_reports = {}
        self.timings = timings if timings is not None else Timings()
        self.geometry_cache = geometry_cache

    def performance(self):
        return {**self.timings.describe(), **self.scene_counts,
                "geometry_cache": dict(self.geometry_cache.stats) if self.geometry_cache else {"status": "disabled"}}

    def scene(self):
        if self.snapshot is not None:
            return self.snapshot
        with self.timings.collect(), measure("scene"):
            if self.geometry_cache is None:
                snapshot = self._scene()
            else:
                try:
                    with self.geometry_cache.collect():
                        snapshot = self._scene()
                    self.geometry_cache.finish()
                finally:
                    self.geometry_cache.close()
        snapshot["performance"] = self.performance()
        snapshot["build_seconds"] = round(snapshot["performance"]["stages_seconds"]["scene"], 2)
        self.snapshot = snapshot
        return snapshot

    def scene_for_transport(self):
        if self.wire_snapshot is None:
            snapshot = self.scene()
            with self.timings.collect(), measure("encode"):
                shapes = encode_scene(snapshot["shapes"])
            self.wire_snapshot = {**snapshot, "shapes": shapes,
                                  "performance": self.performance()}
        return self.wire_snapshot

    def _scene(self):
        try:
            with measure("tessellator_import"):
                from ocp_tessellate.convert import to_ocpgroup, tessellate_group
        except ImportError as exc:
            raise RuntimeError(
                "Install CadKit's desktop extra in this Python environment: pip install 'cadkit-py[desktop]'"
            ) from exc

        self.notify("Building assembly geometry…")
        with measure("assembly"):
            assembly = self.project.get_assembly()
        self.assembly = assembly
        parts = {part.name: part for part in self.project.parts}
        native = []

        def visit(node, parent=""):
            path = parent + "/" + quote(node.name, safe="")
            if isinstance(node, Assembly):
                children = [visit(child, path) for child in node.children]
                return (
                    {
                        "version": 3,
                        "name": quote(node.name, safe=""),
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
            self.components[path] = node
            color = "#" + "".join(f"{round(v * 255):02x}" for v in node.color)
            if isinstance(model, Mesh):
                with measure("mesh", path):
                    triangles = model.triangles()
                    normals = np.asarray(triangles.vertex_normals).ravel()
                geometry = {
                    "vertices": np.asarray(triangles.vertices).ravel(),
                    "normals": normals,
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
                visual = {}
                native.append((path, model, node.name, color, visual))
            visual.update(version=3, id=path, name=quote(node.name, safe=""))
            info = {
                "id": path,
                "name": node.name,
                "kind": "component",
                "group": node.group,
                "metadata": node.metadata,
                "part": node.part,
                "material": parts[node.part].material if node.part else node.material,
                "color": color,
                "geometry": "mesh" if isinstance(model, Mesh) else "native",
            }
            self.metadata[path] = info
            return visual, info

        visuals, tree = visit(assembly)
        if not self.models:
            raise ValueError("The project contains no installed components")
        self.scene_counts = {"component_count": len(self.models),
                             "native_component_count": len(native), "unique_native_shapes": 0}
        if native:
            # One conversion lets ocp-tessellate recognize shared TShapes across
            # installed instances, tessellating their local geometry only once.
            self.notify("Tessellating…")
            with measure("convert"):
                group, instances = to_ocpgroup(
                    *(item[1].wrapped for item in native),
                    names=[item[2] for item in native], colors=[item[3] for item in native],
                )
            self.scene_counts["unique_native_shapes"] = len(instances)
            with measure("tessellate"):
                meshes, converted, _ = tessellate_group(
                    group, instances, kwargs={"deviation": 0.1, "angular_tolerance": 0.2},
                )

            def expand(item, item_path):
                item["id"] = item_path
                item["name"] = item_path.rsplit("/", 1)[-1]
                if "parts" in item:
                    for index, child in enumerate(item["parts"]):
                        expand(child, item_path + f"/shape-{index}")
                elif "ref" in item.get("shape", {}):
                    item["shape"] = meshes[item["shape"]["ref"]]

            if len(converted["parts"]) != len(native):
                raise ValueError("Tessellation omitted an installed component")
            for (path, _, name, _, target), visual in zip(native, converted["parts"]):
                expand(visual, path)
                target.update(visual, version=3, id=path, name=quote(name, safe=""))
        # Native bounding boxes can reuse the triangulation installed by the
        # mesher. Measure after tessellation and reuse the results for scene bounds.
        for path, model in self.models.items():
            with measure("bounds", path):
                bb = bounds(model)
            with measure("volume", path):
                volume = float(model.manifold.volume() if isinstance(model, Mesh) else model.Volume())
            self.metadata[path].update(bounds=bb, size=[b - a for a, b in zip(*bb)], volume_mm3=volume)
        all_bounds = [info["bounds"] for info in self.metadata.values()]
        lo = np.min([bb[0] for bb in all_bounds], axis=0)
        hi = np.max([bb[1] for bb in all_bounds], axis=0)
        visuals["bb"] = {
            key: float(value)
            for key, value in zip(
                ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax"), [*lo, *hi]
            )
        }
        with measure("describe"):
            description = self.project.describe()
        with measure("mechanics"):
            mechanics = self.project.mechanical_descriptions(assembly=assembly)
        return {
            "revision": self.revision,
            "project": description,
            "tree": tree,
            "components": list(self.metadata.values()),
            "mechanics": mechanics,
            "shapes": visuals,
        }

    def section_view(self, revision, ids, plane="XY", mode="section", offset=0, tolerance=0.05):
        if revision != self.revision:
            raise ValueError("This request belongs to an older build")
        from .inspection import drawing
        self.scene()
        return {"revision": self.revision, **drawing(
            self.models, {c["id"]: c for c in self.snapshot["components"]}, ids, plane=plane, mode=mode,
            offset=offset, tolerance=tolerance)}

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

    def mechanical_report(self, revision, parts=None, scan_collisions=True):
        if revision != self.revision:
            raise ValueError("This request belongs to an older build")
        if type(scan_collisions) is not bool:
            raise ValueError("scan_collisions must be a boolean")
        self.scene()
        if scan_collisions not in self.mechanical_reports:
            self.mechanical_reports[scan_collisions] = {
                **self.project.validate_mechanics(assembly=self.assembly, scan_collisions=scan_collisions),
                "revision": self.revision,
            }
        report = self.mechanical_reports[scan_collisions]
        if parts is not None:
            if not parts or len(parts) != len(set(parts)):
                raise ValueError("Choose distinct Parts to review")
            report = scoped_report(report, self.assembly, self.project.select(parts), fastenings=self.project.fastenings)
        return report

    def export_part(self, name, output_dir, validation_override=None):
        part = self.project.select([name])[0]
        destination = Path(output_dir).resolve()
        report = self.mechanical_report(self.revision, parts=[name])
        manifest = build(self.project, [part], destination, mechanical_report=report, validation_override=validation_override)
        return {"directory": str(destination), "manifest": manifest}

    def render_assets(self, revision, ids, output_dir, exploded=False, animation=False):
        if revision != self.revision:
            raise ValueError("Stale build revision")
        if not ids or len(set(ids)) != len(ids) or any(i not in self.components for i in ids):
            raise ValueError("Select current assembly components")
        components = [self.components[i] for i in ids]
        if animation and not any(any(c.explode) for c in components):
            raise ValueError("Selected components have no explosion offsets")
        return export_render_assets(components, output_dir, exploded=exploded, variant_selection=getattr(self.project, "variant_selection", {}))

    def export_parts(self, revision, names, output_dir, validation_override=None):
        if revision != self.revision:
            raise ValueError("This request belongs to an older build")
        if not names or len(names) != len(set(names)):
            raise ValueError("Choose distinct Parts to export")
        parts = self.project.select(names)
        destination = Path(output_dir).resolve()
        report = self.mechanical_report(revision, parts=names)
        manifest = build(self.project, parts, destination, mechanical_report=report, validation_override=validation_override)
        return {"directory": str(destination), "manifest": manifest}


def project_dependencies(project):
    dependencies = set(getattr(getattr(project, "_variants", None), "dependencies", ()))
    prefixes = (Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve())
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and filename.endswith(".py"):
            path = Path(filename).resolve()
            if not any(path.is_relative_to(prefix) for prefix in prefixes):
                dependencies.add(str(path))
    return sorted(dependencies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--variant", action="append", default=[])
    args = parser.parse_args()
    from .variants import parse_variants
    protocol = sys.stdout

    def emit(message, *, scene=False):
        started = time.perf_counter()
        encoded = json.dumps(
            message, default=json_default, separators=(",", ":"), allow_nan=False
        )
        if scene:
            emit({"event": "performance", "serialize_seconds": time.perf_counter() - started,
                  # json.dumps defaults to ASCII, so characters equal bytes.
                  "response_bytes": len(encoded) + 1,
                  "peak_rss_bytes": peak_rss_bytes()})
        protocol.write(encoded)
        protocol.write("\n")
        protocol.flush()

    with redirect_stdout(sys.stderr):
        threads = configure_threads()
        timings = Timings()
        with timings.collect(), measure("cache_prepare"):
            geometry_cache = GeometryCache.for_worker()
        with timings.collect(), measure("project_load"):
            project = load_project(args.project, parse_variants(args.variant))
        if geometry_cache is not None:
            with timings.collect(), measure("cache_prepare"):
                geometry_cache.prepare(args.project, project)
        session = Session(
            project,
            lambda message: emit({"event": "progress", "message": message}),
            timings=timings,
            geometry_cache=geometry_cache,
        )
        # Explicit input paths and imported source outside the interpreter are
        # watched before geometry is built, including consumer libraries outside
        # the project root. Installed runtime upgrades require a restart.
        def emit_inputs():
            dependencies = project_dependencies(session.project)
            if geometry_cache is not None:
                dependencies += geometry_cache.watched_paths()
            emit({"event": "inputs", "paths": sorted({str(Path(p).resolve()) for p in dependencies}),
                  "source_roots": geometry_cache.roots if geometry_cache is not None else []})
        emit_inputs()
        emit({"event": "ready", "occt_threads": threads})
        for line in sys.stdin:
            request = {}
            try:
                request = json.loads(line)
                method = request["method"]
                if method not in {"scene", "measure", "section_view", "export_part", "export_parts", "mechanical_report", "render_assets"}:
                    raise ValueError(f"Unknown method: {method}")
                if method == "scene":
                    # Keep the Python Session's expanded arrays for inspection;
                    # only the worker transport uses the viewer's packed format.
                    params = request.get("params", {})
                    if not isinstance(params, dict) or params:
                        raise ValueError("scene takes no parameters")
                    result = session.scene_for_transport()
                else:
                    result = getattr(session, method)(**request.get("params", {}))
                if method == "scene":
                    emit_inputs()
                emit({"id": request["id"], "result": result}, scene=method == "scene")
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                emit({"id": request.get("id"), "error": str(exc)})


if __name__ == "__main__":
    main()
