"""Mount-derived fit bounds stay attached to geometry and preserve unknowns."""
from dataclasses import replace
import math
import cadquery as cq
import pytest
from cadkit import FastenerSpec
from cadkit import design as d
from cadkit.mechanics import component_index, resolve_components
from test_design import definitions, assembly as insert_fixture


def tapped_fixture(length=6):
    mount = d.ThreadedMount(d.PointPattern(),
        FastenerSpec("socket_head_cap_screw","M3-0.5",length_mm=length),3.4,
        pilot_diameter=2.5,thread_depth=4,hole_depth=5,minimum_engagement=3)
    receiver = d.Part("base",lambda:cq.Workplane("XY").rect(20,20).extrude(-8),d.FDM("PETG"),
                      features={"thread":mount.threaded_side()})
    plate = d.Part("plate",lambda:cq.Workplane("XY").rect(20,20).extrude(2),d.FDM("PETG"),
                   features={"clearance":mount.clearance_side(thickness=2)})
    design = d.Assembly("fixture")
    a,b = design.add("base",receiver),design.add("plate",plate)
    design.fix(a)
    design.connect("mount",mount,through=b.feature("clearance"),into=a.feature("thread"))
    return design


def test_declared_tapping_bounds_allow_only_the_thread_forming_region():
    design = tapped_fixture()
    interface, = design.interfaces()
    assert interface.components == ("/fixture/Hardware/mount/1/screw","/fixture/base")
    assert interface.max_overlap_mm3 == pytest.approx(math.pi*(1.5**2-1.25**2)*4+.001)
    assert interface.region().BoundingBox().zmin == pytest.approx(-4.0001)
    report = design.as_project().validate_mechanics(scan_collisions=False)
    fit = next(f for f in report["findings"] if f["entity"] == interface.name and f["code"] == "fit")
    assert fit["status"] == "pass"


def test_screw_intrusion_past_the_authored_thread_region_is_rejected():
    design = tapped_fixture(length=9)
    interface, = design.interfaces()
    report = design.as_project().validate_mechanics(scan_collisions=False)
    fit = next(f for f in report["findings"] if f["entity"] == interface.name and f["code"] == "fit")
    assert fit["status"] == "fail"
    assert fit["evidence"]["outside_region_mm3"] > 1


def test_insert_outer_diameter_is_explicit_evidence_not_a_geometry_query():
    spec,plate,base = definitions()
    with_od = replace(spec,pocket=replace(spec.pocket,insert_outer_diameter=4.6))
    _,plate,base = definitions(with_od)
    design = insert_fixture(with_od,plate,base)
    interfaces = design.interfaces()
    pocket = next(i for i in interfaces if i.name == "mount-1-insert-pocket")
    assert pocket.max_overlap_mm3 == pytest.approx(math.pi*((4.6/2)**2-2**2)*5.7+.001)
    assert len(interfaces) == 4
    # No declared outer dimension means no automatically permitted press fit.
    unknown,plate,base = definitions()
    assert all(i.kind != "press_fit" for i in insert_fixture(unknown,plate,base).interfaces())


def test_generated_regions_follow_nested_motion_and_hardware_scope():
    spec,plate,base = definitions()
    spec = replace(spec,pocket=replace(spec.pocket,insert_outer_diameter=4.6))
    _,plate,base = definitions(spec)
    child = insert_fixture(spec,plate,base)
    # An explicit frame is sufficient to export the child's bearing datum.
    child.export_port("axis",child.instances["base"].feature("mount"))
    parent = d.Assembly("machine")
    anchor_part = d.Part("anchor",lambda:cq.Workplane("XY").box(1,1,1),d.FDM("PETG"),ports={"axis":d.Frame()})
    anchor,moving = parent.add("anchor",anchor_part),parent.add("head",child)
    parent.fix(anchor)
    angle = parent.connect("angle",d.Revolute(),parent=anchor.port("axis"),child=moving.port("axis"))
    before = next(i for i in parent.interfaces() if i.name.endswith("1-insert-pocket"))
    posed = parent.pose({angle:90})
    after = next(i for i in posed.interfaces() if i.name == before.name)
    assert before.region().Center().toTuple() == pytest.approx((8,0,-5.7/2))
    assert after.region().Center().toTuple() == pytest.approx((0,8,-5.7/2))
    assert after.components[0] == "/machine/Hardware/head%2Fmount/1/insert"
    index = component_index(posed.as_assembly())
    assert len(resolve_components(after.components,index)) == 2


