"""The refined fan's measured drawing sections, local to its blade plane."""

from functools import lru_cache, partial

import cadquery as cq
import cadkit as ck

from ...dimensions import ShaftFit
from ...geometry import axis_frame, cylinder
from ...parts.rotor import BladeSection, blade_body, blade_sweep
from .dimensions import Dimensions, FAN_HUB_LENGTH, FAN_HUB_RADIUS, FAN_HUB_START

# Radius/chord/sweep/lean/thickness are millimetres; stagger is in degrees.
# These stations define the rounded tip. They are not a radial scaling control.
FAN_SECTIONS = (
    BladeSection(radius=13.8, chord=6.0, stagger=54.0, sweep=0.0, lean=0.0, thickness=2.6),
    BladeSection(radius=21.0, chord=11.0, stagger=56.0, sweep=0.7, lean=0.0, thickness=2.6),
    BladeSection(radius=34.0, chord=20.0, stagger=54.0, sweep=3.0, lean=0.5, thickness=2.6),
    BladeSection(radius=48.0, chord=24.0, stagger=51.0, sweep=7.0, lean=1.4, thickness=2.5),
    BladeSection(radius=58.8, chord=24.0, stagger=49.0, sweep=11.0, lean=2.3, thickness=2.4),
    BladeSection(radius=60.8, chord=20.8, stagger=48.5, sweep=11.5, lean=2.5, thickness=2.3),
    BladeSection(radius=62.25, chord=12.6, stagger=48.0, sweep=11.85, lean=2.6, thickness=2.1),
    BladeSection(radius=63.05, chord=2.0, stagger=47.8, sweep=12.0, lean=2.66, thickness=1.6),
)


@lru_cache(maxsize=8)
def fan_blank(dimensions: Dimensions) -> cq.Shape:
    blade = blade_body(FAN_SECTIONS)
    hub = cylinder(FAN_HUB_RADIUS, FAN_HUB_LENGTH, start=FAN_HUB_START)
    blades = [
        blade.rotate((0, 0, 0), (1, 0, 0), 360 * index / dimensions.fan_blade_count)
        for index in range(dimensions.fan_blade_count)
    ]
    return hub.fuse(*blades).clean()


@lru_cache(maxsize=1)
def fan_sweep() -> cq.Shape:
    """A full-turn envelope is independent of how many blades share this profile."""
    hub = cylinder(FAN_HUB_RADIUS, FAN_HUB_LENGTH, start=FAN_HUB_START)
    return hub.fuse(blade_sweep(FAN_SECTIONS)).clean()


def make_fan(dimensions: Dimensions, fit: ShaftFit) -> ck.Part:
    if fit.bore_radius >= FAN_HUB_RADIUS:
        raise ValueError("The fan's keyed bore must leave material in its hub")
    return ck.Part(
        "fan",
        body=partial(fan_blank, dimensions),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group="LP spool",
        description=f"{dimensions.fan_blade_count} swept blades with a broad chord and rounded tips",
        features={
            "shaft-bore": ck.DBore(
                diameter=fit.bore_diameter,
                flat=fit.bore_flat,
                depth=FAN_HUB_LENGTH,
                at=axis_frame(FAN_HUB_START),
                through=True,
            ),
        },
        ports={"axis": axis_frame()},
    )
