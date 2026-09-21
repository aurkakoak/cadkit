# Build real objects with code

CadKit brings your Python geometry, desktop view and AI agent into the same
modelling loop. Write ordinary CadQuery builders, inspect assemblies and fits,
and export parts for fabrication.

## Get the desktop app

Install the latest macOS or Linux release from your terminal:

```sh
curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | sh
```

You can also download an installer from [GitHub Releases](https://github.com/aurkakoak/cadkit/releases).
The packaged desktop includes Python and CadKit and opens a writable example
on first launch. See the [desktop guide](../desktop/README.md) to open your own
project and connect your agent. Projects with extra Python dependencies can
use their own environment; see [installation](install.md).

## Give your agent the skill

From your project directory:

```sh
npx skills add aurkakoak/cadkit --skill cadkit
```

The skill teaches your agent the CadKit modelling workflow. For live selection,
measurements and camera control, open the app and connect the MCP server using
the configuration behind its plug icon. See [working with your agent](interaction.md).

## Find your next step

| You want to… | Start here |
| --- | --- |
| Create or change a part | [Modelling loop](agent-guide.md) and [Python API](api.md) |
| Bring an existing CadQuery project | [Migration guide](migration.md) |
| Inspect geometry with an agent | [Desktop and MCP](../desktop/README.md) |
| Declare joints, hardware and fits | [Mechanical connections](mechanics.md) |
| Export, render or slice parts | [Workflow commands](workflows.md) |
| Try the declarative Python API | [Declarative authoring](declarative.md) |

Geometry stays in your project. CadKit connects named parts, parameters,
assemblies, checks and manufacturing outputs without replacing CadQuery.
