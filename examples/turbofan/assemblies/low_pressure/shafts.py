"""LP shafts and their end fittings, each built around its own local datum."""

from functools import lru_cache, partial
import math

import cadquery as cq
import cadkit as ck

from ...dimensions import (
    ShaftFit,
    LOW_PRESSURE_FRONT_JOURNAL,
    LOW_PRESSURE_REAR_JOURNAL,
)
from ...geometry import axis_frame, cylinder, d_shaft, revolve
from .dimensions import (
    Dimensions,
    FRONT_SHAFT_START,
    FRONT_SHAFT_LENGTH,
    REAR_SHAFT_START,
    REAR_SHAFT_LENGTH,
    COUPLING_DEPTH,
    COUPLING_ROOT_OVERLAP,
    FAN_STATION,
    SPINNER_STATION,
    TAILCONE_STATION,
    FRONT_ROTOR_STAGES,
    REAR_ROTOR_STAGES,
    FAN_REAR_SPACER,
    STAGE_SPACER,
    Spacer,
)


@lru_cache(maxsize=16)
def front_shaft_body(fit: ShaftFit, dimensions: Dimensions) -> cq.Shape:
    shaft = d_shaft(fit.shaft_radius, fit.shaft_flat, FRONT_SHAFT_LENGTH)
    width = dimensions.coupling_socket_width
    socket = cq.Solid.makeBox(
        COUPLING_DEPTH + COUPLING_ROOT_OVERLAP,
        width,
        width,
        (FRONT_SHAFT_LENGTH - COUPLING_DEPTH, -width / 2, -width / 2),
    )
    return shaft.cut(socket).clean()


@lru_cache(maxsize=16)
def rear_shaft_body(fit: ShaftFit, dimensions: Dimensions) -> cq.Shape:
    shaft = d_shaft(fit.shaft_radius, fit.shaft_flat, REAR_SHAFT_LENGTH)
    width = dimensions.coupling_tongue_width
    tongue = cq.Solid.makeBox(
        COUPLING_DEPTH + COUPLING_ROOT_OVERLAP,
        width,
        width,
        (-COUPLING_DEPTH, -width / 2, -width / 2),
    )
    return shaft.fuse(tongue).clean()


def make_front_shaft(fit: ShaftFit, dimensions: Dimensions) -> ck.Part:
    half_socket = dimensions.coupling_socket_width / 2
    if half_socket >= fit.shaft_flat or math.sqrt(2) * half_socket >= fit.shaft_radius:
        raise ValueError("The coupling socket must leave a wall inside the D shaft")
    return ck.Part(
        "lp-shaft-front",
        body=partial(front_shaft_body, fit, dimensions),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="LP spool",
        description="Front D shaft with a square coupling socket",
        ports={
            "axis": axis_frame(),
            "journal": axis_frame(LOW_PRESSURE_FRONT_JOURNAL - FRONT_SHAFT_START),
            "rear-shaft": axis_frame(REAR_SHAFT_START - FRONT_SHAFT_START),
            "fan": axis_frame(FAN_STATION - FRONT_SHAFT_START),
            "fan-spinner": axis_frame(SPINNER_STATION - FRONT_SHAFT_START),
            FAN_REAR_SPACER.name: axis_frame(FAN_REAR_SPACER.station - FRONT_SHAFT_START),
            STAGE_SPACER.name: axis_frame(STAGE_SPACER.station - FRONT_SHAFT_START),
            **{
                stage.name: axis_frame(stage.station - FRONT_SHAFT_START)
                for stage in FRONT_ROTOR_STAGES
            },
        },
    )


def make_rear_shaft(fit: ShaftFit, dimensions: Dimensions) -> ck.Part:
    return ck.Part(
        "lp-shaft-rear",
        body=partial(rear_shaft_body, fit, dimensions),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="LP spool",
        description="Rear D shaft with a square coupling tongue",
        ports={
            "axis": axis_frame(),
            "journal": axis_frame(LOW_PRESSURE_REAR_JOURNAL - REAR_SHAFT_START),
            "exhaust-tailcone": axis_frame(TAILCONE_STATION - REAR_SHAFT_START),
            **{
                stage.name: axis_frame(stage.station - REAR_SHAFT_START)
                for stage in REAR_ROTOR_STAGES
            },
        },
    )


# (Axial position, radius), in millimetres from each part's leading plane.
# These are intentionally shaped meridians rather than independent fit inputs.
SPINNER_PROFILE = (
    (0, 0),  # Nose on the axis.
    (2, 5),  # Successive taper stations.
    (7, 10),
    (13, 13),  # Start of the full-radius rim.
    (14, 13),  # Rear mating face.
    (14, 0),  # Close the section along the axis.
)
TAILCONE_PROFILE = (
    (0, 0),  # Front mating face, starting on the axis.
    (0, 12),
    (5, 12),  # End of the straight grip section.
    (13, 6),  # Aft taper station.
    (18, 1.5),  # Blunt tip.
    (18, 0),
)
SPINNER_LENGTH = 14.0
SPINNER_SOCKET_DEPTH = 3.0
TAILCONE_SOCKET_DEPTH = 4.0


def make_spinner(fit: ShaftFit) -> ck.Part:
    return ck.Part(
        "fan-spinner",
        body=partial(revolve, SPINNER_PROFILE),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="LP spool",
        description="Conical inlet spinner with a blind keyed socket",
        features={
            "shaft-socket": ck.DBore(
                diameter=fit.bore_diameter,
                flat=fit.bore_flat,
                depth=SPINNER_SOCKET_DEPTH,
                at=ck.Frame((SPINNER_LENGTH, 0, 0), z=(-1, 0, 0), x=(0, 1, 0)),
            ),
        },
        ports={"axis": axis_frame()},
    )


def make_tailcone(fit: ShaftFit) -> ck.Part:
    return ck.Part(
        "exhaust-tailcone",
        body=partial(revolve, TAILCONE_PROFILE),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="LP spool",
        description="Rear hand-turn cone with a blind keyed socket",
        features={
            "shaft-socket": ck.DBore(
                diameter=fit.bore_diameter,
                flat=fit.bore_flat,
                depth=TAILCONE_SOCKET_DEPTH,
                at=axis_frame(),
            ),
        },
        ports={"axis": axis_frame()},
    )


def make_spacer(spacer: Spacer, fit: ShaftFit) -> ck.Part:
    return ck.Part(
        spacer.name,
        body=partial(cylinder, spacer.outer_radius, spacer.length),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="LP spool",
        description="Removable keyed axial spacer",
        features={
            "shaft-bore": ck.DBore(
                diameter=fit.bore_diameter,
                flat=fit.bore_flat,
                depth=spacer.length,
                at=axis_frame(),
                through=True,
            ),
        },
        ports={"axis": axis_frame()},
    )
