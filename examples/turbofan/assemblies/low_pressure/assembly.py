"""The complete LP spool, driven through its exported front-journal datum."""

import cadkit as ck

from ... import appearance as colors
from ...dimensions import ShaftFit, MEASUREMENT_ALLOWANCE
from .dimensions import Dimensions, FRONT_SHAFT_START
from .parts import make_parts


def make_assembly(*, fit: ShaftFit, dimensions: Dimensions = Dimensions()) -> ck.Assembly:
    parts = make_parts(fit=fit, dimensions=dimensions)
    assembly = ck.Assembly("low-pressure")
    front_shaft = assembly.add(parts.front_shaft, color=colors.LP_SHAFT)
    assembly.fix(front_shaft, at=ck.Frame((FRONT_SHAFT_START, 0, 0)))
    rear_shaft = assembly.add(parts.rear_shaft, color=colors.LP_SHAFT)
    assembly.connect(
        "shaft-coupling",
        ck.Rigid(),
        parent=front_shaft.port("rear-shaft"),
        child=rear_shaft.port("axis"),
    )
    fan = assembly.add(parts.fan, color=colors.FAN)
    assembly.connect(
        "fan-drive", ck.Rigid(), parent=front_shaft.port("fan"), child=fan.port("axis")
    )
    spinner = assembly.add(parts.spinner, color=colors.SPINNER)
    assembly.connect(
        "spinner-drive",
        ck.Rigid(),
        parent=front_shaft.port("fan-spinner"),
        child=spinner.port("axis"),
    )
    tailcone = assembly.add(parts.tailcone, color=colors.TAILCONE)
    assembly.connect(
        "tailcone-drive",
        ck.Rigid(),
        parent=rear_shaft.port("exhaust-tailcone"),
        child=tailcone.port("axis"),
    )
    for definition in parts.front_rotors:
        rotor = assembly.add(definition.part, color=colors.LP_COMPRESSOR)
        assembly.connect(
            f"{rotor.name}-drive",
            ck.Rigid(),
            parent=front_shaft.port(rotor.name),
            child=rotor.port("axis"),
        )
    for definition in parts.rear_rotors:
        rotor = assembly.add(definition.part, color=colors.LP_TURBINE)
        assembly.connect(
            f"{rotor.name}-drive",
            ck.Rigid(),
            parent=rear_shaft.port(rotor.name),
            child=rotor.port("axis"),
        )
    for part in (parts.fan_rear_spacer, parts.stage_spacer):
        spacer = assembly.add(part, color=colors.SPACER)
        assembly.connect(
            f"{spacer.name}-drive",
            ck.Rigid(),
            parent=front_shaft.port(spacer.name),
            child=spacer.port("axis"),
        )

    assembly.interface(
        "square-shaft-coupling",
        left=front_shaft,
        right=rear_shaft,
        kind="clearance",
        min_clearance_mm=max(0, dimensions.coupling_clearance - MEASUREMENT_ALLOWANCE),
    )
    assembly.export_port("journal", front_shaft.port("journal"))
    assembly.export_component("front-shaft", front_shaft)
    assembly.export_component("rear-shaft", rear_shaft)
    return assembly
