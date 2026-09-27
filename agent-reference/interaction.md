# Shared review

## Connect

Use registered CadKit MCP tools or the consumer's documented MCP helper. The
server attaches to an open app; it does not launch it. For missing tools or a
failed connection, use [recovery](recovery.md).

Read `get_state`: confirm `projectDir`, `reference`, ready build status and
`revision` match the intended checkout/worktree. For “this part”, resolve the
live selection, then `inspect`. With no selection, use an explicitly named target
or ask which item is meant. A Component ID identifies an installed occurrence;
a Part name identifies its manufacturing definition, possibly with many or no
installed occurrences. Use returned IDs and the current revision, not labels.
Read the connected tool schemas for arguments; refresh state after stale-revision errors.

## Show the finding

Prefer a few attached notes explaining the finding, evidence and decision or
next action. Distinguish measurements from assumptions and unknown interfaces.
Stable task-specific note IDs let you revise your findings without duplicates;
keep the user's other annotations.

| Need | Tool and behaviour |
| --- | --- |
| Present findings together | `present_review` upserts target-attached notes, highlights participants and preserves selection and unrelated notes. Default focus reveals and frames participants; `focus:false` preserves camera and visibility. |
| Inspect a hidden interface or hole alignment | `section_view` shows native 2D sections or wireframe projections with shared notes. Read [2D geometry](desktop.md#2d-geometry) for plane conventions and limits. |
| Point out an object | `highlight` preserves selection; use `select` when changing selection serves the task. |
| Show a clearance | `measure` between two installed Component IDs returns whole-object minimum distance. `show:true` selects them and displays a dimension; `show:false` preserves selection. Zero can mean contact or overlap; use geometry checks for interference. Label mesh approximations. |
| Attach one finding or draw an arrow | `annotate`; see [note placement](desktop.md#note-placement) for coordinates and lifetime. |
| Inspect the view | `screenshot`; view the returned image or saved PNG before drawing visual conclusions. |

`visibility.isolate` toggles isolation: repeating the expanded target set restores
prior visibility. Check existing isolation first. `show` with no IDs reveals all.
`camera.fit` frames visible objects; save the returned pose for a temporary view.
Zoom is an absolute scale. Leave a useful, legible view when presenting findings.

For attachment or hardware questions, use [mechanics](mechanics.md). For
fabrication drawings or unsupported analysis, another tool may fit better than
the native review view. Do not infer exact dimensions from pixels.

## Verify an edit

Edit through the [modelling guide](agent-guide.md), then confirm a successful
new build and revision. Failed rebuilds retain old geometry; a visible model
alone does not verify the edit. Re-resolve affected IDs and refresh measurements
and notes. A retained target-attached note does not make its old evidence current.
Sections clear on rebuild; regenerate them if still useful. Inspect a screenshot
to check the changed geometry and the legibility of the review.

Notes are session-only. Save requested durable decisions in consumer source or
documentation. Keep the chat handoff concise and refer to findings shown in the app.
