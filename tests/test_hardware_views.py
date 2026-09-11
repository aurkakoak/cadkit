"""Located hardware must survive default CLI display options."""
import json

import cadquery as cq
import pytest

from cadkit import Assembly, Component, FastenerSite, FastenerSpec, Fastening, HardwareItem, Project
from cadkit.cli import main


@pytest.fixture
def project():
    def components(*, include_hardware=True, angle=0):
        return [
            Component("a", cq.Solid.makeBox(10, 10, 10), "body"),
            Component("b", cq.Solid.makeBox(10, 10, 10).translate((20, 0, 0)), "body"),
        ]

    return Project(
        "fixture", (), components,
        assembly=lambda **options: Assembly("fixture", tuple(components(**options))),
        views={"alternate": components},
        fastenings=(Fastening(
            "mount", ("a", "b"), sites=(FastenerSite("one", (50, 0, 0)),),
            hardware=(HardwareItem("screw", FastenerSpec(
                "socket_head_cap_screw", "M3-0.5", length_mm=10,
            )),),
        ),),
    )


@pytest.mark.parametrize("method", ["get_components", "get_assembly"])
@pytest.mark.parametrize("view, options, hardware_count", [
    (None, {}, 1),
    (None, {"include_hardware": True}, 1),
    (None, {"include_hardware": False}, 0),
    (None, {"angle": 5}, 0),
    (None, {"include_hardware": True, "angle": 5}, 0),
    ("alternate", {"include_hardware": True}, 0),
])
def test_hardware_visibility_preserves_only_the_authored_pose(project, method, view, options, hardware_count):
    result = getattr(project, method)(view, **options)
    components = list(result.components()) if isinstance(result, Assembly) else result
    hardware = [component for component in components if component.metadata.get("role") == "fastener"]
    assert len(hardware) == hardware_count
    assert len(components) == 2 + hardware_count
    if hardware:
        bounds = hardware[0].model.BoundingBox()
        assert bounds.xmin > 40
        assert bounds.zmax == pytest.approx(10)


def test_cli_step_export_includes_hardware_unless_printed_only(project, tmp_path):
    installed = tmp_path / "installed.step"
    printed = tmp_path / "printed.step"
    assert main(["assembly", "--output", str(installed)], project=project) == 0
    assert main(["assembly", "--printed-only", "--output", str(printed)], project=project) == 0
    installed_solids = cq.importers.importStep(str(installed)).val().Solids()
    printed_solids = cq.importers.importStep(str(printed)).val().Solids()
    assert len(installed_solids) == 3
    assert len(printed_solids) == 2
    assert sum(solid.BoundingBox().xmin > 40 for solid in installed_solids) == 1
    assert all(solid.BoundingBox().xmax <= 30 for solid in printed_solids)


def test_cli_render_assets_include_hardware_unless_printed_only(project, tmp_path):
    for printed_only in (False, True):
        destination = tmp_path / ("printed" if printed_only else "installed")
        args = ["render-assets", "--output-dir", str(destination)]
        if printed_only:
            args.append("--printed-only")
        assert main(args, project=project) == 0
        components = json.loads((destination / "scene.json").read_text())["components"]
        hardware = [component for component in components if component["group"] == "Hardware"]
        assert len(hardware) == (0 if printed_only else 1)
        assert len(components) == (2 if printed_only else 3)
        for component in components:
            assert (destination / component["file"]).stat().st_size > 0
