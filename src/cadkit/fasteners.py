"""Located, simplified catalogue hardware backed by cq_warehouse.

The local +Z axis is the insertion direction. A screw's origin is its under-head
seat; its shaft points +Z and its head -Z. Nuts and washers start at local Z=0.
No host geometry is cut implicitly. Supplier-specific factories must describe
whether they provide catalogue geometry or only an envelope.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
from typing import Callable
import cadquery as cq

PROVIDER_REVISION = "daa46507ecc429c0e2dce11d9d5ffd09b12a42af"
_CLASSES = {
    "socket_head_cap_screw": ("SocketHeadCapScrew", "iso4762"),
    "hex_head_screw": ("HexHeadScrew", "iso4017"),
    "button_head_screw": ("ButtonHeadScrew", "iso7380_1"),
    "countersunk_screw": ("CounterSunkScrew", "iso10642"),
    "hex_nut": ("HexNut", "iso4032"),
    "plain_washer": ("PlainWasher", "iso7089"),
    "heat_set_insert": ("HeatSetNut", "McMaster-Carr"),
}


def vector(value, name="vector", *, unit=False):
    value = tuple(float(x) for x in value)
    if len(value) != 3 or not all(math.isfinite(x) for x in value):
        raise ValueError(f"{name} must have three finite coordinates")
    if unit:
        length = math.sqrt(sum(x*x for x in value))
        if length == 0:
            raise ValueError(f"{name} must be nonzero")
        value = tuple(x / length for x in value)
    return value


@dataclass(frozen=True)
class FastenerSpec:
    kind: str
    size: str
    standard: str = ""
    length_mm: float | None = None
    manufacturer: str = ""
    part_number: str = ""
    description: str = ""
    representation: str = "catalogue"
    factory: Callable[["FastenerSpec"], cq.Shape] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.kind not in _CLASSES:
            raise ValueError(f"Unsupported fastener kind: {self.kind}")
        if self.representation not in {"catalogue", "envelope"}:
            raise ValueError("Hardware representation must be catalogue or envelope")
        if not self.size:
            raise ValueError("Fastener size is required")
        if self.kind.endswith("screw") and (self.length_mm is None or not math.isfinite(self.length_mm) or self.length_mm <= 0):
            raise ValueError("Screws require a positive length_mm")
        if self.kind == "countersunk_screw":
            raise ValueError("Countersunk screw length includes the head; this insertion convention does not support it yet")
        if not self.standard:
            object.__setattr__(self, "standard", _CLASSES[self.kind][1])

    @property
    def id(self):
        identity = self.describe(include_id=False)
        identity.pop("description")  # Notes do not create a different purchased item.
        return "hardware-" + sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]

    def describe(self, *, include_id=True):
        data = {"kind": self.kind, "size": self.size, "standard": self.standard,
                "length_mm": self.length_mm, "manufacturer": self.manufacturer,
                "part_number": self.part_number, "description": self.description,
                "representation": self.representation, "custom_factory": self.factory is not None,
                "provider": "cq_warehouse", "provider_revision": PROVIDER_REVISION, "simple": True,
                "geometry_adapter": "catalogue_plain_washer_annulus" if self.kind == "plain_washer" and self.factory is None else None}
        if include_id:
            data["id"] = self.id
        return data

    def catalogue(self):
        """Return the provider object (including thread and head dimensions)."""
        if self.factory is not None:
            result = self.factory(self)
        else:
            try:
                from cq_warehouse import fastener
            except ImportError as exc:
                raise RuntimeError("Install CadKit's pinned cq_warehouse dependency to build hardware") from exc
            cls = getattr(fastener, _CLASSES[self.kind][0])
            kwargs = {"size": self.size, "fastener_type": self.standard}
            if self.kind != "plain_washer":
                kwargs["simple"] = True
            if self.kind.endswith("screw"):
                kwargs["length"] = self.length_mm
            result = cls(**kwargs)
        if self.kind == "plain_washer" and self.factory is None:
            # Upstream's revolved profile is invalid with CQ2.8/OCCT7.9. Use its
            # exact catalogue dimensions to make the same analytic annulus.
            d = result.washer_data
            result.wrapped = cq.Workplane("XY").circle(d["d2"] / 2).circle(d["d1"] / 2).extrude(d["h"]).val().wrapped
        if not isinstance(result, cq.Shape) or not result.isValid() or not result.Solids():
            raise ValueError(f"{self.id}: hardware provider did not return a valid solid")
        return result

    def dimensions(self):
        """Catalogue millimetres; unknown supplier values remain null."""
        item = self.catalogue()
        bb = item.BoundingBox()
        return {"thread_diameter_mm": getattr(item, "thread_diameter", None),
                "thread_pitch_mm": getattr(item, "thread_pitch", None),
                "thread_length_mm": getattr(item, "thread_length", None),
                "head_diameter_mm": getattr(item, "head_diameter", None),
                "head_height_mm": getattr(item, "head_height", None),
                "height_mm": bb.zmax - bb.zmin,
                "clearance_diameters_mm": getattr(item, "clearance_hole_diameters", None)}

    def clearance_diameter(self, fit="Normal"):
        diameters = self.catalogue().clearance_hole_diameters
        if fit not in diameters:
            raise ValueError(f"Unknown clearance fit {fit!r}; choose {tuple(diameters)}")
        return float(diameters[fit])

    def clearance_cutter(self, depth_mm, *, fit="Normal", allowance_mm=0):
        """Explicit +Z hole cutter; allowance is diametral and authored by caller."""
        if not math.isfinite(depth_mm) or depth_mm <= 0 or not math.isfinite(allowance_mm):
            raise ValueError("Cutter depth must be positive and allowance finite")
        diameter = self.clearance_diameter(fit) + allowance_mm
        if diameter <= 0:
            raise ValueError("Cutter diameter must be positive")
        return cq.Solid.makeCylinder(diameter / 2, depth_mm)

    def build(self):
        model = cq.Shape.cast(self.catalogue().wrapped)
        return model.rotate((0, 0, 0), (1, 0, 0), 180) if self.kind.endswith("screw") else model


@dataclass(frozen=True)
class HardwareItem:
    name: str
    spec: FastenerSpec
    offset_mm: float = 0

    def __post_init__(self):
        if not self.name or not math.isfinite(self.offset_mm):
            raise ValueError("Hardware items require a name and finite offset")

    def describe(self):
        return {"name": self.name, "spec": self.spec.describe(), "offset_mm": self.offset_mm}


@dataclass(frozen=True)
class FastenerSite:
    name: str
    origin: tuple[float, float, float] = (0, 0, 0)
    axis: tuple[float, float, float] = (0, 0, 1)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Fastener sites require a name")
        object.__setattr__(self, "origin", vector(self.origin, "origin"))
        object.__setattr__(self, "axis", vector(self.axis, "axis", unit=True))

    def place(self, model, offset_mm=0):
        x, y, z = self.axis
        if z < -1 + 1e-12:
            model = model.rotate((0, 0, 0), (1, 0, 0), 180)
        elif z < 1 - 1e-12:
            model = model.rotate((0, 0, 0), (-y, x, 0), math.degrees(math.acos(z)))
        return model.translate(tuple(a + b * offset_mm for a, b in zip(self.origin, self.axis)))

    def describe(self):
        return {"name": self.name, "origin": self.origin, "axis": self.axis}
