"""CLI and desktop entry points for the TF-300 educational turbofan."""

import cadkit as ck

from .assembly import make_assembly
from .assemblies.housing.parts import make_parts as make_housing_parts
from .assemblies.low_pressure.dimensions import Dimensions as LowPressureDimensions
from .assemblies.stand.dimensions import StandDimensions
from .checks import make_checks
from .dimensions import EngineDimensions, ShaftFit, LOW_PRESSURE_FIT, HIGH_PRESSURE_FIT


def make_project(
    *,
    engine: EngineDimensions = EngineDimensions(),
    lp_fit: ShaftFit = LOW_PRESSURE_FIT,
    hp_fit: ShaftFit = HIGH_PRESSURE_FIT,
    low_pressure: LowPressureDimensions = LowPressureDimensions(),
    stand: StandDimensions = StandDimensions(),
    covers: bool = True,
    pose=None,
) -> ck.Project:
    housing = make_housing_parts()
    assembly = make_assembly(
        engine=engine,
        lp_fit=lp_fit,
        hp_fit=hp_fit,
        low_pressure=low_pressure,
        stand=stand,
        housing=housing,
        covers=covers,
    )
    return assembly.as_project(
        description="A 300 mm educational turbofan with removable covers and two independent spools.",
        parameters=(
            *engine.parameters(scope="engine"),
            *lp_fit.parameters(scope="lp-fit"),
            *hp_fit.parameters(scope="hp-fit"),
            *low_pressure.parameters(scope="low-pressure"),
            *stand.parameters(scope="stand"),
        ),
        checks=make_checks(assembly, pose=pose),
        extra_parts=(housing.front_cover, housing.rear_cover, housing.nozzle_cover),
        pose=pose,
    )


PROJECT = make_project()
OPEN_PROJECT = make_project(covers=False)
