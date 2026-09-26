"""Human and agent CLI over the same explicit Project contract."""

from __future__ import annotations
import argparse
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from ._project import Project
from .export import (
    build,
    inspect_model,
    run_checks,
    export_assembly,
    export_render_assets,
    write_json,
)


def load_project(reference, variants=None):
    """Import a Project from a Python module reference.

    Args:
        reference (str): `module:attribute`, with `PROJECT` as the default attribute.

    Returns:
        (Project): Imported project, created with `Assembly.as_project()`.

    Raises:
        ValueError: The referenced value is not a Project instance.

    Importing executes normal module-level Python code; project construction
    should keep geometry in lazy builders.
    """
    module, sep, attribute = reference.partition(":")
    project = getattr(importlib.import_module(module), attribute or "PROJECT")
    if not isinstance(project, Project):
        raise ValueError(f"{reference} is not a cadkit.Project")
    from .variants import select_variants
    return select_variants(project, variants or {})


def main(argv=None, *, project=None):
    """Run the CadKit CLI over an imported or explicitly supplied Project.

    Args:
        argv (list[str] | None): Arguments excluding the program name, or process argv.
        project (Project | None): Inject a Project instead of importing `--project`.

    Returns:
        (int): Zero on success or one for failed explicit validation checks.

    Argument and supported operational errors exit through argparse with code 2.
    See the CLI reference for command-specific options and output files.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", default="project:PROJECT", help="importable module:Project object"
    )
    parser.add_argument("--variant", action="append", default=[], metavar="NAME=OPTION")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "describe", help="JSON project schema, parts, dimensions, and checks"
    )
    sub.add_parser("doctor", help="report installed tools without starting a GUI")
    sub.add_parser("mechanics", help="resolved joints, interfaces, fastenings and hardware BOM")
    sub.add_parser("bom", help="hardware bill of materials from located fastenings")
    mechanical = sub.add_parser("validate-assembly", help="scan installed collisions and validate declared mechanical relationships")
    mechanical.add_argument("--parts", nargs="+", help="review a print set in complete assembly context")
    mechanical.add_argument("--no-collision-scan", action="store_true", help="only declared checks; automatic collision coverage remains unverified")
    mechanical.add_argument("--output", type=Path, default=Path("build/assembly-validation.json"))
    listing = sub.add_parser("list", help="list parts and manufacturing metadata")
    listing.add_argument("--json", action="store_true")
    inspect = sub.add_parser(
        "inspect", help="build one part and return measured geometry as JSON"
    )
    inspect.add_argument("part")
    building = sub.add_parser(
        "build", help="validate and export named parts to STL and native STEP"
    )
    building.add_argument("parts", nargs="*", default=["all"])
    building.add_argument("--group")
    building.add_argument("--validation-override", help="reason for exporting despite confirmed assembly failures; retained in manifest")
    building.add_argument("--output-dir", type=Path, default=Path("build/cadquery"))
    checking = sub.add_parser(
        "check", help="run named interference and required-contact checks"
    )
    checking.add_argument("names", nargs="*")
    checking.add_argument(
        "--output-dir", type=Path, default=Path("build/checks/clearance-failures")
    )
    assembly = sub.add_parser(
        "assembly", help="export installed STEP assembly and mesh omission manifest"
    )
    assembly.add_argument(
        "--output", type=Path, default=Path("build/assembly/full-machine.step")
    )
    for cmd, helptext in [
        ("preview", "open the CQ viewer"),
        ("render-assets", "export component meshes and Blender scene metadata"),
    ]:
        p = sub.add_parser(cmd, help=helptext)
        if cmd == "render-assets":
            p.add_argument("--output-dir", type=Path, default=Path("render/exports"))
        else:
            p.add_argument("--screenshot", type=Path)
            p.add_argument("--no-interact", action="store_true")
    for p in (assembly, sub.choices["preview"], sub.choices["render-assets"]):
        p.add_argument("--view", help="named assembly view from the project schema")
        p.add_argument("--exploded", action="store_true")
        p.add_argument("--printed-only", action="store_true")
    blender = sub.add_parser(
        "blender", help="build a scene or image with the shared Blender runner"
    )
    blender.add_argument(
        "--assets", type=Path, default=Path("render/exports/scene.json")
    )
    blender.add_argument("--output", type=Path, default=Path("render/project.blend"))
    blender.add_argument("--render", type=Path)
    blender.add_argument("--animation", action="store_true")
    blender.add_argument("--blender", default="blender")
    blender.add_argument("--samples", type=int, default=64)
    blender.add_argument("--width", type=int, default=1200)
    blender.add_argument("--height", type=int, default=1200)
    blender.add_argument("--camera", choices=("Overview", "Front", "Rear"), default="Overview")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            import cadquery as cq

            print(
                json.dumps(
                    {
                        "python": sys.version.split()[0],
                        "cadquery": cq.__version__,
                        "tools": {
                            name: shutil.which(name)
                            for name in (
                                "blender",
                                "CQ-editor",
                                "BambuStudio",
                                "orca-slicer",
                                "prusa-slicer",
                            )
                        },
                        "bambu_flatpak": (
                            str(
                                Path.home()
                                / ".local/share/flatpak/exports/bin/com.bambulab.BambuStudio"
                            )
                            if (
                                Path.home()
                                / ".local/share/flatpak/exports/bin/com.bambulab.BambuStudio"
                            ).exists()
                            else None
                        ),
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "blender":
            script = Path(__file__).with_name("blender_scene.py")
            command = [
                args.blender,
                "--background",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python",
                str(script),
                "--",
                "--manifest",
                str(args.assets.resolve()),
                "--output",
                str(args.output.resolve()),
                "--samples",
                str(args.samples),
                "--width", str(args.width),
                "--height", str(args.height),
                "--camera", args.camera,
            ]
            if args.render:
                command += ["--render", str(args.render.resolve())]
            if args.animation:
                command += ["--animation"]
            subprocess.run(command, check=True)
            return 0
        from .variants import parse_variants, select_variants
        selection = parse_variants(args.variant)
        if project is None:
            # Console scripts start with the environment's bin directory on
            # sys.path. Models (including lazy imports) live in the caller's cwd.
            project_root = str(Path.cwd())
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            project = load_project(args.project, selection)
        else:
            project = select_variants(project, selection)
        if args.command in {"mechanics", "bom"}:
            descriptions = project.mechanical_descriptions(assembly=project.get_assembly())
            print(json.dumps(descriptions["hardware_bom"] if args.command == "bom" else descriptions, indent=2))
            return 0
        if args.command == "validate-assembly":
            from .preflight import scoped_report
            assembly = project.get_assembly()
            report = project.validate_mechanics(assembly=assembly, scan_collisions=not args.no_collision_scan)
            if args.parts:
                report = scoped_report(report, assembly, project.select(args.parts), fastenings=project.fastenings)
            write_json(args.output, report)
            print(json.dumps(report, indent=2))
            return 1 if report["status"] == "fail" else 0
        if args.command == "describe":
            print(json.dumps(project.describe(), indent=2))
            return 0
        if args.command == "list":
            if args.json:
                print(json.dumps([p.describe() for p in project.parts], indent=2))
            else:
                for p in project.parts:
                    print(
                        f"{p.name:48} {p.group:12} {p.material:5} qty={p.quantity}"
                        + (" [optional]" if not p.production else "")
                    )
        elif args.command == "inspect":
            p = project.select([args.part])[0]
            print(json.dumps({**p.describe(), **inspect_model(p.build())}, indent=2))
        elif args.command == "build":
            selected = project.select(args.parts or ["all"], args.group)
            build(project, selected, args.output_dir, validation_override=args.validation_override)
        elif args.command == "check":
            known = {c.name: c for c in project.checks}
            unknown = set(args.names) - known.keys()
            if unknown:
                raise ValueError(f"Unknown checks: {', '.join(sorted(unknown))}")
            selected = [known[n] for n in args.names] if args.names else project.checks
            return (
                0
                if all((r["passed"] for r in run_checks(selected, args.output_dir)))
                else 1
            )
        elif args.command in ("assembly", "render-assets", "preview"):
            items = project.get_components(
                args.view, include_hardware=not args.printed_only
            )
            if args.printed_only:
                items = [component for component in items if component.part is not None]
            if args.command == "assembly":
                export_assembly(items, args.output, exploded=args.exploded, variant_selection=getattr(project, "variant_selection", {}))
            elif args.command == "render-assets":
                export_render_assets(items, args.output_dir, exploded=args.exploded, variant_selection=getattr(project, "variant_selection", {}))
            else:
                from .viewer import show_components

                if args.screenshot:
                    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                show_components(
                    items,
                    exploded=args.exploded,
                    screenshot=str(args.screenshot) if args.screenshot else None,
                    interact=not args.no_interact,
                )
        return 0
    except (
        ValueError,
        KeyError,
        FileNotFoundError,
        ImportError,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
