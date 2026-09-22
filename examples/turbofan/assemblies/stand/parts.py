"""Local stand bodies and manufacturing intent; the assembly places the stand."""

from dataclasses import dataclass
from functools import lru_cache, partial

import cadquery as cq
import cadkit as ck

from ...dimensions import EngineDimensions
from ...geometry import CUTTER_OVERRUN, revolve
from ...profiles import FRONT_NACELLE, REAR_NACELLE, ShellProfile
from .dimensions import BASE_CENTRE_X, FRONT_SADDLE_X, REAR_SADDLE_X, StandDimensions


@lru_cache(maxsize=None)
def base_body(dimensions: StandDimensions) -> cq.Shape:
    """Origin at the bottom-face centre; +X follows the engine axis."""
    body = (
        cq.Workplane("XY")
        .box(
            dimensions.base_length,
            dimensions.base_width,
            dimensions.base_thickness,
            centered=(True, True, False),
        )
        .edges("|Z")
        .fillet(dimensions.corner_radius)
        .val()
    )
    for station in (FRONT_SADDLE_X, REAR_SADDLE_X):
        socket = cq.Solid.makeBox(
            dimensions.socket_length,
            dimensions.socket_width,
            dimensions.base_thickness - dimensions.socket_floor + CUTTER_OVERRUN,
            (
                station - BASE_CENTRE_X - dimensions.socket_length / 2,
                -dimensions.socket_width / 2,
                dimensions.socket_floor,
            ),
        )
        body = body.cut(socket)
    return body


@lru_cache(maxsize=None)
def saddle_body(
    dimensions: StandDimensions,
    engine: EngineDimensions,
    station: float,
    profile: ShellProfile,
) -> cq.Shape:
    """Origin at the tenon's bottom centre; the shared nacelle profile cuts its seat.

    The blank reaches the engine axis, wholly above the required lower seat.
    Cutting the filled profile removes that excess; no guessed pedestal height
    or separately rounded nacelle radius determines the finished saddle.
    """
    stations = profile.stations_between(
        station - dimensions.saddle_thickness / 2,
        station + dimensions.saddle_thickness / 2,
    )
    radii = tuple(profile.outer_radius_at(x) for x in stations)
    if dimensions.saddle_width / 2 >= min(radii):
        raise ValueError("The complete saddle width must lie below the nacelle's lower half")
    local_axis_height = engine.axis_height - dimensions.socket_floor
    if local_axis_height <= max(radii):
        raise ValueError("The engine axis must leave positive saddle height above the socket floor")
    blank = cq.Solid.makeBox(
        dimensions.saddle_thickness,
        dimensions.saddle_width,
        local_axis_height,
        (-dimensions.saddle_thickness / 2, -dimensions.saddle_width / 2, 0),
    )
    section = (
        ((profile.start - station, 0),)
        + tuple((point.x - station, point.outer_radius) for point in profile.stations)
        + ((profile.end - station, 0),)
    )
    nacelle_envelope = revolve(section).translate((0, 0, local_axis_height))
    return blank.cut(nacelle_envelope).clean()


@dataclass(frozen=True)
class StandParts:
    base: ck.Part
    front_saddle: ck.Part
    rear_saddle: ck.Part


def make_parts(dimensions: StandDimensions, engine: EngineDimensions) -> StandParts:
    base = ck.Part(
        "display-base",
        body=partial(base_body, dimensions),
        manufacture=ck.FDM("PLA"),
        group="Display",
        description=f"{dimensions.base_length:g} × {dimensions.base_width:g} mm base with two keyed saddle sockets",
        ports={
            "front-saddle": ck.Frame((FRONT_SADDLE_X - BASE_CENTRE_X, 0, dimensions.socket_floor)),
            "rear-saddle": ck.Frame((REAR_SADDLE_X - BASE_CENTRE_X, 0, dimensions.socket_floor)),
        },
    )
    front_saddle = ck.Part(
        "front-saddle",
        body=partial(saddle_body, dimensions, engine, FRONT_SADDLE_X, FRONT_NACELLE),
        manufacture=ck.FDM("PLA", print_rotation=(90, 0, 0)),
        group="Display",
        description="Removable inlet saddle, clearance in base socket",
        ports={"base": ck.Frame()},
    )
    rear_saddle = ck.Part(
        "rear-saddle",
        body=partial(saddle_body, dimensions, engine, REAR_SADDLE_X, REAR_NACELLE),
        manufacture=ck.FDM("PLA", print_rotation=(90, 0, 0)),
        group="Display",
        description="Removable exhaust saddle",
        ports={"base": ck.Frame()},
    )
    return StandParts(base=base, front_saddle=front_saddle, rear_saddle=rear_saddle)
