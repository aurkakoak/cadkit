"""Feature-bound hardware within a manufactured part, without placement edges."""
from dataclasses import dataclass
from typing import ClassVar
import math
from ..fasteners import FastenerSpec, FastenerSite, HardwareItem
from ..mechanics import Fastening, Interface
from .manufacturing import Hole, CounterboredHole, NutPocket, TappedHole, DBore
from .frames import positive
from .mount_interfaces import _thread_diameter, _region, _hardware_ref


def _dot(left,right):
    return sum(a*b for a,b in zip(left,right))


def _delta(left,right):
    return tuple(a-b for a,b in zip(left,right))


@dataclass(frozen=True)
class CaptiveNutFastening:
    """A screw through an owned hole into an owned, opposing nut pocket."""
    feature_roles: ClassVar[tuple[str, ...]] = ("through", "nut")
    screw: FastenerSpec
    nut: FastenerSpec
    nut_thickness: float

    def __post_init__(self):
        if not self.screw.kind.endswith("screw") or self.screw.kind == "set_screw" or self.nut.kind != "hex_nut":
            raise ValueError("Captive nut fastening requires a headed screw and hex nut")
        if self.screw.size != self.nut.size:
            raise ValueError("Captive screw and nut threads must match")
        positive(self.nut_thickness,"Nut thickness")

    def validate(self,features):
        if set(features) != {"through","nut"} or type(features["through"]) not in {Hole,CounterboredHole} or not isinstance(features["nut"],NutPocket):
            raise TypeError("Captive nut fastening binds through=Hole and nut=NutPocket")
        if features["through"].pattern is not None or features["nut"].pattern is not None:
            raise ValueError("Captive attachments require individual named hole and pocket features")
        if features["nut"].thread != self.nut.size:
            raise ValueError("Pocket and nut thread designations must match")
        diameter = _thread_diameter(self.screw.size)
        if diameter is not None and features["through"].diameter <= diameter:
            raise ValueError("Captive screw requires positive clearance in its owned hole")
        if features["nut"].depth < self.nut_thickness:
            raise ValueError("Nut pocket must accommodate the declared nut thickness")

    def fastening(self,name,*,features,frames,components):
        self.validate(features)
        seat,pocket = frames["through"],frames["nut"]
        recess = features["through"].recess.depth if isinstance(features["through"],CounterboredHole) else 0
        seat_origin = tuple(p+a*recess for p,a in zip(seat.origin,seat.z))
        delta = _delta(pocket.origin,seat_origin)
        separation = _dot(delta,seat.z)
        if _dot(seat.z,pocket.z) > -1+1e-6 or any(abs(v-separation*a)>1e-6 for v,a in zip(delta,seat.z)):
            raise ValueError("Nut pocket and screw hole must share an axis with opposing entry faces")
        grip = separation-features["nut"].depth
        if grip < 0 or separation+recess > features["through"].depth+1e-6:
            raise ValueError("Nut pocket must be reached by the declared clearance hole")
        return Fastening(name,components,sites=(FastenerSite("1",seat_origin,seat.z,x_axis=pocket.x),),
            hardware=(HardwareItem("screw",self.screw),HardwareItem("nut",self.nut,grip)),kind="through",
            grip_mm=grip,thread_depth_mm=self.nut_thickness,min_engagement_mm=self.nut_thickness,
            description="Captive nut closure derived from the owned clearance hole and opposing nut pocket.")

    def interfaces(self,fastening,*,features,frames,hardware_root):
        site = fastening.sites[0]
        origin = tuple(p+a*fastening.grip_mm for p,a in zip(site.origin,site.axis))
        diameter = _thread_diameter(self.screw.size)
        if diameter is None:
            return ()
        length = min(self.nut_thickness,self.screw.length_mm-fastening.grip_mm)
        if length <= 0:
            return ()
        return (Interface(fastening.name+"-thread",
            (_hardware_ref(hardware_root,fastening,site,"screw"),_hardware_ref(hardware_root,fastening,site,"nut")),
            kind="threaded",region=_region(origin,site.axis,diameter,length),
            max_overlap_mm3=math.pi/4*diameter**2*length+.001,
            description="Bounded nominal screw/nut thread engagement. Physical thread fit remains unverified."),)

    def describe(self):
        return {"kind":"captive-nut-fastening","screw":self.screw.describe(),"nut":self.nut.describe(),
                "nut_thickness":self.nut_thickness}


