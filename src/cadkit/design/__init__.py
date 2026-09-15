"""Experimental declarative authoring, additive to the stable Cadkit 0.2 API.

Native geometry is CadQuery. Parts own features; assemblies place their instances.
Features own manufacturing intent; local ports own composition and motion.
"""
from .attachments import CaptiveNutFastening, SetScrew
from .frames import Frame, PolarPattern, PointPattern
from .parts import Part, Feature, FDM, LaserCut
from .mounts import InsertMount, InsertPocket, Counterbore, ThreadedMount, InsertBoss
from .manufacturing import (Hole, CounterboredHole, CountersunkHole, TappedHole,
                            BearingSeat, Slot, NutPocket, DBore, SealGroove, Boss)
from .assembly import Assembly, AssemblyPose
from .purchased import Purchased
from .motion import Rigid, Revolute, Slider

__all__ = ["CaptiveNutFastening", "SetScrew", "Frame", "PolarPattern", "Part", "Feature", "FDM", "LaserCut", "InsertMount",
           "InsertPocket", "Counterbore", "Assembly", "AssemblyPose", "Purchased",
           "PointPattern", "Rigid", "Revolute", "Slider", "ThreadedMount", "InsertBoss",
           "Hole", "CounterboredHole", "CountersunkHole", "TappedHole", "BearingSeat",
           "Slot", "NutPocket", "DBore", "SealGroove", "Boss"]
