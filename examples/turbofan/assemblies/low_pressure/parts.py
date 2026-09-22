"""Public LP spool part factory; assembly placement is owned by its caller."""

from dataclasses import dataclass

import cadkit as ck

from ...dimensions import ShaftFit
from ...parts.rotor import RotorDefinition, make_rotor
from .dimensions import (
    Dimensions,
    FRONT_ROTOR_STAGES,
    REAR_ROTOR_STAGES,
    FAN_REAR_SPACER,
    STAGE_SPACER,
)
from .fan import make_fan
from .shafts import (
    make_front_shaft,
    make_rear_shaft,
    make_spinner,
    make_tailcone,
    make_spacer,
)


@dataclass(frozen=True)
class LowPressureParts:
    front_shaft: ck.Part
    rear_shaft: ck.Part
    fan: ck.Part
    spinner: ck.Part
    tailcone: ck.Part
    front_rotors: tuple[RotorDefinition, ...]
    rear_rotors: tuple[RotorDefinition, ...]
    fan_rear_spacer: ck.Part
    stage_spacer: ck.Part


def make_parts(*, fit: ShaftFit, dimensions: Dimensions = Dimensions()) -> LowPressureParts:
    return LowPressureParts(
        front_shaft=make_front_shaft(fit, dimensions),
        rear_shaft=make_rear_shaft(fit, dimensions),
        fan=make_fan(dimensions, fit),
        spinner=make_spinner(fit),
        tailcone=make_tailcone(fit),
        front_rotors=tuple(
            make_rotor(stage, fit, group="LP spool") for stage in FRONT_ROTOR_STAGES
        ),
        rear_rotors=tuple(make_rotor(stage, fit, group="LP spool") for stage in REAR_ROTOR_STAGES),
        fan_rear_spacer=make_spacer(FAN_REAR_SPACER, fit),
        stage_spacer=make_spacer(STAGE_SPACER, fit),
    )
