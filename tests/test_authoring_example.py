"""Exercise the edit paths promised by the structured shaft-support example."""
from pathlib import Path

import cadkit as ck
import pytest


@pytest.fixture
def example(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "examples"))
    from shaft_support.assemblies.bearing_unit import Dimensions, make_assembly
    from shaft_support.project import make_project

    return Dimensions, make_assembly, make_project


@pytest.mark.parametrize("inputs,shaft_length,base_length,axis_height,support_x,gap", [
    ({}, 102, 98, 16.2, 35, 0.2),
    ({"shaft_diameter": 10, "support_span": 85, "radial_clearance": 0.35},
     117, 113, 17.35, 42.5, 0.35),
])
def test_dimension_changes_reach_bodies_mates_and_evidence(
    example, inputs, shaft_length, base_length, axis_height, support_x, gap,
):
    Dimensions, _, make_project = example
    project = make_project(Dimensions(**inputs))
    components = {
        item.name: item.model
        for item in project.get_components(include_hardware=False)
    }
    assert {part.name: part.quantity for part in project.parts} == {
        "base": 1, "support": 2, "shaft": 1,
    }
    assert components["shaft"].BoundingBox().xlen == pytest.approx(shaft_length)
    assert components["base"].BoundingBox().xlen == pytest.approx(base_length)
    assert components["shaft"].Center().z == pytest.approx(axis_height)
    assert components["left-support"].Center().x == pytest.approx(-support_x)
    assert components["right-support"].Center().x == pytest.approx(support_x)
    for name in ("left-support", "right-support"):
        assert components[name].distance(components["shaft"]) == pytest.approx(gap)
        assert components[name].distance(components["base"]) == pytest.approx(0)
    for shape in components.values():
        assert shape.isValid() and len(shape.Solids()) == 1

    report = project.validate_mechanics()
    assert report["summary"]["fail"] == 0
    for name in ("left-journal-clearance", "right-journal-clearance"):
        finding, = [item for item in report["findings"] if item["entity"] == name]
        assert finding["status"] == "pass"
        assert finding["evidence"]["gap_mm"] == pytest.approx(gap)
    assert project.checks[0].builder().val().Volume() == pytest.approx(0)
    assert all(Path(parameter.source).is_file() for parameter in project.parameters)
    parameters = {parameter.name: parameter for parameter in project.parameters}
    assert len(parameters) == 8
    assert parameters["bearing.shaft_diameter"].value == Dimensions(**inputs).shaft_diameter
    assert parameters["bearing.radial_clearance"].value == gap
    assert "bearing.bore_diameter" not in parameters


def test_reuse_and_subsystem_placement_leave_manufacturing_geometry_local(example):
    Dimensions, make_assembly, _ = example
    assembly = make_assembly(Dimensions())
    left = assembly.instances["left-support"]
    right = assembly.instances["right-support"]
    assert left.part is right.part
    local_support = left.part.build()
    printed_support = left.part.build_for_print()
    assert local_support.BoundingBox().zmin == pytest.approx(0)
    assert printed_support.BoundingBox().zmin == pytest.approx(0, abs=1e-6)
    assert printed_support.Volume() == pytest.approx(local_support.Volume())

    machine = ck.Assembly("machine")
    installed_unit = machine.add("bearing-unit", assembly)
    offset = (120, 40, 30)
    machine.fix(installed_unit, at=ck.Frame(offset))
    machine.name_pose("turned", {"bearing-unit/shaft-turn": 90})
    project = machine.as_project()
    home = {item.name: item.model for item in project.get_components(include_hardware=False)}
    turned = {
        item.name: item.model
        for item in project.get_components(view="turned", include_hardware=False)
    }
    for name in ("left-support", "right-support"):
        expected_x = offset[0] + (-35 if name == "left-support" else 35)
        shape = home[f"bearing-unit/{name}"]
        assert shape.Center().x == pytest.approx(expected_x)
        assert shape.BoundingBox().zmin == pytest.approx(offset[2] + 6)
        assert shape.Volume() == pytest.approx(local_support.Volume())
    for name, shape in home.items():
        assert turned[name].Volume() == pytest.approx(shape.Volume())
    for name in ("left-support", "right-support"):
        assert turned[f"bearing-unit/{name}"].distance(
            turned["bearing-unit/shaft"]
        ) == pytest.approx(0.2)
    # The definition can still be fabricated independently after placement/posing.
    assert left.part.build().BoundingBox().zmin == pytest.approx(0)
    assert left.part.build_for_print().Volume() == pytest.approx(printed_support.Volume())
