"""Geometry and consumer-adapter checks for the authoring model."""
from dataclasses import replace
import json
import math
import cadquery as cq
import pytest
from cadkit._project import Part as FabricationPart
from cadkit import FastenerSpec
from cadkit import design as d
from cadkit.export import build
from cadkit.mechanics import hardware_bom


def insert_model(spec):
    model = cq.Workplane("XY").circle(2.3).circle(1.5).extrude(spec.length_mm).val()
    model.thread_diameter, model.thread_pitch = 3, .5
    return model


def mount():
    return d.InsertMount(
        d.PolarPattern(8, (0, 180)),
        FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=6),
        FastenerSpec("heat_set_insert", "M3-0.5", length_mm=5.7,
                     factory=insert_model, representation="envelope"),
        3.4, d.InsertPocket(4, 6.7), 3,
    )


def definitions(spec=None, thickness=2.4, recess=1.2):
    spec = spec or mount()
    plate = d.Part("plate", lambda: cq.Workplane("XY").rect(30, 20).extrude(thickness),
                   d.FDM("unspecified"),
                   {"mount": spec.clearance_side(thickness=thickness, head_recess=d.Counterbore(6.2, recess))})
    base = d.Part("base", lambda: cq.Workplane("XY").rect(30, 20).extrude(-8),
                  d.FDM("unspecified"), {"mount": spec.insert_side()})
    return spec, plate, base


def assembly(spec, plate, base, at=d.Frame()):
    result = d.Assembly("fixture")
    fixed = result.add("base", base)
    moving = result.add("plate", plate)
    result.fix(fixed, at=at)
    result.connect("mount", spec, through=moving.feature("mount"), into=fixed.feature("mount"))
    return result


def test_features_make_measured_geometry_and_explicit_process_steps():
    spec, plate, base = definitions()
    assert plate.build().Volume() == pytest.approx(30*20*2.4 - 2*math.pi*(1.7**2*1.2+3.1**2*1.2))
    assert base.build().Volume() == pytest.approx(30*20*8 - 2*math.pi*2**2*6.7)
    # The blind floor remains at its authored depth, even with cutter overshoot.
    floor = cq.Solid.makeCylinder(1.9, .5, (8, 0, -7.3))
    assert base.build().intersect(floor).Volume() == pytest.approx(floor.Volume())
    report = base.describe()["features"]["mount"]
    assert report["operations"][0]["kind"] == "install-insert"
    assert report["operations"][0]["quantity"] == 2
    json.dumps(report)


def test_build_is_lazy_and_does_not_modify_authored_body_or_features():
    calls = []
    body = cq.Workplane("XY").rect(30, 20).extrude(2.4).val()
    features = {"mount": mount().clearance_side(thickness=2.4)}
    plate = d.Part("plate", lambda: calls.append(1) or body, d.FDM("unspecified"), features)
    features.clear()
    plate.describe()
    plate.as_part("parts").describe()
    assert calls == []
    assert plate.build().Volume() < body.Volume()
    assert body.Volume() == pytest.approx(1440)
    assert calls == [1]
    with pytest.raises(TypeError):
        plate.features["other"] = plate.features["mount"]


def test_one_pattern_change_updates_both_parts_and_hardware():
    original, plate, base = definitions()
    changed = replace(original, pattern=d.PolarPattern(5, (0, 180)))
    _, new_plate, new_base = definitions(changed)
    for before, after, z in ((plate, new_plate, .3), (base, new_base, -3)):
        old_site = cq.Solid.makeCylinder(.2, .2, (8, 0, z))
        new_site = cq.Solid.makeCylinder(.2, .2, (5, 0, z))
        assert before.build().intersect(old_site).Volume() == pytest.approx(0)
        assert after.build().intersect(old_site).Volume() == pytest.approx(old_site.Volume())
        assert after.build().intersect(new_site).Volume() == pytest.approx(0)
    assert assembly(changed, new_plate, new_base).fastenings()[0].sites[0].origin == pytest.approx((5, 0, 1.2))


def test_frames_determine_placement_and_hardware_under_arbitrary_rotation():
    spec, plate, base = definitions()
    # Nontrivial local feature datum and a rotated/translated assembly root.
    plate = replace(plate, features={"mount": spec.clearance_side(at=d.Frame((0, 0, 4)), thickness=2.4)})
    root = d.Frame((10, 20, 30), z=(0, 1, 0), x=(0, 0, 1))
    fixture = assembly(spec, plate, base, root)
    expected = root.location * cq.Location((0, 0, -4))
    actual = fixture.locations()["plate"]
    assert actual.toTuple()[0] == pytest.approx(expected.toTuple()[0])
    fastening, = fixture.fastenings()
    # Local site (8, 0, 2.4): root X is global Z, root Z is global Y.
    assert fastening.sites[0].origin == pytest.approx((10, 22.4, 38))
    assert fastening.sites[0].axis == pytest.approx((0, -1, 0))
    assert fastening.hardware[1].offset_mm == pytest.approx(2.4)


