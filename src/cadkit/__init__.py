"""Tools for building, inspecting, and fabricating CadQuery projects."""

__version__ = "0.2.0"
from .project import Project, Part, Component, Assembly, Parameter, Check

from .mechanics import Joint, Interface, Fastening, AccessEnvelope
from .fasteners import FastenerSpec, HardwareItem, FastenerSite
