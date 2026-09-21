# Use catalogue fasteners and fit coupons

Use this guide when you need a clearance hole for known hardware, or want to
choose a printed bore allowance from a physical test. You need CadKit installed
in your project's Python environment and the intended hardware dimensions.

## Read the catalogue dimensions

CadKit supplies simplified native hardware geometry through its pinned
cq_warehouse catalogue. For a socket-head M3 screw, specify both pitch and
length:

```python
from cadkit import FastenerSpec

screw = FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=12)
print(screw.dimensions())
print(screw.clearance_diameter(fit="Normal"))
```

The first result includes available thread, head and clearance dimensions in
millimetres. Missing supplier dimensions remain `None`; do not infer usable
thread depth from an envelope's bounding box. Screw length stays an explicit
design choice.

## Cut a clearance hole

This example cuts one hole through a 4 mm plate, with 0.1 mm of additional
**diametral** allowance:

```python
import cadquery as cq
from cadkit import FastenerSite, FastenerSpec

screw = FastenerSpec("socket_head_cap_screw", "M3-0.5", length_mm=12)
plate = cq.Workplane("XY").box(30, 20, 4, centered=(True, True, False)).val()
site = FastenerSite("mount", origin=(0, 0, -0.1), axis=(0, 0, 1))
cutter = site.place(screw.clearance_cutter(4.2, allowance_mm=0.1))
plate = plate.cut(cutter)
```

The cutter starts below the plate and ends above it to avoid coincident boolean
faces. A `FastenerSite` points along the screw's insertion direction. It places
the cutter or hardware; declaring it alone does not cut the plate.

For two parts that share a mounting pattern, use a shared `InsertMount` or
`ThreadedMount` in `cadkit.design` instead of duplicating hole locations. The
[tutorial](../tutorials/index.md) introduces that workflow; the
[feature reference](../reference/design-features.md) describes its dimensions.

## Print a bore coupon

Save this complete project as `calibration.py`:

```python
from cadkit import Part, Project
from cadkit.fits import fit_coupon

ALLOWANCES = (-0.1, 0.0, 0.1, 0.2, 0.3)


def coupon():
    return fit_coupon(4.0, ALLOWANCES, height=6, wall=3)


PROJECT = Project(
    "bore-calibration",
    parts=(Part(
        "bore-coupon", coupon, group="calibration", material="PETG",
        production=False,
        notes="Increasing X: -0.1, 0.0, +0.1, +0.2, +0.3 mm diametral allowance.",
    ),),
    components=lambda **options: [],
)
```

Export the optional part by name:

```sh
uv run cadkit --project calibration:PROJECT build bore-coupon --output-dir build/calibration
```

The coupon has five bores in increasing X order, with diameters from 3.9 to
4.3 mm. The mapping is recorded in the Part notes; the model has no embossed
labels. Print it with the intended material, orientation and slicer settings,
then try the actual mating item. Record the selected allowance and process
settings in your project.

Use the result for a matching feature:

```python
from cadkit.fits import Bore

shaft_bore = Bore(nominal_diameter=4.0, diametral_allowance=0.2)
```

The `0.2` here illustrates a recorded result; it is not a recommended fit for
every printer or material. `Bore` and `BearingSeat` record explicit allowances
and do not predict process accuracy.

See [fastener reference](../reference/fasteners.md) for available families and
[geometry and fits](../reference/geometry.md) for coupon and cutter APIs.
