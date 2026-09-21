"""Named manufacturing features backed by native CadQuery operations.

Hole datums are the entry face, with +Z into the material. Blind depths stop
exactly at the declared floor. Allowances are diametral, in millimetres, and
remain visible independently of nominal dimensions in inspection reports.
"""
from dataclasses import dataclass
import math
import cadquery as cq
from .frames import Frame, positive

_OVERSHOOT = 0.1


def _points(pattern):
    return pattern.points if pattern is not None else ((0.0, 0.0),)


def _describe_pattern(pattern):
    return pattern.describe() if pattern is not None else {"kind": "points", "points": ((0, 0),)}


def _cut(body, sites):
    """Require every declared site to remove material, with valid output."""
    cutters = []
    for i, site in enumerate(sites):
        for cutter in site:
            if body.intersect(cutter).Volume() <= 1e-7:
                raise ValueError(f"Feature site {i+1} does not intersect the part body")
            cutters.append(cutter)
    result = body.cut(*cutters).clean()
    if not result.isValid() or not result.Solids() or result.Volume() >= body.Volume() - 1e-7:
        raise ValueError("Manufacturing feature did not produce a valid material-removing cut")
    return result


def _cylinder(diameter, depth, at, point, *, through=False):
    x, y = point
    return cq.Solid.makeCylinder(diameter/2, depth+_OVERSHOOT*(2 if through else 1),
                                 (x, y, -_OVERSHOOT)).moved(at.location)


@dataclass(frozen=True)
class Hole:
    """A circular blind or through hole at one or more local sites.

    Args:
        diameter: Finished hole diameter in millimetres.
        depth: Positive cutting depth in millimetres from the entry datum.
        at: Entry-face frame whose +Z points into material.
        pattern: PointPattern or PolarPattern; `None` means one hole at the origin.
        through: Extend the exit by 0.1 mm to clear a face at the declared depth.
            A through hole still needs an explicit depth covering the material.

    The entry extends 0.1 mm outside the part. A blind hole stops exactly at
    its declared floor. Every declared site must intersect the body.
    """
    diameter: float
    depth: float
    at: Frame = Frame()
    pattern: object = None
    through: bool = False

    def __post_init__(self):
        positive(self.diameter, "Hole diameter")
        positive(self.depth, "Hole depth")
        if self.pattern is not None and not _points(self.pattern):
            raise ValueError("Hole pattern must not be empty")

    def cutters(self):
        return tuple((_cylinder(self.diameter, self.depth, self.at, p, through=self.through),)
                     for p in _points(self.pattern))

    def apply(self, body):
        return _cut(body, self.cutters())

    def describe(self):
        return {"kind": "hole", "diameter": self.diameter, "depth": self.depth,
                "through": self.through, "frame": self.at.describe(),
                "pattern": _describe_pattern(self.pattern), "operations": []}


@dataclass(frozen=True)
class CounterboredHole(Hole):
    """A Hole with a cylindrical recess measured from the entry face.

    Args:
        diameter: Finished through/pilot diameter in millimetres.
        depth: Total hole depth in millimetres.
        at: Entry frame, +Z into material.
        pattern: Local hole sites or `None` for one site.
        through: Extend the exit to clear a face at the declared depth.
        recess: Counterbore specification. Its diameter must exceed the hole
            diameter and its depth must leave a positive screw seat.
    """
    recess: object = None

    def __post_init__(self):
        super().__post_init__()
        if self.recess is None or self.recess.diameter <= self.diameter:
            raise ValueError("Counterbore must exceed the hole diameter")
        if self.recess.depth >= self.depth:
            raise ValueError("Counterbore must leave a positive screw seat")

    def cutters(self):
        extension = getattr(self.recess, "entry_extension", 0)
        entry = Frame.from_location(self.at.location * cq.Location((0, 0, -extension)))
        return tuple(site + (_cylinder(self.recess.diameter, self.recess.depth+extension,
                                       entry, point),)
                     for site, point in zip(super().cutters(), _points(self.pattern)))

    def describe(self):
        return {**super().describe(), "kind": "counterbored-hole",
                "recess": {"diameter": self.recess.diameter, "depth": self.recess.depth,
                           "entry_extension": getattr(self.recess, "entry_extension", 0)}}


