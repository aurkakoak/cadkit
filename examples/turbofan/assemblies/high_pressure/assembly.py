"""The HP spool, independently driven through its exported sleeve journal."""

import cadkit as ck

from ... import appearance as colors
from ...dimensions import EngineDimensions, ShaftFit
from .dimensions import SLEEVE_START
from .parts import make_parts


def make_assembly(
    *, fit: ShaftFit, low_pressure_fit: ShaftFit, engine: EngineDimensions
) -> ck.Assembly:
    parts = make_parts(fit=fit, low_pressure_fit=low_pressure_fit, engine=engine)
    assembly = ck.Assembly("high-pressure")
    sleeve = assembly.add(parts.sleeve, color=colors.HP_SHAFT)
    assembly.fix(sleeve, at=ck.Frame((SLEEVE_START, 0, 0)))
    for definition in parts.rotors:
        color = colors.HP_TURBINE if definition.stage.name == "hp-turbine" else colors.HP_COMPRESSOR
        rotor = assembly.add(definition.part, color=color)
        assembly.connect(
            f"{rotor.name}-drive",
            ck.Rigid(),
            parent=sleeve.port(rotor.name),
            child=rotor.port("axis"),
        )
    assembly.export_port("journal", sleeve.port("journal"))
    assembly.export_component("shaft", sleeve)
    return assembly
