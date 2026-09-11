"""Verify a local CadKit release and install its skill, Python wheel or desktop."""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def verify(root: Path):
    manifest = json.loads((root / "release.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported release manifest")
    for relative, expected in manifest["sha256"].items():
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError(f"Missing or invalid release file: {relative}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Release checksum mismatch: {relative}")
    return manifest


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    skill = commands.add_parser("skill", help="copy the skill into a consumer repository")
    skill.add_argument("--project", required=True, type=Path)
    python = commands.add_parser("python", help="install the wheel into the supplied Python")
    python.add_argument("--python", required=True, type=Path)
    python.add_argument("--desktop", action="store_true")
    desktop = commands.add_parser("desktop", help="copy a writable desktop runtime")
    desktop.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    manifest = verify(root)
    receipt = {
        "release_id": manifest["release_id"],
        "version": manifest["version"],
        "path": str(root),
        "manifest_sha256": hashlib.sha256((root / "release.json").read_bytes()).hexdigest(),
    }
    if args.command == "verify":
        print(json.dumps(receipt, indent=2))
    elif args.command == "skill":
        project = args.project.resolve()
        if not project.is_dir():
            raise ValueError(f"Consumer project does not exist: {project}")
        destination = project / ".agents" / "skills" / "cadkit"
        if destination.exists():
            raise FileExistsError(f"Skill already exists; left unchanged: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root / "skills" / "cadkit", destination)
        (destination / "release.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"Installed {manifest['release_id']} skill: {destination}")
    elif args.command == "python":
        # Preserve the venv entry point; resolving its symlink loses venv discovery.
        python = str(args.python.absolute())
        wheel = root / manifest["wheel"]
        requirement = str(wheel) + ("[desktop]" if args.desktop else "")
        subprocess.run([python, "-m", "pip", "install", requirement], check=True)
    else:
        destination = args.destination.absolute()
        if destination.exists():
            raise FileExistsError(f"Desktop destination exists; left unchanged: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root / "desktop", destination)
        (destination / "cadkit-release.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"Copied desktop: {destination}; next run npm ci and npm run setup there")


if __name__ == "__main__":
    main()
