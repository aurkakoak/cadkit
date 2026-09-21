# Fasteners

```python
from cadkit import FastenerSpec, HardwareItem, FastenerSite
```

Fastener geometry comes from the pinned `cq_warehouse` catalogue or an explicit
supplier factory. A specification describes a purchased item; a HardwareItem
is a named role in a stack; a FastenerSite places that stack.

## Supported catalogue kinds

| `kind` | Default `standard` | Length convention |
| --- | --- | --- |
| `socket_head_cap_screw` | `iso4762` | Under-head shaft length |
| `set_screw` | `iso4026` | Drive-end to tip |
| `hex_head_screw` | `iso4017` | Under-head shaft length |
| `button_head_screw` | `iso7380_1` | Under-head shaft length |
| `hex_nut` | `iso4032` | Normally omitted |
| `plain_washer` | `iso7089` | Normally omitted |
| `heat_set_insert` | `McMaster-Carr` | Explicit length for engagement contracts |

`countersunk_screw` is rejected by the current insertion convention. You can
still model a [CountersunkHole](design-features.md), but must not infer that
corresponding catalogue hardware is supported.

Thread strings are provider keys, such as `M3-0.5`; vendor inserts may use
provider-specific size strings. Dimensions and simple hardware geometry are
loaded lazily. Catalogue support depends on the pinned provider's tables.

::: cadkit.fasteners.FastenerSpec
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - id
        - describe
        - catalogue
        - dimensions
        - clearance_diameter
        - clearance_cutter
        - build

::: cadkit.fasteners.HardwareItem
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - describe

::: cadkit.fasteners.FastenerSite
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - place
        - describe

For quantities, engagement checks, and named relationships, see
[Fastening and mechanical validation](mechanics.md).
