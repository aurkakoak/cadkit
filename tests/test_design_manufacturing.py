"""Manufacturing intent generates measurable native geometry and process steps."""
import math
from dataclasses import replace
import cadquery as cq
import pytest
from cadkit import FastenerSpec
from cadkit.design import Frame, Part, FDM, InsertPocket, InsertMount, PolarPattern, Counterbore
from cadkit.design.manufacturing import (Hole, CounterboredHole, CountersunkHole,
    TappedHole, BearingSeat, Slot, NutPocket, DBore, SealGroove)
from cadkit.design.mounts import ThreadedMount, InsertBoss


def blank():
    return cq.Workplane("XY").rect(30,30).extrude(10).val()


def test_blind_and_through_holes_preserve_floor_and_original_body():
    body = blank()
    blind = Hole(4, 6).apply(body)
    assert body.Volume()-blind.Volume() == pytest.approx(math.pi*2**2*6)
    floor = cq.Solid.makeCylinder(1,1,(0,0,7))
    assert blind.intersect(floor).Volume() == pytest.approx(floor.Volume())
    through = Hole(4,10,through=True).apply(body)
    assert body.Volume()-through.Volume() == pytest.approx(math.pi*2**2*10)
    assert body.Volume() == pytest.approx(9000)


def test_counterbore_and_countersink_geometry_matches_authored_seat():
    body = blank()
    cb = CounterboredHole(3,10,through=True,recess=Counterbore(6,2))
    assert body.Volume()-cb.apply(body).Volume() == pytest.approx(math.pi*(3**2*2+1.5**2*8))
    cs = CountersunkHole(3,10,head_diameter=6,through=True)
    assert cs.recess_depth == pytest.approx(1.5)
    # Cone frustum replaces the same length of cylindrical hole.
    expected = math.pi*1.5**2*(10-1.5) + math.pi*1.5/3*(3**2+3*1.5+1.5**2)
    assert body.Volume()-cs.apply(body).Volume() == pytest.approx(expected)


def test_each_site_and_each_recess_must_remove_material():
    with pytest.raises(ValueError,match="does not intersect"):
        Hole(3,5,at=Frame((100,0,0))).apply(blank())
    # Existing pilot leaves no material for the declared main hole.
    drilled = Hole(3,10,through=True).apply(blank())
    with pytest.raises(ValueError,match="does not intersect"):
        CounterboredHole(3,10,through=True,recess=Counterbore(6,2)).apply(drilled)
    with pytest.raises(ValueError,match="positive screw seat"):
        CounterboredHole(3,3,recess=Counterbore(6,3))


def test_tapped_hole_models_pilot_and_reports_secondary_operation():
    tap = TappedHole("M3-0.5",2.5,6,thread_depth=5)
    assert blank().Volume()-tap.apply(blank()).Volume() == pytest.approx(math.pi*1.25**2*6)
    assert tap.describe()["operations"] == [{"kind":"tap-after-printing","thread":"M3-0.5",
                                              "thread_depth":5,"quantity":1}]
    with pytest.raises(ValueError,match="Thread depth"):
        replace(tap,thread_depth=7)


def test_fit_allowance_is_independent_of_nominal_geometry():
    seat = BearingSeat(10,.2,4)
    assert seat.describe()["nominal_diameter"] == 10
    assert seat.describe()["allowance"] == .2
    assert blank().Volume()-seat.apply(blank()).Volume() == pytest.approx(math.pi*5.1**2*4)
    with pytest.raises(ValueError,match="nonnegative"):
        replace(seat,allowance=-.1)
    assert replace(seat,allowance=-.1,fit="press").diameter == pytest.approx(9.9)


