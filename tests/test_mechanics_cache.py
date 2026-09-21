"""Repeated pair checks reuse native queries without changing validation results."""
from collections import Counter
from itertools import combinations

import cadquery as cq
import pytest

from cadkit._project import Assembly, Component, Project
from cadkit import AccessEnvelope, Fastening, Interface
from cadkit import mechanics


def fixture(offsets, *, interfaces=(), fastenings=()):
    models = [cq.Solid.makeBox(2, 2, 2).translate((x, 0, 0)) for x in offsets]
    assembly = Assembly("cache", tuple(
        Component(chr(ord("a") + i), model, "body") for i, model in enumerate(models)
    ))
    project = Project("cache", (), lambda: [], interfaces=interfaces, fastenings=fastenings)
    return project, assembly, models


def uncached_report(monkeypatch, project, assembly):
    with monkeypatch.context() as patch:
        patch.setattr(mechanics, "_memoized_geometry_query", lambda query: query)
        return mechanics.validate_mechanics(project, assembly)


def count_queries(monkeypatch, models):
    counters = {name: Counter() for name in ("BoundingBox", "isValid", "Solids")}
    identities = {id(model) for model in models}
    for name, counts in counters.items():
        original = getattr(cq.Shape, name)
        def counted(self, *args, _counts=counts, _original=original, **kwargs):
            if id(self) in identities:
                _counts[id(self)] += 1
            return _original(self, *args, **kwargs)
        monkeypatch.setattr(cq.Shape, name, counted)
    return counters


def test_bounds_and_solid_queries_are_reused_across_interfaces_collisions_and_access(monkeypatch):
    envelope = cq.Solid.makeBox(20, 2, 2)
    project, assembly, models = fixture(
        (0, 0.5, 1, 10),
        interfaces=(
            Interface("seat", ("a", "b"), "press_fit",
                      region=lambda: cq.Solid.makeBox(2, 2, 2).translate((0.5, 0, 0)),
                      max_overlap_mm3=6),
            Interface("gap", ("a", "d"), "clearance", min_clearance_mm=1),
        ),
        fastenings=(Fastening("tool", ("a",), access=(
            AccessEnvelope("driver", lambda: envelope, ("a", "b", "c", "d")),
        )),),
    )
    expected = uncached_report(monkeypatch, project, assembly)
    counters = count_queries(monkeypatch, [*models, envelope])

    report = mechanics.validate_mechanics(project, assembly)

    assert report == expected
    assert report["coverage"]["pairs_scanned"] == len(list(combinations(models, 2)))
    assert report["coverage"]["installed_collisions"] == "checked"
    assert len([row for row in report["findings"] if row["code"].startswith("collision-")]) == 2
    for counts in counters.values():
        assert counts == Counter({id(model): 1 for model in [*models, envelope]})


@pytest.mark.parametrize(("method", "result"), (
    ("BoundingBox", RuntimeError("bounds unavailable")),
    ("isValid", RuntimeError("validity unavailable")),
    ("Solids", RuntimeError("solids unavailable")),
    ("isValid", False),
    ("Solids", []),
))
def test_failed_queries_are_cached_without_suppressing_pair_findings(monkeypatch, method, result):
    project, assembly, models = fixture((0, 0.5, 1), interfaces=(
        Interface("first", ("a", "b"), "clearance"),
        Interface("second", ("a", "c"), "clearance"),
    ))
    calls = 0
    def failed_query():
        nonlocal calls
        calls += 1
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(models[0], method, failed_query)
    expected = uncached_report(monkeypatch, project, assembly)
    calls = 0

    report = mechanics.validate_mechanics(project, assembly)

    assert report == expected
    assert calls == 1
    assert report["coverage"]["pairs_scanned"] == 3
    assert report["coverage"]["kernel_failures"] == 2
    assert report["coverage"]["installed_collisions"] == "partial"
    affected = [row for row in report["findings"] if "/cache/a" in row["component_ids"]]
    assert len(affected) == 4  # Two interfaces and both automatic collision pairs.
    assert all(row["status"] == "unverified" for row in affected)


