"""Small explicit project contract shared by CLIs, viewers, and exporters."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict, replace
from typing import Callable, Any
import re
import hashlib
import json
from urllib.parse import quote
import cadquery as cq
from .geometry import Mesh, shape, normalized_to_bed
from .mechanics import Joint, Interface, Fastening

Model = cq.Workplane | cq.Shape | Mesh
Builder = Callable[[], Model]


@dataclass(frozen=True)
class Parameter:
    name: str
    value: Any
    unit: str
    description: str
    source: str
    measured: bool = False


@dataclass(frozen=True)
class Part:
    name: str
    builder: Builder
    group: str
    quantity: int = 1
    material: str = "PETG"
    description: str = ""
    production: bool = True
    expected_solids: int | None = 1
    print_rotation: tuple[float, float, float] = (0, 0, 0)
    notes: str = ""

    def __post_init__(self):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", self.name):
            raise ValueError(f"Part name must be a safe artifact stem: {self.name!r}")
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError("Part quantities must be positive integers")

    def build(self, *, for_print=True):
        model = shape(self.builder())
        if model is None:
            raise ValueError(f"{self.name}: builder returned no geometry")
        if for_print:
            for axis, angle in zip(
                ((1, 0, 0), (0, 1, 0), (0, 0, 1)), self.print_rotation
            ):
                if angle:
                    model = model.rotate((0, 0, 0), axis, angle)
            model = normalized_to_bed(model)
        return model

    def describe(self):
        return {k: v for k, v in self.__dict__.items() if k != "builder"}


@dataclass(frozen=True)
class Component:
    name: str
    model: Model
    group: str
    color: tuple[float, float, float] = (0.23, 0.27, 0.3)
    material: str = "printed"
    part: str | None = None
    explode: tuple[float, float, float] = (0, 0, 0)

    metadata: dict[str, Any] = field(default_factory=dict)

    def placed(self, fraction=0):
        model = shape(self.model)
        return (
            model.translate(tuple(fraction * x for x in self.explode))
            if fraction
            else model
        )


@dataclass(frozen=True)
class Assembly:
    """A named hierarchy of installed components (all geometry uses world mm).

    A Part is a reusable manufacturing definition; each Component is an instance.
    Names are unique among siblings, making paths stable across rebuilds.
    """

    name: str
    children: tuple[Component | Assembly, ...]
    description: str = ""

    def __post_init__(self):
        names = [child.name for child in self.children]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate child names in assembly {self.name!r}")

    def components(self):
        for child in self.children:
            if isinstance(child, Assembly):
                yield from child.components()
            else:
                yield child


@dataclass(frozen=True)
class Check:
    name: str
    builder: Builder
    required_contact: bool = False
    tolerance_mm3: float = 1e-5
    contact_pair: Callable[[], tuple[Model, Model]] | None = None
    max_gap_mm: float = 0.001


@dataclass
class Project:
    name: str
    parts: tuple[Part, ...]
    components: Callable[..., list[Component]]
    parameters: tuple[Parameter, ...] = ()
    checks: tuple[Check, ...] = ()
    description: str = ""
    views: dict[str, Callable[..., list[Component]]] = field(default_factory=dict)
    assembly: Callable[..., Assembly] | None = None

    joints: tuple[Joint, ...] = ()
    interfaces: tuple[Interface, ...] = ()
    fastenings: tuple[Fastening, ...] = ()

    def get_assembly(self, view=None, **options):
        if self.assembly is not None and view is None:
            result = self.assembly(**options)
        else:
            result = self._grouped_assembly(view, **options)
        hardware = self._hardware_for_view(view, options)
        if hardware is not None:
            result = Assembly(result.name, result.children + (hardware,), result.description)
        return result

    def _grouped_assembly(self, view=None, **options):
        groups = {}
        for component in self._authored_components(view, **options):
            groups.setdefault(component.group, []).append(component)
        return Assembly(
            self.name,
            tuple(Assembly(name, tuple(children)) for name, children in groups.items()),
            self.description,
        )

    def get_components(self, view=None, **options):
        components = list(self._authored_components(view, **options))
        hardware = self._hardware_for_view(view, options)
        if hardware is not None:
            for component in hardware.components():
                identity = (component.metadata["fastening_id"], component.metadata["site"], component.name)
                suffix = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:8]
                name = "hardware--" + "--".join(quote(item, safe="") for item in identity) + "--" + suffix
                components.append(replace(component, name=name))
        return components

    def _hardware_for_view(self, view, options):
        from .mechanics import hardware_assembly
        # Visibility alone preserves the declared pose. Other options and named
        # views may move components away from the hardware's authored locations.
        if (view is not None or not options.get("include_hardware", True)
                or options.keys() - {"include_hardware"}):
            return None
        return hardware_assembly(self.fastenings)

    def _authored_components(self, view=None, **options):
        if view is None:
            return self.components(**options)
        if view not in self.views:
            raise ValueError(f"Unknown view: {view}")
        return self.views[view](**options)

    def __post_init__(self):
        names = [p.name for p in self.parts]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate part names")
        names = [c.name for c in self.checks]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate check names")

        for label in ("joints", "interfaces", "fastenings"):
            names = [item.name for item in getattr(self, label)]
            if len(names) != len(set(names)):
                raise ValueError(f"Duplicate {label} names")

    def mechanical_descriptions(self, assembly=None):
        from .mechanics import mechanical_descriptions
        return mechanical_descriptions(self, assembly)

    def validate_mechanics(self, assembly=None, *, scan_collisions=True, tolerance_mm3=1e-5):
        from .mechanics import validate_mechanics
        return validate_mechanics(self, assembly, scan_collisions=scan_collisions, tolerance_mm3=tolerance_mm3)

    def select(self, names=("all",), group=None):
        known = {p.name: p for p in self.parts}
        unknown = set(names) - known.keys() - {"all"}
        if unknown:
            raise ValueError(f'Unknown parts: {", ".join(sorted(unknown))}')
        parts = (
            [p for p in self.parts if p.production]
            if "all" in names
            else [known[n] for n in dict.fromkeys(names)]
        )
        if group:
            if group not in {p.group for p in self.parts}:
                raise ValueError(f"Unknown group: {group}")
            parts = [p for p in parts if p.group == group]
        return parts

    def describe(self):
        return {
            "schema_version": 1,
            "name": self.name,
            "description": self.description,
            "units": "mm",
            "views": list(self.views),
            "parts": [p.describe() for p in self.parts],
            "parameters": [asdict(p) for p in self.parameters],
            "mechanics": self.mechanical_descriptions(),
            "checks": [
                {
                    "name": c.name,
                    "required_contact": c.required_contact,
                    "tolerance_mm3": c.tolerance_mm3,
                    "contact_distance_check": c.contact_pair is not None,
                    "max_gap_mm": c.max_gap_mm,
                }
                for c in self.checks
            ],
        }
