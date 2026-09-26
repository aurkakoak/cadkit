"""Immutable design inputs backed by standard Python dataclasses."""
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
import inspect
import math
import operator
from pathlib import Path
from typing import Any, dataclass_transform, get_type_hints

from .._project import Parameter


_METADATA_KEY = "cadkit.input"
_COMPARISONS = {"gt": operator.gt, "ge": operator.ge, "lt": operator.lt, "le": operator.le}


@dataclass(frozen=True)
class _Input:
    unit: str
    description: str
    limits: tuple


# Like dataclasses.field, this placeholder is typed as Any for annotated fields.
def input(default: Any = MISSING, *, unit="", description="", gt=None, ge=None, lt=None, le=None) -> Any:
    """Declare a scalar design input on a frozen, keyword-only dataclass.

    Args:
        default (float | int | bool | str): Default Python value. Omit it to
            require a constructor argument.
        unit (str): Display unit, such as `mm` or `deg`; no conversion is performed.
        description (str): What this input controls.
        gt (float | int | None): Exclusive lower bound for a numeric input.
        ge (float | int | None): Inclusive lower bound for a numeric input.
        lt (float | int | None): Exclusive upper bound for a numeric input.
        le (float | int | None): Inclusive upper bound for a numeric input.

    Returns:
        (dataclasses.Field): A standard field carrying CadKit input metadata.

    Raises:
        TypeError: Units or descriptions are not strings, or bounds are not numbers.
        ValueError: A bound is nonfinite or the bounds define an empty interval.

    Annotate each input as `float`, `int`, `bool`, or `str`. Numeric bounds apply
    only to float and int fields. Values are validated when Dimensions is built;
    they are never coerced. Derived values belong in ordinary Python properties.
    """
    if not isinstance(unit, str) or not isinstance(description, str):
        raise TypeError("Input unit and description must be strings")
    limits = tuple((name, value) for name, value in
                   (("gt", gt), ("ge", ge), ("lt", lt), ("le", le)) if value is not None)
    for name, value in limits:
        if type(value) not in (int, float):
            raise TypeError(f"Input {name} bound must be a number, excluding bool")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Input {name} bound must be finite")
    for lower_name, lower in limits:
        if lower_name not in ("gt", "ge"):
            continue
        for upper_name, upper in limits:
            if upper_name in ("lt", "le") and (
                lower > upper or lower == upper and (lower_name == "gt" or upper_name == "lt")
            ):
                raise ValueError("Input bounds define an empty interval")
    return field(default=default, metadata={_METADATA_KEY: _Input(unit, description, limits)})


def _input_fields(cls):
    if not is_dataclass(cls) or "__dataclass_fields__" not in cls.__dict__:
        raise TypeError(f"{cls.__name__} must use @dataclass(frozen=True, kw_only=True)")
    if not cls.__dataclass_params__.frozen:
        raise TypeError(f"{cls.__name__} must be a frozen dataclass")
    try:
        annotations = get_type_hints(cls)
    except (NameError, TypeError) as exc:
        raise TypeError(f"{cls.__name__}: cannot resolve input annotations: {exc}") from exc
    result = []
    for member in fields(cls):
        label = f"{cls.__name__}.{member.name}"
        if not member.kw_only:
            raise TypeError(f"{label}: Dimensions inputs must be keyword-only")
        if member.name in ("parameters", "validate"):
            raise TypeError(f"{label}: input name conflicts with a Dimensions method")
        specification = member.metadata.get(_METADATA_KEY)
        if not isinstance(specification, _Input):
            raise TypeError(f"{label}: declare every input with ck.input()")
        annotation = annotations.get(member.name)
        if annotation not in (float, int, bool, str):
            raise TypeError(f"{label}: unsupported annotation {annotation!r}; use float, int, bool or str")
        if specification.limits and annotation not in (float, int):
            raise TypeError(f"{label}: numeric bounds require a float or int annotation")
        result.append((member, specification, annotation))
    return result


def _source(cls, name):
    # Python 3.14 can store annotations lazily, outside the class dictionary.
    # get_annotations also keeps this lookup local to each declaring class.
    owner = next((base for base in cls.__mro__ if name in inspect.get_annotations(base)), None)
    if owner is None:
        return ""
    try:
        filename = inspect.getsourcefile(owner)
        return str(Path(filename).resolve()) if filename and Path(filename).is_file() else ""
    except (TypeError, OSError):
        return ""


@dataclass_transform(kw_only_default=True, frozen_default=True, field_specifiers=(input,))
class Dimensions:
    """Base for validated, immutable scalar design configurations.

    Subclass this with `@dataclass(frozen=True, kw_only=True)`, annotate every
    instance field and declare it with `cadkit.input()`. Supported annotations
    are float, int, bool and str. Floats accept Python ints as well as floats;
    other types are exact, booleans are not numbers, and floats must be finite.

    Override `validate()` for engineering relationships between inputs. Do not
    override `__post_init__`: it performs common validation before calling that
    hook. Ordinary properties can calculate derived dimensions without becoming
    inputs. Class variables are also excluded from parameter metadata.

    Use `dataclasses.replace(configuration, field=value)` for a new validated
    configuration, then rebuild the parts or project from it. Dimensions has no
    mutable controls, dependency graph, unit conversion or geometry cache.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__post_init__", None) is not Dimensions.__post_init__:
            raise TypeError("Dimensions subclasses must override validate(), not __post_init__()")

    def __init__(self, *args, **kwargs):
        raise TypeError("Dimensions subclasses must use @dataclass(frozen=True, kw_only=True)")

    def __post_init__(self):
        for member, specification, annotation in _input_fields(type(self)):
            value = getattr(self, member.name)
            label = f"{type(self).__name__}.{member.name}"
            valid_type = type(value) in (int, float) if annotation is float else type(value) is annotation
            if not valid_type:
                raise TypeError(f"{label} must be {annotation.__name__}; got {type(value).__name__}")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{label} must be finite")
            for comparison, limit in specification.limits:
                if not _COMPARISONS[comparison](value, limit):
                    raise ValueError(f"{label} must satisfy {comparison} {limit}; got {value}")
        self.validate()

    def validate(self):
        """Check relationships between already validated inputs.

        Override this method and raise ValueError for invalid engineering
        combinations. When extending another Dimensions subclass, call its
        `super().validate()` if its additional constraints still apply.
        """

    def parameters(self, scope="") -> tuple[Parameter, ...]:
        """Describe inputs using CadKit's existing Parameter records.

        Args:
            scope (str): Optional name prefix, such as `bearing` or `left.bearing`.
                A field called `shaft_diameter` becomes `bearing.shaft_diameter`.

        Returns:
            (tuple[cadkit.Parameter, ...]): Fields in dataclass order, with current
                values, units, descriptions and their declaring class's source file.
                Source is an empty string when no existing source file is available.

        Derived properties are not evaluated or published. Names retain their
        underscores. These records describe a configuration; they do not provide
        setters, live UI controls or automatic rebuilding.
        """
        if not isinstance(scope, str):
            raise TypeError("Parameter scope must be a string")
        prefix = f"{scope}." if scope else ""
        return tuple(
            Parameter(prefix + member.name, getattr(self, member.name), specification.unit,
                      specification.description, _source(type(self), member.name))
            for member, specification, _ in _input_fields(type(self))
        )
