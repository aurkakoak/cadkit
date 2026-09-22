"""The core/bypass boundary, open above its local X axis."""

from functools import lru_cache

import cadquery as cq

from ...geometry import lower_half, revolve
from ...profiles import ShellProfile


@lru_cache(maxsize=None)
def liner_body(profile: ShellProfile) -> cq.Shape:
    """Put the profile's leading station at the part's local X=0 face."""
    return lower_half(revolve(profile.polygon(origin=profile.start)))
