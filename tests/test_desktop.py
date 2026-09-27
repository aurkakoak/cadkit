import cadquery as cq
import pytest

from cadkit._project import Assembly, Component, Part, Project
from cadkit.desktop import Session
from cadkit.geometry import mesh

pytest.importorskip("ocp_tessellate")


def fixture_project(mesh_second=False):
    first = cq.Workplane("XY").box(10, 10, 10).val()
    second = first.translate((15, 0, 0))
    if mesh_second:
        second = mesh(second)
    a = Component("block", first, "fixture", part="block")
    b = Component("other", second, "fixture")
    tree = Assembly("fixture", (Assembly("left", (a,)), Assembly("right", (b,))))
    return Project(
        "fixture",
        (Part("block", lambda: first, "fixture"),),
        lambda: [a, b],
        assembly=lambda: tree,
    )


def test_hierarchy_preserves_instances_and_part_metadata():
    session = Session(fixture_project())
    scene = session.scene()
    assert scene["tree"]["children"][0]["children"][0]["part"] == "block"
    assert [c["id"] for c in scene["components"]] == [
        "/fixture/left/block",
        "/fixture/right/other",
    ]
    assert scene["shapes"]["bb"]["xmax"] == pytest.approx(20)
    assert scene["components"][0]["volume_mm3"] == pytest.approx(1000)
    # The nested conversion keeps rendered geometry and metadata in the same coordinates.
    leaf = scene["shapes"]["parts"][1]["parts"][0]
    assert leaf["id"] == "/fixture/right/other"
    assert len(leaf["shape"]["face_types"]) == 6


def test_shared_geometry_is_meshed_once_with_distinct_placements_and_colors():
    first = cq.Workplane("XY").box(10, 20, 30).val()
    location = cq.Location((40, 50, 60), (0, 0, 1), 90)
    second = first.moved(location)
    nodes = (Component("first", first, "fixture", color=(1, 0, 0)),
             Component("second", second, "fixture", color=(0, 1, 0)))
    project = Project("fixture", (), lambda: nodes)
    session = Session(project)
    scene = session.scene()
    a, b = scene["shapes"]["parts"][0]["parts"]
    assert a["shape"] is b["shape"]
    assert a["color"] != b["color"]
    assert a["id"] != b["id"]
    # Verify rendered vertex placement independently of native measurements.
    from ocp_tessellate.ocp_utils import tq_to_loc
    import numpy as np
    transform = cq.Matrix(tq_to_loc(*b["loc"]).Transformation())
    vertices = np.asarray([cq.Vector(*v).transform(transform).toTuple()
                           for v in b["shape"]["vertices"].reshape(-1, 3)])
    assert vertices.min(axis=0) == pytest.approx(scene["components"][1]["bounds"][0])
    assert vertices.max(axis=0) == pytest.approx(scene["components"][1]["bounds"][1])
    assert session.models[scene["components"][1]["id"]].isSame(second)
    assert scene["performance"]["unique_native_shapes"] == 1
    assert scene["performance"]["native_component_count"] == 2
    assert session.scene() is scene


def test_scene_timings_cover_build_and_preserve_cached_report():
    session = Session(fixture_project())
    scene = session.scene()
    report = scene["performance"]
    assert all(value >= 0 for value in report["stages_seconds"].values())
    assert report["stages_seconds"]["scene"] >= report["stages_seconds"]["assembly"]
    assert {"assembly", "convert", "tessellate", "bounds", "volume", "describe", "mechanics"} <= report["stages_seconds"].keys()
    assert session.scene()["performance"] == report


@pytest.mark.parametrize("mesh_second", [False, True])
def test_transport_roundtrips_viewer_buffers_and_preserves_native_snapshot(mesh_second):
    import base64
    import json
    import numpy as np
    from cadkit.desktop import json_default
    session = Session(fixture_project(mesh_second))
    original = session.scene()
    wire = session.scene_for_transport()
    assert session.scene_for_transport() is wire
    assert session.scene() is original
    assert wire["shapes"] is not original["shapes"]
    assert wire["components"] == original["components"]
    packed = json.loads(json.dumps(wire, default=json_default))["shapes"]

    def compare(before, after):
        assert before["id"] == after["id"]
        assert json.loads(json.dumps(before.get("loc"))) == after.get("loc")
        if "shape" in before:
            assert "ref" not in before["shape"]
            encoded = packed["instances"][after["shape"]["ref"]]
            for field, values in before["shape"].items():
                buffer = encoded[field]
                dtype = np.dtype(buffer["dtype"]).newbyteorder("<")
                assert buffer["codec"] == "b64"
                decoded = np.frombuffer(base64.b64decode(buffer["buffer"]), dtype=dtype)
                np.testing.assert_array_equal(decoded, np.asarray(values, dtype=dtype).ravel())
        for child, packed_child in zip(before.get("parts", []), after.get("parts", [])):
            compare(child, packed_child)

    compare(original["shapes"], packed["shapes"])


def test_transport_keeps_partial_edge_buffers_inline():
    edge = Component("edge", cq.Edge.makeLine((0, 0, 0), (10, 0, 0)), "fixture")
    session = Session(Project("fixture", (), lambda: [edge]))
    packed = session.scene_for_transport()["shapes"]
    leaf = packed["shapes"]["parts"][0]["parts"][0]
    assert leaf["type"] == "edges"
    assert "ref" not in leaf["shape"]
    assert leaf["shape"]["edges"]["dtype"] == "float32"


