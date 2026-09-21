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
    """A discoverable design input, recorded without changing its value.

    Args:
        name: Stable parameter name.
        value: Current Python value; use JSON-compatible values for CLI output.
        unit: Display unit, such as `mm`, `deg`, or an empty string.
        description: What the input controls.
        source: Source file or other human-readable location of the input.
        measured: Whether the value came from a physical measurement.

    Parameters are metadata, not setters or live desktop controls.
    """
    name: str
    value: Any
    unit: str
    description: str
    source: str
    measured: bool = False


@dataclass(frozen=True)
class Part:
    """A reusable manufacturing definition with a lazy geometry builder.

    Args:
        name: Unique artifact stem using letters, numbers, `_` and `-`.
        builder: Zero-argument callable returning one CadQuery Workplane, native
            Shape, or explicit `cadkit.geometry.Mesh`. Return a compound for
            multiple native solids; a Workplane is reduced with `.val()`.
        group: Manufacturing group used by CLI filters and quantity reports.
        quantity: Positive manufacturing quantity, independent of visible instances.
        material: Manufacturing material label.
        description: Short description of the manufactured part.
        production: Include the part when selecting `all`.
        expected_solids: Required solid count, or `None` for intentionally variable counts.
        print_rotation: X, then Y, then Z rotations in degrees, applied before
            placing the lowest point on Z=0. X and Y are not recentered.
        notes: Markdown manufacturing notes.

    See also `cadkit.design.parts.Part` for a definition that owns named features.
    """
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
        """Build geometry, optionally in its manufacturing orientation.

        Args:
            for_print (bool): Apply `print_rotation` and translate onto Z=0.
                Set to `False` for authored coordinates used by an installed component.

        Returns:
            (cq.Shape | Mesh): Built geometry in millimetres.

        Raises:
            ValueError: The builder returned no geometry.
        """
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
        """Return manufacturing metadata without running the geometry builder."""
        return {k: v for k, v in self.__dict__.items() if k != "builder"}


@dataclass(frozen=True)
class Component:
    """One installed instance of already positioned geometry.

    Args:
        name: Unique name within its parent assembly.
        model: Built geometry in world millimetres; assembly hierarchy does not
            apply any additional placement.
        group: Default assembly group when no explicit hierarchy is supplied.
        color: Red, green, blue values from 0 to 1.
        material: Rendering category, separate from `Part.material`.
        part: Matching manufacturing Part name, or `None` for nonmanufactured geometry.
        explode: Presentation translation in millimetres at full explosion.
        metadata: Additional inspection metadata, normally JSON-compatible.
    """
    name: str
    model: Model
    group: str
    color: tuple[float, float, float] = (0.23, 0.27, 0.3)
    material: str = "printed"
    part: str | None = None
    explode: tuple[float, float, float] = (0, 0, 0)

    metadata: dict[str, Any] = field(default_factory=dict)

    def placed(self, fraction=0):
        """Return installed geometry with an optional explosion translation.

        Args:
            fraction (float): Multiplier of `explode`; zero is the installed position.

        Returns:
            (cq.Shape | Mesh): Geometry translated once by the requested presentation offset.
        """
        model = shape(self.model)
        return (
            model.translate(tuple(fraction * x for x in self.explode))
            if fraction
            else model
        )


@dataclass(frozen=True)
class Assembly:
    """A hierarchy of installed components whose geometry is already in world millimetres.

    Args:
        name: Assembly name, unique among siblings.
        children: Components and nested assemblies.
        description: Short description for inspection.

    This stable class organizes geometry; it does not solve placement. For local
    parts connected through frames, use `cadkit.design.assembly.Assembly`.
    Sibling names must be unique because they define desktop component paths.
    """

    name: str
    children: tuple[Component | Assembly, ...]
    description: str = ""

    def __post_init__(self):
        names = [child.name for child in self.children]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate child names in assembly {self.name!r}")

    def components(self):
        """Yield leaf Components in depth-first child order."""
        for child in self.children:
            if isinstance(child, Assembly):
                yield from child.components()
            else:
                yield child


