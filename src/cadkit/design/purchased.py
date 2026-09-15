"""Purchased component definitions share the same local-frame composition model."""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

from .frames import Frame, name
from .parts import native


@dataclass(frozen=True)
class Purchased:
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
