"""Assembly intent and bounded validation, independent of the viewport.

Declarations describe existing geometry; they never modify printed Parts. Native
intersection checks establish installed fit, not the existence of an assembly
sequence. Unspecified motion, tools and material/process data remain unverified.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import combinations
import math
import re
from typing import Callable
from urllib.parse import quote
import cadquery as cq
from .geometry import Mesh, shape
from .fasteners import FastenerSpec, HardwareItem, FastenerSite, vector


@dataclass(frozen=True)
class Joint:
    """A declared relationship between already installed components.

    Args:
        name: Unique joint name.
        components: At least two distinct component names or full assembly paths.
        kind: `rigid`, `revolute`, or `slider`.
        origin: Installed joint origin in world millimetres.
        axis: Installed motion axis, normalized on construction.
        limits: Optional inclusive coordinate limits, in degrees for revolute
            motion or millimetres for sliders.
        position: Declared installed coordinate in the corresponding units.
        interfaces: Related Interface names.
        fastenings: Related Fastening names.
        description: Human-readable intent.

    Stable Joint metadata does not move geometry. For pose-driven placement,
    use declarative Assembly connections.
    """
    name: str
    components: tuple[str, ...]
    kind: str = "rigid"
    origin: tuple[float, float, float] = (0, 0, 0)
    axis: tuple[float, float, float] = (0, 0, 1)
    limits: tuple[float, float] | None = None
    position: float = 0
    interfaces: tuple[str, ...] = ()
    fastenings: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self):
        _entity(self.name, self.components)
        if self.kind not in {"rigid", "revolute", "slider"}:
            raise ValueError(f"Unknown joint kind: {self.kind}")
        object.__setattr__(self, "origin", vector(self.origin, "origin"))
        object.__setattr__(self, "axis", vector(self.axis, "axis", unit=True))
        if not math.isfinite(self.position):
            raise ValueError("Joint position must be finite")
        if self.limits is not None and (len(self.limits) != 2 or not all(math.isfinite(x) for x in self.limits) or self.limits[0] > self.limits[1]):
            raise ValueError("Joint limits must be ordered finite bounds")

    def describe(self):
        return {"id": self.name, "name": self.name, "kind": self.kind,
                "components": self.components, "description": self.description,
                "origin": self.origin, "axis": self.axis, "limits": self.limits,
                "position": self.position, "position_unit": "deg" if self.kind == "revolute" else "mm",
                "interfaces": self.interfaces, "fastenings": self.fastenings}


@dataclass(frozen=True)
class Interface:
    """A bounded contact or clearance contract between two installed components.

    Args:
        name: Unique interface name.
        components: Exactly two component names or full paths.
        kind: `contact`, `clearance`, `press_fit`, `threaded`, or `mesh`.
        region: Lazy native solid in world millimetres delimiting allowed overlap.
            Required whenever `max_overlap_mm3` is positive.
        max_overlap_mm3: Maximum permitted native intersection volume inside
            the region. It cannot be positive for a clearance interface.
        min_clearance_mm: Minimum required separation in millimetres.
        max_gap_mm: Maximum allowed distance in millimetres. Contact interfaces
            replace `None` with 0.001; other kinds may leave it unspecified.
        description: Explanation of the intended fit or contact.

    Values must be nonnegative when supplied. Permitting overlap does not
    excuse collisions outside the specified region.
    """
    name: str
    components: tuple[str, str]
    kind: str = "contact"
    region: Callable[[], cq.Shape] | None = field(default=None, repr=False, compare=False)
    max_overlap_mm3: float = 0
    min_clearance_mm: float = 0
    max_gap_mm: float | None = None
    description: str = ""

    def __post_init__(self):
        _entity(self.name, self.components)
        if len(self.components) != 2:
            raise ValueError("An Interface requires exactly two components")
        if self.kind not in {"contact", "clearance", "press_fit", "threaded", "mesh"}:
            raise ValueError(f"Unknown interface kind: {self.kind}")
        for name in ("max_overlap_mm3", "min_clearance_mm", "max_gap_mm"):
            _nonnegative(getattr(self, name), name)
        if self.max_overlap_mm3 > 0 and self.region is None:
            raise ValueError("Permitted overlap requires an explicit bounded region")
        if self.kind == "clearance" and self.max_overlap_mm3 > 0:
            raise ValueError("Clearance interfaces cannot permit overlap")
        if self.kind == "contact" and self.max_gap_mm is None:
            object.__setattr__(self, "max_gap_mm", 0.001)

    def describe(self):
        return {"id": self.name, "name": self.name, "components": self.components,
                "kind": self.kind, "description": self.description, "has_region": self.region is not None,
                "max_overlap_mm3": self.max_overlap_mm3, "min_clearance_mm": self.min_clearance_mm,
                "max_gap_mm": self.max_gap_mm}


@dataclass(frozen=True)
class AccessEnvelope:
    """A complete swept tool or insertion solid checked against explicit obstacles.

    Args:
        name: Unique access name within a fastening.
        envelope: Lazy native solid in installed world millimetres, including
            the whole swept tool body, not only a centre line.
        obstacles: Explicit component references to test against the envelope.
        description: The intended tool, direction, and assembly operation.

    An omitted envelope records unverified access. A supplied envelope proves
    only this geometry against this obstacle set in the installed pose.
    """
    name: str
    envelope: Callable[[], cq.Shape] | None = field(default=None, repr=False, compare=False)
    obstacles: tuple[str, ...] = ()
    description: str = ""

    def describe(self):
        return {"name": self.name, "has_envelope": self.envelope is not None,
                "obstacles": self.obstacles, "description": self.description}


@dataclass(frozen=True)
class Fastening:
    """Repeated located hardware and explicit grip/engagement requirements.

    Args:
        name: Unique fastening name.
        components: One or more distinct participating component references.
        sites: Installed axes where the entire hardware stack is repeated.
        hardware: Named HardwareItems, each with an axial offset.
        joint: Associated Joint name, if this fastening secures a joint.
        kind: `through`, `tapped`, or `insert`.
        grip_mm: Clamped stack thickness along the screw axis.
        thread_depth_mm: Available thread engagement depth.
        min_engagement_mm: Minimum required screw engagement.
        hole_depth_mm: Total receiving depth for blind-hole tip-clearance checks.
        min_tip_clearance_mm: Required free depth beyond the screw tip.
        access: Explicit swept tool/access checks.
        insertion_distance_mm: Outward distance for the presentation preview.
        description: Human-readable assembly intent.
        quantity: Positive BOM count for unlocated hardware, or a count matching
            the number of sites when sites are present.
        thread_size: Explicit receiving thread designation, when known.

    Unknown dimensions remain `None` and related checks remain unverified.
    A BOM quantity without sites does not establish hardware placement.
    """
    name: str
    components: tuple[str, ...]
    sites: tuple[FastenerSite, ...] = ()
    hardware: tuple[HardwareItem, ...] = ()
    joint: str | None = None
    kind: str = "through"
    grip_mm: float | None = None
    thread_depth_mm: float | None = None
    min_engagement_mm: float | None = None
    hole_depth_mm: float | None = None
    min_tip_clearance_mm: float = 0.2
    access: tuple[AccessEnvelope, ...] = ()
    insertion_distance_mm: float = 20
    description: str = ""
    quantity: int | None = None
    thread_size: str | None = None

    def __post_init__(self):
        _entity(self.name, self.components, minimum=1)
        if self.quantity is not None and (type(self.quantity) is not int or self.quantity < 1 or (self.sites and self.quantity != len(self.sites))):
            raise ValueError("Fastening quantity must be a positive integer matching located sites")
        if self.kind not in {"through", "tapped", "insert"}:
            raise ValueError(f"Unknown fastening kind: {self.kind}")
        for name in ("grip_mm", "thread_depth_mm", "min_engagement_mm", "hole_depth_mm", "min_tip_clearance_mm", "insertion_distance_mm"):
            _nonnegative(getattr(self, name), name)
        for label, items in (("site", self.sites), ("hardware", self.hardware), ("access", self.access)):
            if len({item.name for item in items}) != len(items):
                raise ValueError(f"Duplicate {label} names in fastening {self.name}")

    def describe(self):
        return {"id": self.name, "name": self.name, "components": self.components,
                "joint": self.joint, "kind": self.kind, "description": self.description,
                "sites": [s.describe() for s in self.sites], "hardware": [h.describe() for h in self.hardware],
                "quantity": self.quantity if self.quantity is not None else len(self.sites),
                "thread_size": self.thread_size,
                "grip_mm": self.grip_mm, "thread_depth_mm": self.thread_depth_mm,
                "min_engagement_mm": self.min_engagement_mm, "hole_depth_mm": self.hole_depth_mm,
                "min_tip_clearance_mm": self.min_tip_clearance_mm,
                "access": [a.describe() for a in self.access], "insertion_distance_mm": self.insertion_distance_mm}


def _entity(name, components, *, minimum=2):
    if not name or len(components) < minimum or len(set(components)) != len(components):
        raise ValueError(f"Mechanical entities require a name and at least {minimum} distinct component references")


def _nonnegative(value, name):
    if value is not None and (not math.isfinite(value) or value < 0):
        raise ValueError(f"{name} must be finite and nonnegative")


def component_index(assembly):
    """Same URL-encoded IDs as the desktop tree; no dependence on viewport state."""
    from .project import Assembly
    result = {}
    def visit(node, parent=""):
        path = parent + "/" + quote(node.name, safe="")
        if isinstance(node, Assembly):
            for child in node.children:
                visit(child, path)
        else:
            result[path] = node
    visit(assembly)
    return result


def resolve_components(refs, index):
    result = []
    for ref in refs:
        matches = [ref] if ref in index else [path for path, node in index.items() if node.name == ref]
        if len(matches) != 1:
            raise ValueError(f"Component reference {ref!r} is {'unknown' if not matches else 'ambiguous; use its full assembly path'}")
        result.append(matches[0])
    if len(result) != len(set(result)):
        raise ValueError("Distinct references resolve to the same component")
    return result


def hardware_assembly(fastenings):
    from .project import Assembly, Component
    groups = []
    built = {}
    for fastening in fastenings:
        sites = []
        for site in fastening.sites:
            hardware = []
            for item in fastening.hardware:
                cache_key = (item.spec.id, id(item.spec.factory))
                if cache_key not in built:
                    built[cache_key] = item.spec.build()
                offset = tuple(-x * fastening.insertion_distance_mm for x in site.axis)
                model = site.place(built[cache_key], item.offset_mm)
                hardware.append(Component(item.name, model, "Hardware", color=(0.58, 0.62, 0.66), material="hardware", explode=offset,
                    metadata={"role": "fastener", "type": "hardware", "fastening_id": fastening.name,
                              "site": site.name, "hardware": item.name, "spec_id": item.spec.id,
                              "spec": item.spec.describe(), "preview_offset_mm": offset,
                              "insertion": {"axis": site.axis, "distance_mm": fastening.insertion_distance_mm}}))
            if hardware:
                sites.append(Assembly(site.name, tuple(hardware)))
        if sites:
            groups.append(Assembly(fastening.name, tuple(sites), fastening.description))
    return Assembly("Hardware", tuple(groups)) if groups else None


def hardware_bom(fastenings):
    """Aggregate hardware quantities by FastenerSpec identity without building shapes.

    Args:
        fastenings (tuple[Fastening, ...]): Located or quantity-only hardware declarations.

    Returns:
        (list[dict]): Specification, quantity, associated fastening IDs, and whether
            all contributions are located.
    """
    rows = {}
    for fastening in fastenings:
        for item in fastening.hardware:
            entry = rows.setdefault(item.spec.id, {"id": item.spec.id, "spec": item.spec.describe(), "quantity": 0, "fastening_ids": [], "located": True})
            entry["quantity"] += fastening.quantity if fastening.quantity is not None else len(fastening.sites)
            entry["located"] &= bool(fastening.sites)
            if fastening.name not in entry["fastening_ids"]:
                entry["fastening_ids"].append(fastening.name)
    return list(rows.values())


def mechanical_descriptions(project, assembly=None):
    index = component_index(assembly) if assembly is not None else None
    result = {}
    for label in ("joints", "interfaces", "fastenings"):
        result[label] = []
        for entity in getattr(project, label):
            row = entity.describe()
            row["component_ids"] = []
            if index is not None:
                try:
                    row["component_ids"] = resolve_components(entity.components, index)
                except ValueError as exc:
                    row["resolution_error"] = str(exc)
            if label == "fastenings":
                row["hardware_ids"] = [path for path, node in (index or {}).items() if node.metadata.get("fastening_id") == entity.name]
            result[label].append(row)
    result["hardware_bom"] = hardware_bom(project.fastenings)
    return result


def _bounds(model):
    bb = model.BoundingBox()
    return ((bb.xmin, bb.ymin, bb.zmin), (bb.xmax, bb.ymax, bb.zmax))


def _overlaps_bounds(a, b, *, bounds=None):
    bounds = _bounds if bounds is None else bounds
    aa, bb = bounds(a), bounds(b)
    return all(min(aa[1][i], bb[1][i]) > max(aa[0][i], bb[0][i]) + 1e-8 for i in range(3))


def _memoized_geometry_query(query):
    """Cache one validation run's queries, including failures, by shape identity."""
    results = {}
    def cached(model):
        key = id(model)
        if key not in results:
            try:
                result = query(model)
            except Exception as exc:
                result = exc
            # Retain the shape so transient access envelopes cannot reuse its ID.
            results[key] = (model, result)
        result = results[key][1]
        if isinstance(result, Exception):
            raise result.with_traceback(None)
        return result
    return cached


