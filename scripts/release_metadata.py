"""Validate versions and write a complete release asset checksum manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def version() -> str:
    python = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    desktop = json.loads((ROOT / "desktop/package.json").read_text())["version"]
    if python != desktop:
        raise ValueError(f"Version mismatch: Python {python}, desktop {desktop}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", python):
        raise ValueError("Release versions must use MAJOR.MINOR.PATCH")
    return python


def prepare_assets(directory: Path, release_version: str) -> None:
    expected = [f"CadKit-{release_version}-macos-{arch}.{extension}"
                for arch in ("arm64", "x64") for extension in ("dmg", "zip")]
    expected += [f"CadKit-{release_version}-linux-{arch}.tar.gz" for arch in ("arm64", "x64")]
    expected += [f"cadkit-{release_version}-py3-none-any.whl",
                 f"cadkit-{release_version}.tar.gz", f"cadkit-skill-{release_version}.zip"]
    missing = [name for name in expected if not (directory / name).is_file()]
    if missing:
        raise ValueError(f"Release incomplete; missing assets: {', '.join(missing)}")
    lines = []
    for name in sorted(expected):
        with (directory / name).open('rb') as asset:
            lines.append(f"{hashlib.file_digest(asset, 'sha256').hexdigest()}  {name}\n")
    (directory / "SHA256SUMS").write_text("".join(lines))


def skill_archive(directory: Path, release_version: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(directory / f"cadkit-skill-{release_version}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for source in sorted((ROOT / "skill").rglob("*")):
            if source.is_file():
                archive.write(source, Path("cadkit") / source.relative_to(ROOT / "skill"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--checksums", type=Path)
    parser.add_argument("--skill", type=Path)
    args = parser.parse_args()
    current = version()
    if args.tag and args.tag != f"v{current}":
        parser.error(f"Tag must be v{current}, got {args.tag}")
    if args.skill:
        skill_archive(args.skill, current)
    if args.checksums:
        prepare_assets(args.checksums, current)
    print(current)


if __name__ == "__main__":
    main()
