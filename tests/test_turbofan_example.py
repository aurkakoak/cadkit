"""Exercise the turbofan's motion and the dimensional edits its source advertises."""

from dataclasses import replace
from math import cos, radians, sin
from pathlib import Path

import cadquery as cq
import pytest


@pytest.fixture
def turbofan(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "examples"))
    from turbofan import project

    return project


LP_PARTS = {
    "lp-shaft-front",
    "lp-shaft-rear",
    "fan",
    "fan-spinner",
    "exhaust-tailcone",
    "lp-compressor-1",
    "lp-compressor-2",
    "lp-turbine-1",
    "lp-turbine-2",
    "fan-rear-spacer",
    "lp-stage-spacer",
}
HP_PARTS = {
    "hp-shaft-sleeve",
    "hp-compressor-1",
    "hp-compressor-2",
    "hp-compressor-3",
    "hp-turbine",
}
COVERS = {"nacelle-front-cover", "nacelle-rear-cover", "exhaust-upper-cover"}


def positioned_point(location):
    """An off-axis witness detects rotation even for an axisymmetric part."""
    return cq.Vertex.makeVertex(0, 3, 2).moved(location).Center().toTuple()


@pytest.mark.parametrize(
    "pose,lp_angle,hp_angle",
    [
        ("lp-45deg", 45, 0),
        ("hp-30deg", 0, 30),
        ("spools-turned", 45, -30),
    ],
)
def test_each_spool_moves_every_follower_and_leaves_other_parts_fixed(
    turbofan,
    pose,
    lp_angle,
    hp_angle,
):
    from turbofan.assembly import make_assembly
    from turbofan.dimensions import EngineDimensions

    assembly = make_assembly()
    home = assembly.locations()
    posed = assembly.locations(pose=pose)
    assert LP_PARTS | HP_PARTS <= home.keys()
    for name, location in home.items():
        x, y, z = positioned_point(location)
        angle = lp_angle if name in LP_PARTS else hp_angle if name in HP_PARTS else 0
        theta = radians(angle)
        height = EngineDimensions().axis_height
        expected = (
            x,
            y * cos(theta) - (z - height) * sin(theta),
            height + y * sin(theta) + (z - height) * cos(theta),
        )
        assert positioned_point(posed[name]) == pytest.approx(expected), name


def test_open_view_removes_covers_without_losing_optional_manufacturing_parts(turbofan):
    from turbofan.assembly import make_assembly

    closed, opened = turbofan.PROJECT, turbofan.OPEN_PROJECT
    for project in (closed, opened):
        assert len(project.parts) == 39
        assert len(project.select()) == 36
        assert all(part.quantity == 1 for part in project.parts)
        assert {part.name for part in project.parts if not part.production} == COVERS
        assert {part.name for part in project.select(tuple(sorted(COVERS)))} == COVERS
    assert set(make_assembly().instances) - set(make_assembly(covers=False).instances) == COVERS
    assembly = make_assembly()
    for name, instance in assembly.instances.items():
        assert instance.group == instance.part.group, name
    assert {item.group for item in assembly.instances.values()} == {
        "Display",
        "Casing",
        "Covers",
        "Static core",
        "Combustor",
        "LP spool",
        "HP spool",
    }


@pytest.mark.parametrize("diameter,flat,clearance", [(8.8, 3.6, 0.25), (9.2, 3.8, 0.35)])
def test_fit_edits_change_both_the_round_and_flat_bore_surfaces(
    turbofan,
    diameter,
    flat,
    clearance,
):
    from turbofan.assemblies.low_pressure.dimensions import FAN_REAR_SPACER
    from turbofan.assemblies.low_pressure.parts import make_parts
    from turbofan.dimensions import ShaftFit
    from turbofan.geometry import d_shaft

    fit = ShaftFit(shaft_diameter=diameter, shaft_flat=flat, radial_clearance=clearance)
    part = make_parts(fit=fit).fan_rear_spacer
    body = part.build()
    x = FAN_REAR_SPACER.length / 2
    probe_offset = 0.02
    # A section through the finished native body: void just inside the bore,
    # material just outside it, independently on its circle and its flat.
    assert not body.isInside((x, 0, fit.bore_radius - probe_offset))
    assert body.isInside((x, 0, fit.bore_radius + probe_offset))
    assert not body.isInside((x, fit.bore_flat - probe_offset, 0))
    assert body.isInside((x, fit.bore_flat + probe_offset, 0))
    shaft = d_shaft(fit.shaft_radius, fit.shaft_flat, FAN_REAR_SPACER.length)
    assert body.distance(shaft) == pytest.approx(clearance)
    assert body.isValid() and len(body.Solids()) == 1
    assert part.build_for_print().BoundingBox().zmin == pytest.approx(0, abs=1e-6)


def test_axis_height_edit_moves_engine_and_recuts_the_stand_seat(turbofan):
    from turbofan.assembly import make_assembly
    from turbofan.dimensions import EngineDimensions

    default = make_assembly()
    engine = replace(EngineDimensions(), axis_height=120)
    raised = make_assembly(engine=engine)
    default_locations, raised_locations = default.locations(), raised.locations()
    for name in raised.instances:
        before = positioned_point(default_locations[name])
        after = positioned_point(raised_locations[name])
        delta_z = 0 if name in {"display-base", "front-saddle", "rear-saddle"} else 12
        assert after == pytest.approx((before[0], before[1], before[2] + delta_z)), name

    for saddle_name, shell_name in (
        ("front-saddle", "nacelle-front-lower"),
        ("rear-saddle", "nacelle-rear-lower"),
    ):
        before = default.instances[saddle_name].part.build()
        saddle = raised.instances[saddle_name].part.build()
        assert saddle.BoundingBox().zmax - before.BoundingBox().zmax == pytest.approx(12)
        installed_saddle = saddle.moved(raised_locations[saddle_name])
        shell = raised.instances[shell_name].part.build().moved(raised_locations[shell_name])
        assert installed_saddle.distance(shell) == pytest.approx(0, abs=1e-6)
        assert installed_saddle.intersect(shell).Volume() == pytest.approx(0, abs=1e-6)


def test_blade_count_edit_changes_fan_geometry_and_published_parameters(turbofan):
    from turbofan.assemblies.low_pressure.dimensions import Dimensions
    from turbofan.assemblies.low_pressure.fan import make_fan
    from turbofan.dimensions import EngineDimensions, LOW_PRESSURE_FIT

    default_dimensions = Dimensions()
    fewer_blades = replace(default_dimensions, fan_blade_count=16)
    original = make_fan(default_dimensions, LOW_PRESSURE_FIT).build()
    changed = make_fan(fewer_blades, LOW_PRESSURE_FIT).build()
    assert changed.isValid() and len(changed.Solids()) == 1
    assert changed.Volume() < original.Volume()
    assert changed.BoundingBox().xlen == pytest.approx(original.BoundingBox().xlen)

    project = turbofan.make_project(
        engine=EngineDimensions(axis_height=120),
        low_pressure=fewer_blades,
    )
    parameters = {parameter.name: parameter for parameter in project.parameters}
    assert parameters["low-pressure.fan_blade_count"].value == 16
    assert parameters["engine.axis_height"].value == 120
    assert all(Path(parameter.source).is_file() for parameter in project.parameters)
    assert "low-pressure.coupling_socket_width" not in parameters
    # Compiling another variant leaves the original entry point unchanged.
    original_parameters = {
        parameter.name: parameter.value for parameter in turbofan.PROJECT.parameters
    }
    assert original_parameters["low-pressure.fan_blade_count"] == 20
    assert original_parameters["engine.axis_height"] == 108
