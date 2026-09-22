"""Cross-subsystem evidence measured from native geometry and resolved placement."""

from functools import cache

import cadquery as cq
import cadkit as ck

from .assemblies.high_pressure.dimensions import ROTOR_STAGES as HP_STAGES
from .assemblies.low_pressure.dimensions import FRONT_ROTOR_STAGES, REAR_ROTOR_STAGES
from .assemblies.low_pressure.fan import fan_sweep
from .parts.rotor import rotor_sweep


def intersections(envelopes: tuple[cq.Shape, ...], obstacles: tuple[cq.Shape, ...]) -> cq.Compound:
    witnesses = []
    for envelope in envelopes:
        swept = envelope.BoundingBox()
        for obstacle in obstacles:
            fixed = obstacle.BoundingBox()
            if swept.xmin <= fixed.xmax and swept.xmax >= fixed.xmin:
                witnesses.append(envelope.intersect(obstacle))
    return cq.Compound.makeCompound(witnesses)


def make_checks(assembly: ck.Assembly, *, pose=None) -> tuple[ck.Check, ...]:
    # Freeze the same graph used for export; building a check cannot follow later edits.
    installed = assembly.pose(pose or {})
    fixed_groups = {"Casing", "Covers", "Static core", "Combustor", "Display"}
    fixed_names = tuple(
        name for name, instance in assembly.instances.items() if instance.part.group in fixed_groups
    )

    @cache
    def models() -> dict[str, cq.Shape]:
        return {name: model.val() for name, model in installed.models().items()}

    @cache
    def sweeps() -> dict[str, cq.Shape]:
        locations = installed.locations()
        result = {"fan": fan_sweep().moved(locations["fan"])}
        for stage in (*FRONT_ROTOR_STAGES, *HP_STAGES, *REAR_ROTOR_STAGES):
            result[stage.name] = rotor_sweep(stage).moved(locations[stage.name])
        return result

    def fan_casing_overlap() -> cq.Compound:
        casing = tuple(
            models()[name]
            for name in (
                "inlet-lip",
                "nacelle-front-lower",
                "nacelle-front-cover",
            )
            if name in models()
        )
        return intersections((sweeps()["fan"],), casing)

    def core_rotor_liner_overlap() -> cq.Compound:
        core_rotors = tuple(shape for name, shape in sweeps().items() if name != "fan")
        return intersections(core_rotors, (models()["core-cutaway"],))

    def concentric_shaft_overlap() -> cq.Shape:
        return models()["lp-shaft-front"].intersect(models()["hp-shaft-sleeve"])

    def shaft_coupling_overlap() -> cq.Shape:
        return models()["lp-shaft-front"].intersect(models()["lp-shaft-rear"])

    def all_rotors_fixed_engine_overlap() -> cq.Compound:
        fixed_parts = tuple(models()[name] for name in fixed_names)
        return intersections(tuple(sweeps().values()), fixed_parts)

    return (
        ck.Check("fan-full-turn-casing-clearance", fan_casing_overlap),
        ck.Check("all-core-rotors-full-turn-liner-clearance", core_rotor_liner_overlap),
        ck.Check("concentric-shafts-no-overlap", concentric_shaft_overlap),
        ck.Check("shaft-square-coupling-no-overlap", shaft_coupling_overlap),
        ck.Check("all-nine-rotors-full-turn-versus-fixed-engine", all_rotors_fixed_engine_overlap),
    )
