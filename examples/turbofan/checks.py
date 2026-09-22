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
    stationary = tuple(assembly.instances[name] for name in ("housing", "core", "stand"))
    fixed_names = tuple(
        f"{unit.name}/{path}" for unit in stationary for path in unit.part.locations(names="path")
    )

    @cache
    def models() -> dict[str, cq.Shape]:
        return {name: model.val() for name, model in installed.models(names="path").items()}

    @cache
    def sweeps() -> dict[str, cq.Shape]:
        locations = installed.locations(names="path")
        result = {"fan": fan_sweep().moved(locations["low-pressure/fan"])}
        for unit, stages in (
            ("low-pressure", (*FRONT_ROTOR_STAGES, *REAR_ROTOR_STAGES)),
            ("high-pressure", HP_STAGES),
        ):
            for stage in stages:
                result[stage.name] = rotor_sweep(stage).moved(locations[f"{unit}/{stage.name}"])
        return result

    def fan_casing_overlap() -> cq.Compound:
        casing = tuple(
            models()[name]
            for name in (
                "housing/inlet-lip",
                "housing/nacelle-front-lower",
                "housing/nacelle-front-cover",
            )
            if name in models()
        )
        return intersections((sweeps()["fan"],), casing)

    def core_rotor_liner_overlap() -> cq.Compound:
        core_rotors = tuple(shape for name, shape in sweeps().items() if name != "fan")
        return intersections(core_rotors, (models()["core/core-cutaway"],))

    def concentric_shaft_overlap() -> cq.Shape:
        return models()["low-pressure/lp-shaft-front"].intersect(
            models()["high-pressure/hp-shaft-sleeve"]
        )

    def shaft_coupling_overlap() -> cq.Shape:
        return models()["low-pressure/lp-shaft-front"].intersect(
            models()["low-pressure/lp-shaft-rear"]
        )

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
