# The edit, rebuild and inspect loop

The Python project is the source of the model. The desktop displays a built
revision of that source, and an attached agent observes the same desktop
session as the person using it. Keeping those three states explicit makes
collaboration more reliable.

## The app is a view of executable source

Opening a project runs its Python builders. A local Python worker keeps the
native geometry used for measurement and export; the viewer receives geometry
for display. Saving a Python file starts a rebuild in a fresh worker, so old
module imports do not hide the change.

The app replaces the previous worker only after a successful build. If an edit
raises an exception, the last successful model remains visible while the
failure is reported. This preserves a useful working view, but means that
seeing a model is not evidence that the latest edit succeeded. Build status
and revision are part of every meaningful inspection.

Manufacturing parameters are descriptive metadata today. They help a reader
or agent find the source of a dimension, but are not live controls that modify
the model. An agent changes Python through its ordinary editing tools, then
checks the resulting build.

## The skill and MCP have different jobs

The CadKit skill provides modelling instructions and reference material. MCP
connects the agent to the running app's state and operations: selection,
inspection, measurement, view controls, notes, screenshots and slicing jobs.
Installing the skill does not establish that connection.

The connection is scoped to a project directory and import reference. It sees
the user's actual camera and selection, which makes requests such as “check
this lid” meaningful. A second checkout is a separate session; identical
filenames do not make it the same model.

MCP is not an embedded coding agent or a general shell. Source edits use the
agent client's existing filesystem tools. The app's bridge supplies validated
operations on the open model.

## A revision links an observation to geometry

The agent reads `get_state` before inspecting the model. That response identifies
the project, current build status, revision and object IDs. Geometry-dependent
requests carry the revision, so an old measurement request cannot silently act
on a newly rebuilt model.

After an edit, the agent waits for a successful new revision, resolves the
affected objects again and repeats relevant checks. Stable assembly paths help
selection and view state survive rebuilds, but an ID discovered in another
project or before a rename is not a reliable target.

A good review combines suitable evidence. A native measurement can answer a
clearance question; a screenshot can reveal that the wrong instance was
selected. Neither substitutes for the other, and neither replaces a physical
fit test where process behavior matters.

## Collaboration changes shared state

Selecting, isolating or moving the camera changes the user's view too.
Highlighting can point out a component while leaving selection alone.
Target-attached annotations can carry a discussion across rebuilds when the
target path remains stable, but app notes are session-only. Lasting decisions
belong in project source or documentation.

The same principle applies to fabrication: a slice job belongs to the revision
and profiles it started with. A later edit does not update the artifacts
already being produced. Keeping revisions and reports with outputs gives both
the person and the agent a concrete basis for deciding what to rebuild.

See [Connect an agent](../how-to/connect-an-agent.md) for setup and
[Inspect and measure an assembly](../how-to/inspect-and-measure.md) for the
desktop workflow.
