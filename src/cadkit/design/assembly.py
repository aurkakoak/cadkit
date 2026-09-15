"""Local part definitions composed by explicit datums, motion and shared mounts.

The authoring graph owns relationships, never world-space copies of parts.
Resolution is lazy and deterministic; the adapters all consume the same graph.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
import math
from types import MappingProxyType, SimpleNamespace
from urllib.parse import quote
import cadquery as cq

from ..project import Assembly as LegacyAssembly, Component, Project
from ..mechanics import Joint, Interface, AccessEnvelope, hardware_assembly
from .frames import Frame, name as valid_name
from .parts import Part, native
from .purchased import Purchased
from .motion import Rigid, Revolute, Slider


def _path(prefix, name):
    return f"{prefix}/{name}" if prefix else name


@dataclass(frozen=True, eq=False)
class Instance:
    name: str
    part: Part | Purchased | Assembly
    group: str | None
    _owner: object = field(repr=False)
    color: tuple | None = None
    material: str | None = None
    explode: tuple = (0, 0, 0)

    def feature(self, key):
        if isinstance(self.part, Assembly) or key not in self.part.features:
            raise ValueError(f"{self.name}: unknown feature {key!r}")
        return FeatureRef(self, key)

    def port(self, key):
        ports = self.part._ports if isinstance(self.part, Assembly) else self.part.ports
        if key not in ports:
            raise ValueError(f"{self.name}: unknown port {key!r}")
        return PortRef(self, key)


@dataclass(frozen=True)
class PortRef:
    instance: Instance
    key: str


@dataclass(frozen=True)
class FeatureRef(PortRef):
    @property
    def definition(self):
        return self.instance.part.features[self.key]


@dataclass(frozen=True, eq=False)
class Connection:
    name: str
    mount: object
    through: FeatureRef
    into: FeatureRef
    fastening_name: str
    placing: bool = True
    via: tuple[FeatureRef, ...] = ()

    @property
    def child(self):
        return self.through

    @property
    def parent(self):
        return self.into


@dataclass(frozen=True)
class Attachment:
    name: str
    recipe: object
    features: object


@dataclass(frozen=True, eq=False)
class MotionConnection:
    name: str
    motion: Rigid | Revolute | Slider
    parent: PortRef
    child: PortRef
    description: str = ""
    placing: bool = True


@dataclass(frozen=True)
class Coupling:
    name: str
    driver: str
    driven: str
    ratio: float
    offset: float = 0


@dataclass(frozen=True)
class Contact:
    name: str
    left: Instance
    right: Instance
    kind: str
    region: object = None
    max_overlap_mm3: float = 0
    min_clearance_mm: float = 0
    max_gap_mm: float | None = None
    description: str = ""


@dataclass(frozen=True)
class ToolAccess:
    name: str
    connection: str
    envelope: object
    obstacles: tuple[Instance, ...]
    at: Frame = Frame()
    description: str = ""


class Assembly:
    """Reusable local assembly whose instances have one placement parent each.

    Ports describe coincident frames. Revolute coordinates are degrees about Z;
    slider coordinates are millimetres along Z. Multiple fixed roots are allowed
    for intentional independent references; ungrounded and cyclic graphs fail.
    """
    def __init__(self, name):
        self.name = valid_name(name)
        self._instances = {}
        self._fixed = {}
        self._connections = {}
        self._attachments = {}
        self._ports = {}
        self._couplings = {}
        self._poses = {}
        self._interfaces = {}
        self._access = {}

    @property
    def instances(self):
        return MappingProxyType(self._instances)

    @property
    def connections(self):
        return MappingProxyType(self._connections)

    @property
    def attachments(self):
        return MappingProxyType(self._attachments)

    @property
    def ports(self):
        return MappingProxyType(self._ports)

    def add(self, name, part, *, group=None, color=None, material=None, explode=(0, 0, 0)):
        valid_name(name)
        if not isinstance(part, (Part, Purchased, Assembly)):
            raise TypeError("Assembly instances need a design.Part, Purchased or Assembly definition")
        if part is self:
            raise ValueError("An assembly cannot contain itself")
        if name in self._instances:
            raise ValueError(f"Duplicate instance {name!r}")
        if any(i.part.name == part.name and i.part is not part for i in self._instances.values()):
            raise ValueError(f"Different part definitions share {part.name!r}; name the variant explicitly")
        if color is not None and (len(color) != 3 or any(not math.isfinite(c) or not 0 <= c <= 1 for c in color)):
            raise ValueError("Component color must have three values between zero and one")
        instance = Instance(name, part, group, self, tuple(color) if color is not None else None, material, tuple(explode))
        self._instances[name] = instance
        return instance

    def _owned(self, instance):
        if not isinstance(instance, Instance) or instance._owner is not self or self._instances.get(instance.name) is not instance:
            raise ValueError("Instance belongs to a different assembly")

    def _ref(self, ref):
        if not isinstance(ref, PortRef):
            raise TypeError("Use instance.port(name) or instance.feature(name) as an attachment datum")
        self._owned(ref.instance)

    def _parented(self, instance):
        return instance.name in self._fixed or any(c.placing and c.child.instance is instance for c in self._connections.values())

    def fix(self, instance, *, at=Frame()):
        self._owned(instance)
        if not isinstance(at, Frame):
            raise TypeError("Fixed placement must be a Frame")
        if self._parented(instance):
            raise ValueError(f"{instance.name} already has a placement")
        self._fixed[instance.name] = at
        return instance

    def export_port(self, name, ref):
        valid_name(name)
        self._ref(ref)
        if name in self._ports:
            raise ValueError(f"Duplicate exported port {name!r}")
        self._ports[name] = ref

    def connect(self, name, relationship, *, parent=None, child=None, through=None, into=None,
                fastening_name=None, place=True, via=(), description=""):
        valid_name(name)
        if name in self._connections or name in self._attachments:
            raise ValueError("Duplicate connection or attachment name")
        if isinstance(relationship, (Rigid, Revolute, Slider)):
            if through is not None or into is not None or via or fastening_name is not None or not place:
                raise ValueError("Motion connections require parent and child ports and determine placement")
            self._ref(parent)
            self._ref(child)
            connection = MotionConnection(name, relationship, parent, child, description)
        else:
            if parent is not None or child is not None:
                raise ValueError("Mount connections require through and into feature references")
            fastening_name = valid_name(fastening_name or name)
            if fastening_name in self._attachments or any(isinstance(c, Connection) and c.fastening_name == fastening_name for c in self._connections.values()):
                raise ValueError("Duplicate fastening name")
            for ref, role in ((through, "clearance"), (into, getattr(relationship, "receiver_role", "insert")),
                              *((ref, "middle") for ref in via)):
                self._ref(ref)
                if not isinstance(ref, FeatureRef):
                    raise ValueError("Mount connections require manufacturing feature references")
                feature = ref.definition
                if getattr(feature, "mount", None) is not relationship or getattr(feature, "role", None) != role:
                    raise ValueError(f"{ref.instance.name}/{ref.key} must bind this mount's {role} side")
            if len({id(ref.instance) for ref in (through, into, *via)}) != 2 + len(via):
                raise ValueError("A connection needs distinct participating instances")
            if hasattr(relationship, "validate_stack"):
                relationship.validate_stack(through.definition, tuple(ref.definition for ref in via))
            connection = Connection(name, relationship, through, into, fastening_name, place, tuple(via))
        if connection.parent.instance is connection.child.instance:
            raise ValueError("A connection needs two distinct instances")
        if place and self._parented(connection.child.instance):
            raise ValueError(f"{connection.child.instance.name} already has a placement")
        self._connections[name] = connection
        return connection

    def fasten(self, name, mount, *, through, into, via=(), fastening_name=None):
        """Bind matching features on already placed parts without adding a parent."""
        return self.connect(name, mount, through=through, into=into, via=via,
                            fastening_name=fastening_name, place=False)

    def attach(self, name, recipe, **features):
        """Bind hardware to existing owned features, without adding placement.

        A captive closure or set screw may act within one physical part; it is
        a fastening rather than a joint between fabricated components.
        """
        valid_name(name)
        if name in self._attachments or name in self._connections or any(
                isinstance(c, Connection) and c.fastening_name == name for c in self._connections.values()):
            raise ValueError("Duplicate attachment or fastening name")
        if not features:
            raise ValueError("Hardware attachments require named manufacturing features")
        for ref in features.values():
            self._ref(ref)
            if not isinstance(ref, FeatureRef):
                raise TypeError("Hardware attachments require manufacturing feature references")
        recipe.validate({key: ref.definition for key,ref in features.items()})
        roles = getattr(recipe, "feature_roles", tuple(features))
        attachment = Attachment(name,recipe,MappingProxyType({key:features[key] for key in roles}))
        self._attachments[name] = attachment
        return attachment

    def interface(self, name, *, left, right, kind="contact", region=None,
                  max_overlap_mm3=0, min_clearance_mm=0, max_gap_mm=None, description=""):
        """Declare physical contact in this assembly's local coordinates.

        A bounded overlap region is a local CadQuery builder transformed together
        with the containing assembly; references must identify leaf components.
        """
        valid_name(name)
        for instance in (left, right):
            self._owned(instance)
            if isinstance(instance.part, Assembly):
                raise ValueError("Contact interfaces must identify leaf part instances")
        if name in self._interfaces:
            raise ValueError("Duplicate interface name")
        # Validate the same bounded allowances as the public mechanics contract.
        Interface(name, (left.name, right.name), kind, region, max_overlap_mm3, min_clearance_mm, max_gap_mm, description)
        contact = Contact(name, left, right, kind, region, max_overlap_mm3, min_clearance_mm, max_gap_mm, description)
        self._interfaces[name] = contact
        return contact

    def access(self, name, *, connection, envelope, obstacles, at=Frame(), description=""):
        """Bind a tool envelope to a fastening's receiver datum in every pose.

        The builder supplies the complete swept tool shape in datum coordinates.
        Obstacles are explicit local instances, including entire subassemblies.
        """
        valid_name(name)
        if name in self._access:
            raise ValueError("Duplicate access envelope name")
        if isinstance(connection, Connection):
            if self._connections.get(connection.name) is not connection:
                raise ValueError("Access connection belongs to a different assembly")
            connection = connection.name
        if not isinstance(self._connections.get(connection), Connection):
            raise ValueError("Access envelopes require a fastening connection")
        for obstacle in obstacles:
            self._owned(obstacle)
        if not callable(envelope) or not isinstance(at, Frame):
            raise TypeError("Access needs a CadQuery builder and local Frame")
        result = ToolAccess(name, connection, envelope, tuple(obstacles), at, description)
        self._access[name] = result
        return result

    def driver_access(self, name, *, connection, diameter, length, obstacles):
        """Straight driver probes at every screw seat, along outward datum Z."""
        from .frames import positive
        positive(diameter, "Driver diameter")
        positive(length, "Driver access length")
        if isinstance(connection, str):
            connection = self._connections.get(connection)
        if not isinstance(connection, Connection) or self._connections.get(connection.name) is not connection:
            raise ValueError("Driver access requires a local fastening connection")
        points = tuple(connection.mount.pattern.points)
        seat = connection.through.definition.seat
        def probes():
            return cq.Compound.makeCompound([
                cq.Solid.makeCylinder(diameter / 2, length, (x, y, seat)) for x, y in points])
        return self.access(name, connection=connection, envelope=probes, obstacles=obstacles,
                           description=f"Straight driver access: {diameter:g} mm diameter, {length:g} mm length from each screw seat")

    def _joint_key(self, key):
        if isinstance(key, MotionConnection):
            candidates = [path for path, (_, connection) in self._motion_index().items() if connection is key]
            if len(candidates) != 1:
                raise ValueError("Joint reference is foreign or ambiguous; use its scoped path")
            return candidates[0]
        if not isinstance(key, str):
            raise TypeError("Pose and coupling keys must be joint references or scoped joint paths")
        if key not in self._motion_index():
            raise ValueError(f"Unknown motion joint {key!r}; use its scoped path")
        return key

    def couple(self, name, *, driver, driven, ratio, offset=0):
        """Derive driven = driver * ratio + offset; units follow each joint."""
        valid_name(name)
        if name in self._couplings:
            raise ValueError("Duplicate coupling name")
        if not all(math.isfinite(v) for v in (ratio, offset)):
            raise ValueError("Coupling ratio and offset must be finite")
        driver, driven = self._joint_key(driver), self._joint_key(driven)
        if driver == driven:
            raise ValueError("A coupling cannot drive itself")
        if any(c.driven == driven for c in self._couplings.values()):
            raise ValueError(f"Motion joint {driven!r} already has a driver")
        coupling = Coupling(name, driver, driven, ratio, offset)
        self._couplings[name] = coupling
        return coupling

    def name_pose(self, name, positions):
        valid_name(name)
        if name in self._poses:
            raise ValueError("Duplicate pose name")
        values = self._normalize_pose(positions)
        self._positions(values)
        self._poses[name] = values
        return self

    def pose(self, positions):
        values = self._normalize_pose(positions)
        self._positions(values)
        return AssemblyPose(self._snapshot(), values)

    def _normalize_pose(self, values):
        if values is None:
            return {}
        if isinstance(values, str):
            if values not in self._poses:
                raise ValueError(f"Unknown pose {values!r}")
            return dict(self._poses[values])
        return {self._joint_key(key): value for key, value in values.items()}

    def _walk(self, prefix="", ancestors=()):
        if id(self) in ancestors:
            raise ValueError("Recursive assembly cycle")
        yield prefix, self
        for instance in self._instances.values():
            if isinstance(instance.part, Assembly):
                yield from instance.part._walk(_path(prefix, instance.name), (*ancestors, id(self)))

    def _motion_index(self):
        return {_path(prefix, name): (prefix, connection)
                for prefix, assembly in self._walk()
                for name, connection in assembly._connections.items()
                if isinstance(connection, MotionConnection) and not isinstance(connection.motion, Rigid)}

    def _positions(self, overrides):
        motions = self._motion_index()
        unknown = overrides.keys() - motions.keys()
        if unknown:
            raise ValueError(f"Unknown motion joints: {', '.join(sorted(unknown))}")
        result = {name: connection.motion.position for name, (_, connection) in motions.items()}
        result.update(overrides)
        couplings = [replace(c, name=_path(prefix, c.name), driver=_path(prefix, c.driver), driven=_path(prefix, c.driven))
                     for prefix, assembly in self._walk() for c in assembly._couplings.values()]
        driven = [c.driven for c in couplings]
        if len(driven) != len(set(driven)):
            raise ValueError("A motion joint has multiple coupling drivers")
        if overrides.keys() & set(driven):
            raise ValueError("A coupled joint is derived; set its driver instead")
        pending = list(couplings)
        while pending:
            ready = [c for c in pending if c.driver not in {other.driven for other in pending}]
            if not ready:
                raise ValueError("Motion coupling cycle")
            for coupling in ready:
                if coupling.driver not in result or coupling.driven not in result:
                    raise ValueError("Coupling references an unknown motion joint")
                result[coupling.driven] = result[coupling.driver] * coupling.ratio + coupling.offset
                pending.remove(coupling)
        for name, value in result.items():
            try:
                motions[name][1].motion.location(value)
            except ValueError as exc:
                raise ValueError(f"{name}: {exc}") from exc
        return result

    def _frame(self, ref, prefix, positions):
        if isinstance(ref, FeatureRef):
            return ref.definition.at.location
        definition = ref.instance.part
        if isinstance(definition, Assembly):
            inner_prefix = _path(prefix, ref.instance.name)
            inner = definition._ports[ref.key]
            locations = definition._locations(inner_prefix, positions)
            return locations[inner.instance.name] * definition._frame(inner, inner_prefix, positions)
        frame = definition.ports[ref.key]
        if not isinstance(frame, Frame):
            raise TypeError("Part ports must be local Frames")
        return frame.location

    def _locations(self, prefix, positions):
        result = {name: frame.location for name, frame in self._fixed.items()}
        pending = {name: c for name, c in self._connections.items() if c.placing}
        while pending:
            progress = False
            for name, connection in tuple(pending.items()):
                parent = connection.parent.instance.name
                if parent not in result:
                    continue
                motion = (connection.motion.location(positions.get(_path(prefix, name), 0))
                          if isinstance(connection, MotionConnection) else cq.Location())
                result[connection.child.instance.name] = (result[parent] * self._frame(connection.parent, prefix, positions)
                    * motion * self._frame(connection.child, prefix, positions).inverse)
                del pending[name]
                progress = True
            if not progress:
                raise ValueError("Unresolved placement: cycle or ungrounded parent")
        missing = self._instances.keys() - result.keys()
        if missing:
            raise ValueError(f"Unplaced instances: {', '.join(sorted(missing))}")
        # A secondary fastening must agree with the already resolved geometry.
        for connection in self._connections.values():
            if isinstance(connection, Connection):
                parent = result[connection.into.instance.name] * self._frame(connection.into, prefix, positions)
                for ref in (connection.through, *connection.via):
                    child = result[ref.instance.name] * self._frame(ref, prefix, positions)
                    relative = Frame.from_location(parent.inverse * child)
                    if (any(abs(x) > 1e-7 for x in relative.origin)
                        or any(abs(a-b) > 1e-7 for a, b in zip(relative.x, (1, 0, 0)))
                        or any(abs(a-b) > 1e-7 for a, b in zip(relative.z, (0, 0, 1)))):
                        raise ValueError(f"{_path(prefix, connection.name)}: fastening feature datums do not coincide")
        return result

    def locations(self, *, at=Frame(), pose=None):
        """Resolve immediate instance locations without building geometry."""
        positions = self._positions(self._normalize_pose(pose))
        return {name: at.location * location for name, location in self._locations("", positions).items()}

    def _resolve(self, *, at=Frame(), pose=None):
        positions = self._positions(self._normalize_pose(pose))
        assemblies, leaves = {}, {}
        def visit(assembly, prefix, location):
            local = assembly._locations(prefix, positions)
            assemblies[prefix] = (assembly, location, local)
            for instance in assembly._instances.values():
                path = _path(prefix, instance.name)
                world = location * local[instance.name]
                if isinstance(instance.part, Assembly):
                    visit(instance.part, path, world)
                else:
                    leaves[path] = (instance, world)
        visit(self, "", at.location)
        return Resolution(self, positions, assemblies, leaves)

    def fastenings(self, *, at=Frame(), pose=None):
        return self._resolve(at=at, pose=pose).fastenings()

    def joints(self, *, at=Frame(), pose=None):
        return self._resolve(at=at, pose=pose).joints()

    def interfaces(self, *, at=Frame(), pose=None):
        return self._resolve(at=at, pose=pose).interfaces()

    def components(self, *, at=Frame(), pose=None, include_hardware=False, kind=None):
        return self._resolve(at=at, pose=pose).components(include_hardware=include_hardware, kind=kind)

    def models(self, *, kind=None, names="leaf", at=Frame(), pose=None):
        """Native Workplanes keyed by leaf names or unambiguous relative paths."""
        if kind not in {None, "manufactured", "purchased"} or names not in {"leaf", "path"}:
            raise ValueError("models expects kind manufactured/purchased and names leaf/path")
        result = {}
        for path, component in self._resolve(at=at, pose=pose)._native_components(kind=kind).items():
            key = component.name if names == "leaf" else path
            if key in result:
                raise ValueError(f"Ambiguous leaf name {key!r}; request names='path'")
            result[key] = cq.Workplane(obj=component.model)
        return result

    def purchased_bom(self):
        """Instance quantities of purchased definitions, independent of pose."""
        rows = {}
        for prefix, assembly in self._walk():
            for instance in assembly._instances.values():
                definition = instance.part
                if isinstance(definition, Purchased):
                    key = (definition.name, definition.supplier, definition.sku)
                    row = rows.setdefault(key, {"name": definition.name, "supplier": definition.supplier,
                                               "sku": definition.sku, "quantity": 0, "instances": []})
                    row["quantity"] += definition.quantity
                    row["instances"].append(_path(prefix, instance.name))
        return tuple(rows.values())

    def embed(self, *, at=Frame(), pose=None):
        """Expose a frozen subsystem through the stable, flat Project contract.

        Leaf names must be unique. All geometry and mechanics are resolved by
        this library; consumers do not reconstruct placements or hardware.
        """
        values = self._normalize_pose(pose)
        result = Embedding(self._snapshot(), at, values)
        result._reference_map()
        return result

    def as_assembly(self, *, at=Frame(), pose=None, include_hardware=True, kind=None):
        return self._resolve(at=at, pose=pose).as_assembly(include_hardware=include_hardware, kind=kind)

    def as_cq_assembly(self, *, at=Frame(), pose=None, include_hardware=True, kind=None):
        def convert(tree):
            result = cq.Assembly(name=tree.name)
            for child in tree.children:
                if isinstance(child, LegacyAssembly):
                    result.add(convert(child))
                else:
                    result.add(child.model, name=child.name, color=cq.Color(*child.color))
            return result
        return convert(self.as_assembly(at=at, pose=pose, include_hardware=include_hardware, kind=kind))

    def describe(self):
        self._motion_index()  # Reject recursive authoring before recursing below.
        return {"schema_version": 1, "name": self.name, "kind": "assembly",
                "instances": {name: {"definition": instance.part.describe(), "group": instance.group}
                              for name, instance in self._instances.items()},
                "fixed": {name: frame.describe() for name, frame in self._fixed.items()},
                "ports": {name: {"instance": ref.instance.name, "port": ref.key,
                                  "feature": isinstance(ref, FeatureRef)} for name, ref in self._ports.items()},
                "connections": {name: self._describe_connection(c) for name, c in self._connections.items()},
                "attachments": {name: {"recipe":a.recipe.describe(),
                    "features":{key:{"instance":ref.instance.name,"feature":ref.key} for key,ref in a.features.items()}}
                    for name,a in self._attachments.items()},
                "couplings": {name: {"driver": c.driver, "driven": c.driven, "ratio": c.ratio, "offset": c.offset}
                              for name, c in self._couplings.items()},
                "interfaces": {name: {"left": c.left.name, "right": c.right.name, "kind": c.kind,
                                       "max_overlap_mm3": c.max_overlap_mm3, "min_clearance_mm": c.min_clearance_mm,
                                       "max_gap_mm": c.max_gap_mm, "has_region": c.region is not None,
                                       "description": c.description} for name, c in self._interfaces.items()},
                "access": {name: {"connection": value.connection, "obstacles": [i.name for i in value.obstacles],
                                   "frame": value.at.describe(), "description": value.description}
                           for name, value in self._access.items()},
                "poses": {name: dict(values) for name, values in self._poses.items()}}

    @staticmethod
    def _describe_connection(connection):
        result = {"parent": {"instance": connection.parent.instance.name, "datum": connection.parent.key},
                  "child": {"instance": connection.child.instance.name, "datum": connection.child.key}}
        if isinstance(connection, Connection):
            return {**result, "kind": "fastening", "mount": connection.mount.describe(),
                    "places_child": connection.placing,
                    "via": [{"instance": ref.instance.name, "feature": ref.key} for ref in connection.via]}
        return {**result, **connection.motion.describe(), "description": connection.description}

    def _snapshot(self, ancestors=()):
        if id(self) in ancestors:
            raise ValueError("Recursive assembly cycle")
        frozen = Assembly(self.name)
        replacements = {}
        for name, instance in self._instances.items():
            definition = instance.part._snapshot((*ancestors, id(self))) if isinstance(instance.part, Assembly) else instance.part
            replacements[id(instance)] = replace(instance, part=definition, _owner=frozen)
            frozen._instances[name] = replacements[id(instance)]
        def ref(value):
            return replace(value, instance=replacements[id(value.instance)])
        frozen._fixed = dict(self._fixed)
        frozen._ports = {key: ref(value) for key, value in self._ports.items()}
        for name, connection in self._connections.items():
            if isinstance(connection, Connection):
                frozen._connections[name] = replace(connection, through=ref(connection.through), into=ref(connection.into),
                                                     via=tuple(ref(value) for value in connection.via))
            else:
                frozen._connections[name] = replace(connection, parent=ref(connection.parent), child=ref(connection.child))
        frozen._attachments = {name: replace(a,features=MappingProxyType({key:ref(value) for key,value in a.features.items()}))
                               for name,a in self._attachments.items()}
        frozen._couplings = dict(self._couplings)
        frozen._poses = {name: dict(values) for name, values in self._poses.items()}
        frozen._interfaces = {name: replace(c, left=replacements[id(c.left)], right=replacements[id(c.right)])
                              for name, c in self._interfaces.items()}
        frozen._access = {name: replace(value, obstacles=tuple(replacements[id(i)] for i in value.obstacles))
                          for name, value in self._access.items()}
        return frozen

    def as_project(self, *, parameters=(), checks=(), description="", pose=None):
        """Snapshot into Cadkit's tooling contract; native definitions stay local."""
        values = self._normalize_pose(pose)
        return DesignProject(self._snapshot(), values, parameters=parameters, checks=checks, description=description)