@dataclass(frozen=True)
class SetScrew:
    """A radial set screw whose tip stops at an owned D-bore's flat plane."""
    feature_roles: ClassVar[tuple[str, ...]] = ("thread", "stop")
    screw: FastenerSpec
    minimum_engagement: float | None = None

    def __post_init__(self):
        if self.screw.kind != "set_screw":
            raise ValueError("SetScrew attachment requires an ISO set-screw specification")
        if self.minimum_engagement is not None:
            positive(self.minimum_engagement,"Minimum set-screw engagement")

    def validate(self,features):
        if set(features) != {"thread","stop"} or not isinstance(features["thread"],TappedHole) or not isinstance(features["stop"],DBore):
            raise TypeError("SetScrew binds thread=TappedHole and stop=DBore")
        if features["thread"].thread != self.screw.size:
            raise ValueError("Set screw and tapped feature threads must match")
        diameter = _thread_diameter(self.screw.size)
        if diameter is not None and features["thread"].pilot_diameter >= diameter:
            raise ValueError("Set-screw pilot must leave material for its thread")
        if features["thread"].pattern is not None or features["stop"].pattern is not None:
            raise ValueError("Set-screw attachments require individually named features")

    def fastening(self,name,*,features,frames,components):
        self.validate(features)
        thread,stop = frames["thread"],frames["stop"]
        if _dot(thread.z,stop.x) > -1+1e-6:
            raise ValueError("Set-screw pilot must point inward toward the D-flat plane")
        plane = tuple(p+a*features["stop"].flat for p,a in zip(stop.origin,stop.x))
        travel = -_dot(_delta(plane,thread.origin),stop.x)
        threaded_depth = features["thread"].thread_depth or features["thread"].depth
        if travel < self.screw.length_mm-1e-6 or travel > threaded_depth+1e-6:
            raise ValueError("Set screw must fit between its D-flat stop and the declared thread entry")
        tip = tuple(p+a*travel for p,a in zip(thread.origin,thread.z))
        relative = _delta(tip,stop.origin)
        axial = _dot(relative,stop.z)
        tangent_axis = (stop.z[1]*stop.x[2]-stop.z[2]*stop.x[1],
                        stop.z[2]*stop.x[0]-stop.z[0]*stop.x[2],
                        stop.z[0]*stop.x[1]-stop.z[1]*stop.x[0])
        chord = math.sqrt((features["stop"].diameter/2)**2-features["stop"].flat**2)
        if not -1e-6 <= axial <= features["stop"].depth+1e-6 or abs(_dot(relative,tangent_axis)) > chord+1e-6:
            raise ValueError("Set-screw tip must lie on the finite D-bore flat")
        seat = tuple(p-a*self.screw.length_mm for p,a in zip(tip,thread.z))
        return Fastening(name,components,sites=(FastenerSite("1",seat,thread.z,x_axis=thread.x),),
            hardware=(HardwareItem("screw",self.screw),),kind="tapped",grip_mm=0,
            thread_size=self.screw.size,thread_depth_mm=self.screw.length_mm,
            min_engagement_mm=self.minimum_engagement,
            description="Set-screw tip is derived from the D-bore flat plane; actual shaft flat and retention remain unverified.")

    def interfaces(self,fastening,*,features,frames,hardware_root):
        diameter = _thread_diameter(self.screw.size)
        if diameter is None:
            return ()
        site = fastening.sites[0]
        length = self.screw.length_mm
        overlap = math.pi/4*max(0,diameter**2-features["thread"].pilot_diameter**2)*length
        return (Interface(fastening.name+"-thread",
            (_hardware_ref(hardware_root,fastening,site,"screw"),fastening.components[0]),kind="threaded",
            region=_region(site.origin,site.axis,diameter,length),max_overlap_mm3=overlap+.001,
            description="Set-screw thread interference bounded by its owned pilot and D-flat tip datum; retention is unverified."),)

    def describe(self):
        return {"kind":"set-screw","screw":self.screw.describe(),"minimum_engagement":self.minimum_engagement}
