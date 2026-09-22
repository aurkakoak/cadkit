"""Definition defaults and explicitly exported leaves compose across subsystem boundaries."""
import json
from math import sqrt

import cadquery as cq
import pytest

import cadkit as ck


def block(name="foot", *, group="Printed", origin=(3, 0, 0), calls=None):
    def build():
        if calls is not None:
            calls.append(name)
        return cq.Solid.makeBox(1, 1, 1, origin)

    return ck.Part(name, build, ck.FDM("PLA"), group=group, ports={"axis": ck.Frame()})


def moving_unit(*, calls=None):
    unit = ck.Assembly("unit")
    pivot = unit.add(ck.Purchased(
        "pivot", lambda: cq.Solid.makeCylinder(0.5, 1),
        ports={"axis": ck.Frame()}, representation="detailed",
    ))
    foot = unit.add(block(calls=calls))
    unit.fix(pivot)
    unit.connect("turn", ck.Revolute(), parent=pivot.port("axis"), child=foot.port("axis"))
    unit.export_component("foot", foot)
    unit.export_component("contact-pad", foot)
    unit.export_component("pivot", pivot)
    return unit


def repeated_units(*, calls=None):
    unit = moving_unit(calls=calls)
    pair = ck.Assembly("pair")
    left = pair.add("left", unit)
    right = pair.add("right", unit)
    pair.fix(left)
    pair.fix(right, at=ck.Frame((-4, 3, 0)))
    pair.export_component("left-foot", left.component("foot"))
    pair.export_component("right-foot", right.component("foot"))
    return unit, pair


@pytest.mark.parametrize("form", ["definition", "keyword-definition", "alias", "keyword-alias"])
def test_add_accepts_inferred_or_explicit_names_without_building(form):
    calls = []
    part = block(calls=calls)
    assembly = ck.Assembly("fixture")
    if form == "definition":
        instance = assembly.add(part)
    elif form == "keyword-definition":
        instance = assembly.add(part=part)
    elif form == "alias":
        instance = assembly.add("other", part)
    else:
        instance = assembly.add(name="other", part=part)
    assert instance.name == ("other" if "alias" in form else "foot")
    assert instance.part is part
    assert instance.group == "Printed"
    assert calls == []


def test_display_defaults_and_overrides_do_not_change_manufacturing_groups():
    part = block()
    unit = ck.Assembly("unit")
    standard = unit.add(part)
    override = unit.add("highlight", part, group="Highlighted")
    bought = unit.add(ck.Purchased("sensor", lambda: cq.Solid.makeBox(1, 1, 1)))
    for index, instance in enumerate((standard, override, bought)):
        unit.fix(instance, at=ck.Frame((index * 10, 0, 0)))
    outer = ck.Assembly("outer")
    child = outer.add(unit, group="Container")
    outer.fix(child)
    project = outer.as_project()
    assert {item.name: item.group for item in project.get_components()} == {
        "unit/foot": "Printed", "unit/highlight": "Highlighted", "unit/sensor": "Purchased",
    }
    part_record, = project.parts
    assert (part_record.group, part_record.quantity) == ("Printed", 2)
    assert bought.group == "Purchased"


def test_name_inference_rejects_collisions_and_ambiguous_arguments():
    assembly = ck.Assembly("fixture")
    part = block()
    assembly.add(part)
    with pytest.raises(ValueError, match="Duplicate instance"):
        assembly.add(part=part)
    with pytest.raises(TypeError, match="definition alone"):
        assembly.add(part, part)
    with pytest.raises(TypeError, match="definition"):
        assembly.add("missing-definition")
    with pytest.raises(TypeError, match="definition"):
        assembly.add()


def test_reused_nested_exports_follow_each_occurrence_and_pose_in_native_validation():
    _, pair = repeated_units()
    machine = ck.Assembly("machine")
    installed_pair = machine.add(pair)
    placement = ck.Frame((10, 20, 30), z=(0, 1, 0), x=(0, 0, 1))
    machine.fix(installed_pair, at=placement)
    machine.interface(
        "pad-clearance", left=installed_pair.component("left-foot"),
        right=installed_pair.component("right-foot"), kind="clearance", min_clearance_mm=1,
    )
    machine.name_pose("left-turned", {"pair/left/turn": 90})
    project = machine.as_project()
    interface, = project.interfaces
    assert interface.components == ("/machine/pair/left/foot", "/machine/pair/right/foot")
    assert {part.name: part.quantity for part in project.parts} == {"foot": 2}

    home = project.validate_mechanics()
    finding = next(row for row in home["findings"] if row["entity"] == "pad-clearance")
    assert finding["status"] == "pass"
    assert finding["evidence"]["gap_mm"] == pytest.approx(sqrt(13))
    turned_tree = project.get_assembly("left-turned")
    turned = project.validate_mechanics(turned_tree)
    finding = next(row for row in turned["findings"] if row["entity"] == "pad-clearance")
    assert finding["status"] == "fail"
    assert finding["evidence"]["overlap_mm3"] == pytest.approx(1)
    assert finding["component_ids"] == list(interface.components)

    home_locations = machine.locations(names="path")
    moved_locations = machine.locations(names="path", pose="left-turned")
    assert set(home_locations) == {"pair/left/pivot", "pair/left/foot", "pair/right/pivot", "pair/right/foot"}
    for path in ("pair/right/foot", "pair/left/pivot", "pair/right/pivot"):
        assert moved_locations[path].toTuple() == home_locations[path].toTuple()
    witness = cq.Vertex.makeVertex(3.5, 0.5, 0.5)
    moved = witness.moved(moved_locations["pair/left/foot"]).Center().toTuple()
    expected = cq.Vertex.makeVertex(-0.5, 3.5, 0.5).moved(placement.location).Center().toTuple()
    assert moved == pytest.approx(expected)


