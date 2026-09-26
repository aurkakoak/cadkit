"""Install built distributions in fresh uv projects and exercise the public API."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]
PROJECT = '''import cadquery as cq
import cadkit as ck

plate = ck.Part("plate", body=lambda: cq.Workplane("XY").rect(20, 10).extrude(3),
                manufacture=ck.FDM("PLA"))
assembly = ck.Assembly("installation-check")
assembly.fix(assembly.add("plate", plate))
PROJECT = assembly.as_project()
'''
SMOKE = '''import importlib.metadata as metadata
import importlib.resources as resources
import importlib.util
from pathlib import Path
import sys

import cadkit as ck

assert Path(ck.__file__).is_relative_to(Path(sys.prefix)), ck.__file__
assert metadata.version("cadkit-py") == ck.__version__
assert importlib.util.find_spec("cq_warehouse") is None
assert all("@" not in requirement for requirement in metadata.requires("cadkit-py"))
vendor = resources.files("cadkit._vendor.cq_warehouse")
assert "Apache License" in vendor.joinpath("LICENSE").read_text()
assert ck.fasteners.PROVIDER_REVISION in vendor.joinpath("README.md").read_text()
hardware = [
    ck.FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=10),
    ck.FastenerSpec("set_screw", "M3-0.5", length_mm=6),
    ck.FastenerSpec("hex_head_screw", "M3-0.5", length_mm=10),
    ck.FastenerSpec("button_head_screw", "M3-0.5", length_mm=10),
    ck.FastenerSpec("hex_nut", "M3-0.5"),
    ck.FastenerSpec("plain_washer", "M3"),
    ck.FastenerSpec("heat_set_insert", "M3-0.5-Standard", length_mm=5.7),
]
for spec in hardware:
    shape = spec.build()
    assert shape.isValid() and shape.Volume() > 0, spec.kind
print(f"CadKit {ck.__version__}: imports and {len(hardware)} catalogue types passed")
'''


def check(artifact: Path, python: str) -> None:
    environment = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT",
                "UV_PROJECT", "UV_WORKING_DIR"):
        environment.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="cadkit-install-") as directory:
        consumer = Path(directory)

        def run(*arguments: str) -> None:
            subprocess.run(["uv", *arguments], cwd=consumer, env=environment, check=True)

        print(f"Checking {artifact.name} with Python {python}", flush=True)
        run("init", "--bare", "--no-workspace", "--vcs", "none", "--python", python)
        run("python", "pin", python)
        run("add", str(artifact))
        run("run", "--locked", "python", "-I", "-c", SMOKE)
        run("run", "--locked", "cadkit", "--help")
        (consumer / "project.py").write_text(PROJECT)
        run("run", "--locked", "cadkit", "--project", "project:PROJECT", "build", "all")
        assert any(consumer.rglob("*.stl")), "CLI did not export an STL"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="*", type=Path)
    parser.add_argument("--python", default="3.12")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    artifacts = args.artifacts or [ROOT / "dist" / f"cadkit_py-{version}-py3-none-any.whl",
                                  ROOT / "dist" / f"cadkit_py-{version}.tar.gz"]
    for artifact in artifacts:
        artifact = artifact.resolve(strict=True)
        check(artifact, args.python)


if __name__ == "__main__":
    main()
