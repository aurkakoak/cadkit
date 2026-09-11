import json
from pathlib import Path
import cadquery as cq
import pytest
from cadkit import Project, Part, Component, Check
from cadkit.export import build, run_checks, export_render_assets
from cadkit.geometry import cube


def test_print_orientation_does_not_move_installed_component(tmp_path):
    original = cube((4, 6, 8)).translate((10, 20, 30))
    part = Part("test", lambda: original, "fixtures", print_rotation=(180, 0, 0))
    assert part.build().BoundingBox().zmin == pytest.approx(0)
    assert part.build(for_print=False).BoundingBox().zmin == pytest.approx(30)
    p = Project("fixture", (part,), lambda: [])
    manifest = build(p, [part], tmp_path)
    assert manifest["parts"][0]["sha256"]["step"]
    assert json.loads((tmp_path / "quantities.json").read_text()) == {"test": 1}
    assert json.loads((tmp_path / "subassemblies.json").read_text()) == {
        "fixtures": ["test"]
    }
    imported = cq.importers.importStep(str(tmp_path / "test.step")).val()
    assert imported.Volume() == pytest.approx(192)


def test_invalid_parts_do_not_export_and_names_are_safe(tmp_path):
    with pytest.raises(ValueError):
        Part("../bad", lambda: cube((1, 1, 1)), "test")
    part = Part(
        "two-solids",
        lambda: cube((1, 1, 1)).fuse(cube((1, 1, 1)).translate((5, 0, 0))),
        "test",
    )
    with pytest.raises(ValueError, match="expected 1 solid"):
        build(Project("test", (part,), lambda: []), [part], tmp_path)
    assert not list(tmp_path.glob("*.stl"))


def test_contacts_collisions_and_errors_are_distinct(tmp_path):
    a = cube((10, 10, 10))
    touching = cube((10, 10, 10)).translate((10, 0, 0))
    separate = touching.translate((1, 0, 0))
    checks = [
        Check(
            "touch",
            lambda: a.intersect(touching),
            True,
            contact_pair=lambda: (a, touching),
        ),
        Check(
            "missing",
            lambda: a.intersect(separate),
            True,
            contact_pair=lambda: (a, separate),
        ),
        Check("collision", lambda: a),
        Check("broken", lambda: 1 / 0),
    ]
    report = run_checks(checks, tmp_path)
    assert [x["passed"] for x in report] == [True, False, False, False]
    assert report[0]["gap_mm"] == 0
    assert report[1]["gap_mm"] == pytest.approx(1)
    assert (tmp_path / "collision.stl").exists()
    assert "error" in report[3]


def test_render_manifest_uses_installed_coordinates_and_explosion(tmp_path):
    c = Component(
        "installed",
        cube((5, 5, 5)).translate((0, 0, 50)),
        "machine",
        explode=(0, 0, 20),
    )
    data = export_render_assets([c], tmp_path, exploded=True)
    assert data["units"] == "mm"
    assert data["components"][0]["explosion_mm"] == (0, 0, 20)
    import trimesh

    assert trimesh.load_mesh(tmp_path / "installed.stl").bounds[0, 2] == pytest.approx(
        50
    )
