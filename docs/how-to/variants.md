# Variants

Variants select alternative parts or assemblies before compiling a project. Each
selection has its own installed geometry, manufacturing inventory, hardware and
checks. Existing projects need no changes unless they expose choices.

```python
import cadkit as ck


def make_base():
    base = ck.Assembly("base")
    construction = base.variant(
        "base", ck.Variant(("printed", "hybrid"), default="printed", label="Base"),
    )
    definition = printed_base() if construction == "printed" else hybrid_base()
    base.fix(base.add("shell", definition))
    return base


def make_project():
    machine = ck.Assembly("machine")
    machine.fix(machine.add("base", make_base()))
    return machine.as_project()


VARIANTS = ck.Variants(make_project, dependencies=("inputs/materials.json",))
PROJECT = VARIANTS.project()
```

`PROJECT` is an ordinary `ck.Project`, so existing Python consumers continue to
work. `VARIANTS.project(base="hybrid")` builds a separate configured snapshot;
it does not mutate the default. The subsystem declares and resolves its own choice
with `assembly.variant(...)`. Parents compose it normally, without forwarding
selection arguments. CadKit discovers the owning assembly's installed path and
places the selector on that tree row, including while the row is collapsed.

Choice keys must be unique within a project. Repeated independently configurable
subsystems must use distinct keys. `selected=` on `assembly.variant` supports
standalone construction; an active `Variants.project` selection takes precedence.
Unknown choices/options fail, and failed builders cannot leak their selections
into later builds. Builders must return matching geometry and checks. Geometry
should remain lazy.

For genuinely project-wide choices, the original
`Variants(builder, choices={...})` form remains available: it passes declared
choices as keyword arguments and places their controls on the root assembly row.
Do not declare the same key both locally and in `choices`.

Use one choice for alternatives that must change together. Independent choices
are separate keys. A builder may reject incompatible combinations with a useful
error. Inactive definitions do not enter the manufacturing inventory; `extra_parts`
continues to mean intentionally registered uninstalled parts.

Keep instance paths stable for unchanged components. A replaced part and a
multi-part replacement can share their containing slot's name, but do not reuse a
leaf identity for an unrelated component. Export public ports/features from nested
assemblies when the parent needs to connect to them.

## Desktop and agents

Each owning assembly row shows its choice. The selector shows the requested choice
while building and returns to the displayed configuration on failure. The old
model remains available during construction. Camera position and surviving
component selections follow the switch; measurements and validation reset.

Successful selections are saved per project in the app's local preferences.
`get_state.project.variants` lists choices; `variant_selection` identifies the
actual displayed model. MCP `set_variants` accepts its current `revision` and a
partial `selection` map. Read the returned new revision before further operations.

Three recently used configurations are cached as complete native workers, scene
data and prepared viewport scenes. The first visit builds geometry; subsequent
visits reuse it. After the viewport has painted, idle work prewarms nearby choices
in separate CAD processes. Speculation fills unused cache slots only, builds one
configuration at a time, and never changes the displayed model or error state.
An explicit request reuses a matching in-flight warm build or cancels a different
one. Warming prepares native geometry and tessellation; GPU viewport scenes are
created only when visited, so warming does not block the renderer with hidden
scene construction. Other combinations are built on demand. Each activation has a
new revision even when the geometry is cached, so late results cannot become
current again after switching away and back.

Python source edits invalidate the cache, including imported source outside the
project directory. Declare other inputs using `dependencies`: file or directory
paths, relative to the desktop project directory or absolute. Input directories
must not contain generated outputs. Runtime/user-data directories and conventional
`build`/`dist` directories are excluded from watching. Arbitrary network, clock and
environment dependencies are not inferred. **Rebuild** bypasses the cache;
restart the app after changing installed runtime dependencies. Caches are bounded
and session-local; they are not persisted across app restarts.

## CLI and output

```sh
cadkit --project project:PROJECT --variant base=hybrid describe
cadkit --project project:PROJECT --variant base=hybrid check
cadkit --project project:PROJECT --variant base=hybrid assembly --output build/hybrid.step
```

Repeat `--variant NAME=OPTION` before the command for multiple choices. Omitted
choices retain the exported project's selection. Part-build, assembly and render
manifests record `variant_selection`. Separate output directories preserve exports
of different configurations. Laser-cut parts remain in Parts and fabrication
exports, but are excluded from the desktop Print panel.
