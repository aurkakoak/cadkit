#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { definitions } from "./control-schema.mjs";
import { callApp, connectionFile } from "./local-bridge.mjs";

const arg = (name, fallback) => {
  const index = process.argv.indexOf(name);
  return index < 0 ? fallback : process.argv[index + 1];
};
const file = await connectionFile(
  arg("--project-dir", process.cwd()),
  arg("--project", "project:PROJECT"),
);
const server = new McpServer({ name: "cadkit", version: "0.2.0" });
for (const [name, definition] of Object.entries(definitions)) {
  server.registerTool(
    name,
    {
      description: definition.description,
      inputSchema: definition.schema,
      annotations: {
        readOnlyHint: [
          "get_state",
          "inspect",
          "inspect_connection",
          "mechanical_report",
          "screenshot",
          "slicer_settings",
          "slice_status",
        ].includes(name),
        destructiveHint: false,
        openWorldHint: false,
      },
    },
    async (params) => {
      try {
        const result = await callApp(file, name, params);
        if (name === "screenshot")
          return {
            content: [
              { type: "image", data: result.data, mimeType: "image/png" },
            ],
          };
        return {
          content: [{ type: "text", text: JSON.stringify(result) }],
          structuredContent: result,
        };
      } catch (error) {
        return {
          isError: true,
          content: [{ type: "text", text: error.message }],
        };
      }
    },
  );
}
server.registerResource(
  "state",
  "cadkit://state",
  {
    mimeType: "application/json",
    description: "Current CadKit project and live UI state",
  },
  async (uri) => ({
    contents: [
      {
        uri: uri.href,
        mimeType: "application/json",
        text: JSON.stringify(await callApp(file, "get_state")),
      },
    ],
  }),
);
server.registerResource(
  "mechanics",
  "cadkit://mechanics",
  {
    mimeType: "application/json",
    description:
      "First-class Joint, Interface and Fastening definitions, resolved participants, hardware BOM and latest revision-scoped validation. Joint motion metadata is not a solved assembly path.",
  },
  async (uri) => {
    const state = await callApp(file, "get_state");
    return {
      contents: [
        {
          uri: uri.href,
          mimeType: "application/json",
          text: JSON.stringify({
            revision: state.revision,
            mechanics: state.mechanics,
            validation: state.mechanicalReport,
            selectedConnection: state.selectedConnection,
            hardwareView: state.hardwareView,
          }),
        },
      ],
    };
  },
);
await server.connect(new StdioServerTransport());
