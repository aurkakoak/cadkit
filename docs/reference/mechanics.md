# Mechanical contracts and validation

```python
from cadkit import Joint, Interface, Fastening, AccessEnvelope
```

These mechanical records describe installed geometry. They do not move
parts or cut holes. [Assemblies](design-assemblies.md) can generate
these records from their local connection graph.

Component references may be an unambiguous leaf name or a full URL-encoded
assembly path. Duplicate leaf names require full paths. Discover live app IDs
from `get_state`; don't reconstruct them from a screenshot or reuse stale IDs.

::: cadkit.mechanics.Joint
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - describe

::: cadkit.mechanics.Interface
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - describe

::: cadkit.mechanics.Fastening
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - describe

::: cadkit.mechanics.AccessEnvelope
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 2
      members:
        - describe

## Validation

::: cadkit.mechanics.validate_mechanics
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

The corresponding Project method is the convenient entry point:

```python
report = PROJECT.validate_mechanics()
```

| Overall status | Meaning |
| --- | --- |
| `pass` | The declared checks and recorded coverage passed |
| `fail` | At least one confirmed failure exists |
| `incomplete` | No confirmed failure, but some checks or coverage are unverified |

Unknown values remain unknown. Contact at one pose, simplified supplier
geometry, and a clear tool envelope do not establish loaded strength,
manufacturing tolerances, or a complete assembly sequence.

See [preflight](export.md#preflight) for how reports gate manufacturing exports,
and [file contracts](contracts.md#mechanical-validation) for report fields.

## Hardware bill of materials

::: cadkit.mechanics.hardware_bom
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