@dataclass(frozen=True)
class AssemblyPose:
    _assembly: Assembly = field(repr=False)
    positions: dict

    def __post_init__(self):
        object.__setattr__(self, "positions", MappingProxyType(dict(self.positions)))

    def _call(self, method, *args, **options):
        if "pose" in options:
            raise ValueError("This assembly already has a resolved pose")
        return getattr(self._assembly, method)(*args, pose=self.positions, **options)

    def locations(self, **options):
        return self._call("locations", **options)

    def components(self, **options):
        return self._call("components", **options)

    def models(self, **options):
        return self._call("models", **options)

    def joints(self, **options):
        return self._call("joints", **options)

    def fastenings(self, **options):
        return self._call("fastenings", **options)

    def interfaces(self, **options):
        return self._call("interfaces", **options)

    def as_assembly(self, **options):
        return self._call("as_assembly", **options)

    def as_cq_assembly(self, **options):
        return self._call("as_cq_assembly", **options)

    def as_project(self, **options):
        return self._call("as_project", **options)

    def embed(self, **options):
        return self._call("embed", **options)

    def describe(self):
        return {"assembly": self._assembly.describe(), "positions": dict(self.positions)}


@dataclass
class Resolution:
    definition: Assembly
    positions: dict
    assemblies: dict
    leaves: dict

    def _id(self, path):
        return "/" + "/".join(quote(name, safe="") for name in (self.definition.name, *path.split("/")))

    def _refs(self, prefix, instance):
        path = _path(prefix, instance.name)
        return tuple(self._id(key) for key in self.leaves if key == path or key.startswith(path + "/"))

    def _attachment_records(self):
        for prefix,(assembly,world,local) in self.assemblies.items():
            for name,attachment in assembly._attachments.items():
                features = {key:ref.definition for key,ref in attachment.features.items()}
                frames = {key:Frame.from_location(world * local[ref.instance.name]
                          * assembly._frame(ref,prefix,self.positions)) for key,ref in attachment.features.items()}
                components = tuple(dict.fromkeys(self._id(_path(prefix,ref.instance.name))
                                   for ref in attachment.features.values()))
                yield _path(prefix,name),attachment,features,frames,components

    def fastenings(self):
        result = [attachment.recipe.fastening(name,features=features,frames=frames,components=components)
                  for name,attachment,features,frames,components in self._attachment_records()]
        for prefix, (assembly, world, local) in self.assemblies.items():
            for connection in assembly._connections.values():
                if not isinstance(connection, Connection):
                    continue
                frame = Frame.from_location(world * local[connection.into.instance.name]
                                            * assembly._frame(connection.into, prefix, self.positions))
                options = {"through": self._id(_path(prefix, connection.through.instance.name)),
                           "into": self._id(_path(prefix, connection.into.instance.name)),
                           "frame": frame, "clearance": connection.through.definition,
                           "joint": _path(prefix, connection.name)}
                if connection.via:
                    options["via"] = tuple(self._id(_path(prefix, ref.instance.name)) for ref in connection.via)
                fastening = connection.mount.fastening(_path(prefix, connection.fastening_name), **options)
                access = tuple(AccessEnvelope(
                    value.name,
                    lambda value=value, frame=frame: native(value.envelope()).moved(frame.location * value.at.location),
                    tuple(ref for obstacle in value.obstacles for ref in self._refs(prefix, obstacle)), value.description)
                    for value in assembly._access.values() if value.connection == connection.name)
                result.append(replace(fastening, access=access) if access else fastening)
        return tuple(result)

    def joints(self):
        result = []
        for prefix, (assembly, world, local) in self.assemblies.items():
            for name, connection in assembly._connections.items():
                frame = Frame.from_location(world * local[connection.parent.instance.name]
                                            * assembly._frame(connection.parent, prefix, self.positions))
                refs = tuple(dict.fromkeys((*self._refs(prefix, connection.parent.instance),
                                            *self._refs(prefix, connection.child.instance))))
                if isinstance(connection, Connection):
                    refs = tuple(dict.fromkeys((*refs, *(ref for middle in connection.via for ref in self._refs(prefix, middle.instance)))))
                    result.append(Joint(_path(prefix, name), refs, origin=frame.origin, axis=frame.z,
                                        fastenings=(_path(prefix, connection.fastening_name),)))
                else:
                    result.append(Joint(_path(prefix, name), refs, kind=connection.motion.kind,
                                        origin=frame.origin, axis=frame.z,
                                        limits=getattr(connection.motion, "limits", None),
                                        position=self.positions.get(_path(prefix, name), 0), description=connection.description))
        return tuple(result)

    def interfaces(self):
        result = []
        fastenings = {item.name: item for item in self.fastenings()}
        hardware_root = "/" + quote(self.definition.name, safe="") + "/Hardware"
        for name,attachment,features,frames,_ in self._attachment_records():
            result.extend(attachment.recipe.interfaces(fastenings[name],features=features,frames=frames,
                          hardware_root=hardware_root))
        for prefix, (assembly, world, _) in self.assemblies.items():
            for name, contact in assembly._interfaces.items():
                region = (lambda builder=contact.region, location=world: native(builder()).moved(location)) if contact.region else None
                result.append(Interface(_path(prefix, name), (self._id(_path(prefix, contact.left.name)), self._id(_path(prefix, contact.right.name))),
                                        contact.kind, region, contact.max_overlap_mm3, contact.min_clearance_mm,
                                        contact.max_gap_mm, contact.description))
            for connection in assembly._connections.values():
                if isinstance(connection, Connection) and hasattr(connection.mount, "interfaces"):
                    result.extend(connection.mount.interfaces(
                        fastenings[_path(prefix, connection.fastening_name)], receiver=connection.into.definition,
                        hardware_root=hardware_root,
                        receiver_representation=getattr(connection.into.instance.part, "representation", None)))
        return tuple(result)

    def _native_components(self, *, kind=None):
        if kind not in {None, "manufactured", "purchased"}:
            raise ValueError("Component kind must be manufactured or purchased")
        bodies, result = {}, {}
        for path, (instance, location) in self.leaves.items():
            purchased = isinstance(instance.part, Purchased)
            if kind is not None and kind != ("purchased" if purchased else "manufactured"):
                continue
            key = id(instance.part)
            if key not in bodies:
                bodies[key] = instance.part.build()
            result[path] = Component(instance.name, bodies[key].moved(location),
                instance.group or ("Purchased" if purchased else "parts"),
                color=instance.color or ((0.58, 0.62, 0.66) if purchased else (0.23, 0.27, 0.3)),
                material=instance.material or ("purchased" if purchased else "printed"),
                part=None if purchased else instance.part.name, explode=instance.explode,
                metadata={"design": instance.part.describe(), "design_path": self._id(path),
                          "design_kind": "purchased" if purchased else "manufactured",
                          **({"representation": instance.part.representation} if purchased else {})})
        return result

    def components(self, *, include_hardware=False, kind=None):
        result = [replace(component, name=path) for path, component in self._native_components(kind=kind).items()]
        if include_hardware:
            hardware = hardware_assembly(self.fastenings())
            def visit(tree, prefix=""):
                for child in tree.children:
                    path = _path(prefix, child.name)
                    if isinstance(child, LegacyAssembly):
                        yield from visit(child, path)
                    else:
                        yield replace(child, name=_path("Hardware", path))
            if hardware:
                result.extend(visit(hardware))
        return result

    def as_assembly(self, *, include_hardware=True, kind=None):
        components = self._native_components(kind=kind)
        def visit(assembly, prefix):
            children = []
            for name, instance in assembly._instances.items():
                path = _path(prefix, name)
                if isinstance(instance.part, Assembly):
                    child = replace(visit(instance.part, path), name=name)
                    if child.children:
                        children.append(child)
                elif path in components:
                    children.append(components[path])
            return LegacyAssembly(assembly.name, tuple(children))
        tree = visit(self.definition, "")
        fastenings, joints, interfaces = self.fastenings(), self.joints(), self.interfaces()
        hardware = hardware_assembly(fastenings) if include_hardware else None
        return _ResolvedAssembly(tree.name, tree.children + ((hardware,) if hardware else ()), tree.description,
                                 joints, interfaces, fastenings)


