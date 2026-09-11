# Working alongside the user

Use the consumer's launch commands, Python environment and Project reference.
The desktop and agent must target the same checkout: each worktree is a separate
app session. Read the local workflow guide before assuming generic paths.

## Connect and inspect

Use available CadKit MCP tools. If they are not registered, look for the
consumer's documented MCP command helper; it can attach over stdio without
changing the agent's global settings. Otherwise, the app's plug icon supplies
the client connection configuration. The MCP server attaches to an open app;
it does not launch the desktop. Use the project's launch command when opening
the app is part of the task.

Call `get_state` to confirm `projectDir`, `reference`, build `status` and
`revision`. Read the current selection and Part definition, then use `inspect`
for details. A Part may have many installed Components or none, as with a
calibration coupon. Use a Component ID for an installed location and a Part
name for manufacturing metadata or export. With no selected item, continue
from an explicitly named target or ask which item the user means.

Read tool schemas from the connected server when needed. Do not guess IDs from
labels, reuse IDs from another project, or infer exact dimensions from pixels.
On a stale revision, read fresh state and resolve the intended target again.
If the host blocks the app's local socket, use the host's permission mechanism;
do not weaken the bridge's permissions. Report a connection problem accurately
instead of treating it as an empty selection.

## Explain in the viewer

- Use `highlight` to point out objects while preserving the user's selection.
  Use `select` when changing selection helps the requested task.
- Use `visibility` with `isolate` to solo a component or branch. Repeating the
  same expanded target set restores its prior visibility. Check current
  isolation before issuing it; it is a toggle. `show` with no IDs reveals all.
- Use `camera` to choose an orientation or fit visible geometry. Save the
  returned camera pose when a temporary inspection should be reversible;
  `zoom` is an absolute scale.
- Use `measure` on two installed Component IDs. `show:true` selects the pair
  and displays a dimension; `show:false` obtains the answer without changing
  selection. This is whole-object minimum clearance, not face/edge selection.
  Zero can mean contact or overlap. For interference, use geometry checks.
  Report mesh approximations and distinguish bounds from native dimensions.
- Use `annotate` with a stable note ID and `target` for a Markdown note shared
  with the assembly row. Keep notes short; longer text can expand. Target-only
  notes follow rebuilds; explicit coordinate notes and highlights clear on
  rebuild. Notes are session-only. Save requested durable design decisions in
  the consumer's source or documentation.
- Use `screenshot` to inspect the viewport or whole window. View the returned
  image (or the helper's saved PNG) before drawing visual conclusions. Keep
  existing user annotations; use note IDs to update or remove your own notes.

See the supplied desktop reference for argument schemas, coordinate spaces
and examples. Leave a useful final view for the user when the task calls for it.

## Edit and verify

Locate the Part builder, installed placement and parameter source before
editing. Follow the [modelling loop](agent-guide.md) and the consumer's design
interfaces. Edit Python inputs/builders rather than generated STL/STEP/Blender
files. Changing one Part may affect every installed instance.

Run checks relevant to the changed interface. The desktop watches Python files
and builds in a fresh worker; read state after the rebuild and verify successful
status and a new revision. Failed builds retain the previous geometry, so a
visible model is not proof that the edit succeeded. Re-resolve affected IDs,
remeasure and inspect a screenshot when that helps validate the change.

For fabrication, use Part print poses and the intended quantities and material
set. Read `slicer_settings` before `slice_parts`; monitor the returned job with
`slice_status`. Saved profiles are configured in the app's Print panel. For
manual preparation, `prepare_parts` opens the exported STLs in the slicer.
Use the [workflows](workflows.md) for CLI exports and Blender presentation.
Slicing generates estimates and artifacts; it does not submit to a printer.
