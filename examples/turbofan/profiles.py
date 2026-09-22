"""The shared mating surfaces; axial positions and radii are in millimetres.

These stations describe the TF-300 silhouette. Shells, core supports and stand
saddles consume these same surfaces rather than keeping their own copies.
"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ShellStation:
    x: float
    outer_radius: float
    inner_radius: float


@dataclass(frozen=True)
class ShellProfile:
    stations: tuple[ShellStation, ...]

    def __post_init__(self):
        if len(self.stations) < 2:
            raise ValueError("A shell profile needs at least two stations")
        if any(a.x >= b.x for a, b in zip(self.stations, self.stations[1:])):
            raise ValueError("Profile stations must run from inlet to exhaust")
        if any(not 0 < s.inner_radius < s.outer_radius for s in self.stations):
            raise ValueError("Each shell station needs a positive wall thickness")

    @property
    def start(self) -> float:
        return self.stations[0].x

    @property
    def end(self) -> float:
        return self.stations[-1].x

    @property
    def length(self) -> float:
        return self.end - self.start

    def polygon(self, origin: float = 0) -> tuple[tuple[float, float], ...]:
        return tuple((s.x - origin, s.outer_radius) for s in self.stations) + tuple(
            (s.x - origin, s.inner_radius) for s in reversed(self.stations)
        )

    def _radius_at(self, x: float, *, inner: bool) -> float:
        for left, right in zip(self.stations, self.stations[1:]):
            if left.x <= x <= right.x:
                start = left.inner_radius if inner else left.outer_radius
                end = right.inner_radius if inner else right.outer_radius
                return start + (end - start) * (x - left.x) / (right.x - left.x)
        raise ValueError(f"Station {x:g} lies outside this shell profile")

    def outer_radius_at(self, x: float) -> float:
        return self._radius_at(x, inner=False)

    def inner_radius_at(self, x: float) -> float:
        return self._radius_at(x, inner=True)

    def stations_between(self, start: float, end: float) -> tuple[float, ...]:
        self.outer_radius_at(start)
        self.outer_radius_at(end)
        return tuple(sorted({start, end} | {s.x for s in self.stations if start < s.x < end}))


FRONT_NACELLE = ShellProfile(
    (
        ShellStation(x=18.4, outer_radius=71.0, inner_radius=68.4),
        ShellStation(x=35.0, outer_radius=71.0, inner_radius=68.4),
        ShellStation(x=65.0, outer_radius=68.0, inner_radius=65.4),
        ShellStation(x=105.0, outer_radius=62.0, inner_radius=59.4),
        ShellStation(x=150.0, outer_radius=57.0, inner_radius=54.4),
        ShellStation(x=166.0, outer_radius=55.0, inner_radius=52.4),
    )
)

REAR_NACELLE = ShellProfile(
    (
        ShellStation(x=166.5, outer_radius=54.94, inner_radius=52.34),
        ShellStation(x=206.0, outer_radius=49.5, inner_radius=47.0),
        ShellStation(x=246.0, outer_radius=43.0, inner_radius=40.5),
        ShellStation(x=277.0, outer_radius=38.5, inner_radius=36.0),
    )
)

CORE_LINER = ShellProfile(
    (
        ShellStation(x=58.0, outer_radius=39.0, inner_radius=36.6),
        ShellStation(x=101.0, outer_radius=37.0, inner_radius=34.6),
        ShellStation(x=164.0, outer_radius=29.5, inner_radius=27.1),
        ShellStation(x=172.0, outer_radius=33.0, inner_radius=30.6),
        ShellStation(x=213.0, outer_radius=33.0, inner_radius=30.6),
        ShellStation(x=237.0, outer_radius=34.0, inner_radius=31.6),
        ShellStation(x=275.0, outer_radius=36.0, inner_radius=33.6),
    )
)