def test_supplier_envelope_intrusion_does_not_claim_blind_thread_depth():
    mount = d.ThreadedMount(d.PointPattern(),
        FastenerSpec("socket_head_cap_screw","M1.6-0.35",length_mm=3),1.8,minimum_engagement=1)
    clearance = mount.clearance_side(thickness=1.9)
    receiver = mount.threaded_side(supplied=True)
    fastening = mount.fastening("motor",through="plate",into="motor",frame=d.Frame(),clearance=clearance)
    bounded, = mount.interfaces(fastening,receiver=receiver,hardware_root="/fixture/Hardware",receiver_representation="envelope")
    assert bounded.region().BoundingBox().zmin == pytest.approx(-1.1001)
    assert fastening.thread_depth_mm is None
    assert fastening.hole_depth_mm is None
    assert "not evidence of blind-hole depth" in bounded.description
    assert mount.interfaces(fastening,receiver=receiver,hardware_root="/fixture/Hardware",receiver_representation="detailed") == ()


def test_graph_inspection_does_not_build_hardware_or_parts():
    calls = []
    def hardware(spec):
        calls.append("hardware")
        raise RuntimeError("Must remain lazy")
    mount = d.ThreadedMount(d.PointPattern(),FastenerSpec("socket_head_cap_screw","M3-0.5",length_mm=6,factory=hardware),
                           3.4,pilot_diameter=2.5,thread_depth=4,hole_depth=5)
    base = d.Part("base",lambda:calls.append("base"),d.FDM("PETG"),features={"thread":mount.threaded_side()})
    plate = d.Part("plate",lambda:calls.append("plate"),d.FDM("PETG"),features={"clearance":mount.clearance_side(thickness=2)})
    design = d.Assembly("fixture")
    a,b = design.add("base",base),design.add("plate",plate)
    design.fix(a)
    design.connect("mount",mount,through=b.feature("clearance"),into=a.feature("thread"))
    design.describe()
    design.as_project().describe()
    assert len(design.interfaces()) == 1
    assert calls == []


def test_embedding_rebases_only_hardware_references_and_preserves_bounds():
    design = tapped_fixture()
    embedded = design.embed(at=d.Frame((10,20,30)))
    interface, = embedded.interfaces(hardware_root="/host/Hardware")
    assert interface.components == ("/host/Hardware/mount/1/screw","base")
    assert interface.region().Center().toTuple() == pytest.approx((10,20,28))


def test_countersunk_head_uses_flush_face_and_head_inclusive_length():
    from cadkit import Countersink
    screw = FastenerSpec('countersunk_screw', 'M3-0.5', length_mm=8)
    shape = screw.build()
    assert shape.BoundingBox().zmin == pytest.approx(0)
    assert shape.BoundingBox().zmax == pytest.approx(8)
    mount = d.ThreadedMount(d.PointPattern(), screw, 3.4,
        pilot_diameter=2.5, thread_depth=6, hole_depth=7, minimum_engagement=4.5)
    role = mount.clearance_side(thickness=3, head_recess=Countersink(3.4, 6))
    plate = d.Part('plate', lambda: cq.Workplane('XY').rect(20, 20).extrude(3), d.LaserCut('steel', 3), features={'hole': role})
    base = d.Part('base', lambda: cq.Workplane('XY').rect(20, 20).extrude(-8), d.FDM('PLA'), features={'thread': mount.threaded_side()})
    a = d.Assembly('flush')
    receiver = a.fix(a.add(base))
    clamped = a.add(plate)
    a.connect('mount', mount, through=clamped.feature('hole'), into=receiver.feature('thread'))
    models = {c.name: c.model for c in a.components(include_hardware=True)}
    installed, = [shape for name, shape in models.items() if name.endswith('/1/screw')]
    assert installed.BoundingBox().zmax == pytest.approx(3)
    assert installed.BoundingBox().zmin == pytest.approx(-5)
    assert installed.intersect(models['plate']).Volume() < 1e-6
    # The conical seat touches, without hiding a floating screw or interference.
    assert installed.distance(models['plate']) < 1e-6
    findings = a.as_project().validate_mechanics()['findings']
    engagement = next(f for f in findings if f['code'] == 'engagement')
    assert engagement['status'] == 'pass'
    assert engagement['evidence']['engagement_mm'] == pytest.approx(5)
    assert role.describe()['operations'][0]['kind'] == 'countersink'
    with pytest.raises(ValueError, match='countersunk clearance'):
        mount.clearance_side(thickness=3)
    with pytest.raises(ValueError, match='positive screw seat'):
        mount.clearance_side(thickness=1, head_recess=Countersink(3.4, 6))
