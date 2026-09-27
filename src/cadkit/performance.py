"""Scoped wall-clock diagnostics; no geometry or process-global profiling hooks."""

from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
import sys

_current = ContextVar("cadkit_timings", default=None)


def peak_rss_bytes():
    """Process peak resident memory on Unix; unavailable platforms return None."""
    try:
        import resource
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


class Timings:
    """Collect inclusive timings for one build. Nested stages must not be summed."""

    def __init__(self):
        self.entries = {}

    @contextmanager
    def collect(self):
        token = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(token)

    def add(self, stage, name, seconds):
        entry = self.entries.setdefault((stage, name), [0.0, 0])
        entry[0] += seconds
        entry[1] += 1

    def describe(self):
        stages = {}
        operations = []
        for (stage, name), (seconds, calls) in self.entries.items():
            stages[stage] = stages.get(stage, 0.0) + seconds
            if name:
                operations.append({"stage": stage, "name": name,
                                   "seconds": round(seconds, 6), "calls": calls})
        return {"stages_seconds": {key: round(value, 6) for key, value in stages.items()},
                "operations": sorted(operations, key=lambda item: -item["seconds"])}


@contextmanager
def measure(stage, name=""):
    """Time a stage only while a build collector is active, including failures."""
    collector = _current.get()
    if collector is None:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        collector.add(stage, name, perf_counter() - started)
