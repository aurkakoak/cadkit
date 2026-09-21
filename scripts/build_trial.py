"""Build a self-contained local trial release, without consumer code or caches."""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib


def main():
    source = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="unique trial label, e.g. trial.1")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", args.label):
        parser.error("Use a lowercase alphanumeric trial label separated by dots or hyphens")
    output = args.output.resolve()
    if output.exists():
        parser.error("Output already exists; choose a new release directory")
    base = tomllib.loads((source / "pyproject.toml").read_text())["project"]["version"]
    version = f"{base}+{args.label.replace('-', '.')}"
    release_id = f"cadkit-{version}"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only after the wheel and all release files have been assembled.
    with tempfile.TemporaryDirectory(prefix="cadkit-release-", dir=output.parent) as temporary:
        staging = Path(temporary)
        root = staging / output.name
        root.mkdir()
        package = staging / "package"
        package.mkdir()
        for name in ("README.md", "PROVENANCE.md"):
            shutil.copy2(source / name, root / name)
            shutil.copy2(source / name, package / name)
        text = (source / "pyproject.toml").read_text()
        text = text.replace(f'version = "{base}"', f'version = "{version}"', 1)
        (package / "pyproject.toml").write_text(text)
        shutil.copytree(source / "src" / "cadkit", package / "src" / "cadkit",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (root / "python").mkdir()
        subprocess.run(["uv", "build", "--wheel", "--python", sys.executable,
                        "--out-dir", str(root / "python"), str(package)], check=True)
        wheel, = (root / "python").glob("*.whl")
        shutil.copytree(source / "examples", root / "examples",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(source / "tests", root / "tests",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(source / "desktop", root / "desktop", ignore=shutil.ignore_patterns(
            "node_modules", "dist", "bundle", "release", "test-results", "playwright-report", ".DS_Store"))
        shutil.copytree(source / "skill", root / "skills" / "cadkit")
        docs = root / "docs"
        docs.mkdir()
        for document in sorted((source / "docs").glob("*.md")):
            if not document.name.endswith(".local.md"):
                shutil.copy2(document, docs / document.name)
        if (source / "docs" / "assets").exists():
            shutil.copytree(source / "docs" / "assets", docs / "assets")
        shutil.copy2(source / "scripts" / "install_trial.py", root / "install.py")
        (root / "START-HERE.md").write_text(
            f"# {release_id}\n\n"
            "Start with [installation](docs/install.md). This bundle contains a Python wheel, "
            "a separate desktop runtime, a portable agent skill, an independent example and tests.\n\n"
            "Verify it with `python3 install.py verify`. Install the skill with "
            "`python3 install.py skill --project /path/to/consumer`. "
            "Neither command installs runtime dependencies.\n\n"
            "Use [migration](docs/migration.md), [API](docs/api.md), "
            "[workflows](docs/workflows.md), [desktop/MCP](desktop/README.md) and "
            "[contracts](docs/contracts.md) as needed. "
            "Release checksums identify content; no hosted registry is required.\n"
        )
        for doc in root.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", doc.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                if not (doc.parent / target.split("#")[0]).exists():
                    raise ValueError(f"Broken release documentation link: {doc.relative_to(root)} -> {target}")
        files = sorted(p for p in root.rglob("*") if p.is_file())
        manifest = {
            "schema_version": 1, "release_id": release_id, "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "wheel": str(wheel.relative_to(root)),
            "sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in files},
        }
        (root / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
        root.rename(output)
    print(f"Built {release_id}: {output}")


if __name__ == "__main__":
    main()
