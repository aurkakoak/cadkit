import json
import math
from dataclasses import replace
import runpy
from pathlib import Path
import cadquery as cq
import pytest
from cadkit._project import Project, Part, Component, Assembly
from cadkit import Joint, Interface, Fastening, FastenerSpec, HardwareItem, FastenerSite, AccessEnvelope
from cadkit.mechanics import component_index


def box(x=0):
    return cq.Solid.makeBox(10, 10, 10).translate((x, 0, 0))


def project(*, joints=(), interfaces=(), fastenings=(), separation=11):
    return Project("fixture", (), lambda **opts: [Component("a", box(), "body"), Component("b", box(separation), "body")],
                   joints=joints, interfaces=interfaces, fastenings=fastenings)


def row(report, code):
    return next(item for item in report["findings"] if item["code"] == code)


def bolt(**kwargs):
    defaults = dict(name="bolts", components=("a", "b"),
        sites=(FastenerSite("one", (50, 0, 0)),),
        hardware=(HardwareItem("screw", FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=10)),
                  HardwareItem("nut", FastenerSpec("hex_nut", "M3-0.5"), 5)),
        grip_mm=5, thread_depth_mm=2.4, min_engagement_mm=2.4, hole_depth_mm=11)
    defaults.update(kwargs)
    return Fastening(**defaults)


def test_legacy_description_remains_lazy_and_marks_unknown_coverage():
    p = Project("old", (), lambda: (_ for _ in ()).throw(AssertionError("must not build")))
    assert p.describe()["mechanics"] == {"joints": [], "interfaces": [], "fastenings": [], "hardware_bom": []}
    r = project().validate_mechanics()
    assert r["status"] == "incomplete"
    assert r["coverage"]["installed_collisions"] == "checked"
    assert row(r, "declarations")["status"] == "unverified"


def test_stable_paths_and_hardware_bom_do_not_change_manufactured_parts():
    original = box()
    p = project(fastenings=(bolt(sites=(FastenerSite("one", (50,0,0)), FastenerSite("two",(70,0,0)))),))
    p.parts = (Part("a", lambda: original, "body"),)
    assembly = p.get_assembly()
    ids = component_index(assembly)
    assert "/fixture/Hardware/bolts/one/screw" in ids
    assert ids["/fixture/Hardware/bolts/one/screw"].metadata["preview_offset_mm"] == (0,0,-20)
    descriptors = p.mechanical_descriptions(assembly)
    assert descriptors["fastenings"][0]["component_ids"] == ["/fixture/body/a", "/fixture/body/b"]
    assert len(descriptors["fastenings"][0]["hardware_ids"]) == 4
    assert [r["quantity"] for r in descriptors["hardware_bom"]] == [2,2]
    assert p.parts[0].build(for_print=False).Volume() == original.Volume()
    names = [c.name for c in p.get_components()]
    assert len(names) == len(set(names))
    assert len(p.get_components(angle=5)) == 2
    assert len(list(p.get_assembly(angle=5).components())) == 2
    json.dumps(descriptors)


def test_unlocated_bill_of_materials_is_explicit():
    p=project(fastenings=(bolt(sites=(),quantity=3),))
    assert [r["quantity"] for r in p.mechanical_descriptions()["hardware_bom"]] == [3,3]
    assert not p.mechanical_descriptions()["hardware_bom"][0]["located"]
    assert row(p.validate_mechanics(),"locations")["status"] == "unverified"


def test_catalogue_washer_adapter_matches_analytic_dimensions():
    spec=FastenerSpec("plain_washer","M3")
    w=spec.build()
    assert w.isValid() and len(w.Solids())==1
    assert w.Volume()==pytest.approx(math.pi*(7**2-3.2**2)/4*.55)
    assert spec.describe()["geometry_adapter"]=="catalogue_plain_washer_annulus"
    assert spec.dimensions()["height_mm"]==pytest.approx(.55)


def test_explicit_catalogue_hole_cutter_and_screw_orientation():
    screw=FastenerSpec("socket_head_cap_screw","M3-0.5",length_mm=10)
    assert screw.clearance_diameter()==3.4
    cutter=screw.clearance_cutter(6,allowance_mm=.2)
    assert cutter.Volume()==pytest.approx(math.pi*1.8**2*6)
    body=screw.build()
    assert body.BoundingBox().zmin==pytest.approx(-3)
    assert body.BoundingBox().zmax==pytest.approx(10)
    placed=FastenerSite("down",(0,0,50),(0,0,-2)).place(body)
    assert placed.BoundingBox().zmin==pytest.approx(40)
    assert placed.BoundingBox().zmax==pytest.approx(53)
    lateral=FastenerSite("side",(20,0,0),(1,0,0)).place(body)
    assert lateral.BoundingBox().xmin==pytest.approx(17)
    assert lateral.BoundingBox().xmax==pytest.approx(30)