@dataclass(frozen=True)
class CountersunkHole(Hole):
    """A Hole with an explicit conical screw-head recess.

    Args:
        diameter: Finished throat diameter in millimetres.
        depth: Total cutting depth in millimetres.
        at: Entry frame, +Z into material.
        pattern: Local hole sites or `None`.
        through: Extend the exit to clear a face at the declared depth.
        head_diameter: Recess mouth diameter, larger than `diameter`.
        included_angle: Full cone angle in degrees, strictly between 0 and 180.

    The derived recess depth must be less than the total hole depth. This
    feature is supported independently of countersunk hardware rendering.
    """
    head_diameter: float = 0
    included_angle: float = 90

    def __post_init__(self):
        super().__post_init__()
        positive(self.head_diameter, "Countersink head diameter")
        if self.head_diameter <= self.diameter:
            raise ValueError("Countersink must exceed the hole diameter")
        if not math.isfinite(self.included_angle) or not 0 < self.included_angle < 180:
            raise ValueError("Countersink angle must be between 0 and 180 degrees")
        if self.recess_depth >= self.depth:
            raise ValueError("Countersink must leave a positive screw seat")

    @property
    def recess_depth(self):
        return (self.head_diameter-self.diameter)/(2*math.tan(math.radians(self.included_angle/2)))

    def cutters(self):
        result = []
        for site, (x, y) in zip(super().cutters(), _points(self.pattern)):
            cone = cq.Solid.makeCone(self.head_diameter/2, self.diameter/2,
                                    self.recess_depth, (x, y, 0)).moved(self.at.location)
            mouth = cq.Solid.makeCylinder(self.head_diameter/2, _OVERSHOOT,
                                         (x, y, -_OVERSHOOT)).moved(self.at.location)
            result.append(site + (cone.fuse(mouth),))
        return tuple(result)

    def describe(self):
        return {**super().describe(), "kind": "countersunk-hole", "head_diameter": self.head_diameter,
                "included_angle": self.included_angle, "recess_depth": self.recess_depth}


@dataclass(frozen=True)
class TappedHole:
    """A pilot hole plus a recorded thread-manufacturing operation.

    Args:
        thread: Thread designation such as `M3-0.5`.
        pilot_diameter: Explicit drill/print pilot diameter in millimetres.
        depth: Pilot depth in millimetres.
        at: Entry frame, +Z into material.
        pattern: Local sites or `None`.
        method: `tap-after-printing`, `tap-after-machining`, or `self-tapping`.
        thread_depth: Intended thread depth in millimetres; defaults to pilot depth.
            It cannot exceed the pilot depth.

    Geometry is the pilot hole. This class records thread intent; it does not
    generate helical threads or choose the pilot diameter for a material.
    """
    thread: str
    pilot_diameter: float
    depth: float
    at: Frame = Frame()
    pattern: object = None
    method: str = "tap-after-printing"
    thread_depth: float | None = None

    def __post_init__(self):
        positive(self.pilot_diameter, "Tap pilot diameter")
        positive(self.depth, "Tap pilot depth")
        if not self.thread:
            raise ValueError("Thread designation is required")
        if self.method not in {"tap-after-printing", "tap-after-machining", "self-tapping"}:
            raise ValueError("Tapped hole needs an explicit supported manufacturing method")
        if self.thread_depth is not None:
            positive(self.thread_depth, "Thread depth")
            if self.thread_depth > self.depth:
                raise ValueError("Thread depth cannot exceed pilot hole depth")

    def apply(self, body):
        return Hole(self.pilot_diameter, self.depth, self.at, self.pattern).apply(body)

    def describe(self):
        return {"kind": "tapped-hole", "thread": self.thread, "pilot_diameter": self.pilot_diameter,
                "depth": self.depth, "thread_depth": self.thread_depth or self.depth,
                "frame": self.at.describe(), "pattern": _describe_pattern(self.pattern),
                "operations": [{"kind": self.method, "thread": self.thread,
                                "thread_depth": self.thread_depth or self.depth,
                                "quantity": len(_points(self.pattern))}]}


