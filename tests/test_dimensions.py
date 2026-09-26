"""Typed immutable inputs, validation, and the metadata consumed by projects."""
from dataclasses import FrozenInstanceError, dataclass, fields, replace
from pathlib import Path
from typing import ClassVar

import cadkit as ck
import pytest


@dataclass(frozen=True, kw_only=True)
class BearingDimensions(ck.Dimensions):
    shaft_diameter: float = ck.input(
        default=8.0, unit="mm", description="Nominal shaft diameter", gt=0,
    )
    radial_clearance: float = ck.input(default=0.2, unit="mm", ge=0, lt=1)
    count: int = ck.input(default=2, ge=1, le=8)
    label: str = ck.input(default="bearing")
    enabled: bool = ck.input(default=True)
    category: ClassVar[str] = "bearings"

    @property
    def bore_diameter(self):
        return self.shaft_diameter + 2 * self.radial_clearance

    @property
    def expensive_measurement(self):
        raise AssertionError("Publishing inputs must not evaluate properties")

    def validate(self):
        if self.radial_clearance >= self.shaft_diameter / 2:
            raise ValueError("Clearance must be smaller than the shaft radius")


def test_metadata_comes_from_the_configuration_and_excludes_calculations():
    dimensions = BearingDimensions()
    parameters = dimensions.parameters(scope="left.bearing")
    assert [p.name for p in parameters] == [
        "left.bearing.shaft_diameter", "left.bearing.radial_clearance",
        "left.bearing.count", "left.bearing.label", "left.bearing.enabled",
    ]
    assert [p.value for p in parameters] == [8.0, 0.2, 2, "bearing", True]
    assert parameters[0].unit == "mm"
    assert parameters[0].description == "Nominal shaft diameter"
    assert all(isinstance(p, ck.Parameter) and not p.measured for p in parameters)
    assert all(Path(p.source).resolve() == Path(__file__).resolve() for p in parameters)
    assert dimensions.bore_diameter == pytest.approx(8.4)
    assert dimensions.parameters()[0].name == "shaft_diameter"
    assert [f.name for f in fields(dimensions)] == [
        "shaft_diameter", "radial_clearance", "count", "label", "enabled",
    ]


def test_variants_are_independent_and_project_metadata_is_a_value_snapshot():
    original = BearingDimensions()
    variant = replace(original, shaft_diameter=10, label="larger")
    assert variant.bore_diameter == pytest.approx(10.4)
    assert original.bore_diameter == pytest.approx(8.4)
    with pytest.raises(FrozenInstanceError):
        original.shaft_diameter = 12
    with pytest.raises(TypeError):
        BearingDimensions(10)

    project = ck.Assembly("metadata-example").as_project(
        parameters=original.parameters(scope="bearing"),
    )
    described = {p["name"]: p for p in project.describe()["parameters"]}
    assert described["bearing.shaft_diameter"]["value"] == 8.0
    assert variant.parameters()[0].value == 10


@pytest.mark.parametrize("overrides,field", [
    ({"shaft_diameter": 0}, "shaft_diameter"),
    ({"shaft_diameter": -1}, "shaft_diameter"),
    ({"shaft_diameter": float("nan")}, "shaft_diameter"),
    ({"shaft_diameter": float("inf")}, "shaft_diameter"),
    ({"radial_clearance": -0.1}, "radial_clearance"),
    ({"radial_clearance": 1}, "radial_clearance"),
    ({"count": 0}, "count"),
    ({"count": 9}, "count"),
])
def test_bad_numeric_inputs_fail_before_geometry(overrides, field):
    with pytest.raises(ValueError, match=field):
        BearingDimensions(**overrides)


@pytest.mark.parametrize("overrides,field", [
    ({"shaft_diameter": True}, "shaft_diameter"),
    ({"shaft_diameter": "8"}, "shaft_diameter"),
    ({"count": 2.5}, "count"),
    ({"count": True}, "count"),
    ({"enabled": 1}, "enabled"),
    ({"label": 10}, "label"),
])
def test_types_are_validated_without_implicit_coercion(overrides, field):
    with pytest.raises(TypeError, match=field):
        BearingDimensions(**overrides)


