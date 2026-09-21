"""Connection recipes own matched manufacturing roles and hardware stacks.

Role frames share a mating datum: +Z points from the receiving part toward the
clamped part. Each role remains explicitly owned by its part definition.
"""
from dataclasses import dataclass
from typing import ClassVar
import math
import cadquery as cq
from ..fasteners import FastenerSpec, FastenerSite, HardwareItem
from ..mechanics import Fastening
from .frames import Frame, positive
from .manufacturing import Hole, _cut, _points, _describe_pattern

_OVERSHOOT = 0.1


@dataclass(frozen=True)
class Counterbore:
    """Dimensions of a cylindrical head recess used by a hole or mount role.

    Args:
        diameter: Finished recess diameter in millimetres.
        depth: Recess depth below the entry face in millimetres.
        entry_extension: Additional cutter extension outside the entry face in
            millimetres. It does not increase the nominal recess depth.
    """
    diameter: float
    depth: float
    entry_extension: float = 0

    def __post_init__(self):
        positive(self.diameter, "Counterbore diameter")
        positive(self.depth, "Counterbore depth")
        if not math.isfinite(self.entry_extension) or self.entry_extension < 0:
            raise ValueError("Counterbore entry extension must be finite and nonnegative")


@dataclass(frozen=True)
class InsertPocket:
    """Explicit receiving geometry for a heat-set insert.

    Args:
        diameter: Finished pocket diameter in millimetres.
        depth: Pocket depth in millimetres.
        insert_outer_diameter: Optional measured insert outer diameter in
            millimetres, used to bound installed-fit validation.

    A catalogue thread size does not determine printed pocket fit. Choose
    dimensions using the supplier's guidance and a process-specific coupon.
    """
    diameter: float
    depth: float
    insert_outer_diameter: float | None = None

    def __post_init__(self):
        positive(self.diameter, "Pocket diameter")
        positive(self.depth, "Pocket depth")
        if self.insert_outer_diameter is not None:
            positive(self.insert_outer_diameter, "Insert outer diameter")

    def feature(self, *, at=Frame(), pattern=None, insert=None):
        """Create a standalone owned feature for this pocket.

        Args:
            at (Frame): Entry frame, +Z into receiving material, matching Hole.
            pattern (PointPattern | PolarPattern | None): Local XY sites.
            insert (FastenerSpec | None): Heat-set insert specification with explicit
                length. When provided, metadata includes an installation operation.

        Returns:
            (InsertPocketFeature): Material-removing feature for a Part definition.
        """
        return InsertPocketFeature(self, at, pattern, insert)


@dataclass(frozen=True)
class InsertPocketFeature:
    pocket: InsertPocket
    at: Frame = Frame()
    pattern: object = None
    insert: FastenerSpec | None = None

    def __post_init__(self):
        if self.insert is not None:
            if self.insert.kind != "heat_set_insert" or self.insert.length_mm is None:
                raise ValueError("An insert pocket needs a heat-set insert with an explicit length")
            if self.pocket.depth < self.insert.length_mm:
                raise ValueError("Pocket must accommodate the insert length")

    def apply(self, body):
        return Hole(self.pocket.diameter, self.pocket.depth, self.at, self.pattern).apply(body)

    def describe(self):
        return {"kind": "insert-pocket", "diameter": self.pocket.diameter, "depth": self.pocket.depth,
                "frame": self.at.describe(), "pattern": _describe_pattern(self.pattern),
                "insert": self.insert.describe() if self.insert else None,
                "insert_outer_diameter": self.pocket.insert_outer_diameter,
                "operations": ([{"kind": "install-insert", "quantity": len(_points(self.pattern)),
                                "spec_id": self.insert.id}] if self.insert else [])}