def test_bounded_overlap_cannot_hide_an_outside_collision_or_excess_volume():
    good = Interface("fit", ("a","b"), "press_fit", region=lambda: cq.Solid.makeBox(2,10,10).translate((9,0,0)), max_overlap_mm3=100)
    r=project(interfaces=(good,),separation=9).validate_mechanics()
    assert row(r,"fit")["status"]=="pass"
    assert not [f for f in r["findings"] if f["status"]=="fail"]
    for bad in (replace(good, max_overlap_mm3=50), replace(good,region=lambda: cq.Solid.makeBox(2,5,10).translate((9,0,0)))):
        r=project(interfaces=(bad,),separation=9).validate_mechanics()
        assert row(r,"fit")["status"]=="fail"
        assert any(f["code"].startswith("collision-") for f in r["findings"])
    with pytest.raises(ValueError,match="bounded region"):
        Interface("bad",("a","b"),"press_fit",max_overlap_mm3=1)


def test_contact_region_cannot_pass_from_contact_elsewhere():
    contact=Interface("seat",("a","b"),region=lambda:cq.Solid.makeBox(2,2,2))
    r=project(interfaces=(contact,),separation=10).validate_mechanics()
    assert row(r,"fit")["status"]=="fail"
    valid=replace(contact,region=lambda:cq.Solid.makeBox(2,2,2).translate((9,2,2)))
    assert row(project(interfaces=(valid,),separation=10).validate_mechanics(),"fit")["status"]=="pass"


def test_fastener_short_long_mismatched_thread_and_stack_are_failures():
    good=bolt()
    r=project(fastenings=(good,)).validate_mechanics()
    assert row(r,"engagement")["status"]=="pass"
    assert row(r,"bottoming")["status"]=="pass"
    assert row(r,"thread-match-nut")["status"]=="pass"
    assert row(r,"receiver-stack-nut")["status"]=="pass"
    short=replace(good,hardware=(replace(good.hardware[0],spec=replace(good.hardware[0].spec,length_mm=6)),good.hardware[1]))
    assert row(project(fastenings=(short,)).validate_mechanics(),"engagement")["status"]=="fail"
    long=replace(good,hole_depth_mm=9)
    assert row(project(fastenings=(long,)).validate_mechanics(),"bottoming")["status"]=="fail"
    mismatched=replace(good,hardware=(good.hardware[0],replace(good.hardware[1],spec=FastenerSpec("hex_nut","M4-0.7"))))
    assert row(project(fastenings=(mismatched,)).validate_mechanics(),"thread-match-nut")["status"]=="fail"
    badstack=replace(good,grip_mm=6)
    assert row(project(fastenings=(badstack,)).validate_mechanics(),"receiver-stack-nut")["status"]=="fail"


def test_missing_fastener_dimensions_do_not_pass():
    r=project(fastenings=(bolt(grip_mm=None,hole_depth_mm=None),)).validate_mechanics()
    assert row(r,"engagement")["status"]=="unverified"
    assert row(r,"bottoming")["status"]=="unverified"
    assert row(r,"access")["status"]=="unverified"


def test_tool_envelope_checks_declared_obstacles():
    blocked=AccessEnvelope("driver",lambda:box(),("a",))
    clear=AccessEnvelope("wrench",lambda:box(30),("a","b"))
    r=project(fastenings=(bolt(access=(blocked,clear)),)).validate_mechanics()
    assert row(r,"access-driver")["status"]=="fail"
    assert row(r,"access-driver")["evidence"]["blocked"][0]["component_id"]=="/fixture/body/a"
    assert row(r,"access-wrench")["status"]=="pass"


def test_ambiguous_references_and_invalid_joint_limits():
    p=project(joints=(Joint("hinge",("a","b"),kind="revolute",limits=(0,90),position=91),))
    assert row(p.validate_mechanics(),"position")["status"]=="fail"
    assert row(p.validate_mechanics(),"movement")["status"]=="unverified"
    p.assembly=lambda:Assembly("fixture",(Assembly("one",(Component("a",box(),"x"),)),Assembly("two",(Component("a",box(20),"x"),)),Component("b",box(40),"x")))
    assert row(p.validate_mechanics(),"references")["status"]=="fail"
    with pytest.raises(ValueError): Joint("hinge",("a","b"),axis=(0,0,0))
    with pytest.raises(ValueError): Joint("hinge",("a","b"),limits=(5,0))


def test_kernel_failure_downgrades_coverage(monkeypatch):
    def broken(self,other,*args,**kwargs): raise RuntimeError("kernel failure")
    monkeypatch.setattr(cq.Shape,"intersect",broken)
    r=project(separation=9).validate_mechanics()
    assert r["coverage"]["installed_collisions"]=="partial"
    assert r["coverage"]["kernel_failures"]==1
    assert r["status"]=="incomplete"


def test_independent_bolted_plate_example_has_no_physical_failures():
    p=runpy.run_path(str(Path(__file__).parents[1]/"examples"/"mechanical_joint.py"))["PROJECT"]
    r=p.validate_mechanics()
    assert r["summary"]["fail"]==0
    assert r["status"]=="incomplete"  # Complete assemblability is never inferred.
    assert r["coverage"]["pairs_scanned"]==45


