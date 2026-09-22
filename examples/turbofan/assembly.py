"""Compose the housing, core, stand and independently rotating spools."""

import cadkit as ck

from .assemblies.core.assembly import make_assembly as make_core
from .assemblies.high_pressure.assembly import make_assembly as make_high_pressure
from .assemblies.housing.assembly import make_assembly as make_housing
from .assemblies.housing.parts import HousingParts
from .assemblies.low_pressure.assembly import make_assembly as make_low_pressure
from .assemblies.low_pressure.dimensions import Dimensions as LowPressureDimensions
from .assemblies.stand.assembly import make_assembly as make_stand
from .assemblies.stand.dimensions import StandDimensions
from .dimensions import EngineDimensions, ShaftFit, LOW_PRESSURE_FIT, HIGH_PRESSURE_FIT
from .interfaces import declare_interfaces


def make_assembly(
    *,
    engine: EngineDimensions = EngineDimensions(),
    lp_fit: ShaftFit = LOW_PRESSURE_FIT,
    hp_fit: ShaftFit = HIGH_PRESSURE_FIT,
    low_pressure: LowPressureDimensions = LowPressureDimensions(),
    stand: StandDimensions = StandDimensions(),
    housing: HousingParts | None = None,
    covers: bool = True,
) -> ck.Assembly:
    assembly = ck.Assembly("TF-300")
    display = assembly.add(make_stand(stand, engine))
    assembly.fix(display)
    casing = assembly.add(make_housing(parts=housing, covers=covers))
    assembly.fix(casing, at=ck.Frame((0, 0, engine.axis_height)))
    core = assembly.add(make_core(lp_fit, hp_fit))
    assembly.fix(core, at=ck.Frame((0, 0, engine.axis_height)))

    lp = assembly.add(make_low_pressure(fit=lp_fit, dimensions=low_pressure))
    assembly.connect(
        "low-pressure-spool",
        ck.Revolute(),
        parent=core.port("lp-journal"),
        child=lp.port("journal"),
    )
    hp = assembly.add(make_high_pressure(fit=hp_fit, low_pressure_fit=lp_fit, engine=engine))
    assembly.connect(
        "high-pressure-spool",
        ck.Revolute(),
        parent=core.port("hp-journal"),
        child=hp.port("journal"),
    )

    declare_interfaces(
        assembly,
        stand=display,
        housing=casing,
        core=core,
        low_pressure=lp,
        high_pressure=hp,
        engine=engine,
        lp_fit=lp_fit,
        hp_fit=hp_fit,
    )
    assembly.name_pose("lp-45deg", {"low-pressure-spool": 45})
    assembly.name_pose("hp-30deg", {"high-pressure-spool": 30})
    assembly.name_pose("spools-turned", {"low-pressure-spool": 45, "high-pressure-spool": -30})
    return assembly