@dataclass(frozen=True)
class InsertBoss(InsertPocketFeature):
    """Add attached cylindrical reinforcement and cut an insert pocket into it.

    Args:
        pocket: Explicit InsertPocket dimensions.
        at: Boss base and pocket entry frame, +Z into the boss.
        pattern: Local XY sites or `None`.
        insert: Optional heat-set insert specification with explicit length.
        outer_diameter: Boss diameter in millimetres, larger than the pocket.
        depth: Boss height in millimetres, at least the pocket depth.

    Each boss must join the existing body. Pocket entry conventions match
    `InsertPocket.feature()`, rather than the mating datum used by InsertMount.
    """
    outer_diameter: float = 0
    depth: float = 0

    def __post_init__(self):
        super().__post_init__()
        positive(self.outer_diameter, "Boss outer diameter")
        positive(self.depth, "Boss depth")
        if self.outer_diameter <= self.pocket.diameter:
            raise ValueError("Boss must leave a positive wall around its pocket")
        if self.depth < self.pocket.depth:
            raise ValueError("Boss depth must accommodate its pocket")

    def apply(self, body):
        bosses = [cq.Solid.makeCylinder(self.outer_diameter/2, self.depth, (x,y,0)).moved(self.at.location)
                  for x,y in _points(self.pattern)]
        result = body.fuse(*bosses).clean()
        if not result.isValid() or len(result.Solids()) > len(body.Solids()):
            raise ValueError("Insert bosses must join the part body")
        return super().apply(result)

    def describe(self):
        return {**super().describe(), "kind": "insert-boss", "outer_diameter": self.outer_diameter,
                "boss_depth": self.depth}


class _Mount:
    def clearance_side(self, *, at=Frame(), thickness, head_recess=None,
                       offset=0, slot_length=None, slot_angle=0, slot_radial=False, supplied=False, drill_offsets=None):
        """Create the outermost clamped role on which the screw head seats.

        Args:
            at (Frame): Shared mating datum, +Z toward the clamped layers.
            thickness (float): This layer's thickness in millimetres.
            head_recess (Counterbore | None): Optional head recess; must leave a seat.
            offset (float): Layer start above the mating datum, in millimetres.
            slot_length (float | None): Overall milled-slot length in millimetres.
            slot_angle (float): Slot orientation in local XY degrees.
            slot_radial (bool): Orient each slot along its radius from the pattern origin.
            supplied (bool): Describe already supplied geometry without cutting it.
            drill_offsets (tuple | None): Local XY drill offsets at every fastening
                site. Mutually exclusive with `slot_length`; must cover the nominal axis.

        Returns:
            (MountFeature): Owned clearance role. Seat Z is offset plus thickness
                minus recess depth, determining screw grip.
        """
        return MountFeature(self, "clearance", at, thickness, head_recess, offset,
                            slot_length, slot_angle, slot_radial, supplied, drill_offsets)

    def middle_side(self, *, at=Frame(), thickness, offset=0, head_recess=None, supplied=False):
        """Create an intermediate clamped layer sharing the same mating datum.

        Args:
            at (Frame): Datum shared by every role.
            thickness (float): Layer thickness in millimetres.
            offset (float): Layer start above the receiver, in millimetres.
            head_recess (Counterbore | None): Optional recess at this layer's outer face.
            supplied (bool): Describe supplied geometry without modifying it.

        Returns:
            (MountFeature): Middle role to pass through `via=` in a connection.

        Intermediate and outer layers must cover the grip continuously, without
        gaps or overlaps. Every intermediate instance must also be placed.
        """
        return MountFeature(self, "middle", at, thickness, head_recess, offset=offset, supplied=supplied)

    def validate_stack(self, clearance, intermediates=()):
        layers = sorted(((f.offset, f.seat, f) for f in (*intermediates, clearance)),
                        key=lambda item: item[0])
        end = 0.0
        for start, stop, feature in layers:
            if feature.mount is not self:
                raise ValueError("Stack layers must belong to the same mount")
            if abs(start-end) > 1e-6:
                raise ValueError("Stack layers must cover the grip continuously without gaps or overlaps")
            end = stop
        if layers[-1][2] is not clearance:
            raise ValueError("The screw head must seat on the outermost clearance role")

    def interfaces(self, fastening, *, receiver, hardware_root, receiver_representation=None):
        """Derive bounded installed-fit contracts from this recipe's geometry."""
        from .mount_interfaces import mount_interfaces
        return mount_interfaces(self, fastening, receiver=receiver, hardware_root=hardware_root,
                                receiver_representation=receiver_representation)

    def _sites(self, frame, clearance):
        sites = []
        for i, (x, y) in enumerate(self.pattern.points):
            site = Frame.from_location(frame.location * cq.Location((x, y, clearance.seat)))
            sites.append(FastenerSite(str(i+1), site.origin, tuple(-v for v in site.z), x_axis=site.x))
        return tuple(sites)


