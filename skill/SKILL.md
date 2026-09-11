---
name: cadkit
description: Work on CadKit CAD projects day to day. Edit CadQuery parts and parameters, inspect the user's live selection, declare joints, interfaces and fastenings, measure fits, control the viewer, annotate designs, export, render and slice. Also supports setting up or migrating a project when requested.
---

# CadKit

Use the consumer's existing CadKit project and commands. Start with its README,
local workflow guide (often `docs/cadkit.md`), and Project adapter as needed.
Ordinary design work continues the existing setup; installation and migration
are separate tasks, not prerequisites to repeat each session.

Choose references for the task:

- Working alongside the user in the app: [interaction](references/interaction.md).
- Joints, intended interfaces, cq_warehouse fasteners and assembly validation: [mechanics](references/mechanics.md).
- Editing geometry and parameters: [modelling loop](references/agent-guide.md).
- Parts, Components, Assemblies and checks: [API](references/api.md).
- Export, Blender and slicing: [workflows](references/workflows.md).
- MCP tools, measurement and annotation details: [desktop](references/desktop.md).
- File formats and units: [contracts](references/contracts.md).
- Setup or import failures: [install](references/install.md).
- Requested adoption of an existing project: [migration](references/migration.md).

For “this part” or “what I selected”, read the live app's `get_state` and
`inspect` through available CadKit MCP tools or the consumer's documented MCP
helper. Use returned IDs and revision; confirm the app's project directory and
reference match this checkout. A skill supplies guidance, not an MCP connection.
If the app is unavailable, use CLI discovery for named parts; do not invent a
live selection. Discussion of a possible design change remains discussion
until the user asks for implementation.

Keep geometry in the consumer's Python builders. A Part is a manufacturing
definition; a Component is an installed instance. Print pose and installed
placement are distinct transforms, applied once. Assemblies organize already
placed geometry. Preserve quantities, materials, variants and geometry
provenance. Parameters describe source inputs; they are not live UI setters.

Use `describe` and `inspect` for discovery. After a geometry edit, run relevant
consumer tests and CadKit checks and inspect the changed geometry visually.
For a live app, confirm a successful new build before reporting the result:
a failed rebuild retains the old model. A valid solid or an empty passing
check set alone does not establish fit or manufacturing readiness.

Follow the consumer setup for the active CadKit runtime. An installed
`release.json` identifies a supplied trial, but an explicit development-source
configuration takes precedence over an older receipt. Do not substitute a
registry package or another checkout implicitly.
Keep frozen releases unchanged. For a migration, record baseline, equivalence
evidence, retained adapters and adoption gaps in the consumer.
