"""Contacts between subsystems use their exported components only."""

import cadkit as ck

from .dimensions import EngineDimensions, ShaftFit, MEASUREMENT_ALLOWANCE


def declare_interfaces(
    assembly: ck.Assembly,
    *,
    stand: ck.Instance,
    housing: ck.Instance,
    core: ck.Instance,
    low_pressure: ck.Instance,
    high_pressure: ck.Instance,
    engine: EngineDimensions,
    lp_fit: ShaftFit,
    hp_fit: ShaftFit,
) -> None:
    assembly.interface(
        "concentric-shafts",
        left=low_pressure.component("front-shaft"),
        right=high_pressure.component("shaft"),
        kind="clearance",
        min_clearance_mm=max(0, engine.concentric_clearance - MEASUREMENT_ALLOWANCE),
    )
    for name, shaft, bearing, fit in (
        (
            "front-journal",
            low_pressure.component("front-shaft"),
            core.component("front-bearing"),
            lp_fit,
        ),
        (
            "rear-journal",
            low_pressure.component("rear-shaft"),
            core.component("rear-bearing"),
            lp_fit,
        ),
        (
            "hp-front-journal",
            high_pressure.component("shaft"),
            core.component("hp-front-bearing"),
            hp_fit,
        ),
        (
            "hp-rear-journal",
            high_pressure.component("shaft"),
            core.component("hp-rear-bearing"),
            hp_fit,
        ),
    ):
        assembly.interface(
            name,
            left=shaft,
            right=bearing,
            kind="clearance",
            min_clearance_mm=max(0, fit.journal_clearance - MEASUREMENT_ALLOWANCE),
        )
    assembly.interface(
        "front-saddle-nacelle",
        left=stand.component("front-saddle"),
        right=housing.component("front-shell"),
        kind="contact",
    )
    assembly.interface(
        "rear-saddle-nacelle",
        left=stand.component("rear-saddle"),
        right=housing.component("rear-shell"),
        kind="contact",
    )
    assembly.interface(
        "front-bypass-support-nacelle-front-lower",
        left=core.component("front-support"),
        right=housing.component("front-shell"),
        kind="contact",
    )
    assembly.interface(
        "rear-bypass-support-nacelle-rear-lower",
        left=core.component("rear-support"),
        right=housing.component("rear-shell"),
        kind="contact",
    )
