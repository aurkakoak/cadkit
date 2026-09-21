"""Purchased component definitions share the same local-frame composition model."""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

from .frames import Frame, name
from .parts import native


@dataclass(frozen=True)
class Purchased:
    """A supplied component with local geometry and attachment datums.

    Args:
        name: Stable definition name.
        body: Zero-argument builder returning a valid native CadQuery solid.
        ports: Named local Frames.
        features: Explicit feature operations. Use `supplied=True` mount roles
            for already present supplier geometry; other features modify the body.
        description: Human-readable component description.
        supplier: Supplier name for the purchased BOM.
        sku: Supplier identifier for the purchased BOM.
        representation: `envelope` for approximate geometry or `detailed`.
        quantity: Positive supplier quantity represented by each assembly instance.

    Purchased objects are not exported as manufactured Parts by `as_project()`.
    An envelope does not establish exact supplier fit.
    """
    name: str
    body: Callable
    ports: Mapping[str, Frame] = field(default_factory=dict)
    features: Mapping = field(default_factory=dict)
    description: str = ""
    supplier: str = ""
    sku: str = ""
    representation: str = "envelope"
    quantity: int = 1

    def __post_init__(self):
        name(self.name)
        if self.representation not in {"envelope", "detailed"}:
            raise ValueError("Purchased representation must be envelope or detailed")
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError("Purchased quantity per instance must be a positive integer")
        for label in ("ports", "features"):
            values = dict(getattr(self, label))
            for key in values:
                name(key)
            object.__setattr__(self, label, MappingProxyType(values))
        if any(not isinstance(frame, Frame) for frame in self.ports.values()):
            raise ValueError("Purchased ports must be local Frames")

    def build(self):
        """Build and copy the native body, then apply any explicit owned feature operations."""
        body = native(self.body()).copy()
        # Supplied features describe a vendor component. Geometry-changing
        # features are explicit if a purchased blank is subsequently machined.
        for key, feature in self.features.items():
            try:
                body = native(feature.apply(body))
            except Exception as exc:
                raise ValueError(f"{self.name}/features/{key}: {exc}") from exc
        return body

    def describe(self):
        return {"schema_version": 1, "name": self.name, "kind": "purchased",
                "description": self.description, "supplier": self.supplier,
                "sku": self.sku, "representation": self.representation,
                "quantity": self.quantity,
                "ports": {key: frame.describe() for key, frame in self.ports.items()},
                "features": {key: feature.describe() for key, feature in self.features.items()}}
