# Connect an agent to the open model

You need an agent client that supports MCP and a project
[open in CadKit](install.md#open-your-own-project). The agent should work in
the same project checkout. The desktop connection gives it access to the
model you are viewing; the skill supplies instructions for using CadKit.

## Install the skill

From your project directory, run:

```sh
npx skills add aurkakoak/cadkit --skill cadkit
```

Choose your agent client in the installer's prompts. Start a fresh agent task
if the client discovers skills only when a task starts. The skill does not
install CadKit or automatically establish an MCP connection.

## Copy the app's connection settings

Click the **plug icon** in CadKit and copy the MCP configuration. Add it to
your agent client's MCP server settings, following that client's configuration
format. The copied values include this session's executable, project directory
and Python import reference.

For example, an installed Linux app opened on `/home/alex/enclosure` produces
a configuration of this form:

```json
{
  "mcpServers": {
    "cadkit": {
      "command": "/home/alex/.local/share/cadkit/cadkit-desktop",
      "args": [
        "--mcp",
        "--project-dir", "/home/alex/enclosure",
        "--project", "project:PROJECT"
      ]
    }
  }
}
```

Use the configuration copied from **your** app, not these example paths. On
macOS the command is the executable inside `CadKit.app`. The installed app's
`--mcp` entry point needs no separate Node installation.

Keep the app open. The MCP process attaches to it; it does not launch a second
CAD session. A worktree at another directory is a separate session even when
its files look identical.

## Verify the connection

Select an object in the viewer, then ask your agent:

> Use the CadKit skill. Read the open app's state, confirm the project directory,
> and tell me which part I selected. Inspect it before suggesting any edits.

The first tool call should be `get_state`. Its `projectDir`, `reference`, build
status and `revision` identify the active model. The agent can then use
`inspect` with a returned component ID or Part name.

If the server says the app is not running, compare the configured directory
and project reference with the open app. If the model is rebuilding or failed,
resolve that status before exporting or evaluating an edit.

## Give the agent a bounded modelling task

A useful request names the intended change and the checks that matter:

> Increase the enclosure's inside height by 5 mm. Keep the lid mounting pattern
> unchanged. Run the affected checks, wait for the app to rebuild successfully,
> then show me the changed parts and explain any unresolved fit questions.

The agent edits the Python model using its normal file tools. MCP tools can
inspect, measure, select, annotate and capture the running app; they do not
provide a live parameter editor. After a successful rebuild, the agent must
read the new revision and resolve object IDs again before measuring.

Ask the agent to highlight a feature when you want to keep your current
selection, or to annotate an item when a note helps the discussion. Save
lasting decisions in the project: app annotations are session-only.

See [The edit, rebuild and inspect loop](../explanation/agent-workflow.md) for
how source, app state and agent observations relate, and the
[desktop reference](../reference/desktop.md) for tool schemas.
