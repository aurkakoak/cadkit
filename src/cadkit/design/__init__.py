"""Experimental declarative authoring, additive to the stable Cadkit 0.2 API.

Native geometry is CadQuery. Parts own features; assemblies place their instances.
This first slice supports rigid insert-mount connections and FDM orientation.
"""
from .frames import Frame, PolarPattern
from .parts import Part, Feature, FDM
from .mounts import InsertMount, InsertPocket, Counterbore
from .assembly import Assembly

__all__ = ["Frame", "PolarPattern", "Part", "Feature", "FDM", "InsertMount",
           "InsertPocket", "Counterbore", "Assembly"]
