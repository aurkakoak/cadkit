"""Exported mounts preserve leaf ownership, occurrence frames and pose constraints."""
from dataclasses import replace

import cadquery as cq
import pytest

from cadkit import design as d
from cadkit.mechanics import component_index, resolve_components
from test_design import definitions
from test_design_assembly import block
from test_motion_graph import evaluate


def exported_unit(part, *, moving=False):
    unit = d.Assembly(part.name + "-unit")
    leaf = unit.add("leaf", replace(part, ports={"axis": d.Frame()}))
    if moving:
        root = unit.add("root", block())
        unit.fix(root, at=d.Frame((3, 4, 5)))
        unit.connect("slide", d.Slider(position=2, limits=(0, 10)),
                     parent=root.port("axis"), child=leaf.port("axis"))
    else:
        unit.fix(leaf, at=d.Frame((3, 4, 5)))
    unit.export_feature("mount", leaf.feature("mount"))
    wrapper = d.Assembly(part.name + "-wrapper")
    sub = wrapper.add("unit", unit)
    wrapper.fix(sub, at=d.Frame((10, 0, 0), x=(0, 1, 0)))
    wrapper.export_feature("mount", sub.feature("mount"))
    return wrapper, unit


def test_reexported_rotated_reused_features_place_nested_children_and_scope_hardware():
    mount, plate, base = definitions()
    receiver, _ = exported_unit(base)
    clamped, _ = exported_unit(plate)
    design = d.Assembly("twins")
    for name, at in (("left", d.Frame()), ("right", d.Frame((100, 0, 0), z=(0, 1, 0)))):
        a = design.add(name + "-base", receiver)
        b = design.add(name + "-plate", clamped)
        assert a.feature("mount").definition is base.features["mount"]
        design.fix(a, at=at)
        connection = design.connect(name, mount, through=b.feature("mount"), into=a.feature("mount"))
        design.driver_access(name, connection=connection, diameter=2, length=10, obstacles=(a,))
    frozen = design.as_project()
    tree = frozen.get_assembly()
    index = component_index(tree)
    left, right = frozen.fastenings
    assert left.sites[0].origin == pytest.approx((6, 11, 6.2))
    assert right.sites[0].origin == pytest.approx((106, 6.2, -11))
    assert left.components == ("/twins/left-plate/unit/leaf", "/twins/left-base/unit/leaf")
    assert right.components == ("/twins/right-plate/unit/leaf", "/twins/right-base/unit/leaf")
    for fastening in frozen.fastenings:
        assert resolve_components(fastening.components, index) == list(fastening.components)
        assert fastening.access[0].obstacles == (fastening.components[1],)
    for joint in frozen.joints:
        assert len(joint.components) == 2
        assert joint.parent_components == (next(f for f in frozen.fastenings if f.joint == joint.name).components[1],)
    assert {p.name: p.quantity for p in frozen.parts} == {"base": 2, "plate": 2}
    assert receiver.describe()["exported_features"]["mount"]["component"] == "unit/leaf"


@pytest.mark.parametrize("moving_receiver", [True, False])
def test_exported_moving_features_native_and_viewer_hardware_follow_the_same_datum(moving_receiver):
    mount, plate, base = definitions()
    receiver, _ = exported_unit(base, moving=moving_receiver)
    clamped, _ = exported_unit(plate, moving=not moving_receiver)
    design = d.Assembly("machine")
    a, b = design.add("receiver", receiver), design.add("clamped", clamped)
    design.fix(a)
    connection = design.connect("mount", mount, through=b.feature("mount"), into=a.feature("mount"))
    design.driver_access("driver", connection=connection, diameter=2, length=10, obstacles=(a,))
    project = design.as_project()
    pose = {("receiver" if moving_receiver else "clamped") + "/unit/slide": 8}
    before = project.get_assembly()
    after = project.get_assembly(pose=pose)
    graph = project.mechanical_descriptions(before)["motion"]
    transforms = evaluate(graph, pose)
    for key, component in component_index(after).items():
        center = component_index(before)[key].model.Center().toTuple()
        assert (transforms[key] @ [*center, 1])[:3] == pytest.approx(component.model.Center().toTuple(), abs=1e-7)
    old, = design.fastenings()
    new, = design.fastenings(pose=pose)
    assert new.sites[0].origin[2] - old.sites[0].origin[2] == pytest.approx(6 if moving_receiver else 0)
    assert new.access[0].envelope().Center().z - old.access[0].envelope().Center().z == pytest.approx(6 if moving_receiver else 0)


def test_secondary_fastening_between_exported_leaves_validates_pose_and_disables_viewer_joint():
    mount, plate, base = definitions()
    unit = d.Assembly("unit")
    a = unit.add("base", replace(base, ports={"axis": d.Frame()}))
    b = unit.add("plate", replace(plate, ports={"axis": d.Frame()}))
    unit.fix(a)
    unit.connect("slide", d.Slider(limits=(0, 10)), parent=a.port("axis"), child=b.port("axis"))
    unit.export_feature("receiver", a.feature("mount"))
    unit.export_feature("clamped", b.feature("mount"))
    outer = d.Assembly("outer")
    sub = outer.add("unit", unit)
    outer.fix(sub)
    outer.fasten("mount", mount, through=sub.feature("clamped"), into=sub.feature("receiver"))
    assert outer.fastenings()[0].components == ("/outer/unit/plate", "/outer/unit/base")
    joint, = outer.motion_graph()["joints"]
    assert joint["disabled_reason"] == "This joint has additional fastening constraints."
    with pytest.raises(ValueError, match="datums do not coincide"):
        outer.fastenings(pose={"unit/slide": 1})


