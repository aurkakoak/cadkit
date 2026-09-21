"""Public authoring flows preserve fabrication intent and geometry representation."""
from dataclasses import replace
import json

import cadquery as cq
import pytest

import cadkit as ck
from cadkit import design, geometry
from cadkit.export import export_part


def block(name="block", **options):
    return ck.Part(name, lambda: cq.Workplane("XY").box(2, 4, 6),
                   ck.FDM("PETG"), **options)


def test_public_names_share_one_authoring_model():
    assert ck.Part is design.Part
    assert ck.Assembly is design.Assembly
    assert not hasattr(ck, "Component")
    project = ck.Assembly("fixture").as_project(extra_parts=(block(),))
    assert isinstance(project, ck.Project)


def test_inventory_is_lazy_and_independent_of_display_groups_and_visibility(tmp_path):
    calls = []
    definition = ck.Part("bracket", lambda: calls.append(1) or cq.Workplane("XY").box(2, 4, 6),
                         ck.FDM("PETG"), group="structure", description="Reusable bracket",
                         notes="Deburr the edges.")
    coupon = ck.Part("coupon", lambda: cq.Compound.makeCompound([
        cq.Solid.makeBox(2, 2, 2), cq.Solid.makeBox(2, 2, 2, (5, 0, 0))]),
        ck.FDM("PLA"), group="calibration", production=False, expected_solids=2)
    machine = ck.Assembly("fixture")
    machine.fix(machine.add("left", definition, group="left-hand-side"))
    machine.fix(machine.add("right", definition, group="right-hand-side"), at=ck.Frame((20, 0, 0)))
    quantities = {"bracket": 3, "coupon": 2}
    project = machine.as_project(extra_parts=(definition, coupon, coupon), quantities=quantities)
    quantities["bracket"] = 100
    data = project.describe()
    assert calls == []
    assert {p.name: p.quantity for p in project.parts} == {"bracket": 3, "coupon": 2}
    assert [p.name for p in project.select()] == ["bracket"]
    assert [p.name for p in project.select(["coupon"])] == ["coupon"]
    assert data["parts"][0]["group"] == "structure"
    assert data["parts"][0]["notes"] == "Deburr the edges."
    assert data["parts"][0]["description"] == "Reusable bracket"
    project.get_components(include_hardware=False)
    assert {p.name: p.quantity for p in project.parts} == {"bracket": 3, "coupon": 2}
    manifest = export_part(project.select(["coupon"])[0], tmp_path)
    assert manifest["solid_count"] == 2
    assert manifest["quantity"] == 2


def test_inventory_rejects_ambiguous_definitions_and_invalid_quantity_overrides():
    machine = ck.Assembly("fixture")
    definition = block()
    machine.fix(machine.add("block", definition))
    with pytest.raises(ValueError, match="Different part definitions"):
        machine.as_project(extra_parts=(replace(definition, notes="different"),))
    with pytest.raises(ValueError, match="Unknown manufacturing quantity"):
        machine.as_project(quantities={"typo": 2})
    for quantity in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="positive integers"):
            machine.as_project(quantities={"block": quantity})
    with pytest.raises(TypeError, match="Part definitions"):
        machine.as_project(extra_parts=(ck.Purchased("motor", lambda: cq.Solid.makeBox(1, 1, 1)),))


