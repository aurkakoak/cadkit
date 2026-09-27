import math

import cadquery as cq
import pytest

from cadkit.inspection import drawing
from cadkit.geometry import mesh
from cadkit.desktop import Session
from cadkit._project import Component, Project


def test_native_section_preserves_holes_and_installed_coordinates():
    ring = (
        cq.Workplane("XY").circle(10).circle(5).extrude(8).val().translate((20, 30, 40))
    )
    session = Session(
        Project("fixture", (), lambda: [Component("ring", ring, "fixture")])
    )
    scene = session.scene()
    id = scene["components"][0]["id"]
    result = session.section_view(scene["revision"], [id], offset=44)
    assert result["method"] == "native-section"
    lines = result["components"][0]["lines"]
    assert len(lines) == 2
    assert sorted(
        math.hypot(line[0][0] - 20, line[0][1] - 30) for line in lines
    ) == pytest.approx([5, 10])
    assert all(line[0] == line[-1] for line in lines)
    assert result["bounds"][0] == pytest.approx([10, 20], abs=0.05)
    assert result["bounds"][1] == pytest.approx([30, 40], abs=0.05)
    assert session.section_view(scene["revision"], [id], offset=60)["bounds"] is None
    with pytest.raises(ValueError, match="older build"):
        session.section_view("old", [id])


@pytest.mark.parametrize(
    "plane,offset,lo,hi",
    [
        ("XY", 35, [10, 20], [12, 24]),
        ("XZ", 22, [10, 30], [12, 36]),
        ("YZ", 11, [20, 30], [24, 36]),
    ],
)
@pytest.mark.parametrize("mode", ["section", "projection"])
def test_axis_mapping_and_projection(plane, offset, lo, hi, mode):
    block = (
        cq.Workplane("XY").box(2, 4, 6, centered=False).val().translate((10, 20, 30))
    )
    result = drawing(
        {"block": block},
        {"block": {"name": "block"}},
        ["block"],
        plane=plane,
        offset=offset,
        mode=mode,
    )
    assert result["bounds"][0] == pytest.approx(lo)
    assert result["bounds"][1] == pytest.approx(hi)
    assert result["frame"] == "installed"


def test_section_rejects_meshes_and_invalid_requests():
    block = cq.Workplane("XY").box(2, 4, 6).val()
    models, metadata = {"a": block, "mesh": mesh(block)}, {"a": {"name": "a"}}
    for args, message in [
        ({"ids": ["missing"]}, "Unknown"),
        ({"ids": ["mesh"]}, "native"),
        ({"ids": ["a", "a"]}, "distinct"),
        ({"ids": ["a"], "offset": math.inf}, "finite"),
    ]:
        with pytest.raises(ValueError, match=message):
            drawing(models, metadata, **args)
