"""Tools for building, inspecting, and fabricating CadQuery projects."""

__version__ = "0.6.0"
from .design import *
from .design import __all__ as _design_exports
from .design.assembly import Project
from ._project import Parameter, Check

from .mechanics import Joint, Interface, Fastening, AccessEnvelope
from .fasteners import FastenerSpec, HardwareItem, FastenerSite

__all__ = [*_design_exports, "Project", "Parameter", "Check", "Joint", "Interface",
           "Fastening", "AccessEnvelope", "FastenerSpec", "HardwareItem", "FastenerSite"]