@dataclass(frozen=True)
class InsertMount(_Mount):
    """One shared pattern, screw, and insert recipe for matching part features.

    Args:
        pattern: PointPattern or PolarPattern shared by every role.
        screw: Headed screw specification, including its length.
        insert: Matching heat-set insert specification with explicit length.
        clearance_diameter: Finished screw clearance diameter in millimetres.
        pocket: Explicit receiving pocket dimensions.
        minimum_engagement: Required screw engagement in millimetres.

    A mount frame is a mating datum: +Z points out of the receiver toward the
    clamped parts. Insert pockets cut into negative local Z; clearance layers
    occupy positive Z. Bind roles from the same mount object when connecting.
    """
    pattern: object
    screw: FastenerSpec
    insert: FastenerSpec
    clearance_diameter: float
    pocket: InsertPocket
    minimum_engagement: float
    receiver_role: ClassVar[str] = "insert"

    def __post_init__(self):
        if not self.screw.kind.endswith("screw") or self.insert.kind != "heat_set_insert":
            raise ValueError("InsertMount needs a screw and a heat-set insert")
        if self.screw.size != self.insert.size:
            raise ValueError("Screw and insert threads must match")
        positive(self.clearance_diameter, "Clearance diameter")
        positive(self.minimum_engagement, "Minimum engagement")
        if self.insert.length_mm is None:
            raise ValueError("Insert length must be specified")
        positive(self.insert.length_mm, "Insert length")
        if self.pocket.depth < self.insert.length_mm:
            raise ValueError("Pocket must accommodate the insert length")

    def insert_side(self, *, at=Frame(), supplied=False):
        """Create the receiving insert role owned by a Part or Purchased definition.

        Args:
            at (Frame): Mating datum, +Z out of the receiver.
            supplied (bool): Describe existing supplier geometry without cutting it.

        Returns:
            (MountFeature): Insert-side feature.
        """
        return MountFeature(self, "insert", at, supplied=supplied)

    def describe(self):
        return {"kind": "insert-mount", "pattern": self.pattern.describe(),
                "screw": self.screw.describe(), "insert": self.insert.describe(),
                "clearance_diameter": self.clearance_diameter,
                "pocket": {"diameter": self.pocket.diameter, "depth": self.pocket.depth,
                           "insert_outer_diameter": self.pocket.insert_outer_diameter},
                "minimum_engagement": self.minimum_engagement}

    def fastening(self, name, *, through, into, frame, clearance, joint=None, via=()):
        grip = clearance.seat
        return Fastening(name, (through, *via, into), sites=self._sites(frame, clearance), joint=joint, kind="insert",
                         grip_mm=grip, thread_depth_mm=self.insert.length_mm,
                         hole_depth_mm=grip+self.pocket.depth,
                         min_engagement_mm=self.minimum_engagement,
                         hardware=(HardwareItem("screw", self.screw), HardwareItem("insert", self.insert, grip)))


