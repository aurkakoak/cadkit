"""Assemble the stand and expose its two nacelle seats."""

import cadkit as ck

from ... import appearance as colors
from ...dimensions import EngineDimensions
from .dimensions import BASE_CENTRE_X, StandDimensions
from .parts import make_parts


def make_assembly(dimensions: StandDimensions, engine: EngineDimensions) -> ck.Assembly:
    parts = make_parts(dimensions, engine)
    assembly = ck.Assembly("stand")
    base = assembly.add(parts.base, color=colors.BASE)
    assembly.fix(base, at=ck.Frame((BASE_CENTRE_X, 0, 0)))

    front_saddle = assembly.add(parts.front_saddle, color=colors.SADDLE)
    assembly.connect(
        "front-saddle-seat",
        ck.Rigid(),
        parent=base.port("front-saddle"),
        child=front_saddle.port("base"),
    )
    rear_saddle = assembly.add(parts.rear_saddle, color=colors.SADDLE)
    assembly.connect(
        "rear-saddle-seat",
        ck.Rigid(),
        parent=base.port("rear-saddle"),
        child=rear_saddle.port("base"),
    )
    for saddle in (front_saddle, rear_saddle):
        assembly.interface(f"{saddle.name}-seat", left=base, right=saddle, kind="contact")
        assembly.export_component(saddle.name, saddle)
    return assembly