@dataclass(frozen=True)
class BearingSeat:
    """A nominal cylindrical seat with an explicit diametral allowance.

    Args:
        nominal_diameter: Bearing's nominal mating diameter in millimetres.
        allowance: Added to diameter, not radius, in millimetres.
        depth: Cutting depth in millimetres.
        at: Entry frame, +Z into material.
        pattern: Local sites or `None`.
        through: Extend the exit beyond the declared depth.
        fit: `clearance` requires a nonnegative allowance; `press` requires a
            nonpositive allowance; `transition` accepts either sign.

    The fit label is declared intent. Process calibration and physical trials
    remain necessary to establish the actual manufactured fit.
    """
    nominal_diameter: float
    allowance: float
    depth: float
    at: Frame = Frame()
    pattern: object = None
    through: bool = False
    fit: str = "clearance"

    def __post_init__(self):
        positive(self.nominal_diameter, "Bearing nominal diameter")
        if not math.isfinite(self.allowance):
            raise ValueError("Bearing allowance must be finite")
        positive(self.diameter, "Bearing seat diameter")
        positive(self.depth, "Bearing seat depth")
        if self.fit not in {"clearance", "transition", "press"}:
            raise ValueError("Bearing fit must be clearance, transition or press")
        if self.fit == "clearance" and self.allowance < 0:
            raise ValueError("Clearance bearing seats require nonnegative allowance")
        if self.fit == "press" and self.allowance > 0:
            raise ValueError("Press bearing seats require nonpositive allowance")

    @property
    def diameter(self):
        return self.nominal_diameter + self.allowance

    def apply(self, body):
        return Hole(self.diameter, self.depth, self.at, self.pattern, self.through).apply(body)

    def describe(self):
        return {**Hole(self.diameter, self.depth, self.at, self.pattern, self.through).describe(),
                "kind": "bearing-seat", "nominal_diameter": self.nominal_diameter,
                "allowance": self.allowance, "fit": self.fit}


@dataclass(frozen=True)
class Slot:
    """A rounded slot whose overall length includes both semicircular ends.

    Args:
        length: Overall local-X length in millimetres, at least `width`.
        width: Slot width in millimetres.
        depth: Cutting depth in millimetres.
        at: Entry frame, +Z into material; X defines the slot's long direction.
        pattern: Local site translations or `None`.
        through: Extend the exit beyond the declared depth.
    """
    length: float
    width: float
    depth: float
    at: Frame = Frame()
    pattern: object = None
    through: bool = False

    def __post_init__(self):
        for label in ("length", "width", "depth"):
            positive(getattr(self, label), f"Slot {label}")
        if self.length < self.width:
            raise ValueError("Slot length must be at least its width")

    def apply(self, body):
        sites = []
        for x, y in _points(self.pattern):
            cutter = (cq.Workplane("XY", origin=(x, y, -_OVERSHOOT))
                      .slot2D(self.length, self.width)
                      .extrude(self.depth + _OVERSHOOT*(2 if self.through else 1)).val())
            sites.append((cutter.moved(self.at.location),))
        return _cut(body, sites)

    def describe(self):
        return {"kind": "slot", "length": self.length, "width": self.width, "depth": self.depth,
                "frame": self.at.describe(), "pattern": _describe_pattern(self.pattern),
                "through": self.through, "operations": []}


@dataclass(frozen=True)
class NutPocket:
    """A hexagonal nut trap with a recorded installation operation.

    Args:
        across_flats: Finished pocket width across flats in millimetres.
        depth: Pocket depth in millimetres.
        at: Entry frame, +Z into material.
        pattern: Local sites or `None`.
        thread: Required nut thread designation such as `M3-0.5`.

    Supply the measured or calibrated pocket dimensions explicitly; the thread
    label does not select a catalogue nut or infer its external dimensions.
    """
    across_flats: float
    depth: float
    at: Frame = Frame()
    pattern: object = None
    thread: str = ""

    def __post_init__(self):
        positive(self.across_flats, "Nut pocket across flats")
        positive(self.depth, "Nut pocket depth")
        if not self.thread:
            raise ValueError("Nut pocket requires a thread designation")

    def apply(self, body):
        sites = []
        for x, y in _points(self.pattern):
            cutter = (cq.Workplane("XY", origin=(x, y, -_OVERSHOOT))
                      .polygon(6, self.across_flats*2/math.sqrt(3))
                      .extrude(self.depth+_OVERSHOOT).val().moved(self.at.location))
            sites.append((cutter,))
        return _cut(body, sites)

    def describe(self):
        return {"kind": "nut-pocket", "across_flats": self.across_flats, "depth": self.depth,
                "thread": self.thread, "frame": self.at.describe(),
                "pattern": _describe_pattern(self.pattern),
                "operations": [{"kind": "install-nut", "thread": self.thread,
                                "quantity": len(_points(self.pattern))}]}