def test_packed_transport_rejects_nonfinite_display_buffers():
    import numpy as np
    from cadkit.desktop import encode_scene
    with pytest.raises(ValueError, match="Non-finite vertices"):
        encode_scene({"type": "shapes", "shape": {"vertices": np.array([float("nan"), 0, 0])}})


@pytest.mark.parametrize("mesh_second", [False, True])
def test_distance_uses_world_coordinates_and_discloses_mesh_boundary(mesh_second):
    session = Session(fixture_project(mesh_second))
    scene = session.scene()
    result = session.measure(scene["revision"], [c["id"] for c in scene["components"]])
    assert result["minimum_mm"] == pytest.approx(5)
    assert result["center_distance_mm"] == pytest.approx(15)
    assert result["center_delta_mm"] == pytest.approx([15, 0, 0])
    assert result["method"] == ("mesh" if mesh_second else "native")
    if not mesh_second:
        assert cq.Vector(*result["points"][0]).sub(
            cq.Vector(*result["points"][1])
        ).Length == pytest.approx(5)


def test_stale_or_invalid_selection_is_rejected():
    session = Session(fixture_project())
    scene = session.scene()
    ids = [c["id"] for c in scene["components"]]
    with pytest.raises(ValueError, match="older build"):
        session.measure("stale", ids)
    with pytest.raises(ValueError, match="different"):
        session.measure(scene["revision"], [ids[0], ids[0]])
    with pytest.raises(ValueError, match="Unknown"):
        session.measure(scene["revision"], [ids[0], "/missing"])


def test_duplicate_sibling_names_are_rejected():
    component = Component("same", cq.Workplane("XY").box(1, 1, 1), "fixture")
    with pytest.raises(ValueError, match="Duplicate child"):
        Assembly("root", (component, component))


def test_export_uses_part_print_pose_not_installed_pose(tmp_path):
    session = Session(fixture_project())
    session.export_part("block", tmp_path)
    imported = cq.importers.importStep(str(tmp_path / "block.step")).val()
    assert imported.BoundingBox().zmin == pytest.approx(0)
    assert imported.Volume() == pytest.approx(1000)


def test_existing_flat_projects_get_a_grouped_tree():
    project = fixture_project()
    project.assembly = None
    tree = project.get_assembly()
    assert [child.name for child in tree.children] == ["fixture"]
    assert len(list(tree.components())) == 2


def test_batch_export_for_slicing_checks_revision_and_print_pose(tmp_path):
    model = cq.Workplane("XY").box(10, 20, 30)
    part = Part("block", lambda: model, "fixture", quantity=2, print_rotation=(90, 0, 0))
    session = Session(Project("fixture", (part,), lambda: [Component("block", model, "fixture")]))
    with pytest.raises(ValueError, match="older build"):
        session.export_parts("stale", ["block"], tmp_path)
    with pytest.raises(ValueError, match="distinct"):
        session.export_parts(session.revision, ["block", "block"], tmp_path)
    result = session.export_parts(session.revision, ["block"], tmp_path)
    assert result["manifest"]["parts"][0]["quantity"] == 2
    info = result["manifest"]["parts"][0]["bounds_mm"]
    assert info["min"][2] == pytest.approx(0)
    assert info["size"] == pytest.approx([10, 30, 20])


@pytest.mark.parametrize("mesh_second", [False, True])
def test_render_exports_captured_installed_selection(tmp_path, mesh_second, monkeypatch):
    session = Session(fixture_project(mesh_second))
    scene = session.scene()
    monkeypatch.setattr(type(session.project), "get_assembly", lambda _: pytest.fail("rebuilt"))
    result = session.render_assets(scene["revision"], ["/fixture/right/other"], tmp_path)
    assert len(result["components"]) == 1
    item = result["components"][0]
    assert item["name"] == "other"
    assert item["geometry"] == ("mesh" if mesh_second else "brep")
    import trimesh
    assert trimesh.load_mesh(tmp_path / item["file"]).bounds[0, 0] == pytest.approx(10)
    with pytest.raises(ValueError, match="Stale"):
        session.render_assets("old", ["/fixture/right/other"], tmp_path)
    with pytest.raises(ValueError, match="no explosion"):
        session.render_assets(scene["revision"], ["/fixture/right/other"], tmp_path, animation=True)


def test_viewer_tree_names_match_encoded_ids_for_nested_hardware_and_compounds():
    shape = cq.Workplane("XY").box(2, 2, 2).val()
    compound = cq.Compound.makeCompound([shape, shape.translate((5, 0, 0))])
    leaf = Component("screw", compound, "Hardware")
    tree = Assembly("fixture", (Assembly("base/top-mount", (leaf,)),))
    project = Project("fixture", (), lambda: [leaf], assembly=lambda: tree)
    snapshot = Session(project).scene()
    def check(node, parent=""):
        # three-cad-viewer's visibility tree indexes names, while its geometry
        # indexes IDs. Every tree path must address the same rendered group.
        path = parent + "/" + node["name"]
        assert node["id"] == path
        for child in node.get("parts", []):
            check(child, path)
    check(snapshot["shapes"])
    assert snapshot["tree"]["children"][0]["name"] == "base/top-mount"
