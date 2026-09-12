"""A shared insert-mount recipe generates both explicitly owned part roles."""
from dataclasses import dataclass
import cadquery as cq
from ..fasteners import FastenerSpec, FastenerSite, HardwareItem
from ..mechanics import Fastening
from .frames import Frame, PolarPattern, positive

# Boolean overshoot is confined to open ends, never the bottom of a blind hole.
_OVERSHOOT = 0.1


@dataclass(frozen=True)
class Counterbore:
    diameter: float
    depth: float

    def __post_init__(self):
        positive(self.diameter, "Counterbore diameter")
        positive(self.depth, "Counterbore depth")


@dataclass(frozen=True)
class InsertPocket:
    diameter: float
    depth: float

    def __post_init__(self):
        positive(self.diameter, "Pocket diameter")
        positive(self.depth, "Pocket depth")


@dataclass(frozen=True)
class InsertMount:
    pattern: PolarPattern
    screw: FastenerSpec
    insert: FastenerSpec
    clearance_diameter: float
    pocket: InsertPocket
    minimum_engagement: float

    def __post_init__(self):
        if self.screw.kind != "socket_head_cap_screw" or self.insert.kind != "heat_set_insert":
            raise ValueError("InsertMount currently supports socket-head screws and heat-set inserts")
        if self.screw.size != self.insert.size:
            raise ValueError("Screw and insert threads must match")
        positive(self.clearance_diameter, "Clearance diameter")
        positive(self.minimum_engagement, "Minimum engagement")
        if self.insert.length_mm is None:
            raise ValueError("Insert length must be specified")
        positive(self.insert.length_mm, "Insert length")
        if self.pocket.depth < self.insert.length_mm:
            raise ValueError("Pocket must accommodate the insert length")

    def clearance_side(self, *, at=Frame(), thickness, head_recess=None):
        return MountFeature(self, "clearance", at, thickness, head_recess)

    def insert_side(self, *, at=Frame()):
        return MountFeature(self, "insert", at)

    def describe(self):
        return {"kind": "insert-mount", "pattern": self.pattern.describe(),
                "screw": self.screw.describe(), "insert": self.insert.describe(),
                "clearance_diameter": self.clearance_diameter,
                "pocket": {"diameter": self.pocket.diameter, "depth": self.pocket.depth},
                "minimum_engagement": self.minimum_engagement}

    def fastening(self, name, *, through, into, frame, clearance, joint=None):
        """Lower one bound connection into the existing mechanical contract."""
        grip = clearance.seat
        sites = []
        for i, (x, y) in enumerate(self.pattern.points):
            site = Frame.from_location(frame.location * cq.Location((x, y, grip)))
            sites.append(FastenerSite(str(i+1), site.origin, tuple(-v for v in site.z)))
        return Fastening(name, (through, into), sites=tuple(sites), joint=joint, kind="insert",
                         grip_mm=grip, thread_depth_mm=self.insert.length_mm,
                         hole_depth_mm=grip+self.pocket.depth,
                         min_engagement_mm=self.minimum_engagement,
                         hardware=(HardwareItem("screw", self.screw), HardwareItem("insert", self.insert, grip)))


@dataclass(frozen=True)
class MountFeature:
    """Both frames lie on the mating plane, +Z from receiver to clamped part."""
    mount: InsertMount
    role: str
    at: Frame = Frame()
    thickness: float | None = None
    head_recess: Counterbore | None = None

    def __post_init__(self):
        if self.role not in {"insert", "clearance"}:
            raise ValueError("Unknown mount role")
        if self.role == "clearance":
            if self.thickness is None:
                raise ValueError("Clearance side needs a thickness")
            positive(self.thickness, "Thickness")
            if self.head_recess is not None:
                if self.head_recess.depth >= self.thickness:
                    raise ValueError("Counterbore must leave a positive screw seat")
                if self.head_recess.diameter <= self.mount.clearance_diameter:
                    raise ValueError("Counterbore must exceed clearance diameter")
        elif self.thickness is not None or self.head_recess is not None:
            raise ValueError("Insert side cannot have a clamped thickness or head recess")

    @property
    def seat(self):
        if self.role != "clearance":
            raise ValueError("Only the clearance side has a screw seat")
        return self.thickness - (self.head_recess.depth if self.head_recess else 0)

    def cutters(self):
        cutters = []
        for x, y in self.mount.pattern.points:
            if self.role == "insert":
                pocket = self.mount.pocket
                items = [(pocket.diameter, -pocket.depth, pocket.depth+_OVERSHOOT)]
            else:
                items = [(self.mount.clearance_diameter, -_OVERSHOOT, self.thickness+2*_OVERSHOOT)]
                if self.head_recess:
                    items.append((self.head_recess.diameter, self.seat, self.head_recess.depth+_OVERSHOOT))
            cutters.append(tuple(cq.Solid.makeCylinder(d/2, h, (x, y, z)).moved(self.at.location)
                                 for d, z, h in items))
        return tuple(cutters)

    def apply(self, body):
        cutters = self.cutters()
        # Catch misplaced roles per site, rather than silently recording empty cuts.
        for i, site in enumerate(cutters):
            if body.intersect(site[0]).Volume() <= 1e-7:
                raise ValueError(f"Mount site {i+1} does not intersect the part body")
        return body.cut(*(c for site in cutters for c in site)).clean()

    def describe(self):
        return {"kind": "insert-mount-role", "role": self.role, "frame": self.at.describe(),
                "mount": self.mount.describe(), "thickness": self.thickness,
                "head_recess": ({"diameter": self.head_recess.diameter, "depth": self.head_recess.depth}
                                if self.head_recess else None),
                "operations": ([{"kind": "install-insert", "quantity": len(self.mount.pattern.points),
                                 "spec_id": self.mount.insert.id}] if self.role == "insert" else [])}
