"""Validated fabrication artifacts and machine-readable build manifests."""

from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import cadquery as cq
import numpy as np
from .geometry import Mesh, shape, mesh, TOLERANCE


def inspect_model(model):
    """Measure geometry without applying print orientation.

    Args:
        model (object): Native Shape, Workplane, or Mesh.

    Returns:
        (dict): Representation, validity, solid count, volume in mm³, and min/max/
            size bounds in mm. Mesh validity requires positive watertight geometry
            with consistent winding.
    """
    model = shape(model)
    if isinstance(model, Mesh):
        tm = model.triangles()
        bounds = tm.bounds
        volume = float(tm.volume)
        count = len(model.manifold.decompose())
        valid = bool(tm.is_watertight and tm.is_winding_consistent and volume > 0)
        kind = "mesh"
    else:
        bb = model.BoundingBox()
        bounds = np.array([[bb.xmin, bb.ymin, bb.zmin], [bb.xmax, bb.ymax, bb.zmax]])
        volume = sum(s.Volume() for s in model.Solids())
        count = len(model.Solids())
        valid = bool(model.isValid() and count > 0 and volume > 0)
        kind = "brep"
    return {
        "geometry": kind,
        "valid": valid,
        "solid_count": count,
        "volume_mm3": round(volume, 5),
        "bounds_mm": {
            "min": bounds[0].tolist(),
            "max": bounds[1].tolist(),
            "size": (bounds[1] - bounds[0]).tolist(),
        },
    }


def validate_part(part, model):
    """Validate built fabrication geometry against its Part definition.

    Args:
        part (cadkit._project.Part): Manufacturing definition.
        model (object): Geometry already in print orientation.

    Returns:
        (dict): Measurement information from `inspect_model`.

    Raises:
        ValueError: Geometry is invalid, solid count differs from `expected_solids`,
            or its lowest Z is more than 0.001 mm from the bed.
    """
    info = inspect_model(model)
    if not info["valid"]:
        raise ValueError(f'{part.name}: invalid {info["geometry"]} geometry')
    if part.expected_solids is not None and info["solid_count"] != part.expected_solids:
        raise ValueError(
            f'{part.name}: expected {part.expected_solids} solid(s), found {info["solid_count"]}'
        )
    if abs(info["bounds_mm"]["min"][2]) > 0.001:
        raise ValueError(f"{part.name}: print orientation does not touch the bed")
    return info


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def export_stl(model, path):
    """Write a native Shape or explicit Mesh to STL, creating parent directories. Native tessellation uses 0.025 mm linear and 0.08 rad angular tolerance."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(model, Mesh):
        model.triangles().export(path)
    else:
        cq.exporters.export(
            model, str(path), tolerance=TOLERANCE, angularTolerance=0.08
        )


def export_part(part, directory):
    """Build and validate a Part, then write print-oriented STL and native STEP.

    Args:
        part (cadkit.Part | object): Part definition or selected project fabrication record.
        directory (str | Path): Destination directory, created if needed.

    Returns:
        (dict): Part metadata, measured geometry, relative filenames, and SHA-256
            hashes. Mesh parts have STL only; a stale same-name STEP is removed.

    This primitive does not review assembly mechanics. Use `build` for a
    project-aware export with the mechanical preflight gate and manifests.
    """
    from .design.parts import Part
    if isinstance(part, Part):
        part = part.as_part()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    model = part.build()
    info = {**part.describe(), **validate_part(part, model)}
    stl = directory / f"{part.name}.stl"
    export_stl(model, stl)
    files = {"stl": stl.name}
    step = directory / f"{part.name}.step"
    if isinstance(model, Mesh):
        step.unlink(missing_ok=True)
        info["step_unavailable_reason"] = (
            "Source includes attributed vendor mesh geometry; no analytic STEP solid exists."
        )
    else:
        cq.exporters.export(model, str(step))
        files["step"] = step.name
    info["files"] = files
    info["sha256"] = {
        kind: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for kind, name in files.items()
    }
    return info


def build(project, parts, directory, *, mechanical_report=None, validation_override=None):
    """Export a selected manufacturing set with validation and manifests.

    Args:
        project (cadkit.Project): Source project and mechanical declarations.
        parts (list): Selected fabrication records from `project.select()`.
        directory (str | Path): Destination directory.
        mechanical_report (dict | None): Optional precomputed scoped report.
            Otherwise, projects declaring mechanics are checked automatically.
        validation_override (str | None): Explicit review reason of 3–1000
            characters for exporting despite confirmed assembly failures.

    Returns:
        (dict): Build manifest also written to `manifest.json`, alongside
            `quantities.json` and `subassemblies.json`.

    Confirmed mechanical failures block export unless deliberately overridden.
    An incomplete review remains visible and does not prove full assembly fit.
    A partial build's manifest contains exactly the selected set.
    """
    from .preflight import scoped_report, reviewed_report
    directory = Path(directory)
    parts = list(parts)
    if mechanical_report is None and (project.joints or project.interfaces or project.fastenings):
        assembly = project.get_assembly()
        mechanical_report = scoped_report(project.validate_mechanics(assembly=assembly), assembly, parts, fastenings=project.fastenings)
    if mechanical_report is not None:
        # Persist the failed review too, but never leave an old manifest advertising it as a new successful build.
        (directory / "manifest.json").unlink(missing_ok=True)
        write_json(directory / "assembly-validation.json", mechanical_report)
        mechanical_report = reviewed_report(mechanical_report, validation_override)
        write_json(directory / "assembly-validation.json", mechanical_report)
    summaries = []
    for part in parts:
        info = export_part(part, directory)
        summaries.append(info)
        print(
            f'ok  {part.name}: {info["geometry"]}, {info["volume_mm3"]:.1f} mm³',
            flush=True,
        )
    manifest = {
        "schema_version": 1,
        "project": project.name,
        "cadquery_version": cq.__version__,
        "units": "mm",
        "tessellation": {
            "linear_tolerance_mm": TOLERANCE,
            "angular_tolerance_rad": 0.08,
        },
        "parts": summaries,
    }
    if mechanical_report is not None:
        manifest["assembly_validation"] = mechanical_report
    write_json(directory / "manifest.json", manifest)
    write_json(directory / "quantities.json", {p.name: p.quantity for p in parts})
    write_json(
        directory / "subassemblies.json",
        {
            group: [p.name for p in parts if p.group == group]
            for group in sorted({p.group for p in parts})
        },
    )
    return manifest


def export_assembly(components, output, *, exploded=False):
    """Write a named, colored installed STEP assembly and omission metadata.

    Args:
        components (list): Installed Components.
        output (str | Path): Destination STEP path.
        exploded (bool): Apply each Component's full explosion translation once.

    Returns:
        (cq.Assembly): Exported native hierarchy. Mesh components are omitted
            and listed in the companion same-stem JSON file.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    assembly = cq.Assembly(name=output.stem)
    omitted = []
    for c in components:
        model = c.placed(1 if exploded else 0)
        if isinstance(model, Mesh):
            omitted.append(c.name)
            continue
        assembly.add(model, name=c.name, color=cq.Color(*c.color))
    assembly.export(str(output))
    write_json(
        output.with_suffix(".json"),
        {
            "schema_version": 1,
            "units": "mm",
            "mesh_components_omitted_from_step": omitted,
            "note": (
                "Use preview or Blender assets for the complete mesh-inclusive assembly."
                if omitted
                else ""
            ),
        },
    )
    return assembly


