"""Slice the explicit artifact list of a CadKit build, with no filename globs."""

import argparse
import hashlib
import json
from pathlib import Path
from .slicing import main as slice_main


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--manifest", type=Path, default=Path("build/cadquery/manifest.json")
    )
    args, remaining = parser.parse_known_args(argv)
    data = json.loads(args.manifest.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported build manifest")
    folder = args.manifest.resolve().parent
    review = data.get("assembly_validation")
    if review and review.get("status") == "fail" and not review.get("override", {}).get("reason"):
        raise ValueError("This build has unresolved assembly failures; review and rebuild with an explicit override before slicing")
    # A saved review belongs to the actual exported files, not a mutable filename.
    for part in data["parts"]:
        expected = part.get("sha256", {}).get("stl")
        if expected:
            actual = hashlib.sha256((folder / part["files"]["stl"]).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"{part['name']}: STL changed since export; rebuild before slicing")
    stls = [str(folder / p["files"]["stl"]) for p in data["parts"]]
    defaults = []
    for flag, name in [
        ("--quantity-file", "quantities.json"),
        ("--group-file", "subassemblies.json"),
    ]:
        if not any(a == flag or a.startswith(flag + "=") for a in remaining):
            defaults.extend([flag, str(folder / name)])
    return slice_main([*remaining, *defaults, *stls])


if __name__ == "__main__":
    raise SystemExit(main())