def test_component_regions_stay_in_the_declaring_frame_under_nested_motion():
    _, pair = repeated_units()
    left, right = pair.instances["left"], pair.instances["right"]
    region = lambda: cq.Solid.makeBox(2, 2, 2, (1, 3, 5))
    pair.interface(
        "limited-overlap", left=left.component("foot"), right=right.component("foot"),
        kind="press_fit", region=region, max_overlap_mm3=1,
    )
    machine = ck.Assembly("machine")
    installed = machine.add(pair)
    placement = ck.Frame((10, 20, 30), z=(0, 1, 0), x=(0, 0, 1))
    machine.fix(installed, at=placement)
    before, = machine.interfaces()
    after, = machine.pose({"pair/left/turn": 90}).interfaces()
    expected = region().moved(placement.location).Center().toTuple()
    assert before.region().Center().toTuple() == pytest.approx(expected)
    assert after.region().Center().toTuple() == pytest.approx(expected)
    assert before.components == after.components


def test_component_exports_are_lazy_read_only_and_describe_resolved_local_paths():
    calls = []
    _, pair = repeated_units(calls=calls)
    left, right = pair.instances["left"], pair.instances["right"]
    pair.interface("gap", left=left.component("foot"), right=right.component("foot"), kind="clearance")
    assert isinstance(pair.exported_components["left-foot"], ck.ComponentRef)
    with pytest.raises(TypeError):
        pair.exported_components["other"] = left.component("foot")
    description = pair.describe()
    assert description["exported_components"] == {"left-foot": "left/foot", "right-foot": "right/foot"}
    assert description["interfaces"]["gap"]["left"] == "left/foot"
    json.dumps(description)
    assert set(pair.locations()) == {"left", "right"}
    assert len(pair.locations(names="path")) == 4
    pair.as_project().describe()
    assert calls == []
    with pytest.raises(ValueError, match="immediate/path"):
        pair.locations(names="unknown")


def test_recursive_snapshots_keep_component_exports_and_participants_isolated():
    unit, pair = repeated_units()
    left, right = pair.instances["left"], pair.instances["right"]
    pair.interface("gap", left=left.component("foot"), right=right.component("foot"), kind="clearance")
    posed = pair.pose({"left/turn": 45})
    project = pair.as_project()
    unit.export_component("new-alias", unit.instances["foot"])
    extra = unit.add(block("extra", origin=(20, 0, 0)))
    unit.fix(extra)
    unit.export_component("extra", extra)
    assert len(pair.locations(names="path")) == 6
    assert len(posed.locations(names="path")) == 4
    assert len(project.get_components()) == 4
    saved = posed.describe()["assembly"]["instances"]["left"]["definition"]["exported_components"]
    assert set(saved) == {"foot", "contact-pad", "pivot"}
    assert posed.interfaces()[0].components == project.interfaces[0].components


def test_component_reference_ownership_exports_and_same_leaf_aliases_are_checked():
    unit = moving_unit()
    parent = ck.Assembly("parent")
    sub = parent.add(unit)
    pad = sub.component("foot")
    other_parent = ck.Assembly("other")
    foreign = other_parent.add(unit)
    with pytest.raises(ValueError, match="different assembly"):
        parent.interface("foreign", left=pad, right=foreign.component("foot"))
    with pytest.raises(ValueError, match="different assembly"):
        parent.export_component("foreign", unit.instances["foot"])
    with pytest.raises(ValueError, match="leaf part"):
        parent.export_component("whole-unit", sub)
    with pytest.raises(ValueError, match="leaf part"):
        parent.interface("whole-unit", left=sub, right=pad)
    with pytest.raises(ValueError, match="unknown exported"):
        sub.component("missing")
    with pytest.raises(ValueError, match="unknown exported"):
        unit.instances["foot"].component("foot")
    with pytest.raises(ValueError, match="Duplicate exported"):
        unit.export_component("foot", unit.instances["pivot"])
    with pytest.raises(ValueError, match="distinct leaf"):
        parent.interface("self", left=pad, right=sub.component("contact-pad"))
    with pytest.raises(TypeError, match="leaf instance"):
        parent.export_component("raw-path", "unit/foot")
    with pytest.raises(TypeError, match="attachment datum"):
        parent.export_port("not-a-datum", pad)


def test_purchased_exports_validate_and_embedding_rebases_selected_leaf_references():
    unit = moving_unit()
    assembly = ck.Assembly("fixture")
    sub = assembly.add(unit)
    assembly.fix(sub)
    stop = assembly.add(block("stop", origin=(2, 0, 0)))
    assembly.fix(stop)
    assembly.interface(
        "bearing-stop", left=sub.component("pivot"), right=stop,
        kind="clearance", min_clearance_mm=1,
    )
    report = assembly.as_project().validate_mechanics(scan_collisions=False)
    finding = next(row for row in report["findings"] if row["entity"] == "bearing-stop")
    assert finding["status"] == "pass"
    assert finding["evidence"]["gap_mm"] == pytest.approx(1.5)
    embedded = assembly.embed(at=ck.Frame((10, 20, 30)))
    interface, = embedded.interfaces()
    assert interface.components == ("pivot", "stop")
    assert {item.name for item in embedded.components()} == {"pivot", "foot", "stop"}
