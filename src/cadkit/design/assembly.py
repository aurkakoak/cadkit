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

from .._project import Assembly as PlacedAssembly, Component, Project as ProjectRecord
from ..geometry import Mesh
from ..mechanics import Joint, Interface, AccessEnvelope, hardware_assembly
from .frames import Frame, name as valid_name
from .parts import Part, native
from .purchased import Purchased
from .motion import Rigid, Revolute, Slider


def _path(prefix, name):
    return f"{prefix}/{name}" if prefix else name


@dataclass(frozen=True, eq=False)
class Instance:
    """Handle returned by `Assembly.add`; use its feature and port accessors.

    Instances belong to one assembly. Do not construct them directly or reuse a
    handle in another assembly. Reuse the underlying Part or Assembly definition.
    """
    name: str
    part: Part | Purchased | Assembly
    group: str | None
    _owner: object = field(repr=False)
    color: tuple | None = None
    material: str | None = None
    explode: tuple = (0, 0, 0)

    def feature(self, key):
        """Reference a named manufacturing feature owned by this instance's definition.

        Args:
            key (str): Feature name.

        Returns:
            (FeatureRef): Bound local datum and feature definition.

        Raises:
            ValueError: The feature is absent or is not exported by the nested assembly.
        """
        features = self.part._exported_features if isinstance(self.part, Assembly) else self.part.features
        if key not in features:
            raise ValueError(f"{self.name}: unknown feature {key!r}")
        return FeatureRef(self, key)

    def port(self, key):
        """Reference a local port or an exported nested-assembly port.

        Args:
            key (str): Port name.

        Returns:
            (PortRef): Instance-bound attachment datum.
        """
        ports = self.part._ports if isinstance(self.part, Assembly) else self.part.ports
        if key not in ports:
            raise ValueError(f"{self.name}: unknown port {key!r}")
        return PortRef(self, key)


    def component(self, key):
        """Reference a selected leaf exported by this nested assembly instance.

        Args:
            key (str): Name declared with the nested assembly's `export_component`.

        Returns:
            (ComponentRef): Leaf reference scoped to this occurrence of the assembly.

        Raises:
            ValueError: This is a leaf instance or the component is not exported.
        """
        if not isinstance(self.part, Assembly) or key not in self.part._exported_components:
            raise ValueError(f"{self.name}: unknown exported component {key!r}")
        return ComponentRef(self, key)


@dataclass(frozen=True)
class ComponentRef:
    """An exported leaf scoped to one installed subassembly occurrence.

    Obtain this with `instance.component(name)`. Pass it to `Assembly.interface`
    or re-export it with `Assembly.export_component`; it is not an attachment
    datum. Reusing a subassembly creates distinct references for its instances.

    Attributes:
        instance (Instance): Nested assembly instance anchoring this reference.
        key (str): Component export name on that instance's assembly definition.
    """
    instance: Instance
    key: str


@dataclass(frozen=True)
class PortRef:
    instance: Instance
    key: str


