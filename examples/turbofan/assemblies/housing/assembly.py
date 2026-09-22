"""Install the casing parts in inlet-relative coordinates."""

import cadkit as ck

from ... import appearance as colors
from .parts import HousingParts, make_parts
from .specifications import HOUSING_LAYOUT


def make_assembly(*, parts: HousingParts | None = None, covers: bool = True) -> ck.Assembly:
    parts = parts if parts is not None else make_parts()
    assembly = ck.Assembly("housing")
    inlet = assembly.add(parts.inlet, color=colors.INLET)
    assembly.fix(inlet, at=ck.Frame((HOUSING_LAYOUT.inlet, 0, 0)))
    front = assembly.add(parts.front_shell, color=colors.NACELLE)
    assembly.fix(front, at=ck.Frame((HOUSING_LAYOUT.front_shell, 0, 0)))
    rear = assembly.add(parts.rear_shell, color=colors.NACELLE)
    assembly.fix(rear, at=ck.Frame((HOUSING_LAYOUT.rear_shell, 0, 0)))
    nozzle = assembly.add(parts.nozzle, color=colors.NOZZLE)
    assembly.fix(nozzle, at=ck.Frame((HOUSING_LAYOUT.nozzle, 0, 0)))

    if covers:
        front_cover = assembly.add(parts.front_cover, color=colors.NACELLE_COVER)
        assembly.connect(
            "front-cover-seat",
            ck.Rigid(),
            parent=front.port("axis"),
            child=front_cover.port("axis"),
        )
        rear_cover = assembly.add(parts.rear_cover, color=colors.NACELLE_COVER)
        assembly.connect(
            "rear-cover-seat", ck.Rigid(), parent=rear.port("axis"), child=rear_cover.port("axis")
        )
        nozzle_cover = assembly.add(parts.nozzle_cover, color=colors.NOZZLE_COVER)
        assembly.connect(
            "nozzle-cover-seat",
            ck.Rigid(),
            parent=nozzle.port("axis"),
            child=nozzle_cover.port("axis"),
        )
        for cover, shell in ((front_cover, front), (rear_cover, rear), (nozzle_cover, nozzle)):
            assembly.interface(f"{cover.name}-seam", left=cover, right=shell, kind="contact")

    assembly.export_component("front-shell", front)
    assembly.export_component("rear-shell", rear)
    return assembly
