#!/usr/bin/env node
// A small MCP client for agents whose host has not registered CadKit tools.
// Uses the desktop's existing SDK; never invokes Python or installs packages.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  if (index < 0) return fallback;
  if (!args[index + 1]) throw new Error(`Missing value for ${name}`);
  return args.splice(index, 2)[1];
};
const client = new Client({ name: "cadkit-command", version: "1.0.0" });
let target;
try {
  const projectDir = option("--project-dir", process.cwd());
  const reference = option("--project", "project:PROJECT");
  target = { projectDir, reference };
  const output = option("--output");
  const [name, json = "{}"] = args;
  if (!name || args.length > 2)
    throw new Error(
      "Usage: node mcp-client.mjs [--project-dir DIR] [--project module:PROJECT] [--output FILE] doctor|tools|TOOL [JSON]",
    );
  const params = JSON.parse(json);
  if (name === "screenshot" && !output)
    throw new Error("screenshot requires --output FILE.png");
  await client.connect(
    new StdioClientTransport({
      command: process.execPath,
      args: [
        fileURLToPath(new URL("./mcp.mjs", import.meta.url)),
        "--project-dir",
        projectDir,
        "--project",
        reference,
      ],
      env: { ...process.env, ELECTRON_RUN_AS_NODE: "1" },
      stderr: "inherit",
    }),
  );
  const result =
    name === "tools"
      ? await client.listTools()
      : await client.callTool({
          name: name === "doctor" ? "get_state" : name,
          arguments: params,
        });
  if (result.isError)
    throw new Error(
      result.content
        .filter((c) => c.type === "text")
        .map((c) => c.text)
        .join("\n"),
    );
  if (name === "doctor") {
    const state = result.structuredContent;
    console.log(
      JSON.stringify(
        {
          connected: true,
          projectDir: state.projectDir,
          reference: state.reference,
          status: state.status,
          revision: state.revision,
          tools: (await client.listTools()).tools.map((t) => t.name),
        },
        null,
        2,
      ),
    );
    if (state.status?.phase !== "ready") process.exitCode = 1;
  } else {
    const image = result.content?.find((c) => c.type === "image");
    const value = image
      ? Buffer.from(image.data, "base64")
      : JSON.stringify(result.structuredContent ?? result, null, 2) + "\n";
    if (output) {
      await writeFile(output, value);
      console.log(output);
    } else process.stdout.write(value);
  }
} catch (error) {
  console.error(error.message);
  if (target) {
    console.error(`Target: ${target.projectDir} (${target.reference})`);
    if (/not running|ENOENT|ECONNREFUSED|disconnected/i.test(error.message))
      console.error(
        "Open CadKit for this exact project directory and reference using the project's launch command, wait for a successful build, then retry doctor. The MCP server does not launch the app.",
      );
    else if (/EACCES|EPERM|permitted|permission/i.test(error.message))
      console.error(
        "Check host sandbox/local socket access and request the host's permission if needed. Keep CadKit's IPC directory private (0700); do not delete a live socket.",
      );
    else if (/build|rebuilding/i.test(error.message))
      console.error(
        "Read the app's build error, run cadkit doctor with the project's Python, correct the reported import/runtime issue, and retry after the build succeeds.",
      );
    else if (/connection closed/i.test(error.message))
      console.error(
        "The MCP process closed before replying. Check its stderr and runtime paths; if the host blocked process/local socket access, use its permission mechanism and retry. This does not establish whether the app is open.",
      );
    else
      console.error(
        "Run cadkit doctor with the project's Python and check the desktop runtime paths. If tools are unregistered, use the app's plug icon to configure this session in the client.",
      );
  }
  process.exitCode = 1;
} finally {
  await client.close();
}
