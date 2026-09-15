"""Graph resolution proves datum composition independently of consumer geometry."""
from dataclasses import replace
import json
import cadquery as cq
import pytest

from cadkit import design as d
from cadkit.mechanics import component_index, resolve_components
from test_design import definitions, assembly as insert_fixture


def block(name="block", calls=None):
    def build():
        if calls is not None:
            calls.append(name)
        return cq.Workplane("XY").box(2, 2, 2).val()
    return d.Part(name, build, d.FDM("PETG"), ports={"axis": d.Frame()})


def stage():
    spec, plate, base = definitions()
    return insert_fixture(spec, replace(plate, ports={"axis": d.Frame()}), replace(base, ports={"axis": d.Frame()}))


def machine():
    result = d.Assembly("machine")
    base = result.add("base", block())
    fixture = stage()
    fixture.export_port("axis", fixture.instances["base"].port("axis"))
    rotating = result.add("stage", fixture)
    result.fix(base)
    azimuth = result.connect("azimuth", d.Revolute(limits=(-180, 180)), parent=base.port("axis"), child=rotating.port("axis"))
    result.name_pose("quarter-turn", {azimuth: 90})
    return result, azimuth, fixture


def test_nested_pose_moves_geometry_hardware_and_exported_frames_together():
    design, azimuth, _ = machine()
    fixed = design.models(names="path")["stage/plate"].val()
    moving = design.pose({azimuth: 90}).models(names="path")["stage/plate"].val()
    assert (fixed.BoundingBox().xlen, moving.BoundingBox().ylen) == pytest.approx((30, 30))
    before, = design.fastenings()
    after, = design.pose({azimuth: 90}).fastenings()
    assert before.name == after.name == "stage/mount"
    assert before.sites[0].origin == pytest.approx((8, 0, 1.2))
    assert after.sites[0].origin == pytest.approx((0, 8, 1.2))
    tree = design.pose({azimuth: 90}).as_assembly()
    index = component_index(tree)
    assert resolve_components(after.components, index) == ["/machine/stage/plate", "/machine/stage/base"]
    assert len(list(tree.components())) == 7


def test_project_named_pose_keeps_hardware_and_mechanics_in_same_pose():
    design, _, _ = machine()
    project = design.as_project()
    posed = project.get_assembly("quarter-turn")
    assert len(project.get_components("quarter-turn")) == 7
    description = project.mechanical_descriptions(posed)
    assert description["fastenings"][0]["sites"][0]["origin"] == pytest.approx((0, 8, 1.2))
    assert next(j for j in description["joints"] if j["name"] == "azimuth")["position"] == 90
    assert len(project.get_components("quarter-turn", include_hardware=False)) == 3
    assert not any("reference" in row["code"] for row in project.validate_mechanics(posed, scan_collisions=False)["findings"])


def test_pose_and_project_recursively_snapshot_later_authoring():
    design, azimuth, child = machine()
    posed = design.pose({azimuth: 45})
    project = design.as_project()
    extra = child.add("extra", block("extra"))
    child.fix(extra, at=d.Frame((100, 0, 0)))
    assert len(design.components()) == 4
    assert len(posed.components()) == len(project.components()) == 3
    with pytest.raises(TypeError):
        posed.positions["azimuth"] = 10


def test_repeat_nested_instance_scopes_identity_and_counts_definition_once():
    design = d.Assembly("twins")
    inner = stage()
    a = design.add("left", inner)
    b = design.add("right", inner)
    design.fix(a)
    design.fix(b, at=d.Frame((100, 0, 0)))
    assert set(design.models(names="path")) == {"left/base", "left/plate", "right/base", "right/plate"}
    with pytest.raises(ValueError, match="Ambiguous"):
        design.models()
    project = design.as_project()
    assert {p.name: p.quantity for p in project.parts} == {"base": 2, "plate": 2}
    assert project.fastenings[1].sites[0].origin == pytest.approx((108, 0, 1.2))
    index = component_index(project.get_assembly())
    for fastening in project.fastenings:
        assert len(resolve_components(fastening.components, index)) == 2


def test_exported_moving_port_resolves_child_before_parent_attachment():
    rail = d.Assembly("rail")
    anchor = rail.add("anchor", block())
    carriage = rail.add("carriage", block("carriage"))
    rail.fix(anchor)
    rail.connect("travel", d.Slider(position=10, limits=(0, 20)), parent=anchor.port("axis"), child=carriage.port("axis"))
    rail.export_port("moving", carriage.port("axis"))
    parent = d.Assembly("fixture")
    base = parent.add("base", block())
    sub = parent.add("rail", rail)
    parent.fix(base, at=d.Frame((0, 0, 100)))
    parent.connect("fix", d.Rigid(), parent=base.port("axis"), child=sub.port("moving"))
    components = {c.name: c for c in parent.components()}
    assert components["rail/carriage"].model.Center().z == pytest.approx(100)
    assert components["rail/anchor"].model.Center().z == pytest.approx(90)
    shifted = parent.pose({"rail/travel": 20}).models(names="path")
    assert shifted["rail/carriage"].val().Center().z == pytest.approx(100)
    assert shifted["rail/anchor"].val().Center().z == pytest.approx(80)


