"""Bearing-unit placement, motion, contact and clearance relationships."""
import cadkit as ck

from .dimensions import Dimensions
from .parts import make_parts


def make_assembly(dimensions: Dimensions) -> ck.Assembly:
    parts = make_parts(dimensions)
    assembly = ck.Assembly("shaft-support")
    base = assembly.add("base", parts.base, color=(0.30, 0.38, 0.45))
    left = assembly.add("left-support", parts.support, color=(0.35, 0.60, 0.72))
    right = assembly.add("right-support", parts.support, color=(0.35, 0.60, 0.72))
    shaft = assembly.add("shaft", parts.shaft, color=(0.88, 0.69, 0.33))

    assembly.fix(base)
    assembly.connect(
        "left-seat",
        ck.Rigid(),
        parent=base.port("left-support"),
        child=left.port("base"),
    )
    assembly.connect(
        "right-seat",
        ck.Rigid(),
        parent=base.port("right-support"),
        child=right.port("base"),
    )
    assembly.connect(
        "shaft-turn",
        ck.Revolute(),
        parent=left.feature("journal"),
        child=shaft.port("journal"),
    )
    # One placement parent locates the shaft. Its fit in both bores is checked
    # independently; the second support does not add a competing constraint.
    assembly.interface(
        "left-journal-clearance",
        left=left,
        right=shaft,
        kind="clearance",
        min_clearance_mm=dimensions.radial_clearance,
    )
    assembly.interface(
        "right-journal-clearance",
        left=right,
        right=shaft,
        kind="clearance",
        min_clearance_mm=dimensions.radial_clearance,
    )
    assembly.interface("left-base-contact", left=left, right=base)
    assembly.interface("right-base-contact", left=right, right=base)
    assembly.name_pose("quarter-turn", {"shaft-turn": 90})
    return assembly
