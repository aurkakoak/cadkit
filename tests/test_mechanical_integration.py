import json
from pathlib import Path
import cadquery as cq
import pytest
from cadkit import Assembly, Component, Interface, Joint, Part, Project
from cadkit.desktop import Session
from cadkit.export import build
from cadkit.cli import main
from cadkit.preflight import scoped_report
from cadkit.slice_build import main as slice_build


def fixture(gap=5):
    solid = cq.Workplane("XY").box(10, 10, 10).val()
    parts = (Part("block", lambda: solid, "blocks"), Part("coupon", lambda: solid, "calibration"))
    a = Component("left", solid, "blocks", part="block")
    b = Component("right", solid.translate((10 + gap, 0, 0)), "blocks")
    return Project("fixture", parts, lambda: [a,b],
        assembly=lambda: Assembly("fixture", (Assembly("blocks", (a,b)),)),
        joints=(Joint("mount", ("left", "right"), interfaces=("gap",)),),
        interfaces=(Interface("gap", ("left", "right"), kind="clearance", min_clearance_mm=4),))


def test_cli_exposes_resolved_entities_and_failed_review(tmp_path, capsys):
    project = fixture(-1)
    assert main(["mechanics"], project=project) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["interfaces"][0]["component_ids"] == ["/fixture/blocks/left", "/fixture/blocks/right"]
    target = tmp_path / "report.json"
    assert main(["validate-assembly", "--output", str(target)], project=project) == 1
    assert json.loads(target.read_text())["status"] == "fail"


def test_failed_preflight_prevents_new_artifact_and_removes_stale_manifest(tmp_path):
    project = fixture(-1)
    (tmp_path / "manifest.json").write_text('{"old": true}')
    with pytest.raises(ValueError, match="Assembly validation failed"):
        build(project, [project.parts[0]], tmp_path)
    assert not (tmp_path / "block.stl").exists()
    assert not (tmp_path / "manifest.json").exists()
    assert json.loads((tmp_path / "assembly-validation.json").read_text())["status"] == "fail"


def test_override_is_explicit_and_persisted_with_export(tmp_path):
    project = fixture(-1)
    with pytest.raises(ValueError, match="reason"):
        build(project, [project.parts[0]], tmp_path, validation_override=" ")
    manifest = build(project, [project.parts[0]], tmp_path, validation_override="Fit coupon only; reviewed collision")
    review = manifest["assembly_validation"]
    assert review["status"] == "fail"
    assert review["override"]["reason"] == "Fit coupon only; reviewed collision"
    assert (tmp_path / "block.stl").exists()
    assert json.loads((tmp_path / "assembly-validation.json").read_text()) == review


def test_slicer_rejects_modified_validated_stl_before_starting(tmp_path, monkeypatch):
    project = fixture()
    manifest = build(project, [project.parts[0]], tmp_path)
    (tmp_path / "block.stl").write_bytes(b"modified")
    def unexpected(*args, **kwargs):
        raise AssertionError("slicer must not start")
    monkeypatch.setattr("cadkit.slice_build.slice_main", unexpected)
    with pytest.raises(ValueError, match="changed since export"):
        slice_build(["--manifest", str(tmp_path / "manifest.json")])


def test_part_scope_retains_unknown_uninstalled_members():
    project = fixture()
    assembly = project.get_assembly()
    report = scoped_report(project.validate_mechanics(assembly), assembly, project.parts, fastenings=project.fastenings)
    missing = next(f for f in report["findings"] if f["code"] == "uninstalled_parts")
    assert missing["evidence"]["parts"] == ["coupon"]
    assert report["status"] == "incomplete"
    assert report["summary"]["unverified"] == sum(f["status"] == "unverified" for f in report["findings"])


def test_session_resolves_mechanics_and_scopes_report_to_revision():
    session = Session(fixture())
    scene = session.scene()
    assert scene["mechanics"]["joints"][0]["id"] == "mount"
    with pytest.raises(ValueError, match="older build"):
        session.mechanical_report("stale")
    full = session.mechanical_report(session.revision)
    scoped = session.mechanical_report(session.revision, parts=["block"])
    assert full["revision"] == scoped["revision"] == session.revision
    assert full is session.mechanical_report(session.revision)
    assert "scope" not in full
    assert scoped["scope"]["parts"] == ["block"]
    assert scoped["status"] == "incomplete"  # Unknown sequence must not become green.


def colliding_hardware_fixture():
    from cadkit import Fastening, FastenerSite, HardwareItem, FastenerSpec
    body = cq.Solid.makeBox(5, 5, 5).translate((50, 0, 0))
    other = body.translate((20, 0, 0))
    coupon = body.translate((40, 0, 0))
    return Project("duplicate-sites",
        (Part("block", lambda: body, "blocks"), Part("coupon", lambda: coupon, "coupons")),
        lambda: [Component("left", body, "blocks", part="block"),
                 Component("right", other, "blocks"),
                 Component("coupon", coupon, "coupons", part="coupon")],
        fastenings=(Fastening("mount", ("left", "right"),
            sites=(FastenerSite("one", (0, 0, 0)), FastenerSite("two", (0, 0, 0))),
            hardware=(HardwareItem("screw", FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=12)),
                      HardwareItem("nut", FastenerSpec("hex_nut", "M3-0.5"), 8)),
            grip_mm=8, thread_depth_mm=2.4, min_engagement_mm=2.4,
        ),))


def test_print_scope_retains_related_hardware_collisions_and_excludes_unrelated_parts(tmp_path, capsys):
    project = colliding_hardware_fixture()
    session = Session(project)
    full = session.mechanical_report(session.revision)
    failures = [f for f in full["findings"] if f["status"] == "fail"]
    assert failures and all(f["code"].startswith("collision-") for f in failures)
    block = session.mechanical_report(session.revision, parts=["block"])
    assert block["status"] == "fail"
    assert block["scope"]["fastening_ids"] == ["mount"]
    assert len(block["scope"]["hardware_ids"]) == 4
    assert {f["id"] for f in failures} <= {f["id"] for f in block["findings"]}
    coupon = session.mechanical_report(session.revision, parts=["coupon"])
    assert coupon["summary"]["fail"] == 0
    assert coupon["scope"]["hardware_ids"] == []
    assert "scope" not in full
    with pytest.raises(ValueError, match="Assembly validation failed"):
        build(project, project.select(["block"]), tmp_path / "build")
    assert not (tmp_path / "build" / "block.stl").exists()
    with pytest.raises(ValueError, match="Assembly validation failed"):
        session.export_part("block", tmp_path / "desktop")
    report = tmp_path / "cli.json"
    assert main(["validate-assembly", "--parts", "block", "--output", str(report)], project=project) == 1
    assert json.loads(report.read_text())["summary"]["fail"] == len(failures)