def test_slot_nut_pocket_and_d_bore_define_inspectable_features():
    slot = Slot(8,4,3)
    assert blank().Volume()-slot.apply(blank()).Volume() == pytest.approx((4*4+math.pi*2**2)*3)
    nut = NutPocket(5.5,2,thread="M3-0.5")
    assert blank().Volume()-nut.apply(blank()).Volume() == pytest.approx(math.sqrt(3)/2*5.5**2*2)
    assert nut.describe()["operations"][0]["kind"] == "install-nut"
    bore = DBore(6,10,through=True,flat=1)
    result = bore.apply(blank())
    # The D flat leaves shaft-key material to the +X side.
    retained = cq.Solid.makeCylinder(.2,1,(2,0,4))
    removed = cq.Solid.makeCylinder(.2,1,(-2,0,4))
    assert result.intersect(retained).Volume() == pytest.approx(retained.Volume())
    assert result.intersect(removed).Volume() == pytest.approx(0)


def test_insert_boss_must_connect_and_preserves_pocket_floor():
    pocket = InsertPocket(4,4)
    boss = InsertBoss(pocket,at=Frame((0,0,-5)),outer_diameter=8,depth=6)
    result = boss.apply(blank())
    assert len(result.Solids()) == 1
    assert result.BoundingBox().zmin == pytest.approx(-5)
    with pytest.raises(ValueError,match="join"):
        replace(boss,at=Frame((40,0,-5))).apply(blank())


def test_toroidal_seal_feature_is_named_and_removes_material():
    groove = SealGroove(8,1,Frame((0,0,1)))
    assert blank().Volume()-groove.apply(blank()).Volume() == pytest.approx(2*math.pi**2*8)
    assert groove.describe()["kind"] == "seal-groove"


def test_threaded_mount_drives_both_roles_and_unknown_supplier_depth_stays_unknown():
    screw = FastenerSpec("socket_head_cap_screw","M3-0.5",length_mm=8)
    mount = ThreadedMount(PolarPattern(8,(0,180)),screw,3.4,2.5,6,7,3)
    top = mount.clearance_side(thickness=3,head_recess=Counterbore(6,1))
    receiver = mount.threaded_side()
    base = cq.Workplane("XY").rect(30,20).extrude(-10).val()
    assert base.Volume()-receiver.apply(base).Volume() == pytest.approx(2*math.pi*1.25**2*7)
    fastening = mount.fastening("joint",through="top",into="base",frame=Frame(),clearance=top)
    assert fastening.grip_mm == 2
    assert fastening.thread_depth_mm == 6
    assert fastening.hole_depth_mm == 9
    assert receiver.describe()["operations"][0]["kind"] == "tap-after-printing"
    supplied_mount = ThreadedMount(mount.pattern,screw,3.4)
    with pytest.raises(ValueError,match="manufactured threaded"):
        supplied_mount.threaded_side()
    supplied = supplied_mount.threaded_side(supplied=True)
    assert supplied.apply(base) is base
    assert supplied.describe()["operations"] == []
    supplied_fastening = supplied_mount.fastening("supplied",through="top",into="motor",
                            frame=Frame(),clearance=supplied_mount.clearance_side(thickness=2))
    assert supplied_fastening.thread_depth_mm is None
    assert supplied_fastening.hole_depth_mm is None


def test_stack_material_faces_derive_grip_and_validate_missing_spacer():
    screw = FastenerSpec("socket_head_cap_screw","M3-0.5",length_mm=50)
    mount = ThreadedMount(PolarPattern(8,(0,180)),screw,3.4)
    gear = mount.middle_side(thickness=6,head_recess=Counterbore(6,1.7))
    spacer = mount.middle_side(offset=4.3,thickness=41.7,supplied=True)
    cover = mount.clearance_side(offset=46,thickness=3,head_recess=Counterbore(6,1))
    mount.validate_stack(cover,(gear,spacer))
    assert cover.seat == 48
    assert gear.seat == 4.3
    with pytest.raises(ValueError,match="continuously"):
        mount.validate_stack(cover,(gear,))
    fastening = mount.fastening("stack",through="cover",into="base",via=("spacer","gear"),
                               frame=Frame(),clearance=cover)
    assert fastening.components == ("cover","spacer","gear","base")
    assert fastening.grip_mm == 48
    assert fastening.sites[0].origin == pytest.approx((8,0,48))