@dataclass(frozen=True)
class DBore(Hole):
    """A shaft bore truncated at local X=`flat`, retaining material on the +X side.

    Args:
        diameter: Full circular bore diameter in millimetres.
        depth: Cutting depth in millimetres.
        at: Entry frame, +Z into material; +X points toward the retained flat.
        pattern: Local sites or `None`.
        through: Extend the exit beyond the declared depth.
        flat: Signed centre-to-flat distance in millimetres, strictly inside
            the bore radius. Positive values retain more than half the circular hole.

    `flat` is a position, not the removed segment depth.
    """
    flat: float = 0

    def __post_init__(self):
        super().__post_init__()
        if not math.isfinite(self.flat) or not -self.diameter/2 < self.flat < self.diameter/2:
            raise ValueError("D-bore flat must lie strictly inside the bore radius")

    def cutters(self):
        result = []
        for x,y in _points(self.pattern):
            cylinder = cq.Solid.makeCylinder(self.diameter/2,
                       self.depth+_OVERSHOOT*(2 if self.through else 1), (x,y,-_OVERSHOOT))
            box = cq.Solid.makeBox(self.diameter+self.flat, 2*self.diameter,
                      self.depth+2*_OVERSHOOT, (x-self.diameter,y-self.diameter,-_OVERSHOOT))
            result.append((cylinder.intersect(box).moved(self.at.location),))
        return tuple(result)

    def describe(self):
        return {**super().describe(), "kind": "d-bore", "flat": self.flat}


@dataclass(frozen=True)
class SealGroove:
    """A toroidal groove with explicit nominal radii.

    Args:
        mean_radius: Radius from the datum axis to the section centre, in millimetres.
        section_radius: Circular section radius in millimetres, smaller than the mean.
        at: Torus centre frame; its axis is local Z.

    The torus straddles the datum XY plane. Groove compression, squeeze, and
    seal material selection are not inferred or validated.
    """
    mean_radius: float
    section_radius: float
    at: Frame = Frame()

    def __post_init__(self):
        positive(self.mean_radius, "Seal mean radius")
        positive(self.section_radius, "Seal section radius")
        if self.section_radius >= self.mean_radius:
            raise ValueError("Seal section radius must be smaller than its mean radius")

    def apply(self, body):
        cutter = cq.Solid.makeTorus(self.mean_radius, self.section_radius).moved(self.at.location)
        return _cut(body, ((cutter,),))

    def describe(self):
        return {"kind": "seal-groove", "mean_radius": self.mean_radius,
                "section_radius": self.section_radius, "frame": self.at.describe(), "operations": []}


@dataclass(frozen=True)
class Boss:
    """Add cylindrical local reinforcement, optionally clipped by a native boundary.

    Args:
        diameter: Outer diameter in millimetres.
        depth: Height along positive local Z in millimetres.
        at: Base frame of the reinforcement.
        pattern: Local XY sites or `None`.
        limit: Optional native Shape or zero-argument native builder restricting
            the reinforcement's outer envelope.

    Added material must join the existing body and increase its volume. Features
    run in declared order: a later boss can restore earlier removed material.
    """
    diameter: float
    depth: float
    at: Frame = Frame()
    pattern: object = None
    limit: object = None

    def __post_init__(self):
        positive(self.diameter, "Boss diameter")
        positive(self.depth, "Boss depth")

    def apply(self, body):
        from .parts import native
        boundary = native(self.limit() if callable(self.limit) else self.limit) if self.limit is not None else None
        bosses = []
        for x,y in _points(self.pattern):
            boss = cq.Solid.makeCylinder(self.diameter/2,self.depth,(x,y,0)).moved(self.at.location)
            if boundary is not None:
                boss = boss.intersect(boundary)
            if not boss.Solids() or not boss.isValid() or boss.Volume() <= 1e-7:
                raise ValueError("Boss boundary leaves no valid material")
            bosses.append(boss)
        result = body.fuse(*bosses).clean()
        if not result.isValid() or len(result.Solids()) > len(body.Solids()):
            raise ValueError("Bosses must join the part body")
        if result.Volume() <= body.Volume()+1e-7:
            raise ValueError("Boss does not add material to the part body")
        return result

    def describe(self):
        return {"kind":"boss","diameter":self.diameter,"depth":self.depth,
                "frame":self.at.describe(),"pattern":_describe_pattern(self.pattern),
                "has_boundary":self.limit is not None,"operations":[]}