def validate_mechanics(project, assembly=None, *, scan_collisions=True, tolerance_mm3=1e-5):
    """Validate installed collisions and the project's declared mechanical contracts.

    Args:
        project (cadkit.project.Project): Project containing declarations.
        assembly (cadkit.project.Assembly | None): Reuse installed geometry, or
            build the project's default assembly.
        scan_collisions (bool): Scan undeclared native component intersections.
            Disabling this leaves collision coverage unverified.
        tolerance_mm3 (float): Volume tolerance for native overlap checks.

    Returns:
        (dict): Schema-versioned report with overall `pass`, `fail`, or
            `incomplete`, findings, summary counts, and coverage information.

    Mesh-dependent checks, unknown supplier dimensions, unspecified tool access,
    and unmodelled motion sweeps are reported as unverified where relevant.
    """
    if tolerance_mm3 <= 0 or not math.isfinite(tolerance_mm3):
        raise ValueError("Collision tolerance must be positive and finite")
    assembly = assembly if assembly is not None else project.get_assembly()
    index = component_index(assembly)
    models = {path: shape(component.model) for path, component in index.items()}
    # Geometry is fixed during validation; discard these caches after every run.
    bounds_for = _memoized_geometry_query(_bounds)
    valid_solid = _memoized_geometry_query(lambda model: bool(model.isValid() and model.Solids()))
    envelope_ids = {
        path for path, component in index.items()
        if component.metadata.get("representation") == "envelope"
        or component.metadata.get("spec", {}).get("representation") == "envelope"
    }
    findings = []
    def finding(concept, entity, code, status, message, ids=(), **evidence):
        findings.append({"id": f"{concept}:{entity}:{code}", "concept": concept, "entity": entity,
            "code": code, "status": status, "severity": {"pass":"info", "fail":"error", "unverified":"warning"}[status],
            "message": message, "component_ids": list(ids), "evidence": evidence})
    resolved = {}
    for label, concept in (("joints", "joint"), ("interfaces", "interface"), ("fastenings", "fastening")):
        for entity in getattr(project, label):
            try:
                resolved[(concept, entity.name)] = resolve_components(entity.components, index)
            except ValueError as exc:
                finding(concept, entity.name, "references", "fail", str(exc))
    for joint in project.joints:
        ids = resolved.get(("joint", joint.name), [])
        if not ids:
            continue
        missing = set(joint.interfaces) - {item.name for item in project.interfaces}
        missing |= set(joint.fastenings) - {item.name for item in project.fastenings}
        if missing:
            finding("joint", joint.name, "links", "fail", "Joint references unknown contracts", ids, missing=sorted(missing))
        else:
            finding("joint", joint.name, "links", "pass", "Joint participants and contract links resolve", ids)
        if joint.kind != "rigid":
            ok = joint.limits is None or joint.limits[0] <= joint.position <= joint.limits[1]
            finding("joint", joint.name, "position", "pass" if ok else "fail", "Declared joint position checked against limits", ids, position=joint.position, limits=joint.limits)
            finding("joint", joint.name, "movement", "unverified", "Travel and swept operating collisions have not been checked", ids)
        finding("joint", joint.name, "alignment", "unverified", "Joint frame is authored intent; mate alignment and load capacity are not solved", ids)

    pair_interfaces = {}
    region_cache = {}
    for interface in project.interfaces:
        ids = resolved.get(("interface", interface.name), [])
        if ids:
            pair_interfaces.setdefault(tuple(sorted(ids)), []).append(interface)
    measured_pairs = {}
    pair_distances = {}
    def measure_pair(ids):
        key = tuple(sorted(ids))
        if key not in measured_pairs:
            a, b = [models[path] for path in key]
            if any(isinstance(model, Mesh) or not isinstance(model, cq.Shape) for model in (a, b)):
                raise TypeError("Native collision/distance validation unavailable for a mesh or unsupported shape")
            if not all(valid_solid(model) for model in (a, b)):
                raise ValueError("Collision/distance validation requires valid solid components")
            overlap = a.intersect(b) if _overlaps_bounds(a, b, bounds=bounds_for) else None
            volume = abs(overlap.Volume()) if overlap is not None else 0
            measured_pairs[key] = (overlap, volume)
        return measured_pairs[key]
    def distance_for_pair(ids):
        key = tuple(sorted(ids))
        if key not in pair_distances:
            a, b = [models[path] for path in key]
            pair_distances[key] = a.distance(b)
        return pair_distances[key]
    def region_for(interface):
        if interface.name not in region_cache:
            region = shape(interface.region()) if interface.region is not None else None
            if region is not None and (not isinstance(region, cq.Shape) or not region.Solids() or not region.isValid()):
                raise ValueError("Overlap region must be a valid native solid")
            region_cache[interface.name] = region
        return region_cache[interface.name]
    for interface in project.interfaces:
        ids = resolved.get(("interface", interface.name), [])
        if not ids:
            continue
        try:
            overlap, volume = measure_pair(ids)
            gap = distance_for_pair(ids)
            region = region_for(interface)
            outside = abs(overlap.cut(region).Volume()) if volume > tolerance_mm3 and region is not None else volume
            regional_gap = gap
            if region is not None and (interface.max_gap_mm is not None or interface.min_clearance_mm > 0):
                regional = [models[path].intersect(region) for path in ids]
                if any(not piece.Solids() for piece in regional):
                    approximate = sorted(envelope_ids.intersection(ids))
                    finding("interface", interface.name, "fit", "unverified" if approximate else "fail",
                        "Contact/clearance region does not include both components" + ("; component envelope cannot establish physical fit" if approximate else ""), ids,
                        nominal_status="fail", envelope_component_ids=approximate)
                    continue
                regional_gap = regional[0].distance(regional[1])
            allowed = volume <= tolerance_mm3 or (region is not None and volume <= interface.max_overlap_mm3 + tolerance_mm3 and outside <= tolerance_mm3)
            ok = allowed and regional_gap + 1e-7 >= interface.min_clearance_mm and (interface.max_gap_mm is None or regional_gap <= interface.max_gap_mm + 1e-7)
            approximate = sorted(envelope_ids.intersection(ids))
            finding("interface", interface.name, "fit", "unverified" if approximate else "pass" if ok else "fail",
                "Contact, clearance and bounded overlap evaluated against component envelopes; physical fit is unverified" if approximate else "Installed contact, clearance and bounded overlap checked", ids,
                nominal_status="pass" if ok else "fail", envelope_component_ids=approximate,
                overlap_mm3=volume, outside_region_mm3=outside, gap_mm=regional_gap, whole_pair_gap_mm=gap,
                max_overlap_mm3=interface.max_overlap_mm3, min_clearance_mm=interface.min_clearance_mm, max_gap_mm=interface.max_gap_mm)
            if interface.kind in {"press_fit", "threaded", "mesh"}:
                finding("interface", interface.name, "process", "unverified", "Nominal geometry does not verify material compliance, fabrication tolerance or functional fit", ids)
        except Exception as exc:
            finding("interface", interface.name, "fit", "unverified", str(exc), ids)

    pairs_scanned = 0
    kernel_failures = 0
    if scan_collisions:
        for ids in combinations(models, 2):
            pairs_scanned += 1
            a, b = [models[path] for path in ids]
            if isinstance(a, Mesh) or isinstance(b, Mesh):
                # Aggregate unsupported coverage rather than emitting thousands of duplicate rows.
                continue
            try:
                if not _overlaps_bounds(a, b, bounds=bounds_for):
                    continue
                overlap, volume = measure_pair(ids)
                if volume <= tolerance_mm3:
                    continue
                applicable = pair_interfaces.get(tuple(sorted(ids)), [])
                permitted = []
                for interface in applicable:
                    region = region_for(interface)
                    if region is not None and volume <= interface.max_overlap_mm3 + tolerance_mm3:
                        permitted.append(region)
                remaining = overlap
                for region in permitted:
                    remaining = remaining.cut(region)
                outside = abs(remaining.Volume())
                if outside > tolerance_mm3:
                    approximate = sorted(envelope_ids.intersection(ids))
                    finding("assembly", "installed", "collision-" + str(pairs_scanned), "unverified" if approximate else "fail",
                        "Component envelope intersects another component; physical interference is unverified" if approximate else "Undeclared or out-of-bounds installed collision",
                        ids, overlap_mm3=volume, unpermitted_overlap_mm3=outside, envelope_component_ids=approximate)
            except Exception as exc:
                kernel_failures += 1
                finding("assembly", "installed", "geometry-" + str(pairs_scanned), "unverified", str(exc), ids)
    mesh_ids = [path for path, model in models.items() if isinstance(model, Mesh)]
    if mesh_ids:
        finding("assembly", "installed", "mesh-coverage", "unverified", "Automatic native collision scan excludes pairs containing mesh components", mesh_ids)
    if envelope_ids:
        finding("assembly", "installed", "envelope-coverage", "unverified",
            "Component envelopes do not establish complete physical collision or clearance coverage", sorted(envelope_ids))
    if not scan_collisions:
        finding("assembly", "installed", "collision-coverage", "unverified", "Automatic installed collision scan was not requested")

    for fastening in project.fastenings:
        ids = resolved.get(("fastening", fastening.name), [])
        hardware_ids = [path for path, node in index.items() if node.metadata.get("fastening_id") == fastening.name]
        all_ids = ids + hardware_ids
        if fastening.joint is not None and fastening.joint not in {joint.name for joint in project.joints}:
            finding("fastening", fastening.name, "joint", "fail", "Fastening references an unknown joint", all_ids)
        if not fastening.sites or not fastening.hardware or len(hardware_ids) != len(fastening.sites) * len(fastening.hardware):
            finding("fastening", fastening.name, "locations", "unverified", "Located sites and hardware are required for physical validation", ids)
        screws = [item for item in fastening.hardware if item.spec.kind.endswith("screw")]
        if len(screws) != 1:
            finding("fastening", fastening.name, "stack", "unverified", "Engagement checks require one screw per fastening site", all_ids)
        else:
            screw = screws[0]
            receivers = [item for item in fastening.hardware if item.spec.kind in {"hex_nut", "heat_set_insert"}]
            expected_kind = {"through": "hex_nut", "insert": "heat_set_insert"}.get(fastening.kind)
            if fastening.kind == "tapped":
                if fastening.thread_size is None:
                    finding("fastening", fastening.name, "thread-match-tapped", "unverified", "Tapped receiver thread_size is not declared", all_ids)
                else:
                    try:
                        male = screw.spec.catalogue()
                        declared = re.fullmatch(r"M([0-9]+(?:\.[0-9]+)?)-([0-9]+(?:\.[0-9]+)?)", fastening.thread_size)
                        if declared is None:
                            raise ValueError("Tapped thread matching currently requires an explicit metric diameter-pitch, e.g. M3-0.5")
                        female_dimensions = tuple(map(float, declared.groups()))
                        male_dimensions = (getattr(male, "thread_diameter", None), getattr(male, "thread_pitch", None))
                        if None in male_dimensions:
                            raise ValueError("Provider does not establish the screw thread dimensions")
                        matches = all(abs(a-b) < 1e-7 for a,b in zip(male_dimensions,female_dimensions))
                        finding("fastening", fastening.name, "thread-match-tapped", "pass" if matches else "fail", "Screw compared with declared tapped receiver diameter/pitch", all_ids, screw_thread_mm=male_dimensions, receiver_thread_mm=female_dimensions)
                    except Exception as exc:
                        finding("fastening", fastening.name, "thread-match-tapped", "unverified", str(exc), all_ids)
            if expected_kind and not any(item.spec.kind == expected_kind for item in receivers):
                finding("fastening", fastening.name, "receiver", "unverified", "Fastening does not declare its expected nut or insert hardware", all_ids, expected_kind=expected_kind)
            for receiver in receivers:
                try:
                    male, female = screw.spec.catalogue(), receiver.spec.catalogue()
                    dimensions = [(getattr(item, "thread_diameter", None), getattr(item, "thread_pitch", None)) for item in (male, female)]
                    if any(value is None for values in dimensions for value in values):
                        raise ValueError("Provider does not establish both mating thread diameters and pitches")
                    compatible = all(abs(a-b) < 1e-7 for a,b in zip(*dimensions))
                    finding("fastening", fastening.name, "thread-match-" + receiver.name, "pass" if compatible else "fail", "Screw and receiver thread diameter/pitch compared", all_ids, screw_thread_mm=dimensions[0], receiver_thread_mm=dimensions[1])
                    if receiver.spec.representation != "catalogue":
                        raise ValueError("Receiver envelope does not establish usable threaded depth")
                    if fastening.grip_mm is None or fastening.thread_depth_mm is None:
                        raise ValueError("Receiver placement cannot be compared without grip and thread depth")
                    bb = female.BoundingBox()
                    start = receiver.offset_mm + bb.zmin
                    end = receiver.offset_mm + bb.zmax
                    fits = abs(start - fastening.grip_mm) <= 1e-5 and fastening.grip_mm + fastening.thread_depth_mm <= end + 1e-5
                    finding("fastening", fastening.name, "receiver-stack-" + receiver.name, "pass" if fits else "fail", "Declared receiver span checked against located catalogue hardware", all_ids,
                        receiver_start_mm=start, receiver_end_mm=end, declared_start_mm=fastening.grip_mm, declared_end_mm=fastening.grip_mm+fastening.thread_depth_mm)
                except Exception as exc:
                    finding("fastening", fastening.name, "receiver-data-" + receiver.name, "unverified", str(exc), all_ids)
            if any(value is None for value in (fastening.grip_mm, fastening.thread_depth_mm, fastening.min_engagement_mm)):
                finding("fastening", fastening.name, "engagement", "unverified", "Declare grip_mm, thread_depth_mm and min_engagement_mm to check engagement", all_ids)
            else:
                try:
                    provider = screw.spec.catalogue()
                    length = screw.spec.length_mm
                    thread_length = getattr(provider, "thread_length", None)
                    if thread_length is None or screw.spec.representation != "catalogue":
                        raise ValueError("Provider does not establish the screw's usable threaded length")
                    screw_start = screw.offset_mm + length - thread_length
                    screw_end = screw.offset_mm + length
                    engaged = max(0, min(screw_end, fastening.grip_mm + fastening.thread_depth_mm) - max(screw_start, fastening.grip_mm))
                    ok = engaged + 1e-7 >= fastening.min_engagement_mm
                    finding("fastening", fastening.name, "engagement", "pass" if ok else "fail", "Thread engagement checked against declared receiver span", all_ids,
                        engagement_mm=engaged, minimum_mm=fastening.min_engagement_mm, grip_mm=fastening.grip_mm, thread_depth_mm=fastening.thread_depth_mm, screw_thread_length_mm=thread_length)
                except Exception as exc:
                    finding("fastening", fastening.name, "engagement", "unverified", str(exc), all_ids)
            if fastening.hole_depth_mm is None:
                finding("fastening", fastening.name, "bottoming", "unverified", "Blind-hole bottom depth or through-hole exit clearance is not declared", all_ids)
            else:
                clearance = fastening.hole_depth_mm - (screw.spec.length_mm + screw.offset_mm)
                finding("fastening", fastening.name, "bottoming", "pass" if clearance + 1e-7 >= fastening.min_tip_clearance_mm else "fail", "Screw tip clearance checked against declared bottom/obstruction depth", all_ids,
                    tip_clearance_mm=clearance, minimum_mm=fastening.min_tip_clearance_mm)
        for item in fastening.hardware:
            if item.spec.representation != "catalogue":
                finding("fastening", fastening.name, "envelope-" + item.name, "unverified", "Hardware geometry is a qualified envelope, not a complete supplier model", all_ids, spec=item.spec.describe())
        if not fastening.access:
            finding("fastening", fastening.name, "access", "unverified", "Tool and insertion access envelopes are not declared", all_ids)
        for access in fastening.access:
            try:
                obstacle_ids = resolve_components(access.obstacles, index)
            except ValueError as exc:
                finding("fastening", fastening.name, "access-" + access.name, "fail", str(exc), all_ids)
                continue
            try:
                if access.envelope is None or not access.obstacles:
                    raise ValueError("Access check requires a solid envelope and explicit obstacle set")
                envelope = shape(access.envelope())
                if not isinstance(envelope, cq.Shape) or not envelope.Solids() or not envelope.isValid():
                    raise ValueError("Access envelope must be a valid native solid")
                blocked = []
                for path in obstacle_ids:
                    model = models[path]
                    if isinstance(model, Mesh):
                        raise ValueError("Native access check unavailable for mesh obstacles")
                    overlap = abs(envelope.intersect(model).Volume()) if _overlaps_bounds(envelope, model, bounds=bounds_for) else 0
                    if overlap > tolerance_mm3:
                        blocked.append({"component_id": path, "overlap_mm3": overlap, "representation": "envelope" if path in envelope_ids else "catalogue"})
                approximate = sorted(envelope_ids.intersection(obstacle_ids))
                confirmed_blocked = [item for item in blocked if item["component_id"] not in envelope_ids]
                status = "fail" if confirmed_blocked else "unverified" if approximate else "pass"
                finding("fastening", fastening.name, "access-" + access.name, status,
                    "Declared access envelope is blocked by a native obstacle" if confirmed_blocked else
                    "Access checked against component envelopes; physical clearance is unverified" if approximate else
                    "Declared access envelope checked against specified obstacles",
                    all_ids + obstacle_ids, blocked=blocked, obstacle_ids=obstacle_ids, envelope_component_ids=approximate)
            except Exception as exc:
                finding("fastening", fastening.name, "access-" + access.name, "unverified", str(exc), all_ids)
        finding("fastening", fastening.name, "load", "unverified", "Clamp preload, strength, hole alignment and material/process allowances are not verified", all_ids)
    if not any((project.joints, project.interfaces, project.fastenings)):
        finding("assembly", "coverage", "declarations", "unverified", "No joint, interface or fastening intent is declared")
    finding("assembly", "coverage", "assembly-sequence", "unverified", "Installed geometry and explicit envelopes do not establish a complete assembly sequence")
    counts = {state: sum(f["status"] == state for f in findings) for state in ("pass", "fail", "unverified")}
    return {"schema_version": 1, "status": "fail" if counts["fail"] else "incomplete" if counts["unverified"] else "pass", "findings": findings,
        "summary": counts, "coverage": {"installed_collisions": "partial" if mesh_ids or envelope_ids or not scan_collisions or kernel_failures else "checked", "component_count": len(index), "pairs_scanned": pairs_scanned,
        "mesh_components": len(mesh_ids), "envelope_components": len(envelope_ids), "kernel_failures": kernel_failures, "joints": len(project.joints), "interfaces": len(project.interfaces), "fastenings": len(project.fastenings),
        "assembly_sequence": "unverified", "operating_motion": "unverified", "material_and_process": "unverified"}}
