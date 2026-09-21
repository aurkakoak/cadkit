"""Run the published tutorial snapshots against native CAD geometry and exports."""
from pathlib import Path
import runpy

import cadquery as cq
import pytest

from cadkit.export import build
from cadkit.mechanics import hardware_bom


EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "tutorial"


def snapshot(filename, *, replacements=()):
    path = EXAMPLES / filename
    if not replacements:
        return runpy.run_path(str(path))
    source = path.read_text()
    for before, after in replacements:
        assert before in source
        source = source.replace(before, after)
    namespace = {"__name__": "tutorial_snapshot", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


def test_first_chapter_runs_and_exports_the_promised_hollow_box(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = runpy.run_path(str(EXAMPLES / "01_box.py"), run_name="__main__")
    box = cq.importers.importStep(str(tmp_path / "build/first-box/box.step")).val()
    lid = cq.importers.importStep(str(tmp_path / "build/first-box/lid.step")).val()
    assert box.isValid() and lid.isValid()
    assert len(box.Solids()) == len(lid.Solids()) == 1
    assert box.Volume() == pytest.approx(20176.896)
    assert lid.Volume() == pytest.approx(12000)
    assert box.BoundingBox().zmin == pytest.approx(-data["HEIGHT"])
    assert box.BoundingBox().zmax == pytest.approx(0)
    cavity_probe = cq.Solid.makeBox(10, 10, 10, (-5, -5, -12))
    floor_probe = cq.Solid.makeBox(10, 10, 1, (-5, -5, -19))
    assert box.intersect(cavity_probe).Volume() == pytest.approx(0)
    assert box.intersect(floor_probe).Volume() == pytest.approx(floor_probe.Volume())


@pytest.mark.parametrize("filename", [
    "02_project.py", "03_export.py", "04_fasteners.py", "05_checks.py", "06_agent.py",
])
def test_each_project_snapshot_builds_valid_parts_and_exports(tmp_path, filename):
    data = snapshot(filename)
    project = data["PROJECT"]
    assert {part.name: part.quantity for part in project.parts} == {"box": 1, "lid": 1}
    box, lid = data["BOX"].build(), data["LID"].build()
    for shape in (box, lid):
        assert shape.isValid() and len(shape.Solids()) == 1
        bounds = shape.BoundingBox()
        assert (bounds.xlen, bounds.ylen) == pytest.approx((80, 50))
    assert (box.BoundingBox().zmin, box.BoundingBox().zmax) == pytest.approx((-20, 0))
    assert (lid.BoundingBox().zmin, lid.BoundingBox().zmax) == pytest.approx((0, 3))
    assert box.intersect(lid).Volume() == pytest.approx(0)
    assert box.distance(lid) == pytest.approx(0)

    # The walkthrough promises no confirmed failures, not a certified physical fit.
    report = project.validate_mechanics()
    assert report["status"] == "incomplete"
    assert report["summary"]["fail"] == 0
    manifest = build(project, project.parts, tmp_path, mechanical_report=report)
    assert {part["name"] for part in manifest["parts"]} == {"box", "lid"}
    for name, expected in (("box", box), ("lid", lid)):
        assert (tmp_path / f"{name}.stl").stat().st_size > 0
        exported = cq.importers.importStep(str(tmp_path / f"{name}.step")).val()
        assert exported.isValid()
        assert exported.Volume() == pytest.approx(expected.Volume())
        assert exported.BoundingBox().zmin == pytest.approx(0, abs=1e-6)

    if "MOUNT" in data:
        bom = hardware_bom(project.fastenings)
        assert {row["spec"]["kind"]: row["quantity"] for row in bom} == {
            "socket_head_cap_screw": 4, "heat_set_insert": 4,
        }
        assert len(project.fastenings[0].sites) == 4
        assert project.fastenings[0].grip_mm == 3
        # Holes reach both parts, while the bottom of each blind pad remains solid.
        for x, y in data["MOUNT_POINTS"]:
            assert lid.intersect(cq.Solid.makeCylinder(1, 1, (x, y, 1))).Volume() == pytest.approx(0)
            assert box.intersect(cq.Solid.makeCylinder(1, 1, (x, y, -6))).Volume() == pytest.approx(0)
            floor = cq.Solid.makeCylinder(1, 0.5, (x, y, -7.5))
            assert box.intersect(floor).Volume() == pytest.approx(floor.Volume())

    if filename in {"05_checks.py", "06_agent.py"}:
        assert any(f["entity"] == "lid-on-rim" and f["status"] == "pass" for f in report["findings"])
        assert any(f["code"] == "access-lid-driver" and f["status"] == "pass" for f in report["findings"])
        assert any(f["code"] == "engagement" and f["status"] == "pass" for f in report["findings"])


def test_short_screw_exercise_fails_engagement_and_blocks_exports(tmp_path):
    data = snapshot("05_checks.py", replacements=(("SCREW_LENGTH = 8", "SCREW_LENGTH = 4"),))
    project = data["PROJECT"]
    report = project.validate_mechanics()
    assert report["status"] == "fail"
    assert any(f["code"] == "engagement" and f["status"] == "fail" for f in report["findings"])
    with pytest.raises(ValueError, match="(?i)(fail|validation)"):
        build(project, project.parts, tmp_path, mechanical_report=report)
    assert (tmp_path / "assembly-validation.json").exists()
    assert not (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "box.stl").exists()


def test_agent_height_change_preserves_rim_lid_hardware_and_checks():
    original = snapshot("06_agent.py")
    taller = snapshot("06_agent.py", replacements=(("HEIGHT = 20", "HEIGHT = 24"),))
    assert taller["BOX"].build().BoundingBox().zmin == pytest.approx(-24)
    assert taller["BOX"].build().BoundingBox().zmax == pytest.approx(0)
    assert taller["LID"].build().Volume() == pytest.approx(original["LID"].build().Volume())
    assert taller["MOUNT"].describe() == original["MOUNT"].describe()
    assert hardware_bom(taller["PROJECT"].fastenings) == hardware_bom(original["PROJECT"].fastenings)
    report = taller["PROJECT"].validate_mechanics()
    assert report["status"] == "incomplete"
    assert report["summary"]["fail"] == 0
