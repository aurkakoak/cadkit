"""Slice the explicit artifact list of a CadKit build, with no filename globs."""

import argparse
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