def test_export_validation_mount_identity_and_snapshot_isolation():
    mount, plate, base = definitions()
    receiver, unit = exported_unit(base)
    outer = d.Assembly("outer")
    a = outer.add("base", receiver)
    b = outer.add("plate", plate)
    outer.fix(a)
    outer.connect("mount", mount, through=b.feature("mount"), into=a.feature("mount"))
    frozen = outer.as_project()
    unit.export_feature("alias", unit.instances["leaf"].feature("mount"))
    unit.fix(unit.add("extra", block("extra")))
    assert len(outer.locations(names="path")) == 3
    assert len(frozen.parts) == 2
    with pytest.raises(TypeError):
        unit.exported_features["alias"] = unit.exported_features["mount"]
    with pytest.raises(ValueError, match="Duplicate exported feature"):
        receiver.export_feature("mount", receiver.instances["unit"].feature("mount"))
    with pytest.raises(ValueError, match="different assembly"):
        receiver.export_feature("foreign", b.feature("mount"))
    with pytest.raises(TypeError, match="instance.feature"):
        unit.export_feature("port", unit.instances["leaf"].port("axis"))
    with pytest.raises(ValueError, match="unknown feature"):
        a.feature("private")
    with pytest.raises(ValueError, match="must bind this mount"):
        outer.fasten("different-recipe", replace(mount), through=b.feature("mount"), into=a.feature("mount"))


def test_nested_purchased_receiver_retains_envelope_evidence():
    from cadkit import FastenerSpec
    mount = d.ThreadedMount(d.PointPattern(), FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=6), 3.4)
    base = d.Purchased("base", lambda: cq.Workplane("XY").box(20, 20, 8),
                       representation="envelope", features={"mount": mount.threaded_side(supplied=True)})
    plate = d.Part("plate", lambda: cq.Workplane("XY").rect(20, 20).extrude(2), d.FDM("PETG"),
                   features={"mount": mount.clearance_side(thickness=2)})
    unit, _ = exported_unit(base)
    outer = d.Assembly("outer")
    a, b = outer.add("base", unit), outer.add("plate", plate)
    outer.fix(a)
    outer.connect("mount", mount, through=b.feature("mount"), into=a.feature("mount"))
    interface, = outer.interfaces()
    assert interface.components[1] == "/outer/base/unit/leaf"
    assert "not evidence of blind-hole depth" in interface.description


def test_exported_middle_layers_and_duplicate_leaf_rejection():
    mount, plate, base = definitions(thickness=2, recess=1)
    plate = replace(plate, features={"mount": mount.clearance_side(thickness=1, offset=1)})
    middle = d.Part("middle", lambda: cq.Workplane("XY").rect(30, 20).extrude(1), d.FDM("PETG"),
                    features={"mount": mount.middle_side(thickness=1)})
    inner = d.Assembly("inner")
    a, spacer = inner.add("base", base), inner.add("middle", middle)
    inner.fix(a)
    inner.fix(spacer)
    inner.export_feature("receiver", a.feature("mount"))
    inner.export_feature("middle", spacer.feature("mount"))
    outer = d.Assembly("outer")
    sub, b = outer.add("inner", inner), outer.add("plate", plate)
    outer.fix(sub)
    outer.connect("stack", mount, through=b.feature("mount"), into=sub.feature("receiver"),
                  via=(sub.feature("middle"),))
    assert outer.fastenings()[0].components == ("/outer/plate", "/outer/inner/middle", "/outer/inner/base")
    # Two roles exported under distinct names must not count the same body twice.
    bad = d.Assembly("bad")
    combined = replace(base, features={"receiver": mount.insert_side(), "middle": mount.middle_side(thickness=1)})
    same = bad.add("same", combined)
    top = bad.add("top", plate)
    bad.fix(same)
    with pytest.raises(ValueError, match="distinct participating"):
        bad.connect("stack", mount, through=top.feature("mount"), into=same.feature("receiver"),
                    via=(same.feature("middle"),))


def test_exported_attachment_preserves_single_leaf_ownership_and_rotated_frames():
    from test_design_attachments import clamp, nut_recipe
    inner = d.Assembly("inner")
    leaf = inner.add("clamp", clamp())
    inner.fix(leaf, at=d.Frame((3, 4, 5)))
    inner.export_feature("bolt", leaf.feature("bolt"))
    inner.export_feature("nut", leaf.feature("nut"))
    outer = d.Assembly("outer")
    sub = outer.add("inner", inner)
    outer.fix(sub, at=d.Frame((10, 0, 0), z=(0, 1, 0)))
    outer.attach("closure", nut_recipe(), through=sub.feature("bolt"), nut=sub.feature("nut"))
    frozen = outer.as_project()
    fastening, = frozen.fastenings
    assert fastening.components == ("/outer/inner/clamp",)
    assert fastening.sites[0].origin == pytest.approx((13, 5, -4))
    assert fastening.sites[0].axis == pytest.approx((0, 1, 0))
    assert fastening.grip_mm == pytest.approx(6.2)
    index = component_index(frozen.get_assembly())
    assert len(index) == 3
    assert all(resolve_components(i.components, index) for i in frozen.interfaces)
