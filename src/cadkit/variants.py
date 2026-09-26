"""Discrete design choices resolved into ordinary, immutable project snapshots."""

from copy import copy
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from urllib.parse import quote
from ._project import Project
from .design.frames import name as valid_name

_selection = ContextVar("cadkit_variant_selection", default={})


def assembly_choice(assembly, key, choice, selected=None):
    valid_name(key)
    if not isinstance(choice, Variant):
        raise TypeError("Assembly variants need a Variant definition")
    if key in assembly._variant_choices:
        raise ValueError(f"Duplicate variant {key!r}")
    value = _selection.get().get(key, choice.default if selected is None else selected)
    if value not in choice.options:
        raise ValueError(f"Unknown option {value!r} for variant {key!r}")
    assembly._variant_choices[key] = (choice, value)
    return value


def bound_choices(project):
    result = {}

    def visit(assembly, path):
        for key, (choice, value) in assembly._variant_choices.items():
            if key in result:
                raise ValueError(
                    f"Variant key {key!r} belongs to multiple assemblies; use unique keys"
                )
            result[key] = (choice, value, path)
        for name, instance in assembly.instances.items():
            if hasattr(instance.part, "_variant_choices"):
                visit(instance.part, path + "/" + quote(name, safe=""))

    definition = getattr(project, "_definition", None)
    if definition is not None:
        visit(definition, "/" + quote(definition.name, safe=""))
    return result


@dataclass(frozen=True)
class Variant:
    """One independently selectable design choice, with stable option identifiers.

    ``label`` is an optional short UI label. Every option must be a nonempty
    identifier; defaults are explicit. Coupled alternatives belong in one choice.
    """

    options: tuple[str, ...]
    default: str
    label: str = ""

    def __post_init__(self):
        options = tuple(self.options)
        if not options or len(set(options)) != len(options):
            raise ValueError("Variant options must be nonempty and unique")
        for option in options:
            valid_name(option)
        if self.default not in options:
            raise ValueError("Variant default must be an option")
        object.__setattr__(self, "options", options)


class Variants:
    """Build a project from named choices without changing Assembly or Part APIs.

    ``builder`` returns a fresh Project and may declare choices locally using
    ``Assembly.variant``. Optional project-wide ``choices`` are passed as keyword
    arguments. ``project()`` resolves defaults; export its result as ``PROJECT``.
    Dependencies list additional input files/directories to watch (relative to the
    desktop project directory, or absolute). Geometry must depend only on source,
    declared inputs and choices; clocks/network state are not tracked.
    """

    def __init__(self, builder, *, choices=None, dependencies=()):
        if not callable(builder):
            raise ValueError("Variants requires a builder")
        choices = choices or {}
        for key, choice in choices.items():
            valid_name(key)
            if not isinstance(choice, Variant):
                raise TypeError("Choices must be Variant definitions")
        self.builder = builder
        self.choices = MappingProxyType(dict(choices))
        self.dependencies = tuple(str(Path(p)) for p in dependencies)

    def project(self, **selection):
        selected = {
            key: selection.get(key, choice.default)
            for key, choice in self.choices.items()
        }
        for key, value in selected.items():
            if value not in self.choices[key].options:
                raise ValueError(f"Unknown option {value!r} for variant {key!r}")
        token = _selection.set(selection)
        try:
            result = self.builder(**selected)
        finally:
            _selection.reset(token)
        if not isinstance(result, Project):
            raise TypeError("Variant builder must return a Project")
        bound = bound_choices(result)
        if bound.keys() & self.choices.keys():
            raise ValueError(
                "Declare each variant either on its assembly or in choices, not both"
            )
        unknown = selection.keys() - self.choices.keys() - bound.keys()
        if unknown:
            raise ValueError(f"Unknown variants: {', '.join(sorted(unknown))}")
        selected.update({key: value for key, (_, value, _) in bound.items()})
        # Do not overwrite metadata on a builder's previously returned snapshot.
        result = copy(result)
        result._variants = self
        result._bound_variants = bound
        result.variant_selection = MappingProxyType(selected)
        return result

    def describe(self, project=None):
        result = {
            key: {
                "label": choice.label or key,
                "options": list(choice.options),
                "default": choice.default,
            }
            for key, choice in self.choices.items()
        }
        for key, (choice, _, scope) in getattr(project, "_bound_variants", {}).items():
            result[key] = {
                "label": choice.label or key,
                "options": list(choice.options),
                "default": choice.default,
                "scope": scope,
            }
        return result


def select_variants(project, selection):
    """Resolve a partial selection against the supplied snapshot's current choices."""
    variants = getattr(project, "_variants", None)
    if variants is None:
        if selection:
            raise ValueError("This project has no variants")
        return project
    selected = {**project.variant_selection, **selection}
    return (
        project
        if selected == dict(project.variant_selection)
        else variants.project(**selected)
    )


def parse_variants(values):
    result = {}
    for value in values:
        key, sep, option = value.partition("=")
        if not sep or not key or not option or key in result:
            raise ValueError("Use --variant name=option once per choice")
        result[key] = option
    return result