@dataclass(frozen=True)
class ThreadedMount(_Mount):
    """Shared screw connection to a manufactured pilot or an existing supplied thread.

    Args:
        pattern: PointPattern or PolarPattern of fastening axes.
        screw: Screw specification including length.
        clearance_diameter: Finished clearance diameter in millimetres.
        pilot_diameter: Manufactured pilot diameter in millimetres.
        thread_depth: Available thread depth in millimetres.
        hole_depth: Pilot or receiving-hole depth in millimetres.
        minimum_engagement: Required engagement in millimetres, if known.
        method: `tap-after-printing`, `tap-after-machining`, or `self-tapping`.

    A generated receiving role requires explicit pilot diameter, thread depth,
    and hole depth. A `supplied=True` role can leave unknown supplier values as
    `None`; those checks remain unverified. +Z points outward from the receiver.
    """
    pattern: object
    screw: FastenerSpec
    clearance_diameter: float
    pilot_diameter: float | None = None
    thread_depth: float | None = None
    hole_depth: float | None = None
    minimum_engagement: float | None = None
    method: str = "tap-after-printing"
    receiver_role: ClassVar[str] = "threaded"

    def __post_init__(self):
        if not self.screw.kind.endswith("screw"):
            raise ValueError("ThreadedMount requires a screw")
        positive(self.clearance_diameter, "Clearance diameter")
        for attr in ("pilot_diameter", "thread_depth", "hole_depth", "minimum_engagement"):
            value = getattr(self, attr)
            if value is not None:
                positive(value, attr)
        if self.thread_depth is not None and self.hole_depth is not None and self.thread_depth > self.hole_depth:
            raise ValueError("Thread depth cannot exceed pilot hole depth")
        if self.method not in {"tap-after-printing", "tap-after-machining", "self-tapping"}:
            raise ValueError("Threaded mount needs an explicit supported manufacturing method")

    def threaded_side(self, *, at=Frame(), supplied=False):
        """Create the receiving thread role.

        Args:
            at (Frame): Mating datum, +Z out of receiving material.
            supplied (bool): Use an existing supplier thread without cutting a pilot.

        Returns:
            (MountFeature): Threaded-side feature with any required tapping operation.
        """
        return MountFeature(self, "threaded", at, supplied=supplied)

    def describe(self):
        return {"kind": "threaded-mount", "pattern": self.pattern.describe(),
                "screw": self.screw.describe(), "clearance_diameter": self.clearance_diameter,
                "pilot_diameter": self.pilot_diameter, "thread_depth": self.thread_depth,
                "hole_depth": self.hole_depth, "minimum_engagement": self.minimum_engagement,
                "method": self.method}

    def fastening(self, name, *, through, into, frame, clearance, joint=None, via=()):
        grip = clearance.seat
        return Fastening(name, (through, *via, into), sites=self._sites(frame, clearance), joint=joint, kind="tapped",
                         grip_mm=grip, thread_depth_mm=self.thread_depth,
                         hole_depth_mm=grip+self.hole_depth if self.hole_depth is not None else None,
                         min_engagement_mm=self.minimum_engagement, thread_size=self.screw.size,
                         hardware=(HardwareItem("screw", self.screw),))