def test_tapped_receiver_thread_declaration_is_checked():
    f=bolt(kind="tapped",thread_size="M4-0.7")
    f=replace(f,hardware=f.hardware[:1])
    assert row(project(fastenings=(f,)).validate_mechanics(),"thread-match-tapped")["status"]=="fail"
    f=replace(f,thread_size="M3-0.50")
    assert row(project(fastenings=(f,)).validate_mechanics(),"thread-match-tapped")["status"]=="pass"
    f=replace(f,thread_size=None)
    assert row(project(fastenings=(f,)).validate_mechanics(),"thread-match-tapped")["status"]=="unverified"


def test_bad_access_reference_is_a_failed_declaration():
    access=AccessEnvelope("driver",lambda:box(),("typo",))
    assert row(project(fastenings=(bolt(access=(access,)),)).validate_mechanics(),"access-driver")["status"]=="fail"


def test_hardware_identity_ignores_notes_and_export_names_cannot_escape():
    spec=FastenerSpec("hex_nut","M3-0.5")
    assert spec.id==replace(spec,description="Use the spare bag").id
    f=bolt(name="../outside",sites=(FastenerSite("../mount",(50,0,0)),))
    names=[c.name for c in project(fastenings=(f,)).get_components() if c.metadata]
    assert all("/" not in name for name in names)


def envelope_project(offset=9, *, interfaces=(), access=()):
    spec=FastenerSpec("hex_nut", "M3-0.5", representation="envelope", factory=lambda spec: box())
    fastening=Fastening("proxy",("a","b"),sites=(FastenerSite("one",(offset,0,0)),),
        hardware=(HardwareItem("proxy-nut",spec),),access=access)
    return project(fastenings=(fastening,),interfaces=interfaces)


def test_envelope_collision_is_unverified_without_hiding_native_failures():
    p=envelope_project()
    r=p.validate_mechanics()
    collisions=[f for f in r["findings"] if f["code"].startswith("collision-")]
    assert collisions and all(f["status"]=="unverified" for f in collisions)
    assert all(f["evidence"]["overlap_mm3"]>0 for f in collisions)
    assert all(f["evidence"]["envelope_component_ids"] for f in collisions)
    assert r["summary"]["fail"]==0
    assert r["coverage"]["installed_collisions"]=="partial"
    assert r["coverage"]["envelope_components"]==1
    native_components=p.components
    p.components=lambda:[*native_components(), Component("exact-obstruction",box(9),"body")]
    r=p.validate_mechanics()
    assert r["status"]=="fail"
    assert any(f["status"]=="fail" and "exact-obstruction" in " ".join(f["component_ids"]) for f in r["findings"])


@pytest.mark.parametrize("offset, expected_nominal", [(9,"fail"),(15,"pass")])
def test_envelope_interface_preserves_nominal_evidence_without_claiming_fit(offset,expected_nominal):
    interface=Interface("gap",("a","proxy-nut"),"clearance",min_clearance_mm=1)
    r=envelope_project(offset,interfaces=(interface,)).validate_mechanics()
    fit=row(r,"fit")
    assert fit["status"]=="unverified"
    assert fit["evidence"]["nominal_status"]==expected_nominal
    assert fit["evidence"]["envelope_component_ids"]


def test_nonintersecting_envelope_still_leaves_physical_coverage_unknown():
    r=envelope_project(offset=40).validate_mechanics()
    assert not [f for f in r["findings"] if f["code"].startswith("collision-")]
    assert row(r,"envelope-coverage")["status"]=="unverified"
    assert r["coverage"]["installed_collisions"]=="partial"


def test_access_distinguishes_envelope_obstruction_from_native_obstruction():
    access=AccessEnvelope("driver",lambda:box(),("proxy-nut",))
    r=envelope_project(access=(access,)).validate_mechanics()
    assert row(r,"access-driver")["status"]=="unverified"
    access=replace(access,obstacles=("proxy-nut","a"))
    r=envelope_project(access=(access,)).validate_mechanics()
    assert row(r,"access-driver")["status"]=="fail"


def test_authored_component_envelope_metadata_qualifies_legacy_proxies():
    p=Project("legacy-proxy", (), lambda:[
        Component("housing",box(),"machine"),
        Component("motor",box(9),"machine",metadata={"representation":"envelope"}),
    ],interfaces=(Interface("motor-clearance",("housing","motor"),"clearance",min_clearance_mm=.2),))
    r=p.validate_mechanics()
    assert r["summary"]["fail"]==0
    assert r["coverage"]["envelope_components"]==1
    assert r["coverage"]["installed_collisions"]=="partial"
    assert row(r,"fit")["status"]=="unverified"
    collision=next(f for f in r["findings"] if f["code"].startswith("collision-"))
    assert collision["status"]=="unverified"
    assert collision["evidence"]["envelope_component_ids"]==["/legacy-proxy/machine/motor"]
