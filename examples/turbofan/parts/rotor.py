"""Rotor family shared by both spools; each blade reference plane is local X=0.

Lengths are millimetres and angles are degrees. The section table describes
shape, while a stage's station is used only by the containing assembly.
"""

from dataclasses import dataclass
from functools import lru_cache, partial
import math

import cadquery as cq
import cadkit as ck

from ..dimensions import ShaftFit
from ..geometry import axis_frame, cylinder

# Material beyond the nominal blade chord supports the blade roots.
HUB_FRONT_EXTENSION = 1.0
HUB_REAR_EXTENSION = 6.0


@dataclass(frozen=True, kw_only=True)
class BladeSection:
    radius: float
    chord: float
    stagger: float
    sweep: float
    lean: float
    thickness: float


@dataclass(frozen=True, kw_only=True)
class RotorStage:
    name: str
    station: float
    tip_radius: float
    blade_count: int
    chord: float
    stagger: float
    sweep: float
    hub_radius: float
    blade_thickness: float = 1.8

    @property
    def hub_start(self) -> float:
        return -self.chord / 2 - HUB_FRONT_EXTENSION

    @property
    def hub_length(self) -> float:
        return self.chord + HUB_FRONT_EXTENSION + HUB_REAR_EXTENSION


@dataclass(frozen=True)
class RotorDefinition:
    stage: RotorStage
    part: ck.Part


@dataclass(frozen=True, kw_only=True)
class SpanSection:
    fraction: float
    chord_scale: float
    stagger_offset: float


# The three shaping stations are intentionally tuned proportions, not fits.
SPAN_SECTIONS = (
    SpanSection(fraction=0, chord_scale=0.65, stagger_offset=18),
    SpanSection(fraction=0.52, chord_scale=0.93, stagger_offset=0),
    SpanSection(fraction=1, chord_scale=1, stagger_offset=-16),
)
ROOT_EMBED = 1.2
TIP_AXIAL_LEAN = 4.0
TIP_THICKNESS_REDUCTION = 0.2
SWEEP_MARGIN = 0.0001  # Numerical enclosure margin, not a running clearance.


def blade_sections(stage: RotorStage) -> tuple[BladeSection, ...]:
    root_radius = stage.hub_radius - ROOT_EMBED
    return tuple(
        BladeSection(
            radius=root_radius + (stage.tip_radius - root_radius) * section.fraction,
            chord=stage.chord * section.chord_scale,
            stagger=stage.stagger + section.stagger_offset,
            sweep=stage.sweep * section.fraction**2,
            lean=TIP_AXIAL_LEAN * section.fraction**2,
            thickness=stage.blade_thickness * (1 - TIP_THICKNESS_REDUCTION * section.fraction),
        )
        for section in SPAN_SECTIONS
    )


@lru_cache(maxsize=32)
def blade_body(sections: tuple[BladeSection, ...]) -> cq.Solid:
    """Loft the stated local sections without applying an installed station."""
    wires = []
    for section in sections:
        plane = cq.Plane(
            origin=(section.lean, section.sweep, section.radius),
            xDir=(1, 0, 0),
            normal=(0, 0, 1),
        )
        wire = (
            cq.Workplane(plane)
            .transformed(rotate=(0, 0, section.stagger))
            .ellipse(section.chord / 2, section.thickness / 2)
            .val()
        )
        wires.append(wire)
    return cq.Solid.makeLoft(wires, ruled=False)


@lru_cache(maxsize=32)
def rotor_blank(stage: RotorStage) -> cq.Shape:
    hub = cylinder(stage.hub_radius, stage.hub_length, start=stage.hub_start)
    blade = blade_body(blade_sections(stage))
    blades = [
        blade.rotate((0, 0, 0), (1, 0, 0), 360 * index / stage.blade_count)
        for index in range(stage.blade_count)
    ]
    return hub.fuse(*blades).clean()


@lru_cache(maxsize=32)
def blade_sweep(sections: tuple[BladeSection, ...]) -> cq.Shape:
    """Enclose a native blade through a full turn using its actual face bounds."""
    bounds = blade_body(sections).BoundingBox()
    radius = (
        math.hypot(
            max(abs(bounds.ymin), abs(bounds.ymax)),
            max(abs(bounds.zmin), abs(bounds.zmax)),
        )
        + SWEEP_MARGIN
    )
    return cylinder(radius, bounds.xlen, start=bounds.xmin)


@lru_cache(maxsize=32)
def rotor_sweep(stage: RotorStage) -> cq.Shape:
    """Keep the hub and blade's distinct axial spans in the full-turn envelope."""
    hub = cylinder(stage.hub_radius, stage.hub_length, start=stage.hub_start)
    return hub.fuse(blade_sweep(blade_sections(stage))).clean()


def make_rotor(stage: RotorStage, fit: ShaftFit, *, group: str) -> RotorDefinition:
    if fit.bore_radius >= stage.hub_radius:
        raise ValueError(f"{stage.name}: the keyed bore must leave material in the hub")
    part = ck.Part(
        stage.name,
        body=partial(rotor_blank, stage),
        manufacture=ck.FDM("PLA", print_rotation=(0, 90, 0)),
        group=group,
        description=f"{stage.blade_count} swept blades on a keyed hub",
        features={
            "shaft-bore": ck.DBore(
                diameter=fit.bore_diameter,
                flat=fit.bore_flat,
                depth=stage.hub_length,
                at=axis_frame(stage.hub_start),
                through=True,
            ),
        },
        ports={"axis": axis_frame()},
    )
    return RotorDefinition(stage=stage, part=part)