def test_fabrication_frame_changes_only_fabrication_geometry(tmp_path):
    frame = ck.Frame((100, -15, 20), z=(0, -1, 0), x=(1, 0, 0))
    part = replace(block(), manufacture=ck.FDM("PETG", print_frame=frame))
    local = part.build()
    printed = part.build_for_print()
    assert local.BoundingBox().zmin == pytest.approx(-3)
    assert printed.BoundingBox().zmin == pytest.approx(0)
    assert (printed.BoundingBox().xlen, printed.BoundingBox().ylen, printed.BoundingBox().zlen) == pytest.approx((2, 6, 4))
    assert printed.Center().toTuple() == pytest.approx((100, -15, 2))
    machine = ck.Assembly("fixture")
    machine.fix(machine.add("part", part), at=ck.Frame((0, 0, 50)))
    project = machine.as_project()
    metadata = project.describe()["parts"][0]
    assert metadata["print_rotation"] == pytest.approx((90, 0, 0))
    assert metadata["print_frame"] == frame.describe()
    assert project.get_components()[0].model.Center().toTuple() == pytest.approx((0, 0, 50))
    manifest = export_part(project.parts[0], tmp_path)
    assert manifest["bounds_mm"]["min"][2] == pytest.approx(0)
    assert cq.importers.importStep(str(tmp_path / "block.step")).val().Center().toTuple() == pytest.approx((100, -15, 2))
    direct = export_part(part, tmp_path / "direct")
    assert direct["bounds_mm"] == manifest["bounds_mm"]
    json.dumps(project.describe())
    with pytest.raises(ValueError, match="Choose print_frame or print_rotation"):
        ck.FDM("PETG", (90, 0, 0), print_frame=frame)


def test_mesh_definition_and_purchased_body_keep_representation_through_placement_and_export(tmp_path):
    source = geometry.mesh(cq.Workplane("XY").box(2, 4, 6))
    part = ck.Part("mesh-part", lambda: source, ck.FDM("PETG", (90, 0, 0)), group="housing")
    reference = ck.Purchased("vendor", lambda: source, ports={"axis": ck.Frame()}, representation="detailed")
    machine = ck.Assembly("fixture")
    sub = ck.Assembly("sub")
    sub.fix(sub.add("printed", part), at=ck.Frame((0, 0, 10)))
    sub.fix(sub.add("reference", reference), at=ck.Frame((20, 0, 10)))
    machine.fix(machine.add("sub", sub), at=ck.Frame((30, 40, 50), z=(0, 1, 0)))
    project = machine.as_project()
    components = project.get_components()
    assert all(isinstance(c.model, geometry.Mesh) for c in components)
    assert components[0].model.triangles().center_mass == pytest.approx((30, 50, 50))
    assert components[1].model.triangles().center_mass == pytest.approx((50, 50, 50))
    assert source.triangles().center_mass == pytest.approx((0, 0, 0))
    assert all(isinstance(m, geometry.Mesh) for m in machine.models().values())
    assert [p.name for p in project.parts] == ["mesh-part"]
    (tmp_path / "mesh-part.step").write_text("stale")
    manifest = export_part(project.parts[0], tmp_path)
    assert manifest["geometry"] == "mesh"
    assert set(manifest["files"]) == {"stl"}
    assert not (tmp_path / "mesh-part.step").exists()
    assert manifest["bounds_mm"]["size"] == pytest.approx((2, 6, 4))
    assert manifest["bounds_mm"]["min"][2] == pytest.approx(0)
    with pytest.raises(ValueError, match="cannot include Mesh"):
        machine.as_cq_assembly()
    with pytest.raises(ValueError, match="Mesh bodies do not support native"):
        replace(part, features={"hole": ck.Hole(diameter=1, depth=1)}).build()


def test_static_contracts_share_the_project_tree_and_cannot_freeze_moving_hardware():
    machine = ck.Assembly("fixture")
    first = machine.add("first", block())
    second = machine.add("second", block("other"))
    machine.fix(first)
    machine.fix(second, at=ck.Frame((20, 0, 0)))
    interface = ck.Interface("gap", ("first", "second"), kind="clearance", min_clearance_mm=10)
    project = machine.as_project(interfaces=(interface,))
    assert project.mechanical_descriptions(project.get_assembly())["interfaces"][0]["name"] == "gap"
    report = project.validate_mechanics(scan_collisions=False)
    assert not any(f["status"] == "fail" for f in report["findings"])
    motion = ck.Assembly("moving")
    definition = replace(block(), ports={"axis": ck.Frame()})
    base = motion.add("base", definition)
    child = motion.add("child", definition)
    motion.fix(base)
    motion.connect("turn", ck.Revolute(), parent=base.port("axis"), child=child.port("axis"))
    with pytest.raises(ValueError, match="static assembly"):
        motion.as_project(interfaces=(interface,))
