"""Directed rigid placement of explicitly owned interfaces; no geometry mutation."""
from dataclasses import dataclass, field
from collections import Counter
import cadquery as cq
from ..project import Assembly as LegacyAssembly, Component, Project
from ..mechanics import Joint
from .frames import Frame, name as valid_name
from .parts import Part
from .mounts import InsertMount, MountFeature


@dataclass(frozen=True, eq=False)
class Instance:
    name: str
    part: Part
    group: str
    _owner: object = field(repr=False)

    def feature(self, key):
        if key not in self.part.features:
            raise ValueError(f"{self.name}: unknown feature {key!r}")
        return FeatureRef(self, key)


@dataclass(frozen=True)
class FeatureRef:
    instance: Instance
    key: str

    @property
    def definition(self):
        return self.instance.part.features[self.key]


@dataclass(frozen=True)
class Connection:
    name: str
    mount: InsertMount
    through: FeatureRef
    into: FeatureRef
    fastening_name: str


class Assembly:
    """A small opt-in authoring graph. Existing cadkit.Assembly stays unchanged.

    Connection frames have the same orientation; +Z points into the clamped part.
    Multiple fixed roots are allowed for independently located components. Every
    other instance needs exactly one placement parent. Cycles fail explicitly.
    """
    def __init__(self, name):
        self.name = valid_name(name)
        self._instances = {}
        self._fixed = {}
        self._connections = {}

    def add(self, name, part, *, group="parts"):
        valid_name(name)
        if name in self._instances:
            raise ValueError(f"Duplicate instance {name!r}")
        if any(i.part.name == part.name and i.part is not part for i in self._instances.values()):
            raise ValueError(f"Different part definitions share {part.name!r}; name the variant explicitly")
        instance = Instance(name, part, group, self)
        self._instances[name] = instance
        return instance

    def _owned(self, instance):
        if instance._owner is not self or self._instances.get(instance.name) is not instance:
            raise ValueError("Instance belongs to a different assembly")

    def _parented(self, instance):
        return instance.name in self._fixed or any(c.through.instance is instance for c in self._connections.values())

    def fix(self, instance, *, at=Frame()):
        self._owned(instance)
        if self._parented(instance):
            raise ValueError(f"{instance.name} already has a placement")
        self._fixed[instance.name] = at

    def connect(self, name, mount, *, through, into, fastening_name=None):
        valid_name(name)
        fastening_name = valid_name(fastening_name or name)
        if name in self._connections or any(c.fastening_name == fastening_name for c in self._connections.values()):
            raise ValueError("Duplicate connection or fastening name")
        for ref, role in ((through, "clearance"), (into, "insert")):
            self._owned(ref.instance)
            feature = ref.definition
            if not isinstance(feature, MountFeature) or feature.mount is not mount or feature.role != role:
                raise ValueError(f"{ref.instance.name}/{ref.key} must bind this mount's {role} side")
        if through.instance is into.instance:
            raise ValueError("A connection needs two distinct instances")
        if self._parented(through.instance):
            raise ValueError(f"{through.instance.name} already has a placement")
        connection = Connection(name, mount, through, into, fastening_name)
        self._connections[name] = connection
        return connection

    def locations(self, *, at=Frame()):
        """Resolve without building any geometry; useful to existing consumers."""
        result = {name: at.location * frame.location for name, frame in self._fixed.items()}
        pending = dict(self._connections)
        while pending:
            progress = False
            for name, connection in tuple(pending.items()):
                parent = connection.into.instance.name
                if parent not in result:
                    continue
                result[connection.through.instance.name] = (
                    result[parent] * connection.into.definition.at.location
                    * connection.through.definition.at.location.inverse)
                del pending[name]
                progress = True
            if not progress:
                raise ValueError("Unresolved placement: cycle or ungrounded parent")
        missing = self._instances.keys() - result.keys()
        if missing:
            raise ValueError(f"Unplaced instances: {', '.join(sorted(missing))}")
        return result

    def fastenings(self, *, at=Frame()):
        locations = self.locations(at=at)
        return tuple(c.mount.fastening(
            c.fastening_name, through=c.through.instance.name, into=c.into.instance.name,
            frame=Frame.from_location(locations[c.into.instance.name] * c.into.definition.at.location),
            clearance=c.through.definition, joint=c.name,
        ) for c in self._connections.values())

    def joints(self, *, at=Frame()):
        locations = self.locations(at=at)
        result = []
        for c in self._connections.values():
            frame = Frame.from_location(locations[c.into.instance.name] * c.into.definition.at.location)
            result.append(Joint(c.name, (c.through.instance.name, c.into.instance.name),
                                origin=frame.origin, axis=frame.z, fastenings=(c.fastening_name,)))
        return tuple(result)

    def components(self, *, at=Frame(), include_hardware=True):
        # Project supplies hardware from the same resolved fastenings.
        locations = self.locations(at=at)
        bodies = {}
        result = []
        for instance in self._instances.values():
            key = id(instance.part)
            if key not in bodies:
                bodies[key] = instance.part.build()
            result.append(Component(instance.name, bodies[key].moved(locations[instance.name]),
                                    instance.group, part=instance.part.name,
                                    metadata={"design": instance.part.describe()}))
        return result

    def as_project(self):
        """Freeze the graph into a legacy Project; later authoring cannot stale it."""
        frozen = Assembly(self.name)
        # Instances retain their identity; no new authoring is exposed on this snapshot.
        frozen._instances = dict(self._instances)
        frozen._connections = dict(self._connections)
        frozen._fixed = dict(self._fixed)
        counts = Counter(id(i.part) for i in frozen._instances.values())
        parts = {}
        for instance in frozen._instances.values():
            if instance.part.name in parts and parts[instance.part.name].group != instance.group:
                raise ValueError("Instances of one part must use the same manufacturing group")
            parts[instance.part.name] = instance.part.as_part(instance.group, quantity=counts[id(instance.part)])
        return Project(self.name, tuple(parts.values()), frozen.components,
                       assembly=lambda **options: LegacyAssembly(self.name, tuple(frozen.components(**options))),
                       fastenings=frozen.fastenings(), joints=frozen.joints())
