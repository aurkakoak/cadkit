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
SUBSYSTEMS = {"stand", "housing", "core", "low-pressure", "high-pressure"}


def leaves_by_path(assembly):
    return {
        f"{unit_name}/{name}": instance
        for unit_name, unit in assembly.instances.items()
        for name, instance in unit.part.instances.items()
    }


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
    home = assembly.locations(names="path")
    posed = assembly.locations(pose=pose, names="path")
    leaves = leaves_by_path(assembly)
    assert home.keys() == posed.keys() == leaves.keys()
    assert {
        leaves[path].part.name for path in home if path.startswith("low-pressure/")
    } == LP_PARTS
    assert {
        leaves[path].part.name for path in home if path.startswith("high-pressure/")
    } == HP_PARTS
    for path, location in home.items():
        name = leaves[path].part.name
        x, y, z = positioned_point(location)
        angle = lp_angle if name in LP_PARTS else hp_angle if name in HP_PARTS else 0
        theta = radians(angle)
        height = EngineDimensions().axis_height
        expected = (
            x,
            y * cos(theta) - (z - height) * sin(theta),
            height + y * sin(theta) + (z - height) * cos(theta),
        )
        assert positioned_point(posed[path]) == pytest.approx(expected), path


def test_open_view_removes_covers_without_losing_optional_manufacturing_parts(turbofan):
    from turbofan.assembly import make_assembly

    closed, opened = turbofan.PROJECT, turbofan.OPEN_PROJECT
    for project in (closed, opened):
        assert len(project.parts) == 39
        assert len(project.select()) == 36
        assert all(part.quantity == 1 for part in project.parts)
        assert {part.name for part in project.parts if not part.production} == COVERS
        assert {part.name for part in project.select(tuple(sorted(COVERS)))} == COVERS
    assembly = make_assembly()
    opened_assembly = make_assembly(covers=False)
    assert set(assembly.instances) == set(opened_assembly.instances) == SUBSYSTEMS
    assert set(assembly.locations()) == SUBSYSTEMS
    closed_leaves, open_leaves = leaves_by_path(assembly), leaves_by_path(opened_assembly)
    assert len(closed_leaves) == 39
    assert len(open_leaves) == 36
    assert set(closed_leaves) - set(open_leaves) == {f"housing/{name}" for name in COVERS}
    for path, instance in closed_leaves.items():
        assert instance.group == instance.part.group, path
    assert {item.group for item in closed_leaves.values()} == {
        "Display",
        "Casing",
        "Covers",
        "Static core",
        "Combustor",
        "LP spool",
        "HP spool",
    }


def test_contacts_resolve_to_scoped_leaves_across_and_within_subsystems(turbofan):
    from turbofan.assembly import make_assembly

    for project, covers, expected_count in (
        (turbofan.PROJECT, True, 18),
        (turbofan.OPEN_PROJECT, False, 15),
    ):
        paths = {
            f"/{project.name}/{path}"
            for path in leaves_by_path(make_assembly(covers=covers))
        }
        assert len(project.interfaces) == expected_count
        assert all(set(interface.components) <= paths for interface in project.interfaces)
        contact_pairs = {
            frozenset(interface.components)
            for interface in project.interfaces
            if interface.kind == "contact"
        }
        for left, right in (
            ("stand/front-saddle", "housing/nacelle-front-lower"),
            ("core/front-bypass-support", "housing/nacelle-front-lower"),
            ("stand/display-base", "stand/front-saddle"),
            ("core/front-bypass-support", "core/core-cutaway"),
        ):
            pair = frozenset((f"/{project.name}/{left}", f"/{project.name}/{right}"))
            assert pair in contact_pairs


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
    default_locations = default.locations(names="path")
    raised_locations = raised.locations(names="path")
    for path in raised_locations:
        before = positioned_point(default_locations[path])
        after = positioned_point(raised_locations[path])
        delta_z = 0 if path.startswith("stand/") else 12
        assert after == pytest.approx((before[0], before[1], before[2] + delta_z)), path

    for saddle_name, shell_name in (
        ("front-saddle", "nacelle-front-lower"),
        ("rear-saddle", "nacelle-rear-lower"),
    ):
        before = default.instances["stand"].part.instances[saddle_name].part.build()
        saddle = raised.instances["stand"].part.instances[saddle_name].part.build()
        assert saddle.BoundingBox().zmax - before.BoundingBox().zmax == pytest.approx(12)
        installed_saddle = saddle.moved(raised_locations[f"stand/{saddle_name}"])
        shell_part = raised.instances["housing"].part.instances[shell_name].part
        shell = shell_part.build().moved(raised_locations[f"housing/{shell_name}"])
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
