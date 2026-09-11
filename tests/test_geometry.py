import math
import cadquery as cq
import pytest
from cadkit import geometry as g
from cadkit.fits import Bore, Countersink, fit_coupon


def test_planar_hull_fills_triangle_and_offsets_one_boundary():
    profile = g.hull(
        [g.translate([g.circle(r=2)], xy) for xy in ((0, 0), (30, 0), (0, 30))]
    )
    assert len(profile.Faces()) == 1
    assert len(profile.Faces()[0].innerWires()) == 0
    # Convex triangle Minkowski-summed with a circle.
    assert profile.Area() == pytest.approx(
        450 + 2 * (60 + 30 * math.sqrt(2)) + 4 * math.pi, abs=1e-6
    )
    inset = g.offset([profile], delta=-1)
    assert len(inset.Faces()) == 1 and not inset.Faces()[0].innerWires()
    assert inset.Area() < profile.Area()


def test_hull_of_single_concave_profile_is_convex():
    profile = g.polygon([(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)])
    convex = g.hull([profile])
    assert convex.Area() == pytest.approx(82)


def test_capsule_and_annulus_keep_analytic_dimensions():
    solid = g.capsule(diameter=6, travel=20, height=4)
    assert solid.Volume() == pytest.approx((120 + math.pi * 9) * 4)
    ring = g.annulus(22, 8, 7).val()
    assert ring.Volume() == pytest.approx(math.pi * (11**2 - 4**2) * 7)


def test_measured_fits_and_countersink():
    assert Bore(8, 0.2).diameter == 8.2
    assert Countersink(4.5, 8.5).depth == pytest.approx(2)
    assert fit_coupon(5).isValid()
    with pytest.raises(ValueError):
        Bore(0)
    with pytest.raises(ValueError):
        _ = Countersink(5, 4).depth
