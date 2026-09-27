"""Shared boolean work must retain exact material-removal semantics."""
import cadquery as cq
import pytest
from cadkit.design.manufacturing import _cut


def box(x=0):
    return cq.Solid.makeBox(10, 10, 10, (x, 0, 0))


@pytest.mark.parametrize('case', ['overlap', 'nested', 'duplicate', 'compound', 'split'])
def test_shared_cut_matches_independent_boolean_geometry(case):
    body = box()
    first = cq.Solid.makeCylinder(2, 12, (4, 5, -1))
    second = cq.Solid.makeCylinder(2, 12, (6, 5, -1))
    if case == 'nested':
        second = cq.Solid.makeCylinder(3, 3, (4, 5, -1))
    elif case == 'duplicate':
        second = first
    elif case == 'compound':
        body = cq.Compound.makeCompound([body, box(20)])
        second = cq.Solid.makeCylinder(2, 12, (25, 5, -1))
    elif case == 'split':
        first = cq.Solid.makeBox(2, 12, 12, (4, -1, -1))
        second = cq.Solid.makeCylinder(1, 12, (2, 5, -1))
    before = body.Volume()
    reference = body.cut(first, second).clean()
    result = _cut(body, ((first,), (second,)))
    assert result.isValid()
    assert len(result.Solids()) == len(reference.Solids())
    assert result.Volume() == pytest.approx(reference.Volume(), abs=1e-7)
    # Equal volumes alone would miss removed material in the wrong place.
    assert result.intersect(reference).Volume() == pytest.approx(reference.Volume(), abs=1e-7)
    assert body.Volume() == pytest.approx(before)


@pytest.mark.parametrize('x', [10, 11])
def test_touching_or_disjoint_site_is_not_material_removal(x):
    good = cq.Solid.makeCylinder(1, 12, (5, 5, -1))
    bad = cq.Solid.makeBox(2, 2, 2, (x, 2, 2))
    with pytest.raises(ValueError, match='Feature site 2 does not intersect'):
        _cut(box(), ((good,), (bad,)))


def test_cut_cannot_consume_entire_body():
    with pytest.raises(ValueError, match='valid material-removing cut'):
        _cut(box(), ((cq.Solid.makeBox(12, 12, 12, (-1, -1, -1)),),))