def export_render_assets(components, directory, *, exploded=False):
    """Write component STLs and a scene manifest for Blender presentation.

    Args:
        components (list): Installed Components, including explicit meshes.
        directory (str | Path): Destination directory.
        exploded (bool): Set the presentation flag in the scene manifest.

    Returns:
        (dict): Manifest also written as `scene.json`.

    STL coordinates stay installed. Explosion offsets are separate metadata
    applied by the renderer, avoiding a duplicated transform.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    items = []
    used_files = set()
    for index, c in enumerate(components):
        model = shape(c.model)
        filename = f"{c.name}.stl"
        if not c.name or any(ch in c.name for ch in '/\\:*?"<>|') or filename.casefold() in used_files:
            filename = f"component-{index:04d}.stl"
        while filename.casefold() in used_files:
            filename = "_" + filename
        used_files.add(filename.casefold())
        export_stl(model, directory / filename)
        items.append(
            {
                "name": c.name,
                "file": filename,
                "group": c.group,
                "part": c.part,
                "color": c.color,
                "material": c.material,
                "explosion_mm": c.explode,
                "geometry": "mesh" if isinstance(model, Mesh) else "brep",
            }
        )
    manifest = {
        "schema_version": 1,
        "units": "mm",
        "exploded": exploded,
        "components": items,
    }
    write_json(directory / "scene.json", manifest)
    return manifest


def run_checks(checks, directory):
    """Evaluate named intersection/contact checks and write results.

    Args:
        checks (tuple): Explicit Check definitions.
        directory (str | Path): Directory for `report.json` and failing witness STLs.

    Returns:
        (list[dict]): Individual outcomes, including intersection volume, optional
            native gap, and errors. Exceptions are failed checks.

    Empty input yields an empty report with a passing aggregate. This means
    no checks ran, not that assembly collisions were ruled out.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    for check in checks:
        witness = directory / f"{check.name}.stl"
        witness.unlink(missing_ok=True)
        try:
            model = shape(check.builder())
            if model is None:
                volume = 0.0
            elif isinstance(model, Mesh):
                volume = abs(float(model.manifold.volume()))
            else:
                volume = sum(abs(s.Volume()) for s in model.Solids())
            contact = volume > check.tolerance_mm3
            passed = contact == check.required_contact
            result = {
                "name": check.name,
                "passed": passed,
                "required_contact": check.required_contact,
                "intersection_mm3": volume,
            }
            if check.contact_pair is not None:
                first, second = (shape(v) for v in check.contact_pair())
                if isinstance(first, Mesh) or isinstance(second, Mesh):
                    raise ValueError("Exact contact distance requires native B-reps")
                gap = first.distance(second)
                result["gap_mm"] = gap
                result["max_gap_mm"] = check.max_gap_mm
                contact = contact or gap <= check.max_gap_mm
                passed = contact == check.required_contact
                result["passed"] = passed
            if not passed and volume > check.tolerance_mm3:
                export_stl(model, witness)
                result["witness"] = str(witness)
        except Exception as error:
            result = {"name": check.name, "passed": False, "error": str(error)}
        results.append(result)
        print(f'{"ok" if result["passed"] else "FAIL"}  {check.name}', flush=True)
    write_json(
        directory / "report.json",
        {
            "schema_version": 1,
            "checks": results,
            "passed": all(r["passed"] for r in results),
        },
    )
    return results
