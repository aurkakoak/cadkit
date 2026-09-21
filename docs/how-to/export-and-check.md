# Export parts and run checks

Start with an importable `project:PROJECT` and a
[CadKit Python environment](install.md#set-up-a-python-project-for-the-cli).
Run these commands from the project directory. Substitute your own part names
for `box` and `lid`.

## Choose the manufacturing set

```sh
uv run cadkit --project project:PROJECT list
uv run cadkit --project project:PROJECT inspect lid
uv run cadkit --project project:PROJECT build box lid --output-dir build/enclosure
```

Native parts produce STL and STEP files. The build also writes `manifest.json`
with artifact hashes, manufacturing quantities, groups and available assembly
review results. Print rotation is applied before export, followed by moving
the lowest Z point onto the bed.

To build every production part:

```sh
uv run cadkit --project project:PROJECT build all
```

`all` excludes parts declared with `production=False`, such as fit coupons.
Name those parts explicitly when you need them. Use `--group enclosure` to
restrict `all` to a registered manufacturing group.

Use a separate output directory for each set you want to retain. A later
partial build replaces the directory's manifest with the new selection, even
if old files are still present. The manifest, rather than a folder listing,
defines the build.

## Run geometric checks

```sh
uv run cadkit --project project:PROJECT check
```

This runs the project's declared `Check` objects and returns a failure status
when one fails. For forbidden interference, a check builder returns the
intersection of two shapes. An empty intersection passes. Failed overlaps
write witness geometry alongside the report in `build/checks/clearance-failures`.

For example, in a project that defines `installed_box()` and
`installed_lid()` shape builders, add this check to `Project(checks=...)`:

```python
from cadkit import Check

no_overlap = Check(
    "box-lid-overlap",
    lambda: installed_box().intersect(installed_lid()),
)
```

Here the two builder names refer to your own installed-coordinate geometry;
the check must use the same placement as the assembly. A project with no
registered checks passes this command without testing any interfaces.

## Review the installed assembly

```sh
uv run cadkit --project project:PROJECT validate-assembly
uv run cadkit --project project:PROJECT bom
```

Read the `status`, findings and coverage in `build/assembly-validation.json`.
The report can be `pass`, `fail` or `incomplete`. An incomplete report currently
returns exit code 0, so automation should inspect the report's status as well
as the process exit code.

To review a manufacturing selection in its complete assembly context:

```sh
uv run cadkit --project project:PROJECT validate-assembly --parts box lid
```

Projects with mechanical declarations run assembly validation before CLI part
builds. Desktop part exports always perform this review. A confirmed failure
blocks the export. Correct the model or, for a deliberate exception, supply
`--validation-override "specific reason"` to `build`. The reason stays with
the exported evidence; it does not turn the failed check into a pass.

## Export an assembled STEP

```sh
uv run cadkit --project project:PROJECT assembly --output build/enclosure.step
```

This preserves installed component placement rather than print orientation.
Add `--view service` for a named project view, or `--printed-only` to omit
hardware. Mesh geometry cannot become native editable STEP; omitted meshes
are recorded in an accompanying manifest.

For a discussion of what a passing report establishes, see
[Validation and evidence](../explanation/validation-and-evidence.md).
The [CLI reference](../reference/cli.md) lists command options.