def test_next_validation_rechecks_the_same_shape_after_translation(monkeypatch):
    project, assembly, models = fixture((0, 1), interfaces=(
        Interface("gap", ("a", "b"), "clearance", min_clearance_mm=1),
    ))
    counters = count_queries(monkeypatch, models)
    first = mechanics.validate_mechanics(project, assembly)
    assert any(row["code"].startswith("collision-") for row in first["findings"])

    models[1].move(cq.Location(cq.Vector(10, 0, 0)))
    second = mechanics.validate_mechanics(project, assembly)

    assert not any(row["code"].startswith("collision-") for row in second["findings"])
    fit = next(row for row in second["findings"] if row["code"] == "fit")
    assert fit["status"] == "pass"
    assert fit["evidence"]["gap_mm"] == pytest.approx(9)
    for counts in counters.values():
        assert counts == Counter({id(model): 2 for model in models})


def test_collision_only_pairs_do_not_query_distance(monkeypatch):
    project, assembly, _ = fixture((0, 0.5, 1))
    expected = mechanics.validate_mechanics(project, assembly)
    calls = []
    def unexpected_distance(self, other):
        calls.append((self, other))
        raise RuntimeError("distance query is unnecessary for collision checking")
    monkeypatch.setattr(cq.Shape, "distance", unexpected_distance)

    report = mechanics.validate_mechanics(project, assembly)

    assert report == expected
    assert calls == []
    assert report["coverage"]["pairs_scanned"] == 3
    assert report["coverage"]["installed_collisions"] == "checked"
    assert report["coverage"]["kernel_failures"] == 0
    collisions = [row for row in report["findings"] if row["code"].startswith("collision-")]
    assert len(collisions) == 3
    assert all(row["status"] == "fail" for row in collisions)


def test_interfaces_query_distances_once_per_pair_and_preserve_report(monkeypatch):
    project, assembly, models = fixture((0, 0.5, 1, 10), interfaces=(
        Interface("gap", ("a", "d"), "clearance", min_clearance_mm=1),
        Interface("gap-again", ("d", "a"), "clearance", min_clearance_mm=1),
        Interface("overlap", ("a", "b"), "clearance"),
    ))
    expected = mechanics.validate_mechanics(project, assembly)
    calls = Counter()
    original = cq.Shape.distance
    def counted_distance(self, other):
        calls[frozenset((id(self), id(other)))] += 1
        return original(self, other)
    monkeypatch.setattr(cq.Shape, "distance", counted_distance)

    report = mechanics.validate_mechanics(project, assembly)

    assert report == expected
    assert calls == Counter({
        frozenset((id(models[0]), id(models[3]))): 1,
        frozenset((id(models[0]), id(models[1]))): 1,
    })
    fits = {row["entity"]: row for row in report["findings"] if row["code"] == "fit"}
    assert fits["gap"]["status"] == fits["gap-again"]["status"] == "pass"
    assert fits["gap"]["evidence"]["gap_mm"] == pytest.approx(8)
    assert fits["overlap"]["status"] == "fail"
    assert fits["overlap"]["evidence"]["gap_mm"] == pytest.approx(0)
    assert report["coverage"]["pairs_scanned"] == 6


def test_failed_interface_distance_preserves_independent_collision_evidence(monkeypatch):
    project, assembly, _ = fixture((0, 0.5, 1), interfaces=(
        Interface("gap", ("a", "b"), "clearance"),
    ))
    expected = mechanics.validate_mechanics(project, assembly)
    calls = 0
    def failed_distance(self, other):
        nonlocal calls
        calls += 1
        raise RuntimeError("native distance unavailable")
    monkeypatch.setattr(cq.Shape, "distance", failed_distance)

    report = mechanics.validate_mechanics(project, assembly)

    assert calls == 1
    fit = next(row for row in report["findings"] if row["code"] == "fit")
    assert fit["status"] == "unverified"
    assert fit["message"] == "native distance unavailable"
    assert report["coverage"] == expected["coverage"]
    assert [row for row in report["findings"] if row["concept"] == "assembly"] == [
        row for row in expected["findings"] if row["concept"] == "assembly"
    ]