@dataclass(frozen=True)
class _ResolvedAssembly(LegacyAssembly):
    _joints: tuple = field(default=(), repr=False, compare=False)
    _interfaces: tuple = field(default=(), repr=False, compare=False)
    _fastenings: tuple = field(default=(), repr=False, compare=False)


class DesignProject(Project):
    """Compatibility adapter with pose-coherent geometry and mechanical metadata."""
    def __init__(self, definition, pose, *, parameters=(), checks=(), description=""):
        self._definition = definition
        self._default_pose = dict(pose)
        resolution = definition._resolve(pose=pose)
        counts = Counter(id(i.part) for i, _ in resolution.leaves.values() if isinstance(i.part, Part))
        parts, identities = {}, {}
        for instance, _ in resolution.leaves.values():
            if not isinstance(instance.part, Part):
                continue
            name, group = instance.part.name, instance.group or "parts"
            if name in identities and identities[name] is not instance.part:
                raise ValueError(f"Different part definitions share {name!r}; name the variant explicitly")
            if name in parts and parts[name].group != group:
                raise ValueError("Instances of one part must use the same manufacturing group")
            identities[name] = instance.part
            parts[name] = instance.part.as_part(group, quantity=counts[id(instance.part)])
        super().__init__(definition.name, tuple(parts.values()), self._components,
                         parameters=tuple(parameters), checks=tuple(checks), description=description,
                         views={name: (lambda _name=name, **options: self._components(pose=_name, **options)) for name in definition._poses},
                         assembly=self._assembly, joints=resolution.joints(), interfaces=resolution.interfaces(), fastenings=resolution.fastenings())

    def _options(self, view=None, **options):
        pose = options.pop("pose", view if view is not None else self._default_pose)
        if view is not None and view not in self._definition._poses:
            raise ValueError(f"Unknown view: {view}")
        return {"pose": pose, **options}

    def _components(self, **options):
        # The stable Project contract expects authored components here.
        options = self._options(**options)
        options["include_hardware"] = False
        return self._definition.components(**options)

    def _assembly(self, **options):
        options = self._options(**options)
        options["include_hardware"] = False
        return self._definition.as_assembly(**options)

    def get_components(self, view=None, **options):
        options = self._options(view, **options)
        options.setdefault("include_hardware", True)
        return self._definition.components(**options)

    def get_assembly(self, view=None, **options):
        options = self._options(view, **options)
        return self._definition.as_assembly(**options)

    def _mechanics(self, assembly):
        if isinstance(assembly, _ResolvedAssembly):
            return SimpleNamespace(joints=assembly._joints, interfaces=assembly._interfaces, fastenings=assembly._fastenings)
        return self

    def mechanical_descriptions(self, assembly=None):
        from ..mechanics import mechanical_descriptions
        return mechanical_descriptions(self._mechanics(assembly), assembly)

    def validate_mechanics(self, assembly=None, *, scan_collisions=True, tolerance_mm3=1e-5):
        from ..mechanics import validate_mechanics
        assembly = assembly if assembly is not None else self.get_assembly()
        return validate_mechanics(self._mechanics(assembly), assembly, scan_collisions=scan_collisions, tolerance_mm3=tolerance_mm3)

    def describe(self):
        return {**super().describe(), "design": self._definition.describe(), "pose": dict(self._default_pose),
                "purchased_bom": self._definition.purchased_bom()}


