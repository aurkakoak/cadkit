"""Single-part hardware closures bind owned features and follow every pose."""
from dataclasses import replace
import cadquery as cq
import pytest
from cadkit import FastenerSpec
from cadkit import design as d
from cadkit.mechanics import Fastening, Joint, Interface, component_index, resolve_components, hardware_bom


def clamp():
    return d.Part("clamp",lambda:cq.Workplane("XY").rect(10,10).extrude(8),d.FDM("PETG"),
        features={"bolt":d.Hole(2.3,8,through=True),
                  "nut":d.NutPocket(4.2,1.8,at=d.Frame((0,0,8),z=(0,0,-1)),thread="M2-0.4")},
        ports={"axis":d.Frame()})


def nut_recipe():
    return d.CaptiveNutFastening(FastenerSpec("socket_head_cap_screw","M2-0.4",length_mm=8),
                                FastenerSpec("hex_nut","M2-0.4"),1.6)


def pinion(flat=1.1):
    return d.Part("pinion",lambda:cq.Workplane("XY").rect(10,10).extrude(8),d.FDM("PETG"),
        features={"shaft":d.DBore(3.2,8,flat=flat,through=True),
                  "pilot":d.TappedHole("M2-0.4",1.6,3.1,at=d.Frame((4,0,4),z=(-1,0,0),x=(0,1,0)))},
        ports={"axis":d.Frame()})


def test_captive_closure_derives_nut_location_and_keeps_part_geometry_unchanged():
    part = clamp()
    before = part.build().Volume()
    design = d.Assembly("closure")
    body = design.add("body",part)
    design.fix(body)
    design.attach("closure-bolt",nut_recipe(),through=body.feature("bolt"),nut=body.feature("nut"))
    fastening, = design.fastenings()
    assert fastening.components == ("/closure/body",)
    assert fastening.grip_mm == pytest.approx(6.2)
    assert fastening.hardware[1].offset_mm == pytest.approx(6.2)
    assert fastening.thread_depth_mm == pytest.approx(1.6)
    assert sum(row["quantity"] for row in hardware_bom(design.fastenings())) == 2
    assert design.joints() == ()
    assert part.build().Volume() == pytest.approx(before)
    tree = design.as_assembly()
    index = component_index(tree)
    assert len(index) == 3
    assert all(resolve_components(i.components,index) for i in design.interfaces())


def test_captive_closure_rejects_unrelated_holes_and_nut_dimensions():
    design = d.Assembly("closure")
    body = design.add("body",clamp())
    design.fix(body)
    with pytest.raises(TypeError,match="through=Hole"):
        design.attach("wrong",nut_recipe(),through=body.feature("nut"),nut=body.feature("bolt"))
    with pytest.raises(ValueError,match="accommodate"):
        design.attach("too-thick",replace(nut_recipe(),nut_thickness=2),through=body.feature("bolt"),nut=body.feature("nut"))
    misaligned = replace(clamp(),features={**clamp().features,
        "nut":d.NutPocket(4.2,1.8,at=d.Frame((1,0,8),z=(0,0,-1)),thread="M2-0.4")})
    other = d.Assembly("bad")
    instance = other.add("body",misaligned)
    other.fix(instance)
    other.attach("bolt",nut_recipe(),through=instance.feature("bolt"),nut=instance.feature("nut"))
    with pytest.raises(ValueError,match="share an axis"):
        other.fastenings()


def test_set_screw_tip_follows_authored_d_flat_and_catalogue_convention():
    spec = FastenerSpec("set_screw","M2-0.4",length_mm=2)
    assert spec.standard == "iso4026"
    screw = spec.build()
    assert screw.BoundingBox().zmin == pytest.approx(0)
    assert screw.BoundingBox().zmax == pytest.approx(2)
    for flat in (1.1,1.3):
        design = d.Assembly("hub")
        part = pinion(flat)
        body = design.add("body",part)
        design.fix(body)
        before = part.build().Volume()
        design.attach("grub",d.SetScrew(spec),thread=body.feature("pilot"),stop=body.feature("shaft"))
        fastening, = design.fastenings()
        site = fastening.sites[0]
        assert site.origin == pytest.approx((flat+2,0,4))
        assert site.axis == pytest.approx((-1,0,0))
        tip = tuple(p+a*spec.length_mm for p,a in zip(site.origin,site.axis))
        assert tip == pytest.approx((flat,0,4))
        assert part.build().Volume() == pytest.approx(before)
        interface, = design.interfaces()
        assert interface.region().Center().toTuple() == pytest.approx((flat+1,0,4))