@dataclass(frozen=True)
class Check:
    """An explicit forbidden-intersection or required-contact check.

    Args:
        name: Unique report name, also used as a collision witness filename.
        builder: Zero-argument callable returning intersection geometry or `None`.
        required_contact: Pass when contact exists instead of requiring separation.
        tolerance_mm3: Intersection volumes at or below this value count as empty.
        contact_pair: Optional native shape pair for an exact surface-gap test.
            This detects touching surfaces even when intersection volume is zero.
        max_gap_mm: Maximum acceptable distance for `contact_pair` contact.

    Builder exceptions produce failed findings. A project with no checks has no
    collision coverage simply because `cadkit check` exits successfully.
    """
    name: str
    builder: Builder
    required_contact: bool = False
    tolerance_mm3: float = 1e-5
    contact_pair: Callable[[], tuple[Model, Model]] | None = None
    max_gap_mm: float = 0.001


@dataclass
class Project:
    """The stable entry point consumed by the CLI, desktop, exporters, and agents.

    Args:
        name: Project name and default assembly root name.
        parts: Unique manufacturing definitions, including optional coupons.
        components: Lazy callable returning installed Components. Accept
            `include_hardware=True` because CLI presentation commands pass it.
        parameters: Discoverable input metadata.
        checks: Explicit interference and contact checks.
        description: Short project description.
        views: Named component callables with the same options as `components`.
        assembly: Optional lazy hierarchy builder. It must describe the same
            installed model as `components`. With no builder, groups form the tree.
        joints: Declared installed mechanical relationships.
        interfaces: Bounded contact, clearance, and permitted-overlap contracts.
        fastenings: Hardware stacks and their installed sites.

    Constructing or describing a project does not build its geometry. Export a
    module-level `PROJECT` variable for `cadkit --project module:PROJECT`.
    """
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
        """Build the requested installed hierarchy.

        Args:
            view (str | None): Named component view, or the default assembly.
            **options (Any): Passed to the authored builder. `include_hardware=False`
                omits generated fastening hardware.

        Returns:
            (Assembly): Installed hierarchy. Named views are grouped by component group.

        Generated fastening hardware is added only for the default view without
        pose-changing custom options; such views must own their hardware placement.
        """
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
        """Build a flat list of installed Components.

        Args:
            view (str | None): Named view, or the default components builder.
            **options (Any): Forwarded builder options, including `include_hardware`.

        Returns:
            (list[Component]): Authored components plus applicable located hardware.
        """
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
        """Describe declarations and hardware quantities without validating fit.

        Args:
            assembly (Assembly | None): Installed hierarchy for resolving component
                references. Omit to keep the description lazy.

        Returns:
            (dict): Joints, interfaces, fastenings, and hardware BOM metadata.
        """
        from .mechanics import mechanical_descriptions
        return mechanical_descriptions(self, assembly)

    def validate_mechanics(self, assembly=None, *, scan_collisions=True, tolerance_mm3=1e-5):
        """Check declared mechanics against installed geometry.

        Args:
            assembly (Assembly | None): Reuse an installed hierarchy, or build the default.
            scan_collisions (bool): Scan undeclared component pairs for collisions.
            tolerance_mm3 (float): Native overlap volume tolerance in cubic millimetres.

        Returns:
            (dict): Report with `pass`, `fail`, or `incomplete` status and individual findings.
        """
        from .mechanics import validate_mechanics
        return validate_mechanics(self, assembly, scan_collisions=scan_collisions, tolerance_mm3=tolerance_mm3)

    def select(self, names=("all",), group=None):
        """Select manufacturing parts by name and optional group.

        Args:
            names (tuple[str, ...]): Names to select. `all` selects production parts
                only; explicitly named optional parts are allowed. Duplicates collapse.
            group (str | None): Restrict the selected set to a known manufacturing group.

        Returns:
            (list[Part]): Parts in registry order for `all`, otherwise requested order.

        Raises:
            ValueError: Any part or group is unknown.
        """
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
        """Return schema-versioned, JSON-compatible metadata without building geometry."""
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