def test_bounds_and_cross_field_rules_apply_to_replacements_too():
    assert BearingDimensions(radial_clearance=0, count=8).count == 8
    with pytest.raises(ValueError, match="Clearance"):
        BearingDimensions(shaft_diameter=0.2)
    with pytest.raises(ValueError, match="shaft_diameter"):
        replace(BearingDimensions(), shaft_diameter=-2)


def test_required_fields_and_inheritance_keep_dataclass_behaviour():
    @dataclass(frozen=True, kw_only=True)
    class Variant(BearingDimensions):
        length: float = ck.input(unit="mm", gt=0)

    with pytest.raises(TypeError, match="length"):
        Variant()
    dimensions = Variant(length=30)
    assert dimensions.parameters()[-1].name == "length"
    assert replace(dimensions, length=40).length == 40
    assert dimensions.length == 30


def test_inherited_parameter_sources_point_to_the_declaring_module(tmp_path, monkeypatch):
    import sys
    from types import ModuleType

    sources = {
        "dimension_source_parent": (
            "from dataclasses import dataclass\n"
            "import cadkit as ck\n"
            "@dataclass(frozen=True, kw_only=True)\n"
            "class Parent(ck.Dimensions):\n"
            "    width: float = ck.input(10)\n"
            "    height: float = ck.input(20)\n"
        ),
        "dimension_source_child": (
            "from dimension_source_parent import Parent, dataclass, ck\n"
            "@dataclass(frozen=True, kw_only=True)\n"
            "class Child(Parent):\n"
            "    height: float = ck.input(30)\n"
        ),
    }
    for name, source in sources.items():
        filename = tmp_path / f"{name}.py"
        filename.write_text(source)
        module = ModuleType(name)
        module.__file__ = str(filename)
        monkeypatch.setitem(sys.modules, name, module)
        exec(compile(source, str(filename), "exec"), module.__dict__)

    dimensions = sys.modules["dimension_source_child"].Child()
    parameters = {p.name: p for p in dimensions.parameters()}
    assert parameters["width"].source == str(tmp_path / "dimension_source_parent.py")
    assert parameters["height"].source == str(tmp_path / "dimension_source_child.py")
    assert parameters["height"].value == 30


def test_schema_mistakes_cannot_silently_drop_inputs_or_validation():
    @dataclass(frozen=True, kw_only=True)
    class MissingDeclaration(ck.Dimensions):
        length: float = 10

    with pytest.raises(TypeError, match="length"):
        MissingDeclaration()

    @dataclass(frozen=True, kw_only=True)
    class MutableInput(ck.Dimensions):
        values: list = ck.input(default=None)

    with pytest.raises(TypeError, match="values"):
        MutableInput(values=[1, 2])

    with pytest.raises(TypeError, match="validate"):
        @dataclass(frozen=True, kw_only=True)
        class OverriddenLifecycle(ck.Dimensions):
            def __post_init__(self):
                pass


def test_configurations_require_frozen_keyword_only_dataclasses():
    @dataclass(kw_only=True)
    class MutableConfiguration(ck.Dimensions):
        length: float = ck.input(default=10)

    with pytest.raises(TypeError, match="frozen"):
        MutableConfiguration()

    @dataclass(frozen=True)
    class PositionalConfiguration(ck.Dimensions):
        length: float = ck.input(default=10)

    with pytest.raises(TypeError, match="keyword-only"):
        PositionalConfiguration()

    class Undecorated(ck.Dimensions):
        length: float = ck.input(default=10)

    with pytest.raises(TypeError, match="dataclass"):
        Undecorated()

    class UndecoratedChild(BearingDimensions):
        length: float = ck.input(default=10)

    with pytest.raises(TypeError, match="dataclass"):
        UndecoratedChild()


@pytest.mark.parametrize("bounds", [
    {"gt": float("nan")}, {"le": float("inf")}, {"ge": True},
    {"gt": 10, "le": 5}, {"ge": 2, "lt": 2},
])
def test_invalid_bound_declarations_are_rejected(bounds):
    with pytest.raises((TypeError, ValueError)):
        ck.input(default=1, **bounds)
