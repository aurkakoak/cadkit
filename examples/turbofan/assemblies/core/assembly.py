"""Build the stationary core and expose its journal datums and casing seats."""

import cadkit as ck

from ... import appearance as colors
from ...dimensions import ShaftFit
from .parts import make_parts
from .specifications import CORE_LAYOUT


def make_assembly(lp_fit: ShaftFit, hp_fit: ShaftFit) -> ck.Assembly:
    parts = make_parts(lp_fit, hp_fit)
    assembly = ck.Assembly("core")
    liner = assembly.add(parts.liner, color=colors.CORE)
    assembly.fix(liner, at=ck.Frame((CORE_LAYOUT.liner, 0, 0)))
    combustor = assembly.add(parts.combustor, color=colors.COMBUSTOR)
    assembly.fix(combustor, at=ck.Frame((CORE_LAYOUT.combustor, 0, 0)))
    front_support = assembly.add(parts.front_support, color=colors.BYPASS_SUPPORT)
    assembly.fix(front_support, at=ck.Frame((CORE_LAYOUT.front_support, 0, 0)))
    rear_support = assembly.add(parts.rear_support, color=colors.BYPASS_SUPPORT)
    assembly.fix(rear_support, at=ck.Frame((CORE_LAYOUT.rear_support, 0, 0)))
    for row, part in parts.guides:
        guide = assembly.add(part, color=colors.GUIDE_VANE)
        assembly.fix(guide, at=ck.Frame((row.station, 0, 0)))

    front_bearing = assembly.add(parts.front_bearing, color=colors.BEARING)
    assembly.fix(front_bearing, at=ck.Frame((CORE_LAYOUT.front_bearing, 0, 0)))
    rear_bearing = assembly.add(parts.rear_bearing, color=colors.BEARING)
    assembly.fix(rear_bearing, at=ck.Frame((CORE_LAYOUT.rear_bearing, 0, 0)))
    hp_front_bearing = assembly.add(parts.hp_front_bearing, color=colors.BEARING)
    assembly.fix(hp_front_bearing, at=ck.Frame((CORE_LAYOUT.hp_front_bearing, 0, 0)))
    hp_rear_bearing = assembly.add(parts.hp_rear_bearing, color=colors.BEARING)
    assembly.fix(hp_rear_bearing, at=ck.Frame((CORE_LAYOUT.hp_rear_bearing, 0, 0)))

    assembly.interface("combustor-locating-bands", left=combustor, right=liner, kind="contact")
    for support in (front_support, rear_support):
        assembly.interface(
            f"{support.name}-core-cutaway", left=support, right=liner, kind="contact"
        )

    assembly.export_port("lp-journal", front_bearing.feature("journal"))
    assembly.export_port("hp-journal", hp_front_bearing.feature("journal"))
    assembly.export_component("front-bearing", front_bearing)
    assembly.export_component("rear-bearing", rear_bearing)
    assembly.export_component("hp-front-bearing", hp_front_bearing)
    assembly.export_component("hp-rear-bearing", hp_rear_bearing)
    assembly.export_component("front-support", front_support)
    assembly.export_component("rear-support", rear_support)
    return assembly
