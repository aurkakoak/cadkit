"""CLI fabrication views distinguish manufactured parts from reference hardware."""
import json

import cadquery as cq
import pytest

import cadkit as ck
from cadkit.cli import main


@pytest.fixture
def project():
    block = ck.Part("block", lambda: cq.Solid.makeBox(10, 10, 10), ck.FDM("PETG"))
    reference = ck.Purchased("motor", lambda: cq.Solid.makeBox(4, 4, 4))
    assembly = ck.Assembly("fixture")
    assembly.fix(assembly.add("a", block))
    assembly.fix(assembly.add("b", block), at=ck.Frame((20, 0, 0)))
    assembly.fix(assembly.add("motor", reference), at=ck.Frame((70, 0, 0)))
    return assembly.as_project(fastenings=(ck.Fastening(
        "mount", ("a", "b"), sites=(ck.FastenerSite("one", (50, 0, 0)),),
        hardware=(ck.HardwareItem("screw", ck.FastenerSpec(
            "socket_head_cap_screw", "M3-0.5", length_mm=10,
        )),),
    ),))


@pytest.mark.parametrize("method", ["get_components", "get_assembly"])
@pytest.mark.parametrize("options, hardware_count", [
    ({}, 1),
    ({"include_hardware": True}, 1),
    ({"include_hardware": False}, 0),
])
def test_hardware_visibility_keeps_purchased_references(project, method, options, hardware_count):
    result = getattr(project, method)(**options)
    components = list(result.components()) if method == "get_assembly" else result
    hardware = [component for component in components if component.metadata.get("role") == "fastener"]
    assert len(hardware) == hardware_count
    assert len(components) == 3 + hardware_count
    assert sum(component.part == "block" for component in components) == 2
    assert any(component.name == "motor" and component.part is None for component in components)
    if hardware:
        bounds = hardware[0].model.BoundingBox()
        assert bounds.xmin > 40
        assert bounds.zmax == pytest.approx(10)


def test_cli_step_export_printed_only_excludes_purchased_and_generated_hardware(project, tmp_path):
    installed = tmp_path / "installed.step"
    printed = tmp_path / "printed.step"
    assert main(["assembly", "--output", str(installed)], project=project) == 0
    assert main(["assembly", "--printed-only", "--output", str(printed)], project=project) == 0
    installed_solids = cq.importers.importStep(str(installed)).val().Solids()
    printed_solids = cq.importers.importStep(str(printed)).val().Solids()
    assert len(installed_solids) == 4
    assert len(printed_solids) == 2
    assert sum(solid.BoundingBox().xmin > 40 for solid in installed_solids) == 2
    assert all(solid.BoundingBox().xmax <= 30 for solid in printed_solids)
    assert sum(solid.Volume() for solid in printed_solids) == pytest.approx(2000)


@pytest.mark.parametrize("printed_only", [False, True])
def test_cli_render_assets_printed_only_excludes_purchased_and_generated_hardware(project, tmp_path, printed_only):
    args = ["render-assets", "--output-dir", str(tmp_path)]
    if printed_only:
        args.append("--printed-only")
    assert main(args, project=project) == 0
    components = json.loads((tmp_path / "scene.json").read_text())["components"]
    hardware = [component for component in components if component["group"] == "Hardware"]
    assert len(hardware) == (0 if printed_only else 1)
    assert len(components) == (2 if printed_only else 4)
    assert ("motor" in {component["name"] for component in components}) is not printed_only
    if printed_only:
        assert {component["name"] for component in components} == {"a", "b"}
    for component in components:
        assert (tmp_path / component["file"]).stat().st_size > 0
