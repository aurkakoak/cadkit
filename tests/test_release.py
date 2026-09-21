"""Release invariants and installer behavior without network or a real install."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_metadata", ROOT / "scripts/release_metadata.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_incomplete_release_is_never_checksummed(tmp_path):
    (tmp_path / "CadKit-0.2.0-windows-x64.exe").write_bytes(b"installer")
    with pytest.raises(ValueError, match="Release incomplete"):
        release.prepare_assets(tmp_path, "0.2.0")
    assert not (tmp_path / "SHA256SUMS").exists()


def test_all_installer_checksums_cover_actual_content(tmp_path):
    names = [f"CadKit-0.2.0-macos-{arch}.{extension}"
             for arch in ("arm64", "x64") for extension in ("dmg", "zip")]
    names += ["CadKit-0.2.0-windows-x64.exe", "cadkit-0.2.0-py3-none-any.whl",
              "cadkit-0.2.0.tar.gz", "cadkit-skill-0.2.0.zip"]
    for name in names:
        (tmp_path / name).write_bytes(name.encode())
    release.prepare_assets(tmp_path, "0.2.0")
    lines = (tmp_path / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == len(names)
    for line in lines:
        digest, name = line.split("  ")
        assert digest == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()


def test_release_tag_must_match_packages():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/release_metadata.py"),
                             "--tag", "v999.0.0"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Tag must be" in result.stderr


@pytest.fixture
def mac_installer(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX installer; Windows uses install.ps1")
    tools = tmp_path / "bin"
    tools.mkdir()
    archive = tmp_path / "archive"
    archive.write_bytes(b"downloaded-release-fixture")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksums = tmp_path / "checksums"
    checksums.write_text(f"{digest}  CadKit-0.2.0-macos-arm64.zip\n")
    fake = {
        "shasum": f"#!{sys.executable}\nimport hashlib, pathlib, sys\np = pathlib.Path(sys.argv[-1]); print(hashlib.sha256(p.read_bytes()).hexdigest(), ' ', p)\n",
        "uname": '#!/bin/sh\nif [ "$1" = -s ]; then echo "${TEST_OS:-Darwin}"; else echo arm64; fi\n',
        "curl": '''#!/bin/sh
output=
url=
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) output=$2; shift ;;
    https://*) url=$1 ;;
  esac
  shift
done
case "$url" in
  */releases/latest) printf '{\\n  "tag_name": "v0.2.0"\\n}\\n' ;;
  */SHA256SUMS) cp "$TEST_CHECKSUMS" "$output" ;;
  *.zip) cp "$TEST_ARCHIVE" "$output" ;;
  *) exit 22 ;;
esac
''',
        "ditto": '''#!/bin/sh
if [ "$1" = -x ]; then
  mkdir -p "$4/CadKit.app/Contents/MacOS"
  printf '#!/bin/sh\\nexit 0\\n' > "$4/CadKit.app/Contents/MacOS/CadKit"
  chmod +x "$4/CadKit.app/Contents/MacOS/CadKit"
else
  cp -R "$1" "$2"
fi
''',
    }
    for name, contents in fake.items():
        target = tools / name
        target.write_text(contents)
        target.chmod(0o755)
    env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"],
           "CADKIT_INSTALL_DIR": str(tmp_path / "Applications with spaces"),
           "TEST_ARCHIVE": str(archive), "TEST_CHECKSUMS": str(checksums)}
    env.pop("CADKIT_VERSION", None)
    env.pop("CADKIT_REPOSITORY", None)
    return env, checksums


def run_installer(env):
    # stdin invocation exercises the published curl | sh installation mode.
    return subprocess.run(["sh"], input=(ROOT / "scripts/install.sh").read_text(),
                          env=env, capture_output=True, text=True)


def test_mac_installer_downloads_checks_and_replaces(mac_installer):
    env, _ = mac_installer
    destination = Path(env["CADKIT_INSTALL_DIR"]) / "CadKit.app"
    destination.mkdir(parents=True)
    (destination / "old-build").write_text("old")
    result = run_installer(env)
    assert result.returncode == 0, result.stderr
    assert (destination / "Contents/MacOS/CadKit").is_file()
    assert not (destination / "old-build").exists()
    assert not list(destination.parent.glob(".cadkit-install.*"))


def test_bad_checksum_preserves_existing_app(mac_installer):
    env, checksums = mac_installer
    checksums.write_text("0" * 64 + "  CadKit-0.2.0-macos-arm64.zip\n")
    destination = Path(env["CADKIT_INSTALL_DIR"]) / "CadKit.app"
    destination.mkdir(parents=True)
    old = destination / "old-build"
    old.write_text("keep me")
    result = run_installer(env)
    assert result.returncode != 0
    assert "Checksum verification failed" in result.stderr
    assert old.read_text() == "keep me"


def test_unsupported_os_is_explicit(mac_installer):
    env, _ = mac_installer
    result = run_installer({**env, "TEST_OS": "Linux"})
    assert result.returncode != 0
    assert "Linux binaries are not yet available" in result.stderr
    assert not Path(env["CADKIT_INSTALL_DIR"]).exists()


def test_untrusted_version_is_rejected(mac_installer):
    env, _ = mac_installer
    result = run_installer({**env, "CADKIT_VERSION": "../../invalid"})
    assert result.returncode != 0
    assert "Invalid release version" in result.stderr
