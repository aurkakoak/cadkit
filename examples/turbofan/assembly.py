"""Install the engine parts and connect the two independently rotating spools."""

import cadkit as ck

from . import appearance as colors
from .assemblies.core.parts import make_parts as make_core_parts
from .assemblies.core.specifications import CORE_LAYOUT
from .assemblies.high_pressure.parts import make_parts as make_hp_parts
from .assemblies.housing.parts import HousingParts, make_parts as make_housing_parts
from .assemblies.housing.specifications import HOUSING_LAYOUT
from .assemblies.low_pressure.dimensions import Dimensions as LowPressureDimensions
from .assemblies.low_pressure.parts import make_parts as make_lp_parts
from .assemblies.stand.dimensions import BASE_CENTRE_X, StandDimensions
from .assemblies.stand.parts import make_parts as make_stand_parts
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
    housing = housing if housing is not None else make_housing_parts()
    core = make_core_parts(lp_fit, hp_fit)
    lp = make_lp_parts(fit=lp_fit, dimensions=low_pressure)
    hp = make_hp_parts(fit=hp_fit, low_pressure_fit=lp_fit, engine=engine)
    display = make_stand_parts(stand, engine)
    assembly = ck.Assembly("TF-300")
    height = engine.axis_height

    base = assembly.add("display-base", display.base, group=display.base.group, color=colors.BASE)
    assembly.fix(base, at=ck.Frame((BASE_CENTRE_X, 0, 0)))
    front_saddle = assembly.add(
        "front-saddle", display.front_saddle, group=display.front_saddle.group, color=colors.SADDLE
    )
    assembly.connect(
        "front-saddle-seat",
        ck.Rigid(),
        parent=base.port("front-saddle"),
        child=front_saddle.port("base"),
    )
    rear_saddle = assembly.add(
        "rear-saddle", display.rear_saddle, group=display.rear_saddle.group, color=colors.SADDLE
    )
    assembly.connect(
        "rear-saddle-seat",
        ck.Rigid(),
        parent=base.port("rear-saddle"),
        child=rear_saddle.port("base"),
    )

    inlet = assembly.add("inlet-lip", housing.inlet, group=housing.inlet.group, color=colors.INLET)
    assembly.fix(inlet, at=ck.Frame((HOUSING_LAYOUT.inlet, 0, height)))
    front_shell = assembly.add(
        "nacelle-front-lower",
        housing.front_shell,
        group=housing.front_shell.group,
        color=colors.NACELLE,
    )
    assembly.fix(front_shell, at=ck.Frame((HOUSING_LAYOUT.front_shell, 0, height)))
    rear_shell = assembly.add(
        "nacelle-rear-lower",
        housing.rear_shell,
        group=housing.rear_shell.group,
        color=colors.NACELLE,
    )
    assembly.fix(rear_shell, at=ck.Frame((HOUSING_LAYOUT.rear_shell, 0, height)))
    nozzle = assembly.add(
        "exhaust-nozzle", housing.nozzle, group=housing.nozzle.group, color=colors.NOZZLE
    )
    assembly.fix(nozzle, at=ck.Frame((HOUSING_LAYOUT.nozzle, 0, height)))

    liner = assembly.add("core-cutaway", core.liner, group=core.liner.group, color=colors.CORE)
    assembly.fix(liner, at=ck.Frame((CORE_LAYOUT.liner, 0, height)))
    combustor = assembly.add(
        "combustor-liner", core.combustor, group=core.combustor.group, color=colors.COMBUSTOR
    )
    assembly.fix(combustor, at=ck.Frame((CORE_LAYOUT.combustor, 0, height)))
    front_support = assembly.add(
        "front-bypass-support",
        core.front_support,
        group=core.front_support.group,
        color=colors.BYPASS_SUPPORT,
    )
    assembly.fix(front_support, at=ck.Frame((CORE_LAYOUT.front_support, 0, height)))
    rear_support = assembly.add(
        "rear-bypass-support",
        core.rear_support,
        group=core.rear_support.group,
        color=colors.BYPASS_SUPPORT,
    )
    assembly.fix(rear_support, at=ck.Frame((CORE_LAYOUT.rear_support, 0, height)))

    for row, part in core.guides:
        guide = assembly.add(row.name, part, group=part.group, color=colors.GUIDE_VANE)
        assembly.fix(guide, at=ck.Frame((row.station, 0, height)))

    front_bearing = assembly.add(
        "front-bearing-spider",
        core.front_bearing,
        group=core.front_bearing.group,
        color=colors.BEARING,
    )
    assembly.fix(front_bearing, at=ck.Frame((CORE_LAYOUT.front_bearing, 0, height)))
    rear_bearing = assembly.add(
        "rear-bearing-spider",
        core.rear_bearing,
        group=core.rear_bearing.group,
        color=colors.BEARING,
    )
    assembly.fix(rear_bearing, at=ck.Frame((CORE_LAYOUT.rear_bearing, 0, height)))
    hp_front_bearing = assembly.add(
        "hp-front-bearing",
        core.hp_front_bearing,
        group=core.hp_front_bearing.group,
        color=colors.BEARING,
    )
    assembly.fix(hp_front_bearing, at=ck.Frame((CORE_LAYOUT.hp_front_bearing, 0, height)))
    hp_rear_bearing = assembly.add(
        "hp-rear-bearing",
        core.hp_rear_bearing,
        group=core.hp_rear_bearing.group,
        color=colors.BEARING,
    )
    assembly.fix(hp_rear_bearing, at=ck.Frame((CORE_LAYOUT.hp_rear_bearing, 0, height)))

    front_shaft = assembly.add(
        "lp-shaft-front", lp.front_shaft, group=lp.front_shaft.group, color=colors.LP_SHAFT
    )
    assembly.connect(
        "low-pressure-spool",
        ck.Revolute(),
        parent=front_bearing.feature("journal"),
        child=front_shaft.port("journal"),
    )
    rear_shaft = assembly.add(
        "lp-shaft-rear", lp.rear_shaft, group=lp.rear_shaft.group, color=colors.LP_SHAFT
    )
    assembly.connect(
        "shaft-coupling",
        ck.Rigid(),
        parent=front_shaft.port("rear-shaft"),
        child=rear_shaft.port("axis"),
    )
    sleeve = assembly.add(
        "hp-shaft-sleeve", hp.sleeve, group=hp.sleeve.group, color=colors.HP_SHAFT
    )
    assembly.connect(
        "high-pressure-spool",
        ck.Revolute(),
        parent=hp_front_bearing.feature("journal"),
        child=sleeve.port("journal"),
    )

    fan = assembly.add("fan", lp.fan, group=lp.fan.group, color=colors.FAN)
    assembly.connect(
        "fan-drive", ck.Rigid(), parent=front_shaft.port("fan"), child=fan.port("axis")
    )
    spinner = assembly.add("fan-spinner", lp.spinner, group=lp.spinner.group, color=colors.SPINNER)
    assembly.connect(
        "spinner-drive",
        ck.Rigid(),
        parent=front_shaft.port("fan-spinner"),
        child=spinner.port("axis"),
    )
    tailcone = assembly.add(
        "exhaust-tailcone", lp.tailcone, group=lp.tailcone.group, color=colors.TAILCONE
    )
    assembly.connect(
        "tailcone-drive",
        ck.Rigid(),
        parent=rear_shaft.port("exhaust-tailcone"),
        child=tailcone.port("axis"),
    )

    for definition in lp.front_rotors:
        rotor = assembly.add(
            definition.stage.name,
            definition.part,
            group=definition.part.group,
            color=colors.LP_COMPRESSOR,
        )
        assembly.connect(
            f"{rotor.name}-drive",
            ck.Rigid(),
            parent=front_shaft.port(rotor.name),
            child=rotor.port("axis"),
        )
    for definition in lp.rear_rotors:
        rotor = assembly.add(
            definition.stage.name,
            definition.part,
            group=definition.part.group,
            color=colors.LP_TURBINE,
        )
        assembly.connect(
            f"{rotor.name}-drive",
            ck.Rigid(),
            parent=rear_shaft.port(rotor.name),
            child=rotor.port("axis"),
        )
    for definition in hp.rotors:
        color = colors.HP_TURBINE if definition.stage.name == "hp-turbine" else colors.HP_COMPRESSOR
        rotor = assembly.add(
            definition.stage.name, definition.part, group=definition.part.group, color=color
        )
        assembly.connect(
            f"{rotor.name}-drive",
            ck.Rigid(),
            parent=sleeve.port(rotor.name),
            child=rotor.port("axis"),
        )
    for part in (lp.fan_rear_spacer, lp.stage_spacer):
        spacer = assembly.add(part.name, part, group=part.group, color=colors.SPACER)
        assembly.connect(
            f"{spacer.name}-drive",
            ck.Rigid(),
            parent=front_shaft.port(spacer.name),
            child=spacer.port("axis"),
        )

    if covers:
        front_cover = assembly.add(
            "nacelle-front-cover",
            housing.front_cover,
            group=housing.front_cover.group,
            color=colors.NACELLE_COVER,
        )
        assembly.connect(
            "front-cover-seat",
            ck.Rigid(),
            parent=front_shell.port("axis"),
            child=front_cover.port("axis"),
        )
        rear_cover = assembly.add(
            "nacelle-rear-cover",
            housing.rear_cover,
            group=housing.rear_cover.group,
            color=colors.NACELLE_COVER,
        )
        assembly.connect(
            "rear-cover-seat",
            ck.Rigid(),
            parent=rear_shell.port("axis"),
            child=rear_cover.port("axis"),
        )
        nozzle_cover = assembly.add(
            "exhaust-upper-cover",
            housing.nozzle_cover,
            group=housing.nozzle_cover.group,
            color=colors.NOZZLE_COVER,
        )
        assembly.connect(
            "nozzle-cover-seat",
            ck.Rigid(),
            parent=nozzle.port("axis"),
            child=nozzle_cover.port("axis"),
        )

    declare_interfaces(
        assembly, engine=engine, lp_fit=lp_fit, hp_fit=hp_fit, low_pressure=low_pressure
    )
    assembly.name_pose("lp-45deg", {"low-pressure-spool": 45})
    assembly.name_pose("hp-30deg", {"high-pressure-spool": 30})
    assembly.name_pose("spools-turned", {"low-pressure-spool": 45, "high-pressure-spool": -30})
    return assembly
