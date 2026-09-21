"""Reusable local part definitions and their manufacturing settings."""
from dataclasses import dataclass, field, asdict
from types import MappingProxyType
from typing import Callable, Mapping, Protocol
import math
import cadquery as cq
from .._project import Part as FabricationPart
from ..geometry import Mesh, normalized_to_bed
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
            fabrication builder, never during local assembly placement.
        print_frame: Optional rigid transform from design to fabrication coordinates.
            Used instead of a nonzero `print_rotation`. The result is translated
            onto Z=0 after this transform; X and Y offsets are preserved.
    """
    material: str
    print_rotation: tuple = (0, 0, 0)
    print_frame: Frame | None = field(default=None, kw_only=True)

    def __post_init__(self):
        if not self.material:
            raise ValueError("Material must be explicit; use 'unspecified' when unknown")
        rotation = tuple(self.print_rotation)
        if len(rotation) != 3 or not all(math.isfinite(v) for v in rotation):
            raise ValueError("Print rotation requires three finite angles")
        object.__setattr__(self, "print_rotation", rotation)
        if self.print_frame is not None:
            if not isinstance(self.print_frame, Frame):
                raise TypeError("print_frame must be a Frame")
            if any(rotation):
                raise ValueError("Choose print_frame or print_rotation, not both")

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


def definition_body(body):
    """Copy a valid definition body without converting its representation."""
    if isinstance(body, Mesh):
        volume = body.manifold.volume()
        if not math.isfinite(volume) or volume <= 0:
            raise ValueError("Part body must be a nonempty positive-volume Mesh")
        return Mesh(body.manifold)
    return native(body).copy()


def apply_features(name, body, features):
    if isinstance(body, Mesh) and features:
        raise ValueError(f"{name}: Mesh bodies do not support native manufacturing features; use ports for attachment datums")
    for key, feature in features.items():
        try:
            body = native(feature.apply(body))
        except Exception as exc:
            raise ValueError(f"{name}/features/{key}: {exc}") from exc
    return body


@dataclass(frozen=True)
class Part:
    """An immutable local definition with owned features and attachment ports.

    Args:
        name: Stable artifact name using letters, numbers, `_` and `-`.
        body: Zero-argument builder returning a valid native solid, explicit
            native compound or `cadkit.geometry.Mesh`. Mesh definitions support
            placement and fabrication, but not native feature operations.
        manufacture: Explicit `FDM` or `LaserCut` manufacturing metadata.
        features: Named feature objects, applied in mapping insertion order.
        ports: Named local Frames for composition; these do not cut geometry.
        finalize: Optional callable receiving the featured Shape and returning
            a native result, for operations such as final edge finishing.
        group: Manufacturing group used by selection and quantity reports.
        description: Short description of the manufactured part.
        production: Include this definition in the default `all` fabrication set.
        expected_solids: Positive expected solid count, or None for a variable count.
        notes: Markdown manufacturing notes.

    Mappings are copied and exposed read-only. Building starts with a copy of
    the body. Assembly placement never changes this reusable definition.
    """
    name: str
    body: Callable
    manufacture: FDM | LaserCut
    features: Mapping[str, Feature] = field(default_factory=dict)
    ports: Mapping[str, Frame] = field(default_factory=dict)
    finalize: Callable | None = field(default=None, repr=False, compare=False)
    group: str = field(default="parts", kw_only=True)
    description: str = field(default="", kw_only=True)
    production: bool = field(default=True, kw_only=True)
    expected_solids: int | None = field(default=1, kw_only=True)
    notes: str = field(default="", kw_only=True)

    def __post_init__(self):
        name(self.name)
        if not isinstance(self.group, str) or not self.group:
            raise ValueError("Manufacturing group must be a nonempty string")
        if self.expected_solids is not None and (type(self.expected_solids) is not int or self.expected_solids < 1):
            raise ValueError("expected_solids must be a positive integer or None")
        if type(self.production) is not bool:
            raise TypeError("production must be a boolean")
        if not isinstance(self.manufacture, (FDM, LaserCut)):
            raise TypeError("Part manufacture must be FDM or LaserCut")
        for mapping in (self.features, self.ports):
            for key in mapping:
                name(key)
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))
        if any(not isinstance(frame, Frame) for frame in self.ports.values()):
            raise TypeError("Part ports must be local Frames")

    def build(self):
        """Build in design coordinates. No assembly or print pose enters here."""
        body = apply_features(self.name, definition_body(self.body()), self.features)
        if self.finalize is not None:
            if isinstance(body, Mesh):
                raise ValueError(f"{self.name}: Mesh bodies do not support native finalization")
            body = native(self.finalize(body))
        if hasattr(self.manufacture, "validate"):
            if isinstance(body, Mesh):
                raise ValueError(f"{self.name}: LaserCut requires native sheet geometry")
            self.manufacture.validate(body)
        return body

    def build_for_print(self):
        """Build fabrication geometry, applying its print transform and placing it on Z=0.

        Returns:
            (cq.Shape | Mesh): Fabrication geometry. This never changes installed
                placement or the result of `build()`.
        """
        body = self.build()
        frame = getattr(self.manufacture, "print_frame", None)
        if frame is not None:
            body = body.moved(frame.location)
        else:
            for axis, angle in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), self.manufacture.print_rotation):
                if angle:
                    body = body.rotate((0, 0, 0), axis, angle)
        return normalized_to_bed(body)

    def describe(self):
        """Return manufacturing, feature, port, and operation metadata without building the body."""
        features = {key: feature.describe() for key, feature in self.features.items()}
        return {"schema_version": 1, "name": self.name,
                "group": self.group, "description": self.description,
                "production": self.production, "expected_solids": self.expected_solids,
                "notes": self.notes,
                "manufacture": self.manufacture.describe(), "features": features,
                "ports": {key: frame.describe() for key, frame in self.ports.items()},
                "operations": [{"feature": key, **operation}
                               for key, feature in features.items()
                               for operation in feature.get("operations", ())]}


    def as_part(self, group=None, *, quantity=1, notes=None, production=None):
        """Prepare a lazy fabrication record for exporters.

        Args:
            group (str | None): Manufacturing group override; defaults to this part's group.
            quantity (int): Positive manufacturing quantity.
            notes (str | None): Manufacturing notes override.
            production (bool | None): Override inclusion in the `all` selection.

        Returns:
            (cadkit._project.Part): Fabrication record with feature metadata and print setup.
        """
        frame = getattr(self.manufacture, "print_frame", None)
        rotation = frame.location.toTuple()[1] if frame is not None else self.manufacture.print_rotation
        return _PartAdapter(self.name, self.build, self.group if group is None else group, quantity=quantity,
                            material=self.manufacture.material, notes=self.notes if notes is None else notes,
                            description=self.description, expected_solids=self.expected_solids,
                            print_rotation=rotation,
                            production=self.production if production is None else production, definition=self)


@dataclass(frozen=True)
class _PartAdapter(FabricationPart):
    definition: Part | None = field(default=None, repr=False, compare=False)

    def build(self, *, for_print=True):
        return self.definition.build_for_print() if for_print else self.definition.build()

    def describe(self):
        result = super().describe()
        result.pop("definition")
        result["design"] = self.definition.describe()
        frame = getattr(self.definition.manufacture, "print_frame", None)
        if frame is not None:
            result["print_frame"] = frame.describe()
        return result