@dataclass(frozen=True)
class Embedding:
    """Frozen leaf-name adapter for embedding a design in an existing Project."""
    _definition: Assembly = field(repr=False)
    at: Frame
    pose: dict

    def __post_init__(self):
        object.__setattr__(self, "pose", MappingProxyType(dict(self.pose)))

    def _resolve(self):
        return self._definition._resolve(at=self.at, pose=self.pose)

    def _reference_map(self):
        resolution = self._resolve()
        result = {resolution._id(path): instance.name for path, (instance, _) in resolution.leaves.items()}
        if len(set(result.values())) != len(result):
            raise ValueError("Embedding has ambiguous leaf names; use a nested design Assembly")
        return result

    def components(self, *, include_hardware=False, kind=None):
        self._reference_map()
        components = self._resolve().components(include_hardware=include_hardware, kind=kind)
        return [replace(c, name=c.name.rsplit("/", 1)[-1]) if "design_kind" in c.metadata else c for c in components]

    def models(self, *, kind=None):
        return self._definition.models(kind=kind, names="leaf", at=self.at, pose=self.pose)

    def fastenings(self):
        refs = self._reference_map()
        return tuple(replace(item, components=tuple(refs[ref] for ref in item.components),
                             access=tuple(replace(access, obstacles=tuple(refs[ref] for ref in access.obstacles)) for access in item.access))
                     for item in self._resolve().fastenings())

    def joints(self):
        refs = self._reference_map()
        return tuple(replace(item, components=tuple(refs[ref] for ref in item.components)) for item in self._resolve().joints())

    def interfaces(self, *, hardware_root=None):
        refs = self._reference_map()
        source = "/" + quote(self._definition.name, safe="") + "/Hardware"
        target = hardware_root or source
        def mapped(ref):
            if ref in refs:
                return refs[ref]
            if ref.startswith(source + "/"):
                return target.rstrip("/") + ref[len(source):]
            raise ValueError(f"Unknown embedded component reference {ref!r}")
        return tuple(replace(item, components=tuple(mapped(ref) for ref in item.components)) for item in self._resolve().interfaces())

    def parts(self):
        return self._definition.as_project(pose=self.pose).parts

    def purchased_bom(self):
        return self._definition.purchased_bom()