@dataclass(frozen=True)
class MountFeature:
    """An owned side of a shared mount, returned by the mount's role factories.

    Prefer `clearance_side`, `middle_side`, `insert_side`, or `threaded_side`
    instead of constructing this record. `apply` performs its explicit cuts;
    `supplied=True` preserves the body. `describe` includes the mounting recipe,
    frame, layer dimensions, and postprocessing operations.
    """
    mount: object
    role: str
    at: Frame = Frame()
    thickness: float | None = None
    head_recess: Counterbore | None = None
    offset: float = 0
    slot_length: float | None = None
    slot_angle: float = 0
    slot_radial: bool = False
    supplied: bool = False
    drill_offsets: tuple | None = None

    def __post_init__(self):
        if self.role not in {self.mount.receiver_role, "clearance", "middle"}:
            raise ValueError("Unknown mount role")
        if not math.isfinite(self.offset) or self.offset < 0:
            raise ValueError("Stack offset must be finite and nonnegative")
        if not math.isfinite(self.slot_angle):
            raise ValueError("Slot angle must be finite")
        if self.drill_offsets is not None:
            offsets = tuple(tuple(float(v) for v in xy) for xy in self.drill_offsets)
            if not offsets or any(len(xy) != 2 or not all(math.isfinite(v) for v in xy) for xy in offsets):
                raise ValueError("Drilled profile needs finite XY offsets")
            if len(set(offsets)) != len(offsets):
                raise ValueError("Drilled profile offsets must be distinct")
            if self.slot_length is not None:
                raise ValueError("Choose a milled slot or a drilled profile, not both")
            if not any(math.hypot(x,y) < self.mount.clearance_diameter/2 for x,y in offsets):
                raise ValueError("Drilled profile must include the nominal fastening axis")
            object.__setattr__(self, "drill_offsets", offsets)
        if self.role in {"clearance", "middle"}:
            if self.thickness is None:
                raise ValueError("Clearance side needs a thickness")
            positive(self.thickness, "Thickness")
            if self.head_recess is not None:
                if self.head_recess.depth >= self.thickness:
                    raise ValueError("Counterbore must leave a positive screw seat")
                if self.head_recess.diameter <= self.mount.clearance_diameter:
                    raise ValueError("Counterbore must exceed clearance diameter")
            if self.slot_length is not None:
                if not math.isfinite(self.slot_length) or self.slot_length < self.mount.clearance_diameter:
                    raise ValueError("Slot length must be at least the clearance diameter")
        elif self.thickness is not None or self.head_recess is not None or self.offset or self.slot_length or self.drill_offsets:
            raise ValueError("Receiver side cannot have a clamped thickness, offset, recess or slot")
        if self.role == "threaded" and not self.supplied:
            if any(value is None for value in (self.mount.pilot_diameter, self.mount.hole_depth, self.mount.thread_depth)):
                raise ValueError("A manufactured threaded role needs pilot diameter, hole depth and thread depth")

    @property
    def seat(self):
        """Return the clamped role screw-seat Z coordinate in millimetres; receivers have no seat."""
        if self.role not in {"clearance", "middle"}:
            raise ValueError("Only clamped roles have a screw/spacer seat")
        return self.offset + self.thickness - (self.head_recess.depth if self.head_recess else 0)

    def cutters(self):
        if self.supplied:
            return ()
        cutters = []
        for x, y in self.mount.pattern.points:
            if self.role in {"insert", "threaded"}:
                diameter = self.mount.pocket.diameter if self.role == "insert" else self.mount.pilot_diameter
                depth = self.mount.pocket.depth if self.role == "insert" else self.mount.hole_depth
                items = [cq.Solid.makeCylinder(diameter/2, depth+_OVERSHOOT, (x,y,-depth))]
            else:
                bottom = self.offset-_OVERSHOOT
                height = self.thickness+2*_OVERSHOOT
                if self.drill_offsets is not None:
                    drills = [cq.Solid.makeCylinder(self.mount.clearance_diameter/2, height,
                              (x+dx,y+dy,bottom)) for dx,dy in self.drill_offsets]
                    cut = drills[0].fuse(*drills[1:]) if len(drills)>1 else drills[0]
                elif self.slot_length is not None:
                    angle = math.degrees(math.atan2(y,x)) if self.slot_radial else self.slot_angle
                    cut = (cq.Workplane("XY", origin=(x,y,bottom))
                           .slot2D(self.slot_length, self.mount.clearance_diameter, angle)
                           .extrude(height).val())
                else:
                    cut = cq.Solid.makeCylinder(self.mount.clearance_diameter/2, height, (x,y,bottom))
                items = [cut]
                if self.head_recess:
                    items.append(cq.Solid.makeCylinder(self.head_recess.diameter/2,
                                 self.head_recess.depth+self.head_recess.entry_extension+_OVERSHOOT, (x,y,self.seat)))
            cutters.append(tuple(c.moved(self.at.location) for c in items))
        return tuple(cutters)

    def apply(self, body):
        if self.supplied:
            return body
        try:
            return _cut(body, self.cutters())
        except ValueError as exc:
            raise ValueError(str(exc).replace("Feature site", "Mount site")) from exc

    def describe(self):
        operations = []
        if not self.supplied and self.role == "insert":
            operations = [{"kind": "install-insert", "quantity": len(self.mount.pattern.points),
                           "spec_id": self.mount.insert.id}]
        elif not self.supplied and self.role == "threaded":
            operations = [{"kind": self.mount.method, "thread": self.mount.screw.size,
                           "thread_depth": self.mount.thread_depth, "quantity": len(self.mount.pattern.points)}]
        return {"kind": self.mount.describe()["kind"]+"-role", "role": self.role,
                "frame": self.at.describe(), "mount": self.mount.describe(), "thickness": self.thickness,
                "offset": self.offset, "supplied": self.supplied, "slot_length": self.slot_length,
                "slot_angle": self.slot_angle, "slot_radial": self.slot_radial, "drill_offsets": self.drill_offsets,
                "head_recess": ({"diameter": self.head_recess.diameter, "depth": self.head_recess.depth,
                                 "entry_extension": self.head_recess.entry_extension}
                                if self.head_recess else None), "operations": operations}
