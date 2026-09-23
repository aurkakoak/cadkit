"""Viewer transforms must agree with native poses without rebuilding parts."""

import math
import numpy as np
import pytest
from cadkit import design as d
from cadkit.design.kinematics import matrix
from test_design_assembly import block, machine


def evaluate(graph, values):
    coordinates = {j["id"]: j["position"] for j in graph["joints"]} | values
    pending = list(graph["couplings"])
    while pending:
        ready = [
            c for c in pending if not any(p["driven"] == c["driver"] for p in pending)
        ]
        assert ready
        for c in ready:
            coordinates[c["driven"]] = (
                coordinates[c["driver"]] * c["ratio"] + c["offset"]
            )
            pending.remove(c)
    nodes = []
    for node in graph["nodes"]:
        value = np.eye(4)
        if "matrix" in node:
            value = np.array(node["matrix"]).reshape((4, 4), order="F")
        elif "product" in node:
            for index in node["product"]:
                value = value @ nodes[index]
        elif "inverse" in node:
            value = np.linalg.inv(nodes[node["inverse"]])
        elif node["kind"] == "slider":
            value[2, 3] = coordinates[node["joint"]]
        else:
            angle = math.radians(coordinates[node["joint"]])
            value[:2, :2] = [
                [math.cos(angle), -math.sin(angle)],
                [math.sin(angle), math.cos(angle)],
            ]
        nodes.append(value)
    return {
        key: nodes[t["node"]] @ np.array(t["inverse"]).reshape((4, 4), order="F")
        for key, t in graph["targets"].items()
    }


def test_nested_hardware_and_directed_sides_match_native_pose():
    design, _, _ = machine()
    project = design.as_project()
    baseline = project.get_assembly()
    mechanics = project.mechanical_descriptions(baseline)
    joint = next(j for j in mechanics["joints"] if j["id"] == "azimuth")
    assert joint["parent_components"] == ("/machine/base",)
    assert "/machine/stage/plate" in joint["moving_components"]
    assert any("/Hardware/" in name for name in joint["moving_components"])
    transforms = evaluate(mechanics["motion"], {"azimuth": 90})
    from cadkit.mechanics import component_index

    before = component_index(baseline)
    after = component_index(project.get_assembly(pose={"azimuth": 90}))
    for key in before:
        a = before[key].model.Center().toTuple()
        b = after[key].model.Center().toTuple()
        assert (transforms[key] @ [*a, 1])[:3] == pytest.approx(b, abs=1e-7)


def test_graph_has_no_geometry_builds_and_handles_nested_moving_datums():
    calls = []
    part = block(calls=calls)
    inner = d.Assembly("inner")
    root = inner.add("root", part)
    tip = inner.add("tip", part)
    inner.fix(root, at=d.Frame((6, 2, 0)))
    inner.connect(
        "bend",
        d.Revolute(position=15),
        parent=root.port("axis"),
        child=tip.port("axis"),
    )
    inner.export_port("tip", tip.port("axis"))
    outer = d.Assembly("outer")
    base = outer.add("base", part)
    arm = outer.add("arm", inner)
    follower = outer.add("follower", part)
    outer.fix(base, at=d.Frame((9, 5, 8), z=(1, 0, 0), x=(0, 1, 0)))
    outer.connect(
        "turn", d.Revolute(position=20), parent=base.port("axis"), child=arm.port("tip")
    )
    outer.connect(
        "follow", d.Rigid(), parent=arm.port("tip"), child=follower.port("axis")
    )
    graph = outer.motion_graph()
    baseline = outer.locations(names="path")
    posed = outer.locations(names="path", pose={"turn": 65, "arm/bend": 50})
    result = evaluate(graph, {"turn": 65, "arm/bend": 50})
    assert calls == []
    for key, value in posed.items():
        before = np.array(matrix(baseline[key])).reshape((4, 4), order="F")
        after = np.array(matrix(value)).reshape((4, 4), order="F")
        assert result["/outer/" + key] @ before == pytest.approx(after)


def test_coupled_rotations_and_slider_match_native():
    assembly = d.Assembly("coupled")
    part = block()
    base = assembly.add("base", part)
    a = assembly.add("a", part)
    b = assembly.add("b", part)
    c = assembly.add("c", part)
    assembly.fix(base)
    driver = assembly.connect(
        "driver", d.Revolute(), parent=base.port("axis"), child=a.port("axis")
    )
    driven = assembly.connect(
        "driven", d.Revolute(), parent=a.port("axis"), child=b.port("axis")
    )
    assembly.connect("slide", d.Slider(), parent=b.port("axis"), child=c.port("axis"))
    assembly.couple("gears", driver=driver, driven=driven, ratio=-2)
    graph = assembly.motion_graph()
    result = evaluate(graph, {"driver": 30, "slide": 10})
    posed = assembly.locations(names="path", pose={"driver": 30, "slide": 10})
    for key, location in posed.items():
        assert result["/coupled/" + key] == pytest.approx(
            np.array(matrix(location)).reshape((4, 4), order="F")
        )
