# Parts and feature ownership

A Part owns its lazy body builder and named manufacturing features. Shared
`InsertMount` and `ThreadedMount` recipes supply matched roles on participating
parts. Definitions are immutable: adding an assembly connection does not cut or
otherwise edit a part. Author the participating features first, then connect them:

```python
import cadkit as ck

# MOUNT is one shared recipe; BASE and COVER own its respective roles.
assembly = ck.Assembly("fixture")
base = assembly.add("base", BASE)
cover = assembly.add("cover", COVER)
assembly.fix(base, at=ck.Frame((0, 0, 40)))
assembly.connect("mount", MOUNT,
    through=cover.feature("mount"), into=base.feature("mount"))
PROJECT = assembly.as_project()
```

See the runnable [insert mount](../examples/insert_mount.py) example.
[Manufacturing features](manufacturing-features.md) owns role-frame conventions,
holes, fits, secondary operations and layered mounts;
[assemblies](declarative-assemblies.md) owns placement and hardware relationships.
[API](api.md) covers print poses, inventory and project compilation.

Native feature application verifies that every hole site intersects the body.
A blind pocket's overshoot extends through its open end only; its nominal bottom
stays fixed. `Part.finalize` can perform a final native operation, such as an
outer-face partition for STEP export. It does not update authored feature metadata,
so final geometry still needs checks. Native-only features and finalizers reject
mesh bodies.

Part and installed-component metadata expose named features, frames, manufacturing
and secondary operations with provenance. The desktop does not offer feature
editing or face selection. Operations such as tapping remain declared requirements,
not operations the framework physically performs.

Mounts derive grip and hardware placement from the authored roles, but screw
lengths and pocket dimensions stay explicit. Frame alignment alone does not prove
contact, stock thickness, load capacity or fit. Preserve supplied envelopes and
unknown thread depths as qualified evidence; use [mechanics](mechanics.md) for validation.
