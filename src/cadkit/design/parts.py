"""Explicit, immutable feature ownership, with an adapter to Cadkit 0.2."""
from dataclasses import dataclass, field, asdict
from types import MappingProxyType
from typing import Callable, Mapping, Protocol
import math
import cadquery as cq
from ..project import Part as LegacyPart
from .frames import Frame, name


class Feature(Protocol):
    """Protocol for a named operation owned by one declarative Part.

    Attributes:
        at: Local manufacturing datum.

    `apply(body)` returns a native CadQuery solid. `describe()` returns
    JSON-compatible feature metadata, optionally including manufacturing
    `operations`. Features run in mapping insertion order.
    """
    at: Frame

    def apply(self, body: cq.Shape) -> cq.Shape: ...
    def describe(self) -> dict: ...


@dataclass(frozen=True)
class FDM:
    """Manufacturing metadata for a fused-deposition printed part.

    Args:
        material: Explicit material name; use `unspecified` when unknown.
        print_rotation: Finite X, Y, Z angles in degrees. Applied only by the
            stable Part adapter for fabrication, never during local assembly placement.
    """
    material: str
    print_rotation: tuple = (0, 0, 0)

    def __post_init__(self):
        if not self.material:
            raise ValueError("Material must be explicit; use 'unspecified' when unknown")
        rotation = tuple(self.print_rotation)
        if len(rotation) != 3 or not all(math.isfinite(v) for v in rotation):
            raise ValueError("Print rotation requires three finite angles")
        object.__setattr__(self, "print_rotation", rotation)

    def describe(self):
        return {"process": "fdm", **asdict(self)}


@dataclass(frozen=True)
class LaserCut:
    """A native blank cut from explicitly dimensioned sheet stock.

    Args:
        material: Sheet material name; use `unspecified` when unknown.
        thickness: Positive sheet thickness in millimetres, along local Z.

    Validation compares the final body's Z extent with `thickness`. It does not
    prove constant cross-section or generate a machine-ready cutting toolpath.
    """
    material: str
    thickness: float
    print_rotation: tuple = field(default=(0, 0, 0), init=False)

    def __post_init__(self):
        if not self.material:
            raise ValueError("Sheet material must be explicit; use 'unspecified' when unknown")
        if not math.isfinite(self.thickness) or self.thickness <= 0:
            raise ValueError("Sheet thickness must be positive and finite")

    def validate(self, body):
        if abs(body.BoundingBox().zlen-self.thickness) > 1e-5:
            raise ValueError("Laser-cut blank thickness does not match declared sheet stock")

    def describe(self):
        return {"process": "laser-cut", "material": self.material, "thickness": self.thickness,
                "profile": "native-xy", "constant_section": "unverified"}


def native(body):
    if isinstance(body, cq.Workplane):
        if len(body.vals()) != 1:
            raise ValueError("Return one native shape or an explicit compound")
        body = body.val()
    if not isinstance(body, cq.Shape) or not body.isValid() or not body.Solids():
        raise ValueError("Part body must be a valid native CadQuery solid")
    return body


@dataclass(frozen=True)
class Part:
    """An immutable local definition with owned features and attachment ports.

    Args:
        name: Stable artifact name using letters, numbers, `_` and `-`.
        body: Zero-argument builder returning one valid native solid or an
            explicit native compound. Mesh bodies are not accepted.
        manufacture: Explicit `FDM` or `LaserCut` manufacturing metadata.
        features: Named feature objects, applied in mapping insertion order.
        ports: Named local Frames for composition; these do not cut geometry.
        finalize: Optional callable receiving the featured Shape and returning
            a native result, for operations such as final edge finishing.

    Mappings are copied and exposed read-only. Building starts with a copy of
    the body's native shape. Use `as_part` to enter the stable Project API.
    """
    name: str
    body: Callable
    manufacture: FDM | LaserCut
    features: Mapping[str, Feature] = field(default_factory=dict)
    ports: Mapping[str, Frame] = field(default_factory=dict)
    finalize: Callable | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        name(self.name)
        for mapping in (self.features, self.ports):
            for key in mapping:
                name(key)
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))

    def build(self):
        """Build in design coordinates. No assembly or print pose enters here."""
        body = native(self.body()).copy()
        for key, feature in self.features.items():
            try:
                body = native(feature.apply(body))
            except Exception as exc:
                raise ValueError(f"{self.name}/features/{key}: {exc}") from exc
        if self.finalize is not None:
            body = native(self.finalize(body))
        if hasattr(self.manufacture, "validate"):
            self.manufacture.validate(body)
        return body

    def describe(self):
        """Return manufacturing, feature, port, and operation metadata without building the body."""
        features = {key: feature.describe() for key, feature in self.features.items()}
        return {"schema_version": 1, "name": self.name,
                "manufacture": self.manufacture.describe(), "features": features,
                "ports": {key: frame.describe() for key, frame in self.ports.items()},
                "operations": [{"feature": key, **operation}
                               for key, feature in features.items()
                               for operation in feature.get("operations", ())]}


    def as_part(self, group, *, quantity=1, notes="", production=True):
        """Adapt this local definition to the stable manufacturing Part contract.

        Args:
            group (str): Manufacturing group.
            quantity (int): Positive manufacturing quantity.
            notes (str): Markdown manufacturing notes.
            production (bool): Include in the stable `all` selection.

        Returns:
            (cadkit.project.Part): Lazy adapter preserving feature metadata and print rotation.
        """
        return _PartAdapter(self.name, self.build, group, quantity=quantity,
                            material=self.manufacture.material, notes=notes,
                            print_rotation=self.manufacture.print_rotation,
                            production=production, definition=self)


@dataclass(frozen=True)
class _PartAdapter(LegacyPart):
    definition: Part | None = field(default=None, repr=False, compare=False)

    def describe(self):
        result = super().describe()
        result.pop("definition")
        result["design"] = self.definition.describe()
        return result