def test_slotted_mount_cuts_and_retains_threaded_hardware_axis():
    mount = ThreadedMount(PolarPattern(8,(0,180)),
                         FastenerSpec("socket_head_cap_screw","M3-0.5",length_mm=8),3.4)
    feature = mount.clearance_side(thickness=3,slot_length=5.4,slot_radial=True)
    body = cq.Workplane("XY").rect(30,20).extrude(3).val()
    assert body.Volume()-feature.apply(body).Volume() == pytest.approx(2*(2*3.4+math.pi*1.7**2)*3)
    assert feature.describe()["slot_radial"] is True


def test_drilled_clearance_profile_preserves_scallops_and_nominal_hardware_axis():
    mount = ThreadedMount(PolarPattern(8,(0,180)),
                         FastenerSpec("socket_head_cap_screw","M2-0.4",length_mm=8),2.4)
    role = mount.clearance_side(thickness=5.5,drill_offsets=((0,-.3),(0,.3)))
    body = cq.Workplane("XY").rect(30,20).extrude(5.5).val()
    expected = body
    for x,y in mount.pattern.points:
        for dy in (-.3,.3):
            expected = expected.cut(cq.Solid.makeCylinder(1.2,5.7,(x,y+dy,-.1)))
    assert role.apply(body).Volume() == pytest.approx(expected.Volume())
    fastening = mount.fastening("mount",through="cover",into="base",frame=Frame(),clearance=role)
    assert fastening.sites[0].origin == pytest.approx((8,0,5.5))
    with pytest.raises(ValueError,match="Choose"):
        replace(role,slot_length=3)


def test_part_manufacturing_plan_traces_secondary_operations_to_named_feature():
    part = Part("block",blank,FDM("PETG"),
                features={"motor-threads":TappedHole("M3-0.5",2.5,6)})
    assert part.describe()["operations"] == [{"feature":"motor-threads","kind":"tap-after-printing",
                 "thread":"M3-0.5","thread_depth":6,"quantity":1}]


def test_counterbore_entry_access_extension_preserves_the_declared_seat():
    mount = ThreadedMount(PolarPattern(8,(0,180)),
                         FastenerSpec("socket_head_cap_screw","M3-0.5",length_mm=8),3.4)
    base = mount.clearance_side(thickness=4,head_recess=Counterbore(6,1.7))
    extended = mount.clearance_side(thickness=4,head_recess=Counterbore(6,1.7,entry_extension=.3))
    body = cq.Workplane("XY").rect(30,20).extrude(5).val()
    assert extended.seat == base.seat == 2.3
    assert base.apply(body).Volume()-extended.apply(body).Volume() == pytest.approx(2*math.pi*3**2*.3)


def test_bosses_support_ordered_manufacturing_and_native_shape_boundaries():
    from cadkit.design.manufacturing import Boss
    body = cq.Workplane("XY").rect(10,10).extrude(4).val()
    hole = Hole(3,4,through=True)
    drilled = hole.apply(body)
    boss = Boss(5,3,at=Frame((0,0,2)),limit=lambda:cq.Workplane("XY").rect(10,10).extrude(4.5))
    restored = boss.apply(drilled)
    assert restored.BoundingBox().zmax == pytest.approx(4.5)
    assert restored.Volume() > drilled.Volume()
    with pytest.raises(ValueError,match="join"):
        Boss(5,3,at=Frame((20,0,0))).apply(body)


def test_sheet_process_requires_declared_thickness_and_describes_laser_cutting():
    from cadkit.design.parts import LaserCut
    process = LaserCut("stainless-steel",2)
    part = Part("sheet",lambda:cq.Workplane("XY").rect(10,20).extrude(2),process)
    assert part.build().Volume() == pytest.approx(400)
    assert part.describe()["manufacture"]["process"] == "laser-cut"
    assert part.as_part("metal").print_rotation == (0,0,0)
    with pytest.raises(ValueError,match="sheet stock"):
        replace(part,manufacture=LaserCut("stainless-steel",3)).build()