def test_recess_change_recomputes_stack_and_existing_engagement_validation():
    spec, plate, base = definitions()
    original = assembly(spec, plate, base).fastenings()[0]
    assert original.grip_mm == pytest.approx(1.2)
    assert original.hole_depth_mm == pytest.approx(7.9)
    spec, plate, base = definitions(thickness=4.4)
    thicker = assembly(spec, plate, base).fastenings()[0]
    assert thicker.grip_mm == pytest.approx(3.2)
    assert thicker.hardware[1].offset_mm == pytest.approx(3.2)
    report = assembly(spec, plate, base).as_project().validate_mechanics(scan_collisions=False)
    assert any(f["code"] == "engagement" and f["status"] == "fail" for f in report["findings"])


def test_project_exports_native_geometry_and_keeps_print_pose_separate(tmp_path):
    spec, plate, base = definitions()
    plate = replace(plate, manufacture=d.FDM("PETG", (180, 0, 0)))
    fixture = assembly(spec, plate, base, d.Frame((0, 0, 40)))
    project = fixture.as_project()
    part = next(p for p in project.parts if p.name == "plate")
    assert isinstance(part, FabricationPart)
    assert part.build().BoundingBox().zmin == pytest.approx(0)
    assert next(c for c in project.components() if c.name == "plate").model.BoundingBox().zmin == pytest.approx(40)
    json.dumps(project.describe())
    # export.build is the pre-existing exporter, without a second geometry path.
    manifest = build(project, [part], tmp_path)
    imported = cq.importers.importStep(str(tmp_path / "plate.step")).val()
    assert imported.isValid()
    assert imported.Volume() == pytest.approx(plate.build().Volume())
    assert manifest["parts"][0]["name"] == "plate"


def test_repeated_part_instances_count_hardware_and_are_independently_placed():
    spec, plate, base = definitions()
    fixture = assembly(spec, plate, base)
    second_base = fixture.add("base-2", base)
    second_plate = fixture.add("plate-2", plate)
    fixture.fix(second_base, at=d.Frame((100, 0, 0)))
    fixture.connect("mount-2", spec, through=second_plate.feature("mount"), into=second_base.feature("mount"))
    project = fixture.as_project()
    assert {p.name: p.quantity for p in project.parts} == {"plate": 2, "base": 2}
    assert sorted(r["quantity"] for r in hardware_bom(project.fastenings)) == [4, 4]
    assert len(list(project.get_assembly().components())) == 12
    assert fixture.locations()["plate-2"].toTuple()[0] == pytest.approx((100, 0, 0))
    assert project.fastenings[1].sites[0].origin == pytest.approx((108, 0, 1.2))


def test_project_snapshot_cannot_mix_new_components_with_old_hardware():
    spec, plate, base = definitions()
    fixture = assembly(spec, plate, base)
    project = fixture.as_project()
    extra = fixture.add("extra", base)
    fixture.fix(extra, at=d.Frame((100, 0, 0)))
    assert len(project.components()) == 2
    assert len(fixture.components()) == 3


def test_invalid_role_ownership_and_missing_placements_are_errors():
    spec, plate, base = definitions()
    fixture = d.Assembly("fixture")
    fixed = fixture.add("base", base)
    moving = fixture.add("plate", plate)
    with pytest.raises(ValueError, match="Unplaced"):
        fixture.locations()
    with pytest.raises(ValueError, match="this mount"):
        fixture.connect("bad", mount(), through=moving.feature("mount"), into=fixed.feature("mount"))
    with pytest.raises(ValueError, match="unknown feature"):
        moving.feature("missing")
    other = d.Assembly("other").add("foreign", base)
    with pytest.raises(ValueError, match="different assembly"):
        fixture.fix(other)
    fixture.connect("mount", spec, through=moving.feature("mount"), into=fixed.feature("mount"))
    with pytest.raises(ValueError, match="ungrounded"):
        fixture.locations()
    with pytest.raises(ValueError, match="already has a placement"):
        fixture.fix(moving)


def test_bad_feature_frame_and_invalid_dimensions_are_errors():
    spec, plate, base = definitions()
    plate = replace(plate, features={"bad": spec.clearance_side(at=d.Frame((100, 0, 0)), thickness=2.4)})
    with pytest.raises(ValueError, match="plate/features/bad.*does not intersect"):
        plate.build()
    with pytest.raises(ValueError, match="positive screw seat"):
        spec.clearance_side(thickness=2, head_recess=d.Counterbore(6, 2))
    with pytest.raises(ValueError, match="threads must match"):
        replace(spec, screw=FastenerSpec("socket_head_cap_screw", "M4-0.7", length_mm=6))
    with pytest.raises(ValueError, match="distinct"):
        d.PolarPattern(8, (0, 360))
    with pytest.raises(ValueError, match="perpendicular"):
        d.Frame(x=(0, 0, 1))


def test_placement_cycles_and_implicit_part_variants_are_rejected():
    spec, plate, base = definitions()
    both = replace(plate, features={"top": spec.clearance_side(thickness=2.4), "bottom": spec.insert_side()})
    fixture = d.Assembly("cycle")
    a, b = fixture.add("a", both), fixture.add("b", both)
    fixture.connect("a-to-b", spec, through=a.feature("top"), into=b.feature("bottom"))
    fixture.connect("b-to-a", spec, through=b.feature("top"), into=a.feature("bottom"))
    with pytest.raises(ValueError, match="cycle"):
        fixture.locations()
    with pytest.raises(ValueError, match="variant"):
        fixture.add("variant", replace(both, manufacture=d.FDM("PETG")))
