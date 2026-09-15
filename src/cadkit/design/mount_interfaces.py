"""Bounded fit contracts derived from authored mount roles and hardware.

Only the material swept by a known insert/thread can be exempted. Incomplete
supplier data never becomes a fabricated blind-hole depth or engagement claim.
"""
from functools import partial
import math
import re
from urllib.parse import quote
import cadquery as cq
from ..mechanics import Interface

# Kernel tolerance only, not manufacturing or fit allowance.
_REGION_TOLERANCE = 1e-4
_VOLUME_TOLERANCE = 1e-3


def _thread_diameter(size):
    """Metric nominal diameter is authored data, never a geometry query."""
    match = re.fullmatch(r"M([0-9]+(?:\.[0-9]+)?)-([0-9]+(?:\.[0-9]+)?)", size)
    if match is None:
        return None
    diameter = float(match.group(1))
    return diameter if math.isfinite(diameter) and diameter > 0 else None


def _region(origin, axis, diameter, depth):
    tolerance = _REGION_TOLERANCE
    return partial(cq.Solid.makeCylinder, diameter/2+tolerance, depth+2*tolerance,
                   tuple(p-a*tolerance for p,a in zip(origin,axis)), axis)


def _hardware_ref(hardware_root, fastening, site, item):
    return "/".join((hardware_root.rstrip("/"), quote(fastening.name,safe=""),
                     quote(site.name,safe=""), quote(item,safe="")))


def mount_interfaces(mount, fastening, *, receiver, hardware_root, receiver_representation=None):
    """Return world-space contracts paired with one resolved fastening.

    ``receiver_representation`` is supplied by the owning Purchased definition,
    not inferred from missing hole geometry. Unknown thread depths are allowed
    only for explicit supplier envelopes, bounded by the installed screw's
    actual intrusion and marked as unverified by mechanical validation.
    """
    if receiver.mount is not mount or receiver.role != mount.receiver_role:
        raise ValueError("Bounded interfaces require this mount's receiving role")
    screw_diameter = _thread_diameter(mount.screw.size)
    if screw_diameter is None:
        # No nominal diameter evidence means no automatic overlap exemption.
        return ()
    intrusion = mount.screw.length_mm-fastening.grip_mm
    result = []
    for site in fastening.sites:
        origin = tuple(p+a*fastening.grip_mm for p,a in zip(site.origin,site.axis))
        prefix = f"{fastening.name}-{site.name}"
        screw_ref = _hardware_ref(hardware_root,fastening,site,"screw")
        if mount.receiver_role == "insert":
            insert_diameter = mount.pocket.insert_outer_diameter
            length = mount.insert.length_mm
            insert_ref = _hardware_ref(hardware_root,fastening,site,"insert")
            if insert_diameter is not None:
                overlap = math.pi/4*max(0,insert_diameter**2-mount.pocket.diameter**2)*length
                result.append(Interface(
                    prefix+"-insert-pocket",(insert_ref,fastening.components[-1]),kind="press_fit",
                    region=_region(origin,site.axis,insert_diameter,length),
                    max_overlap_mm3=overlap+_VOLUME_TOLERANCE, max_gap_mm=0.001,
                    description=("Declared insert outer diameter and authored pilot bound the installation region. "
                                 "Material flow, knurl retention and process capability remain unverified.")))
            engaged = min(length,intrusion)
            if engaged > 0:
                result.append(Interface(
                    prefix+"-thread",(screw_ref,insert_ref),kind="threaded",
                    region=_region(origin,site.axis,screw_diameter,engaged),
                    max_overlap_mm3=math.pi/4*screw_diameter**2*engaged+_VOLUME_TOLERANCE,
                    description="Bounded screw/insert nominal thread region; usable thread and physical fit require supplier evidence."))
        elif mount.receiver_role == "threaded" and intrusion > 0:
            if receiver.supplied:
                if receiver_representation != "envelope":
                    # Detailed purchased geometry with undocumented threads
                    # supplies no evidence for removing an observed collision.
                    continue
                depth = min(intrusion,mount.thread_depth) if mount.thread_depth is not None else intrusion
                overlap = math.pi/4*screw_diameter**2*depth
                description = ("Known installed screw intrusion into an explicitly supplied component envelope. "
                               "This region is not evidence of blind-hole depth or usable thread engagement; physical fit remains unverified.")
            else:
                depth = min(intrusion,mount.thread_depth)
                overlap = math.pi/4*max(0,screw_diameter**2-mount.pilot_diameter**2)*depth
                description = ("Authored pilot and finished thread dimensions bound the region modified by the declared "
                               "thread-forming operation. Material and process capability remain unverified.")
            if depth > 0:
                result.append(Interface(prefix+"-thread",(screw_ref,fastening.components[-1]),kind="threaded",
                    region=_region(origin,site.axis,screw_diameter,depth),
                    max_overlap_mm3=overlap+_VOLUME_TOLERANCE,description=description))
    return tuple(result)
