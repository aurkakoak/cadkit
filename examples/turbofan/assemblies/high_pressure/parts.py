"""Public HP sleeve and rotor definitions, all with local shaft-axis datums."""

from dataclasses import dataclass
from functools import partial

import cadkit as ck

from ...dimensions import (
    EngineDimensions,
    ShaftFit,
    HIGH_PRESSURE_FRONT_JOURNAL,
    HIGH_PRESSURE_REAR_JOURNAL,
)
from ...geometry import axis_frame, d_shaft
from ...parts.rotor import RotorDefinition, make_rotor
from .dimensions import SLEEVE_START, SLEEVE_LENGTH, ROTOR_STAGES


@dataclass(frozen=True)
class HighPressureParts:
    sleeve: ck.Part
    rotors: tuple[RotorDefinition, ...]


def make_parts(
    *,
    fit: ShaftFit,
    low_pressure_fit: ShaftFit,
    engine: EngineDimensions,
) -> HighPressureParts:
    inner_radius = low_pressure_fit.shaft_radius + engine.concentric_clearance
    if inner_radius >= fit.shaft_flat:
        raise ValueError("The concentric shaft bore must leave material under the sleeve's flat")
    sleeve = ck.Part(
        "hp-shaft-sleeve",
        body=partial(d_shaft, fit.shaft_radius, fit.shaft_flat, SLEEVE_LENGTH),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="HP spool",
        description="Concentric D-shaped sleeve with a circular LP-shaft passage",
        features={
            "concentric-bore": ck.Hole(
                diameter=2 * inner_radius,
                depth=SLEEVE_LENGTH,
                at=axis_frame(),
                through=True,
            ),
        },
        ports={
            "axis": axis_frame(),
            "journal": axis_frame(HIGH_PRESSURE_FRONT_JOURNAL - SLEEVE_START),
            "rear-journal": axis_frame(HIGH_PRESSURE_REAR_JOURNAL - SLEEVE_START),
            **{stage.name: axis_frame(stage.station - SLEEVE_START) for stage in ROTOR_STAGES},
        },
    )
    return HighPressureParts(
        sleeve=sleeve,
        rotors=tuple(make_rotor(stage, fit, group="HP spool") for stage in ROTOR_STAGES),
    )
