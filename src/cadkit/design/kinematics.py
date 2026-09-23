"""Geometry-free transform graphs for read-only viewers.

Matrices are column-major, in millimetres. Nodes are topologically ordered;
consumers evaluate joint coordinates, then multiply each target's world matrix
by its captured inverse to move already-installed display geometry.
"""

from functools import lru_cache

import cadquery as cq


def matrix(location):
    transform = location.wrapped.Transformation()
    return [
        transform.Value(row, column) if row < 4 else int(column == 4)
        for column in range(1, 5)
        for row in range(1, 5)
    ]


def motion_graph(resolution):
    from .assembly import Assembly, Connection, MotionConnection, FeatureRef, _path
    from .motion import Rigid

    nodes = []
    native = []
    dependencies = []
    joints = {}

    def node(spec, value, depends=()):
        index = len(nodes)
        nodes.append(spec)
        native.append(value)
        dependencies.append(set(depends))
        return index

    def constant(location):
        return node({"matrix": matrix(location)}, location)

    def product(*indices):
        value = cq.Location()
        depends = set()
        for index in indices:
            value *= native[index]
            depends.update(dependencies[index])
        return node({"product": list(indices)}, value, depends)

    def inverse(index):
        return node({"inverse": index}, native[index].inverse, dependencies[index])

    identity = constant(cq.Location())

    @lru_cache(None)
    def local(prefix, name):
        assembly = resolution.assemblies[prefix][0]
        if name in assembly._fixed:
            return constant(assembly._fixed[name].location)
        connection = next(
            c
            for c in assembly._connections.values()
            if c.placing and c.child.instance.name == name
        )
        parent = local(prefix, connection.parent.instance.name)
        datum = port(prefix, connection.parent)
        movement = identity
        if isinstance(connection, MotionConnection) and not isinstance(
            connection.motion, Rigid
        ):
            key = _path(prefix, connection.name)
            position = resolution.positions[key]
            movement = node(
                {"joint": key, "kind": connection.motion.kind},
                connection.motion.location(position),
                (key,),
            )
            joints[key] = {
                "id": key,
                "kind": connection.motion.kind,
                "position": position,
                "limits": connection.motion.limits,
            }
        return product(parent, datum, movement, inverse(port(prefix, connection.child)))

    def port(prefix, ref):
        if isinstance(ref, FeatureRef):
            return constant(ref.definition.at.location)
        if isinstance(ref.instance.part, Assembly):
            inner_prefix = _path(prefix, ref.instance.name)
            inner = ref.instance.part._ports[ref.key]
            return product(
                local(inner_prefix, inner.instance.name), port(inner_prefix, inner)
            )
        return constant(ref.instance.part.ports[ref.key].location)

    @lru_cache(None)
    def world(prefix):
        if not prefix:
            return constant(resolution.assemblies[""][1])
        parent, _, name = prefix.rpartition("/")
        return product(world(parent), local(parent, name))

    targets = {}
    for path in resolution.leaves:
        index = world(path)
        targets[resolution._id(path)] = {
            "node": index,
            "inverse": matrix(native[index].inverse),
            "joints": sorted(dependencies[index]),
        }

    # Hardware is already located in world coordinates. Its receiver datum
    # defines the display transform; no fastener geometry is rebuilt.
    hardware = {}
    unsupported = set()
    for prefix, (assembly, _, _) in resolution.assemblies.items():
        for connection in assembly._connections.values():
            if isinstance(connection, Connection):
                index = product(
                    world(_path(prefix, connection.into.instance.name)),
                    port(prefix, connection.into),
                )
                hardware[_path(prefix, connection.fastening_name)] = {
                    "node": index,
                    "inverse": matrix(native[index].inverse),
                    "joints": sorted(dependencies[index]),
                }
                if not connection.placing:
                    # Secondary fastenings constrain the pose beyond the placement tree.
                    sides = [
                        dependencies[world(_path(prefix, ref.instance.name))]
                        for ref in (
                            connection.through,
                            connection.into,
                            *connection.via,
                        )
                    ]
                    unsupported.update(set.union(*sides) - set.intersection(*sides))
        for name, attachment in assembly._attachments.items():
            frames = [
                product(world(_path(prefix, ref.instance.name)), port(prefix, ref))
                for ref in attachment.features.values()
            ]
            if frames:
                index = frames[0]
                hardware[_path(prefix, name)] = {
                    "node": index,
                    "inverse": matrix(native[index].inverse),
                    "joints": sorted(dependencies[index]),
                }
                if any(dependencies[i] != dependencies[index] for i in frames):
                    for i in frames:
                        unsupported.update(dependencies[i])

    couplings = []
    for prefix, (assembly, _, _) in resolution.assemblies.items():
        for coupling in assembly._couplings.values():
            couplings.append(
                {
                    "driver": _path(prefix, coupling.driver),
                    "driven": _path(prefix, coupling.driven),
                    "ratio": coupling.ratio,
                    "offset": coupling.offset,
                }
            )
    for key, joint in joints.items():
        joint["moving_components"] = [
            name
            for name, target in targets.items()
            if key in dependencies[target["node"]]
        ]
        if key in unsupported:
            joint["disabled_reason"] = (
                "This joint has additional fastening constraints."
            )
    return {
        "schema_version": 1,
        "nodes": nodes,
        "targets": targets,
        "hardware": hardware,
        "joints": list(joints.values()),
        "couplings": couplings,
    }