@dataclass(frozen=True)
class FeatureRef(PortRef):
    @property
    def definition(self):
        part = self.instance.part
        if isinstance(part, Assembly):
            return part._exported_features[self.key].definition
        return part.features[self.key]


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
    left: Instance | ComponentRef
    right: Instance | ComponentRef
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
    """A local assembly graph resolved through explicit frames and relationships.

    Args:
        name (str): Stable assembly name without path separators.

    Add instances, fix at least one root, and connect the remaining instances.
    Each instance has one placement parent. Multiple fixed roots are allowed;
    cycles, ungrounded instances, and conflicting placements are errors.

    Geometry is built lazily by output methods. Manufacturing definitions remain
    local and reusable across every instance and pose.
    """
    def __init__(self, name):
        self.name = valid_name(name)
        self._instances = {}
        self._fixed = {}
        self._connections = {}
        self._attachments = {}
        self._ports = {}
        self._exported_components = {}
        self._exported_features = {}
        self._couplings = {}
        self._poses = {}
        self._interfaces = {}
        self._access = {}
        self._variant_choices = {}

    def variant(self, key, choice, *, selected=None):
        """Declare and resolve a choice owned by this assembly's tree row.

        Use a stable project-unique key and a ``ck.Variant`` definition. During
        ``ck.Variants(builder).project(...)``, the requested value overrides the
        default. Standalone builders may supply ``selected`` explicitly. The
        containing project discovers the choice and its installed instance path;
        parent assemblies do not need to forward configuration arguments.
        """
        from ..variants import assembly_choice
        return assembly_choice(self, key, choice, selected)

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

    @property
    def exported_components(self):
        """Read-only mapping of public component names to selected leaf references."""
        return MappingProxyType(self._exported_components)

    @property
    def exported_features(self):
        """Read-only mapping of public feature names to owned feature references."""
        return MappingProxyType(self._exported_features)

    def add(self, name=None, part=None, *, group=None, color=None, material=None, explode=(0, 0, 0)):
        """Add a named instance without placing it or building its geometry.

        Args:
            name (str | Part | Purchased | Assembly | None): Unique instance name,
                or the definition itself when using `add(part)`.
            part (Part | Purchased | Assembly | None): Reusable definition. An
                omitted name defaults to its name; duplicate names are errors.
            group (str | None): Display group override. Defaults to the Part's
                manufacturing group or `Purchased`; never changes manufacturing
                grouping. Nested assemblies retain their leaves' display groups.
            color (tuple | None): RGB display override, each channel from 0 to 1.
            material (str | None): Rendering material override.
            explode (tuple): Presentation translation in millimetres.

        Returns:
            (Instance): Owned handle for fixing, connecting, and referencing features.
        """
        if isinstance(name, (Part, Purchased, Assembly)):
            if part is not None:
                raise TypeError("Pass a definition alone or an instance name and definition")
            part, name = name, None
        if not isinstance(part, (Part, Purchased, Assembly)):
            raise TypeError("Assembly instances need a Part, Purchased or Assembly definition")
        name = part.name if name is None else name
        valid_name(name)
        if part is self:
            raise ValueError("An assembly cannot contain itself")
        if name in self._instances:
            raise ValueError(f"Duplicate instance {name!r}")
        if any(i.part.name == part.name and i.part is not part for i in self._instances.values()):
            raise ValueError(f"Different part definitions share {part.name!r}; name the variant explicitly")
        if color is not None and (len(color) != 3 or any(not math.isfinite(c) or not 0 <= c <= 1 for c in color)):
            raise ValueError("Component color must have three values between zero and one")
        if group is None:
            group = part.group if isinstance(part, Part) else "Purchased" if isinstance(part, Purchased) else None
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
        """Ground an instance at an explicit local frame.

        Args:
            instance (Instance): Handle returned by this assembly's `add`.
            at (Frame): Placement relative to the assembly origin.

        Returns:
            (Instance): The same handle, for composition in calling code.

        Raises:
            ValueError: The instance is foreign or already has a placement parent.
        """
        self._owned(instance)
        if not isinstance(at, Frame):
            raise TypeError("Fixed placement must be a Frame")
        if self._parented(instance):
            raise ValueError(f"{instance.name} already has a placement")
        self._fixed[instance.name] = at
        return instance

    def export_port(self, name, ref):
        """Expose an internal datum for connecting this assembly as a reusable subsystem.

        Args:
            name (str): Unique public port name.
            ref (PortRef | FeatureRef): Owned instance's port or feature reference.
        """
        valid_name(name)
        self._ref(ref)
        if name in self._ports:
            raise ValueError(f"Duplicate exported port {name!r}")
        self._ports[name] = ref

    def _feature_path(self, ref):
        """Resolve an owned feature reference to its definition-relative leaf path."""
        self._ref(ref)
        if not isinstance(ref, FeatureRef):
            raise TypeError("Use instance.feature(name) as a manufacturing feature")
        instance = ref.instance
        instance.feature(ref.key)  # Validate even a directly constructed reference.
        if isinstance(instance.part, Assembly):
            target = instance.part._exported_features[ref.key]
            return _path(instance.name, instance.part._feature_path(target))
        return instance.name

    def export_feature(self, name, ref):
        """Expose an owned manufacturing feature for a containing assembly's mount.

        Args:
            name (str): Unique public feature name.
            ref (FeatureRef): Owned leaf feature or an owned nested instance's
                exported feature, obtained with `instance.feature(name)`.

        The containing assembly uses `instance.feature(name)` in `connect`,
        `fasten` or `attach`. Re-exporting preserves the original feature and
        shared mount object; its datum follows this occurrence's nested pose.
        Only the selected leaf participates in the resolved fastening contract.
        Export a port separately when only a placement datum is needed.
        """
        valid_name(name)
        if name in self._exported_features:
            raise ValueError(f"Duplicate exported feature {name!r}")
        self._feature_path(ref)
        self._exported_features[name] = ref

    def _component_path(self, component):
        """Validate a local participant and return its definition-relative leaf path."""
        if isinstance(component, Instance):
            self._owned(component)
            if isinstance(component.part, Assembly):
                raise ValueError("Contact components must identify leaf part instances; use an exported component")
            return component.name
        if not isinstance(component, ComponentRef):
            raise TypeError("Use a leaf instance or instance.component(name) as a contact component")
        instance = component.instance
        self._owned(instance)
        if not isinstance(instance.part, Assembly) or component.key not in instance.part._exported_components:
            raise ValueError(f"{instance.name}: unknown exported component {component.key!r}")
        target = instance.part._exported_components[component.key]
        return _path(instance.name, instance.part._component_path(target))

    def export_component(self, name, component):
        """Expose a selected leaf for contact contracts in a containing assembly.

        Args:
            name (str): Unique public component name.
            component (Instance | ComponentRef): Owned leaf instance, or a leaf
                exported by an owned nested assembly instance.

        A containing assembly accesses this leaf through its own installed
        instance's `component(name)`. Re-exporting a nested component preserves
        its scope. Several public names may refer to the same leaf. Whole
        assemblies are rejected; export attachment datums separately with
        `export_port`.
        """
        valid_name(name)
        if name in self._exported_components:
            raise ValueError(f"Duplicate exported component {name!r}")
        self._component_path(component)
        self._exported_components[name] = component

    def connect(self, name, relationship, *, parent=None, child=None, through=None, into=None,
                fastening_name=None, place=True, via=(), description=""):
        """Connect two instance datums and normally place the child from its parent.

        Args:
            name (str): Unique connection name.
            relationship (Rigid | Revolute | Slider | InsertMount | ThreadedMount):
                Motion relationship or shared mounting recipe.
            parent (PortRef | None): Parent datum for a motion relationship.
            child (PortRef | None): Child datum for a motion relationship.
            through (FeatureRef | None): Mount's clearance-side feature on the child.
            into (FeatureRef | None): Same mount object's receiver feature on the parent.
            fastening_name (str | None): Hardware identity; defaults to connection name.
            place (bool): Whether a mount connection assigns child placement.
                Prefer `fasten()` for a secondary fastening on already placed parts.
            via (tuple[FeatureRef, ...]): Middle roles covering the grip continuously.
                Intermediate instances need their own placement.
            description (str): Description of a motion connection.

        Returns:
            (MotionConnection | Connection): Handle usable for poses or tool access.

        Parent and child datums coincide at zero motion. Rotation is in degrees
        about local Z; sliding is in millimetres along local Z. Mount roles must bind
        the exact same mount object, not merely equal recipe values.
        """
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
            if len({self._feature_path(ref) for ref in (through, into, *via)}) != 2 + len(via):
                raise ValueError("A connection needs distinct participating instances")
            if hasattr(relationship, "validate_stack"):
                relationship.validate_stack(through.definition, tuple(ref.definition for ref in via))
            connection = Connection(name, relationship, through, into, fastening_name, place, tuple(via))
        if place and connection.parent.instance is connection.child.instance:
            raise ValueError("A connection needs two distinct instances")
        if place and self._parented(connection.child.instance):
            raise ValueError(f"{connection.child.instance.name} already has a placement")
        self._connections[name] = connection
        return connection

    def fasten(self, name, mount, *, through, into, via=(), fastening_name=None):
        """Add a mount fastening between already placed instances.

        Args:
            name (str): Unique connection name.
            mount (InsertMount | ThreadedMount): Shared recipe used by each role.
            through (FeatureRef): Outermost clearance-side feature.
            into (FeatureRef): Receiving insert or threaded feature.
            via (tuple[FeatureRef, ...]): Intermediate clamped-layer features.
            fastening_name (str | None): Optional distinct hardware identity.

        Returns:
            (Connection): Nonplacing connection. Resolution requires all role datums
                to coincide in the installed assembly.
        """
        return self.connect(name, mount, through=through, into=into, via=via,
                            fastening_name=fastening_name, place=False)

    def attach(self, name, recipe, **features):
        """Bind hardware to existing features without adding a placement edge.

        Args:
            name (str): Unique attachment and fastening name.
            recipe (CaptiveNutFastening | SetScrew): Hardware attachment recipe.
            **features (FeatureRef): `through` and `nut` references for a captive nut, or `thread`
                and `stop` references for a set screw. Each is an owned FeatureRef.

        Returns:
            (Attachment): Attachment record. Features can belong to one physical part.
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
        """Declare contact or clearance between two selected leaf instances.

        Args:
            name (str): Unique interface name.
            left (Instance | ComponentRef): Owned leaf instance or exported leaf
                anchored to an owned nested assembly instance.
            right (Instance | ComponentRef): Second distinct leaf reference.
            kind (str): `contact`, `clearance`, `press_fit`, `threaded`, or `mesh`.
            region (Callable | None): Native overlap-region builder in this assembly's
                coordinates; it transforms with the declaring assembly, not
                independently with either moving participant.
            max_overlap_mm3 (float): Permitted overlap within the bounded region.
            min_clearance_mm (float): Required minimum separation in millimetres.
            max_gap_mm (float | None): Maximum permitted gap; contact defaults to 0.001.
            description (str): Physical intent of the interface.

        Returns:
            (Contact): Local declaration resolved into an Interface for validation.

        Whole nested assemblies are not contact participants. Select their
        exported leaves with `instance.component(name)`; these references follow
        every placement and pose of that particular nested occurrence.
        """
        valid_name(name)
        participants = (self._component_path(left), self._component_path(right))
        if participants[0] == participants[1]:
            raise ValueError("A contact interface needs two distinct leaf instances")
        if name in self._interfaces:
            raise ValueError("Duplicate interface name")
        # Validate the same bounded allowances as the public mechanics contract.
        Interface(name, participants, kind, region, max_overlap_mm3, min_clearance_mm, max_gap_mm, description)
        contact = Contact(name, left, right, kind, region, max_overlap_mm3, min_clearance_mm, max_gap_mm, description)
        self._interfaces[name] = contact
        return contact

    def access(self, name, *, connection, envelope, obstacles, at=Frame(), description=""):
        """Check a complete tool envelope relative to a fastening's receiving datum.

        Args:
            name (str): Unique tool-access name.
            connection (Connection | str): Local mount connection handle or name.
            envelope (Callable): Zero-argument native builder for the complete swept
                tool solid in receiving-datum coordinates.
            obstacles (tuple[Instance, ...]): Explicit local obstacles, including
                whole subassemblies when appropriate.
            at (Frame): Additional placement relative to the receiving datum.
            description (str): Tool and operation being checked.

        Returns:
            (ToolAccess): Declaration that follows the fastening in every pose.

        Only the supplied envelope and obstacle set are checked. The library does
        not infer a tool path or a complete assembly sequence.
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
        """Add a straight cylindrical driver probe at every screw seat.

        Args:
            name (str): Unique tool-access name.
            connection (Connection | str): Local mount connection handle or name.
            diameter (float): Positive probe diameter in millimetres.
            length (float): Positive outward probe length in millimetres.
            obstacles (tuple[Instance, ...]): Explicit instances to check for obstruction.

        Returns:
            (ToolAccess): Access declaration extending from the screw seats along
                the receiving datum's outward +Z direction.
        """
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
        """Derive one joint coordinate as `driven = driver * ratio + offset`.

        Args:
            name (str): Unique coupling name.
            driver (str | MotionConnection): Driving joint handle or scoped path.
            driven (str | MotionConnection): Joint whose coordinate is derived.
            ratio (float): Finite multiplier; units follow the two joint coordinates.
            offset (float): Finite offset in the driven joint's units.

        Returns:
            (Coupling): Coupling record. A joint can have only one driver.
        """
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
        """Register a named set of scalar joint positions without changing the default pose.

        Args:
            name (str): Unique pose name.
            positions (dict): Motion connection handles or scoped joint paths mapped
                to values in degrees for revolute joints and millimetres for sliders.

        Returns:
            (Assembly): This assembly, allowing chained definitions.
        """
        valid_name(name)
        if name in self._poses:
            raise ValueError("Duplicate pose name")
        values = self._normalize_pose(positions)
        self._positions(values)
        self._poses[name] = values
        return self

    def pose(self, positions):
        """Freeze this definition and resolve a reusable pose selection.

        Args:
            positions (dict | str): Position mapping or previously registered pose name.

        Returns:
            (AssemblyPose): Snapshot whose output methods use the selected positions.
                Later changes to the assembly graph do not alter the snapshot.
        """
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
        definition = ref.instance.part
        if isinstance(definition, Assembly):
            inner_prefix = _path(prefix, ref.instance.name)
            exports = definition._exported_features if isinstance(ref, FeatureRef) else definition._ports
            inner = exports[ref.key]
            locations = definition._locations(inner_prefix, positions)
            return locations[inner.instance.name] * definition._frame(inner, inner_prefix, positions)
        if isinstance(ref, FeatureRef):
            return ref.definition.at.location
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

    def locations(self, *, at=Frame(), pose=None, names="immediate"):
        """Resolve instance locations without building geometry.

        Args:
            at (Frame): Placement of this assembly in its caller's coordinates.
            pose (dict | str | None): Joint positions, named pose, or defaults.
            names (str): `immediate` for this assembly's direct instances, or
                `path` for every leaf keyed by its relative assembly path.

        Returns:
            (dict[str, cq.Location]): Instance names or leaf paths mapped to native locations.
        """
        if names == "path":
            return {path: location for path, (_, location) in self._resolve(at=at, pose=pose).leaves.items()}
        if names != "immediate":
            raise ValueError("locations expects names immediate/path")
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
        """Resolve installed fastenings from this graph and its selected pose.

        Args:
            at (Frame): Placement of this assembly.
            pose (dict | str | None): Joint positions or named pose.

        Returns:
            (tuple[Fastening, ...]): Stable mechanical declarations in world coordinates.
        """
        return self._resolve(at=at, pose=pose).fastenings()

    def motion_graph(self, *, at=Frame(), pose=None):
        """Describe geometry-free viewer transforms for an immutable pose.

        The graph contains column-major millimetre matrices, scalar joints,
        couplings and component targets. It never builds or changes part geometry.
        """
        from .kinematics import motion_graph
        return motion_graph(self._resolve(at=at, pose=pose))

    def joints(self, *, at=Frame(), pose=None):
        """Resolve installed joints from this graph and its selected pose.

        Args:
            at (Frame): Placement of this assembly.
            pose (dict | str | None): Joint positions or named pose.

        Returns:
            (tuple[Joint, ...]): Stable mechanical declarations in world coordinates.
        """
        return self._resolve(at=at, pose=pose).joints()

    def interfaces(self, *, at=Frame(), pose=None):
        """Resolve installed interfaces from this graph and its selected pose.

        Args:
            at (Frame): Placement of this assembly.
            pose (dict | str | None): Joint positions or named pose.

        Returns:
            (tuple[Interface, ...]): Stable mechanical declarations in world coordinates.
        """
        return self._resolve(at=at, pose=pose).interfaces()

    def components(self, *, at=Frame(), pose=None, include_hardware=False, kind=None):
        """Build flattened installed Components from the resolved graph.

        Args:
            at (Frame): Placement of the assembly.
            pose (dict | str | None): Joint positions or named pose.
            include_hardware (bool): Include generated fastening hardware.
            kind (str | None): Restrict leaves to `manufactured` or `purchased`.

        Returns:
            (list[cadkit._project.Component]): Located Components in world millimetres.
        """
        return self._resolve(at=at, pose=pose).components(include_hardware=include_hardware, kind=kind)

    def models(self, *, kind=None, names="leaf", at=Frame(), pose=None):
        """Build models keyed by instance names or relative paths.

        Args:
            kind (str | None): `manufactured`, `purchased`, or all definitions.
            names (str): `leaf` for unique leaf names, or `path` for scoped identities.
            at (Frame): Placement of the assembly.
            pose (dict | str | None): Joint positions or named pose.

        Returns:
            (dict[str, cq.Workplane | Mesh]): Native models as Workplanes and
                explicit meshes as Mesh objects. Generated hardware is excluded.

        Raises:
            ValueError: Leaf names are ambiguous; request `names="path"` instead.
        """
        if kind not in {None, "manufactured", "purchased"} or names not in {"leaf", "path"}:
            raise ValueError("models expects kind manufactured/purchased and names leaf/path")
        result = {}
        for path, component in self._resolve(at=at, pose=pose)._native_components(kind=kind).items():
            key = component.name if names == "leaf" else path
            if key in result:
                raise ValueError(f"Ambiguous leaf name {key!r}; request names='path'")
            result[key] = component.model if isinstance(component.model, Mesh) else cq.Workplane(obj=component.model)
        return result

    def purchased_bom(self):
        """Aggregate quantities of purchased definitions independently of pose.

        Returns:
            (tuple[dict, ...]): Rows keyed by definition name, supplier and SKU,
                containing total quantity and relative instance paths.

        Each instance contributes its definition's quantity. Fastener hardware is
        counted separately by the hardware BOM.
        """
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
        """Freeze a subsystem and expose its resolved geometry and mechanics.

        Args:
            at (Frame): Installed placement of this subsystem.
            pose (dict | str | None): Selected positions or named pose.

        Returns:
            (Embedding): Adapter exposing mutually consistent components, Parts,
                joints, interfaces, fastenings and purchased quantities.

        Raises:
            ValueError: Leaf names are ambiguous; use a nested Assembly instead.
        """
        values = self._normalize_pose(pose)
        result = Embedding(self._snapshot(), at, values)
        result._reference_map()
        return result

    def as_assembly(self, *, at=Frame(), pose=None, include_hardware=True, kind=None):
        """Build a placed cadkit._project.Assembly hierarchy.

        Args:
            at (Frame): Placement of this assembly.
            pose (dict | str | None): Joint positions or named pose.
            include_hardware (bool): Include located fastening hardware.
            kind (str | None): `manufactured`, `purchased`, or all leaves.

        Returns:
            (cadkit._project.Assembly): Hierarchy with native geometry, names, and colors.
        """
        return self._resolve(at=at, pose=pose).as_assembly(include_hardware=include_hardware, kind=kind)

    def as_cq_assembly(self, *, at=Frame(), pose=None, include_hardware=True, kind=None):
        """Build a placed cq.Assembly hierarchy.

        Args:
            at (Frame): Placement of this assembly.
            pose (dict | str | None): Joint positions or named pose.
            include_hardware (bool): Include located fastening hardware.
            kind (str | None): `manufactured`, `purchased`, or all leaves.

        Returns:
            (cq.Assembly): Hierarchy with native geometry, names, and colors.
        """
        def convert(tree):
            result = cq.Assembly(name=tree.name)
            for child in tree.children:
                if isinstance(child, PlacedAssembly):
                    result.add(convert(child))
                else:
                    if isinstance(child.model, Mesh):
                        raise ValueError("A CadQuery assembly cannot include Mesh bodies; use the project assembly exporter for a native STEP and mesh omission manifest")
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
                "exported_features": {name: {"instance": ref.instance.name, "feature": ref.key,
                                              "component": self._feature_path(ref)}
                                      for name, ref in self._exported_features.items()},
                "exported_components": {name: self._component_path(component)
                                        for name, component in self._exported_components.items()},
                "connections": {name: self._describe_connection(c) for name, c in self._connections.items()},
                "attachments": {name: {"recipe":a.recipe.describe(),
                    "features":{key:{"instance":ref.instance.name,"feature":ref.key} for key,ref in a.features.items()}}
                    for name,a in self._attachments.items()},
                "couplings": {name: {"driver": c.driver, "driven": c.driven, "ratio": c.ratio, "offset": c.offset}
                              for name, c in self._couplings.items()},
                "interfaces": {name: {"left": self._component_path(c.left), "right": self._component_path(c.right), "kind": c.kind,
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
        frozen._variant_choices = dict(self._variant_choices)
        replacements = {}
        for name, instance in self._instances.items():
            definition = instance.part._snapshot((*ancestors, id(self))) if isinstance(instance.part, Assembly) else instance.part
            replacements[id(instance)] = replace(instance, part=definition, _owner=frozen)
            frozen._instances[name] = replacements[id(instance)]
        def ref(value):
            return replace(value, instance=replacements[id(value.instance)])
        def component(value):
            return ref(value) if isinstance(value, ComponentRef) else replacements[id(value)]
        frozen._fixed = dict(self._fixed)
        frozen._ports = {key: ref(value) for key, value in self._ports.items()}
        frozen._exported_features = {key: ref(value) for key, value in self._exported_features.items()}
        frozen._exported_components = {key: component(value) for key, value in self._exported_components.items()}
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
        frozen._interfaces = {name: replace(c, left=component(c.left), right=component(c.right))
                              for name, c in self._interfaces.items()}
        frozen._access = {name: replace(value, obstacles=tuple(replacements[id(i)] for i in value.obstacles))
                          for name, value in self._access.items()}
        return frozen

    def as_project(self, *, parameters=(), checks=(), description="", pose=None,
                   extra_parts=(), quantities=None, joints=(), interfaces=(), fastenings=()):
        """Freeze this assembly into an inspectable, exportable Project.

        Args:
            parameters (tuple): Discoverable Parameter metadata.
            checks (tuple): Explicit Check definitions.
            description (str): Project description.
            pose (dict | str | None): Joint positions or named pose for the default view.
            extra_parts (tuple[Part, ...]): Additional manufacturing definitions,
                such as uninstalled coupons or variants. An installed definition
                may also appear here; the same object is counted once.
            quantities (dict[str, int] | None): Positive manufacturing counts by
                part name. Defaults to installed instance counts, or one for an
                uninstalled extra. Counts do not depend on the selected pose.
            joints (tuple): Additional installed mechanical declarations.
            interfaces (tuple): Additional installed contact/clearance contracts.
            fastenings (tuple): Additional installed hardware stacks. Explicit
                installed contracts require a static assembly; use feature-bound
                connections and attachments when hardware must follow motion.

        Returns:
            (cadkit.Project): Snapshot with manufacturing inventory, installed tree,
                mechanics, and named poses. Repeated manufactured definitions contribute
                instance quantities; purchased components stay outside the print registry.
        """
        values = self._normalize_pose(pose)
        return Project(self._snapshot(), values, parameters=parameters, checks=checks,
                             description=description, extra_parts=extra_parts, quantities=quantities,
                             joints=joints, interfaces=interfaces, fastenings=fastenings)


@dataclass(frozen=True)
class AssemblyPose:
    """Immutable pose selection over a snapshot of an authoring graph.

    Obtain this with `assembly.pose(positions)`. Its output methods forward to
    the matching Assembly method with the selected pose. Pass placement and
    filtering options as usual; supplying another `pose` option is rejected.
    """
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

    def motion_graph(self, **options):
        return self._call("motion_graph", **options)

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
                components = tuple(dict.fromkeys(self._id(_path(prefix, assembly._feature_path(ref)))
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
                options = {"through": self._id(_path(prefix, assembly._feature_path(connection.through))),
                           "into": self._id(_path(prefix, assembly._feature_path(connection.into))),
                           "frame": frame, "clearance": connection.through.definition,
                           "joint": _path(prefix, connection.name)}
                if connection.via:
                    options["via"] = tuple(self._id(_path(prefix, assembly._feature_path(ref))) for ref in connection.via)
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
                    parent_refs = (self._id(_path(prefix, assembly._feature_path(connection.into))),)
                    child_refs = (self._id(_path(prefix, assembly._feature_path(connection.through))),)
                    middle_refs = tuple(self._id(_path(prefix, assembly._feature_path(ref))) for ref in connection.via)
                    refs = tuple(dict.fromkeys((*parent_refs, *child_refs, *middle_refs)))
                    result.append(Joint(_path(prefix, name), refs, origin=frame.origin, axis=frame.z,
                                        fastenings=(_path(prefix, connection.fastening_name),),
                                        parent_components=parent_refs,
                                        child_components=child_refs))
                else:
                    result.append(Joint(_path(prefix, name), refs, kind=connection.motion.kind,
                                        origin=frame.origin, axis=frame.z,
                                        limits=getattr(connection.motion, "limits", None),
                                        position=self.positions.get(_path(prefix, name), 0), description=connection.description,
                                        parent_components=self._refs(prefix, connection.parent.instance),
                                        child_components=self._refs(prefix, connection.child.instance)))
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
                participants = tuple(self._id(_path(prefix, assembly._component_path(component)))
                                     for component in (contact.left, contact.right))
                result.append(Interface(_path(prefix, name), participants,
                                        contact.kind, region, contact.max_overlap_mm3, contact.min_clearance_mm,
                                        contact.max_gap_mm, contact.description))
            for connection in assembly._connections.values():
                if isinstance(connection, Connection) and hasattr(connection.mount, "interfaces"):
                    result.extend(connection.mount.interfaces(
                        fastenings[_path(prefix, connection.fastening_name)], receiver=connection.into.definition,
                        hardware_root=hardware_root,
                        receiver_representation=getattr(self.leaves[_path(prefix, assembly._feature_path(connection.into))][0].part, "representation", None)))
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
                    if isinstance(child, PlacedAssembly):
                        yield from visit(child, path)
                    else:
                        yield replace(child, name=_path("Hardware", path))
            if hardware:
                result.extend(visit(hardware))
        return result

    def as_assembly(self, *, include_hardware=True, kind=None):
        from .kinematics import motion_graph
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
            return PlacedAssembly(assembly.name, tuple(children))
        tree = visit(self.definition, "")
        fastenings, joints, interfaces = self.fastenings(), self.joints(), self.interfaces()
        hardware = hardware_assembly(fastenings) if include_hardware else None
        return _ResolvedAssembly(tree.name, tree.children + ((hardware,) if hardware else ()), tree.description,
                                 motion_graph(self), joints, interfaces, fastenings)


@dataclass(frozen=True)
class _ResolvedAssembly(PlacedAssembly):
    _motion: dict = field(default_factory=dict, repr=False, compare=False)
    _joints: tuple = field(default=(), repr=False, compare=False)
    _interfaces: tuple = field(default=(), repr=False, compare=False)
    _fastenings: tuple = field(default=(), repr=False, compare=False)


class Project(ProjectRecord):
    """An assembly snapshot shared by the CLI, desktop and exporters.

    Create one with `Assembly.as_project()`. Its manufacturing inventory contains
    one fabrication record per part definition, with quantities separate from
    display visibility and pose. Geometry builders remain lazy.
    """
    def __init__(self, definition, pose, *, parameters=(), checks=(), description="",
                 extra_parts=(), quantities=None, joints=(), interfaces=(), fastenings=()):
        self._definition = definition
        self._default_pose = dict(pose)
        self._extra_joints = tuple(joints)
        self._extra_interfaces = tuple(interfaces)
        self._extra_fastenings = tuple(fastenings)
        if (self._extra_joints or self._extra_interfaces or self._extra_fastenings) and definition._motion_index():
            raise ValueError("Explicit installed contracts require a static assembly; bind moving mechanics to features")
        resolution = definition._resolve(pose=pose)
        counts = Counter(id(i.part) for i, _ in resolution.leaves.values() if isinstance(i.part, Part))
        identities = {}
        def register(part):
            if not isinstance(part, Part):
                raise TypeError("extra_parts must contain Part definitions")
            if part.name in identities and identities[part.name] is not part:
                raise ValueError(f"Different part definitions share {part.name!r}; name the variant explicitly")
            identities[part.name] = part
        for instance, _ in resolution.leaves.values():
            if isinstance(instance.part, Part):
                register(instance.part)
        for part in extra_parts:
            register(part)
        quantities = dict(quantities or {})
        unknown = quantities.keys() - identities.keys()
        if unknown:
            raise ValueError(f"Unknown manufacturing quantity parts: {', '.join(sorted(unknown))}")
        if any(type(value) is not int or value < 1 for value in quantities.values()):
            raise ValueError("Manufacturing quantities must be positive integers")
        parts = {name: part.as_part(quantity=quantities.get(name, counts[id(part)] or 1))
                 for name, part in identities.items()}
        super().__init__(definition.name, tuple(parts.values()), self._components,
                         parameters=tuple(parameters), checks=tuple(checks), description=description,
                         views={name: (lambda _name=name, **options: self._components(pose=_name, **options)) for name in definition._poses},
                         assembly=self._assembly,
                         joints=resolution.joints() + self._extra_joints,
                         interfaces=resolution.interfaces() + self._extra_interfaces,
                         fastenings=resolution.fastenings() + self._extra_fastenings)

    def _options(self, view=None, **options):
        pose = options.pop("pose", view if view is not None else self._default_pose)
        if view is not None and view not in self._definition._poses:
            raise ValueError(f"Unknown view: {view}")
        return {"pose": pose, **options}

    def _components(self, **options):
        options["include_hardware"] = False
        return self.get_components(**options)

    def _assembly(self, **options):
        options["include_hardware"] = False
        return self.get_assembly(**options)

    def get_components(self, view=None, **options):
        """Build installed components with names scoped to their assembly paths."""
        def visit(tree, prefix=""):
            for child in tree.children:
                path = _path(prefix, child.name)
                if isinstance(child, PlacedAssembly):
                    yield from visit(child, path)
                else:
                    yield replace(child, name=path)
        return list(visit(self.get_assembly(view, **options)))

    def get_assembly(self, view=None, **options):
        """Build the installed hierarchy and matching mechanics for a named pose.

        Args:
            view (str | None): Named pose, or the project's default pose.
            **options (object): `include_hardware`, `pose` and `kind` selection options.
        """
        options = self._options(view, **options)
        include_hardware = options.pop("include_hardware", True)
        tree = self._definition.as_assembly(include_hardware=False, **options)
        fastenings = tree._fastenings + self._extra_fastenings
        hardware = hardware_assembly(fastenings) if include_hardware else None
        if hardware and any(child.name == hardware.name for child in tree.children):
            raise ValueError("Assembly instance name 'Hardware' conflicts with generated hardware")
        return replace(tree, children=tree.children + ((hardware,) if hardware else ()),
                       _joints=tree._joints + self._extra_joints,
                       _interfaces=tree._interfaces + self._extra_interfaces,
                       _fastenings=fastenings)

    def _mechanics(self, assembly):
        if isinstance(assembly, _ResolvedAssembly):
            return SimpleNamespace(joints=assembly._joints, interfaces=assembly._interfaces, fastenings=assembly._fastenings)
        return self

    def mechanical_descriptions(self, assembly=None):
        from ..mechanics import mechanical_descriptions
        result = mechanical_descriptions(self._mechanics(assembly), assembly)
        if isinstance(assembly, _ResolvedAssembly):
            from copy import deepcopy
            from ..mechanics import component_index
            graph = deepcopy(assembly._motion)
            index = component_index(assembly)
            graph["targets"] = {key: value for key, value in graph["targets"].items() if key in index}
            for key, component in index.items():
                target = graph["hardware"].get(component.metadata.get("fastening_id"))
                if target:
                    graph["targets"][key] = target
            for joint in graph["joints"]:
                joint["moving_components"] = [key for key, target in graph["targets"].items()
                                                if joint["id"] in target["joints"]]
            for joint in result["joints"]:
                joint["moving_components"] = next((j["moving_components"] for j in graph["joints"]
                                                    if j["id"] == joint["id"]), [])
            result["motion"] = graph
        return result

    def validate_mechanics(self, assembly=None, *, scan_collisions=True, tolerance_mm3=1e-5):
        from ..mechanics import validate_mechanics
        assembly = assembly if assembly is not None else self.get_assembly()
        return validate_mechanics(self._mechanics(assembly), assembly, scan_collisions=scan_collisions, tolerance_mm3=tolerance_mm3)

    def describe(self):
        return {**super().describe(), "design": self._definition.describe(), "pose": dict(self._default_pose),
                "purchased_bom": self._definition.purchased_bom()}


@dataclass(frozen=True)
class Embedding:
    """Frozen subsystem output with consistently scoped geometry and mechanics.

    Obtain this with `assembly.embed()`. Methods expose components, manufacturing
    parts, and installed mechanics with consistent references. Leaf names must
    be unique. Use its methods together rather than rebuilding transforms in
    the containing project.
    """
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
        return tuple(replace(item, components=tuple(refs[ref] for ref in item.components),
                             parent_components=tuple(refs[ref] for ref in item.parent_components),
                             child_components=tuple(refs[ref] for ref in item.child_components)) for item in self._resolve().joints())

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