def test_affine_drive_ratios_are_explicit_and_validate_derived_limits():
    design = d.Assembly("rack")
    base = design.add("base", block())
    rack = design.add("rack", block("rack"))
    pinion = design.add("pinion", block("pinion"))
    design.fix(base)
    travel = design.connect("travel", d.Slider(position=2, limits=(0, 10)), parent=base.port("axis"), child=rack.port("axis"))
    angle = design.connect("angle", d.Revolute(position=0, limits=(-90, 90)), parent=base.port("axis"), child=pinion.port("axis"))
    design.couple("rack-and-pinion", driver=travel, driven=angle, ratio=-10, offset=5)
    assert next(j for j in design.joints() if j.name == "angle").position == -15
    assert next(j for j in design.pose({travel: 8}).joints() if j.name == "angle").position == -75
    with pytest.raises(ValueError, match="derived"):
        design.pose({angle: 10})
    with pytest.raises(ValueError, match="outside limits"):
        design.pose({travel: 10})
    with pytest.raises(ValueError, match="outside limits"):
        design.pose({travel: -1})
    design.couple("cycle", driver=angle, driven=travel, ratio=1)
    with pytest.raises(ValueError, match="cycle"):
        design.locations()


def test_local_rotated_axis_is_resolved_once_and_native_export_matches():
    design = d.Assembly("axis")
    base = design.add("base", block())
    child = design.add("moving", block("moving"))
    design.fix(base, at=d.Frame((10, 20, 30), z=(1, 0, 0), x=(0, 1, 0)))
    design.connect("travel", d.Slider(position=7), parent=base.port("axis"), child=child.port("axis"))
    assert design.locations()["moving"].toTuple()[0] == pytest.approx((17, 20, 30))
    native = design.as_cq_assembly(include_hardware=False).toCompound()
    assert native.Volume() == pytest.approx(16)
    assert native.Center().toTuple() == pytest.approx((13.5, 20, 30))


def test_describing_and_resolving_graph_is_lazy_and_purchased_is_not_printable():
    calls = []
    design = d.Assembly("bought")
    base = design.add("base", block(calls=calls))
    bought = design.add("motor", d.Purchased("motor", lambda: calls.append("motor") or cq.Workplane("XY").box(1, 1, 1), ports={"axis": d.Frame()}, sku="42"))
    design.fix(base)
    design.connect("mount", d.Rigid(), parent=base.port("axis"), child=bought.port("axis"))
    json.dumps(design.describe())
    design.locations()
    project = design.as_project()
    assert calls == []
    assert [p.name for p in project.parts] == ["block"]
    assert set(design.models(kind="purchased")) == {"motor"}
    assert project.get_components()[1].metadata["design"]["sku"] == "42"


def test_invalid_reference_cycles_unplaced_and_multiple_parents_fail():
    design = d.Assembly("broken")
    a, b = design.add("a", block()), design.add("b", block("b"))
    with pytest.raises(ValueError, match="unknown port"):
        a.port("typo")
    foreign = d.Assembly("other").add("foreign", block())
    with pytest.raises(ValueError, match="different assembly"):
        design.connect("bad", d.Rigid(), parent=a.port("axis"), child=foreign.port("axis"))
    design.connect("one", d.Rigid(), parent=a.port("axis"), child=b.port("axis"))
    with pytest.raises(ValueError, match="already has"):
        design.fix(b)
    design.connect("two", d.Rigid(), parent=b.port("axis"), child=a.port("axis"))
    with pytest.raises(ValueError, match="cycle"):
        design.locations()
    with pytest.raises(ValueError, match="Unknown motion"):
        design.pose({"typo": 3})
    outer, inner = d.Assembly("outer"), d.Assembly("inner")
    outer.add("inner", inner)
    inner.add("outer", outer)
    with pytest.raises(ValueError, match="cycle"):
        outer.describe()


def test_secondary_mount_checks_installed_datums_without_repositioning():
    spec, plate, base = definitions()
    design = d.Assembly("secondary")
    parent, child = design.add("base", base), design.add("plate", plate)
    design.fix(parent)
    design.fix(child, at=d.Frame((1, 0, 0)))
    design.fasten("mount", spec, through=child.feature("mount"), into=parent.feature("mount"))
    with pytest.raises(ValueError, match="do not coincide"):
        design.fastenings()


