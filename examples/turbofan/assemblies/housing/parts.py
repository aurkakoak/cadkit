"""Manufactured housing definitions; installation belongs to the engine assembly."""

from dataclasses import dataclass
from functools import partial

import cadkit as ck

from ...geometry import axis_frame
from ...profiles import FRONT_NACELLE, REAR_NACELLE
from .geometry import inlet_body, nozzle_body, shell_body
from .specifications import INLET_LIP, NOZZLE_SECTION


@dataclass(frozen=True)
class HousingParts:
    inlet: ck.Part
    front_shell: ck.Part
    rear_shell: ck.Part
    front_cover: ck.Part
    rear_cover: ck.Part
    nozzle: ck.Part
    nozzle_cover: ck.Part


def make_parts() -> HousingParts:
    inlet = ck.Part(
        "inlet-lip",
        body=partial(inlet_body, INLET_LIP),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="Casing",
        ports={"axis": axis_frame()},
        description="Rounded intake lip with a rear locating collar",
    )
    front_shell = ck.Part(
        "nacelle-front-lower",
        body=partial(shell_body, FRONT_NACELLE),
        manufacture=ck.FDM("PLA", print_rotation=(90, 0, 0)),
        group="Casing",
        ports={"axis": axis_frame()},
        description="Forward lower half-shell around the fan and bypass duct",
    )
    rear_shell = ck.Part(
        "nacelle-rear-lower",
        body=partial(shell_body, REAR_NACELLE),
        manufacture=ck.FDM("PLA", print_rotation=(90, 0, 0)),
        group="Casing",
        ports={"axis": axis_frame()},
        description="Aft lower half-shell tapering toward the bypass discharge",
    )
    front_cover = ck.Part(
        "nacelle-front-cover",
        body=partial(shell_body, FRONT_NACELLE, upper=True),
        manufacture=ck.FDM("PLA", print_rotation=(-90, 0, 0)),
        group="Covers",
        ports={"axis": axis_frame()},
        production=False,
        description="Removable upper front cover",
    )
    rear_cover = ck.Part(
        "nacelle-rear-cover",
        body=partial(shell_body, REAR_NACELLE, upper=True),
        manufacture=ck.FDM("PLA", print_rotation=(-90, 0, 0)),
        group="Covers",
        ports={"axis": axis_frame()},
        production=False,
        description="Removable upper aft cover",
    )
    nozzle = ck.Part(
        "exhaust-nozzle",
        body=partial(nozzle_body, NOZZLE_SECTION),
        manufacture=ck.FDM("PLA", print_rotation=(90, 0, 0)),
        group="Casing",
        ports={"axis": axis_frame()},
        description="Converging lower exhaust nozzle",
    )
    nozzle_cover = ck.Part(
        "exhaust-upper-cover",
        body=partial(nozzle_body, NOZZLE_SECTION, upper=True),
        manufacture=ck.FDM("PLA", print_rotation=(-90, 0, 0)),
        group="Covers",
        ports={"axis": axis_frame()},
        production=False,
        description="Removable upper nozzle cover",
    )
    return HousingParts(
        inlet=inlet,
        front_shell=front_shell,
        rear_shell=rear_shell,
        front_cover=front_cover,
        rear_cover=rear_cover,
        nozzle=nozzle,
        nozzle_cover=nozzle_cover,
    )
