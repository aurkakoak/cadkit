"""Physical contact and clearance requirements across subsystem boundaries."""

import cadkit as ck

from .assemblies.low_pressure.dimensions import Dimensions as LowPressureDimensions
from .dimensions import EngineDimensions, ShaftFit

MEASUREMENT_ALLOWANCE = 0.01  # Millimetres below the designed nominal clearance.
CONTACT_GAP = 0.001


def declare_interfaces(
    assembly: ck.Assembly,
    *,
    engine: EngineDimensions,
    lp_fit: ShaftFit,
    hp_fit: ShaftFit,
    low_pressure: LowPressureDimensions,
) -> None:
    parts = assembly.instances
    assembly.interface(
        "concentric-shafts",
        left=parts["lp-shaft-front"],
        right=parts["hp-shaft-sleeve"],
        kind="clearance",
        min_clearance_mm=max(0, engine.concentric_clearance - MEASUREMENT_ALLOWANCE),
    )
    for name, shaft, bearing, fit in (
        ("front-journal", "lp-shaft-front", "front-bearing-spider", lp_fit),
        ("rear-journal", "lp-shaft-rear", "rear-bearing-spider", lp_fit),
        ("hp-front-journal", "hp-shaft-sleeve", "hp-front-bearing", hp_fit),
        ("hp-rear-journal", "hp-shaft-sleeve", "hp-rear-bearing", hp_fit),
    ):
        assembly.interface(
            name,
            left=parts[shaft],
            right=parts[bearing],
            kind="clearance",
            min_clearance_mm=max(0, fit.journal_clearance - MEASUREMENT_ALLOWANCE),
        )
    assembly.interface(
        "square-shaft-coupling",
        left=parts["lp-shaft-front"],
        right=parts["lp-shaft-rear"],
        kind="clearance",
        min_clearance_mm=max(0, low_pressure.coupling_clearance - MEASUREMENT_ALLOWANCE),
    )
    for saddle, shell in (
        ("front-saddle", "nacelle-front-lower"),
        ("rear-saddle", "nacelle-rear-lower"),
    ):
        assembly.interface(
            f"{saddle}-seat",
            left=parts["display-base"],
            right=parts[saddle],
            kind="contact",
            max_gap_mm=CONTACT_GAP,
        )
        assembly.interface(
            f"{saddle}-nacelle",
            left=parts[saddle],
            right=parts[shell],
            kind="contact",
            max_gap_mm=CONTACT_GAP,
        )
    for support, shell in (
        ("front-bypass-support", "nacelle-front-lower"),
        ("rear-bypass-support", "nacelle-rear-lower"),
    ):
        for seat in ("core-cutaway", shell):
            assembly.interface(
                f"{support}-{seat}",
                left=parts[support],
                right=parts[seat],
                kind="contact",
                max_gap_mm=CONTACT_GAP,
            )
    assembly.interface(
        "combustor-locating-bands",
        left=parts["combustor-liner"],
        right=parts["core-cutaway"],
        kind="contact",
        max_gap_mm=CONTACT_GAP,
    )
    for cover, shell in (
        ("nacelle-front-cover", "nacelle-front-lower"),
        ("nacelle-rear-cover", "nacelle-rear-lower"),
        ("exhaust-upper-cover", "exhaust-nozzle"),
    ):
        if cover in parts:
            assembly.interface(
                f"{cover}-seam",
                left=parts[cover],
                right=parts[shell],
                kind="contact",
                max_gap_mm=CONTACT_GAP,
            )
