import json
import sys
from types import SimpleNamespace
import cadquery as cq
import cadkit as ck
import pytest
from cadkit.cli import load_project, main
from cadkit.export import build


def fixture():
    def make(base, width):
        a = ck.Assembly("fixture")
        names = ("shell",) if base == "printed" else ("top", "bottom", "skirt")
        for i, name in enumerate(names):
            p = ck.Part(
                name,
                lambda: cq.Workplane("XY").box(10 if width == "small" else 20, 10, 2),
                ck.FDM("PLA"),
            )
            a.fix(a.add(name, p), at=ck.Frame((0, 0, i * 5)))
        return a.as_project()

    return ck.Variants(
        make,
        choices={
            "base": ck.Variant(("printed", "hybrid"), default="printed", label="Base"),
            "width": ck.Variant(("small", "large"), default="small"),
        },
    )


def test_selection_rebuilds_inventory_and_leaves_previous_snapshot_intact(monkeypatch):
    variants = fixture()
    original = variants.project()
    monkeypatch.setitem(
        sys.modules, "variant_fixture", SimpleNamespace(PROJECT=original)
    )
    hybrid = load_project("variant_fixture:PROJECT", {"base": "hybrid"})
    assert isinstance(hybrid, ck.Project)
    assert [p.name for p in original.parts] == ["shell"]
    assert [p.name for p in hybrid.parts] == ["top", "bottom", "skirt"]
    assert hybrid.describe()["variant_selection"] == {
        "base": "hybrid",
        "width": "small",
    }
    assert hybrid.get_components()[0].model.Volume() == pytest.approx(200)
    assert variants.project(base="hybrid", width="large").get_components()[
        0
    ].model.Volume() == pytest.approx(400)
    with pytest.raises(TypeError):
        hybrid.variant_selection["base"] = "printed"


def test_rejects_invalid_choices_and_plain_project_selection():
    from cadkit.variants import select_variants, parse_variants

    with pytest.raises(ValueError, match="default"):
        ck.Variant(("a",), default="b")
    with pytest.raises(ValueError, match="Unknown"):
        fixture().project(base="missing")
    with pytest.raises(ValueError, match="Unknown"):
        fixture().project(missing="a")
    plain = ck.Assembly("plain").as_project()
    assert select_variants(plain, {}) is plain
    with pytest.raises(ValueError, match="no variants"):
        select_variants(plain, {"base": "a"})
    with pytest.raises(ValueError):
        parse_variants(["base=a", "base=b"])


def test_cli_and_export_record_selected_configuration(tmp_path, capsys):
    original = fixture().project()
    assert main(["--variant", "base=hybrid", "describe"], project=original) == 0
    description = json.loads(capsys.readouterr().out)
    assert len(description["parts"]) == 3
    assert description["variant_selection"]["base"] == "hybrid"
    hybrid = fixture().project(base="hybrid")
    manifest = build(hybrid, hybrid.select(), tmp_path)
    assert manifest["variant_selection"] == dict(hybrid.variant_selection)
    assert {p["name"] for p in manifest["parts"]} == {"top", "bottom", "skirt"}


def test_choices_are_declared_locally_and_scoped_to_installed_assembly():
    def subsystem():
        a = ck.Assembly("local-name")
        choice = a.variant("base", ck.Variant(("printed", "hybrid"), default="printed"))
        p = ck.Part(choice, lambda: cq.Workplane("XY").box(2, 2, 2), ck.FDM("PLA"))
        a.fix(a.add(p))
        return a

    def build():
        a = ck.Assembly("machine")
        a.fix(a.add("base", subsystem()))
        return a.as_project()

    variants = ck.Variants(build)
    printed = variants.project()
    hybrid = variants.project(base="hybrid")
    assert hybrid.describe()["variants"]["base"]["scope"] == "/machine/base"
    assert [p.name for p in printed.parts] == ["printed"]
    assert [p.name for p in hybrid.parts] == ["hybrid"]
    assert variants.project().variant_selection["base"] == "printed"
    with pytest.raises(ValueError, match="Unknown option"):
        variants.project(base="missing")
    with pytest.raises(ValueError, match="Unknown variants"):
        variants.project(unknown="printed")
    assert variants.project().variant_selection["base"] == "printed"


def test_repeated_assembly_choices_require_distinct_keys():
    def build():
        a = ck.Assembly("machine")
        for name in ("left", "right"):
            child = ck.Assembly(name)
            child.variant("base", ck.Variant(("a", "b"), default="a"))
            a.fix(a.add(child))
        return a.as_project()

    with pytest.raises(ValueError, match="multiple assemblies"):
        ck.Variants(build).project()