def test_attachment_hardware_and_bounds_follow_nested_pose_and_snapshot():
    child = d.Assembly("hub")
    body = child.add("body",pinion())
    child.fix(body)
    child.export_port("axis",body.port("axis"))
    child.attach("grub",d.SetScrew(FastenerSpec("set_screw","M2-0.4",length_mm=2)),
                 thread=body.feature("pilot"),stop=body.feature("shaft"))
    parent = d.Assembly("machine")
    root = parent.add("root",clamp())
    moving = parent.add("hub",child)
    parent.fix(root)
    angle = parent.connect("angle",d.Revolute(),parent=root.port("axis"),child=moving.port("axis"))
    posed = parent.pose({angle:90})
    fastening, = posed.fastenings()
    assert fastening.sites[0].origin == pytest.approx((0,3.1,4))
    interface, = posed.interfaces()
    assert interface.region().Center().toTuple() == pytest.approx((0,2.1,4))
    assert interface.components[0] == "/machine/Hardware/hub%2Fgrub/1/screw"
    assert len(resolve_components(interface.components,component_index(posed.as_assembly()))) == 2
    # Authored changes after a pose snapshot cannot add hardware to that snapshot.
    child.attach("second",d.SetScrew(FastenerSpec("set_screw","M2-0.4",length_mm=2)),
                 thread=body.feature("pilot"),stop=body.feature("shaft"))
    assert len(parent.fastenings()) == 2
    assert len(posed.fastenings()) == 1


def test_only_fastening_can_reference_one_physical_component():
    Fastening("closure",("part",))
    with pytest.raises(ValueError):
        Joint("joint",("part",))
    with pytest.raises(ValueError):
        Interface("interface",("part",))


def test_hex_nut_clocking_matches_its_pocket_after_arbitrary_nested_rotation():
    child = d.Assembly("clamp")
    part = clamp()
    body = child.add("body",part)
    child.fix(body)
    child.export_port("axis",body.port("axis"))
    child.attach("closure",nut_recipe(),through=body.feature("bolt"),nut=body.feature("nut"))
    parent = d.Assembly("machine")
    anchor = parent.add("anchor",replace(clamp(),name="anchor"))
    moving = parent.add("clamp",child)
    root = d.Frame((10,20,30),z=(0,1,0),x=(0,0,1))
    parent.fix(anchor,at=root)
    angle = parent.connect("angle",d.Revolute(),parent=anchor.port("axis"),child=moving.port("axis"))
    posed = parent.pose({angle:35})
    fastening, = posed.fastenings()
    site = fastening.sites[0]
    assert site.x_axis is not None
    nut = site.place(fastening.hardware[1].spec.build(),fastening.hardware[1].offset_mm)
    part_model = posed.models(names="path")["clamp/body"].val()
    assert nut.intersect(part_model).Volume() == pytest.approx(0,abs=1e-7)
    # Full local transform, including roll, agrees with the positioned component.
    local_site = child.fastenings()[0].sites[0]
    local_nut = local_site.place(fastening.hardware[1].spec.build(),fastening.hardware[1].offset_mm)
    world = posed.locations()["clamp"]
    expected = local_nut.moved(world)
    assert nut.cut(expected).Volume()+expected.cut(nut).Volume() == pytest.approx(0,abs=1e-7)


def test_counterbored_captive_closure_derives_head_seat_and_remaining_grip():
    original = clamp()
    part = replace(original,features={**original.features,
        "bolt":d.CounterboredHole(2.3,8,through=True,recess=d.Counterbore(4.2,1))})
    design = d.Assembly("closure")
    body = design.add("body",part)
    design.fix(body)
    design.attach("bolt",nut_recipe(),through=body.feature("bolt"),nut=body.feature("nut"))
    fastening, = design.fastenings()
    assert fastening.sites[0].origin == pytest.approx((0,0,1))
    assert fastening.grip_mm == pytest.approx(5.2)
    assert fastening.hardware[1].offset_mm == pytest.approx(5.2)


def test_set_screw_thread_host_is_independent_of_keyword_order_across_parts():
    results = []
    for reverse in (False,True):
        design = d.Assembly("fixture")
        threaded = design.add("threaded-hub",pinion())
        stop_part = replace(pinion(),name="stop-part",features={"shaft":pinion().features["shaft"]})
        stop = design.add("stop-part",stop_part)
        design.fix(threaded)
        design.fix(stop)
        bindings = {"thread":threaded.feature("pilot"),"stop":stop.feature("shaft")}
        if reverse:
            bindings = dict(reversed(tuple(bindings.items())))
        design.attach("grub",d.SetScrew(FastenerSpec("set_screw","M2-0.4",length_mm=2)),**bindings)
        fastening, = design.fastenings()
        interface, = design.interfaces()
        assert fastening.components == ("/fixture/threaded-hub","/fixture/stop-part")
        assert interface.components == ("/fixture/Hardware/grub/1/screw","/fixture/threaded-hub")
        results.append((fastening.sites[0].describe(),interface.region().Center().toTuple(),
                        interface.max_overlap_mm3))
    assert results[0] == results[1]
