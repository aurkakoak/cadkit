"""Geometry checks owned by the bearing unit."""
from functools import partial

import cadkit as ck


def shaft_base_overlap(assembly: ck.Assembly):
    models = assembly.models()
    return models["shaft"].intersect(models["base"])


def make_checks(assembly: ck.Assembly) -> tuple[ck.Check, ...]:
    return (ck.Check("shaft-clears-base", partial(shaft_base_overlap, assembly)),)