def test_embedding_flattens_only_unique_names_and_transforms_metadata_once():
    spec, plate, base = definitions()
    fixture = insert_fixture(spec, plate, base)
    embedded = fixture.embed(at=d.Frame((10, 20, 30), z=(0, 1, 0), x=(0, 0, 1)))
    assert [c.name for c in embedded.components()] == ["base", "plate"]
    assert embedded.fastenings()[0].components == ("plate", "base")
    assert embedded.fastenings()[0].sites[0].origin == pytest.approx((10, 21.2, 38))
    assert embedded.models()["plate"].val().Center().y == pytest.approx(20 + plate.build().Center().z)
    assembly_tree = d.Assembly("twice")
    a, b = assembly_tree.add("a", fixture), assembly_tree.add("b", fixture)
    assembly_tree.fix(a)
    assembly_tree.fix(b)
    with pytest.raises(ValueError, match="ambiguous"):
        assembly_tree.embed()


def test_contact_region_and_tool_access_follow_the_same_nested_pose():
    design, azimuth, fixture = machine()
    plate, base = fixture.instances["plate"], fixture.instances["base"]
    fixture.interface("seat", left=plate, right=base, kind="press_fit",
                      region=lambda: cq.Solid.makeCylinder(1, 1, (8, 0, 0)), max_overlap_mm3=1)
    fixture.access("driver", connection=fixture.connections["mount"],
                   envelope=lambda: cq.Solid.makeCylinder(1, 5, (8, 0, 3)), obstacles=(base,))
    posed = design.pose({azimuth: 90})
    contact = next(item for item in posed.interfaces() if item.name == "stage/seat")
    assert contact.region().Center().toTuple() == pytest.approx((0, 8, .5))
    fastening, = posed.fastenings()
    assert fastening.access[0].envelope().Center().toTuple() == pytest.approx((0, 8, 5.5))
    assert fastening.access[0].obstacles == ("/machine/stage/base",)
    fixture_snapshot = fixture.embed(at=d.Frame((10, 0, 0)))
    assert fixture_snapshot.fastenings()[0].access[0].obstacles == ("base",)
    assert fixture_snapshot.fastenings()[0].access[0].envelope().Center().x == pytest.approx(18)


def test_supplied_sets_count_physical_quantities_without_duplicate_geometry():
    design = d.Assembly("spacers")
    component = d.Purchased("spacer-set", lambda: cq.Workplane("XY").box(1, 1, 1), quantity=3, sku="M3-20")
    a, b = design.add("upper", component), design.add("lower", component)
    design.fix(a)
    design.fix(b, at=d.Frame((0, 0, 10)))
    assert design.purchased_bom()[0]["quantity"] == 6
    assert len(design.components()) == 2
    assert design.as_project().describe()["purchased_bom"][0]["instances"] == ["upper", "lower"]


def test_driver_access_derives_pattern_and_seat_in_each_pose():
    design, azimuth, fixture = machine()
    fixture.driver_access("driver", connection="mount", diameter=2, length=10,
                          obstacles=(fixture.instances["base"],))
    fastening, = design.pose({azimuth: 90}).fastenings()
    probes = fastening.access[0].envelope().Solids()
    assert len(probes) == 2
    assert probes[0].Center().toTuple() == pytest.approx((0, 8, 6.2))
    assert probes[1].Center().toTuple() == pytest.approx((0, -8, 6.2))
    assert fastening.access[0].envelope().Volume() == pytest.approx(20 * 3.141592653589793)


def test_kind_filters_native_exports_and_embedding_rebases_generated_hardware():
    design, _, _ = machine()
    purchased = design.add("sensor", d.Purchased("sensor", lambda: cq.Workplane("XY").box(1, 1, 1)))
    design.fix(purchased, at=d.Frame((20, 0, 0)))
    printed = design.as_cq_assembly(kind="manufactured", include_hardware=False).toCompound()
    assert len(printed.Solids()) == 3
    assert len(design.as_assembly(kind="purchased", include_hardware=False).children) == 1
    # Fully nested native export includes the same hardware as the project tree.
    assert len(design.as_cq_assembly().toCompound().Solids()) == 8
    spec, plate, base = definitions()
    embedded = insert_fixture(spec, plate, base).embed()
    generated = embedded.interfaces(hardware_root="/host/Hardware")
    assert generated
    hardware_refs = [ref for item in generated for ref in item.components if ref.startswith("/")]
    assert hardware_refs and all(ref.startswith("/host/Hardware/") for ref in hardware_refs)
