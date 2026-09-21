import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { electronTestArgs } from "./electron-test-options.mjs";

const executable = process.argv[2];
if (!executable)
  throw new Error("Usage: npm run smoke:package -- <packaged executable>");
const temporary = await mkdtemp(
  path.join(os.tmpdir(), "cadkit packaged smoke "),
);
try {
  const output = path.join(temporary, "result.json");
  const env = {
    ...process.env,
    CADKIT_USER_DATA: path.join(temporary, "profile"),
  };
  delete env.ELECTRON_RUN_AS_NODE;
  const result = spawnSync(
    path.resolve(executable),
    electronTestArgs(["--smoke-test", "--smoke-output", output], env),
    {
      cwd: temporary,
      env,
      stdio: "inherit",
      timeout: 180000,
    },
  );
  if (result.error) throw result.error;
  const report = JSON.parse(await readFile(output, "utf8"));
  assert.equal(result.status, 0, JSON.stringify(report));
  assert.equal(report.packaged, true);
  assert.ok(report.components > 0);
  assert.equal(report.rendererRevision, report.workerRevision);
  assert.ok(
    report.python.includes(
      `${path.sep}resources${path.sep}python${path.sep}`,
    ) ||
      report.python.includes(
        `${path.sep}Resources${path.sep}python${path.sep}`,
      ),
  );
  await new Promise((resolve, reject) => {
    const child = spawn(
      path.resolve(executable),
      electronTestArgs(["--mcp", "--project-dir", report.projectDir], env),
      { cwd: temporary, env, stdio: ["pipe", "pipe", "pipe"] },
    );
    let output = "";
    let errors = "";
    let initialized = false;
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`Packaged MCP timed out: ${errors}`));
    }, 30000);
    child.stderr.on("data", (data) => {
      errors += data;
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      if (code === 0 && initialized) resolve();
      else reject(new Error(`Packaged MCP failed (${code}): ${errors}`));
    });
    child.stdout.on("data", (data) => {
      output += data;
      while (output.includes("\n")) {
        const newline = output.indexOf("\n");
        const line = output.slice(0, newline);
        output = output.slice(newline + 1);
        try {
          const message = JSON.parse(line);
          if (
            message.id === 1 &&
            message.result?.serverInfo?.name === "cadkit"
          ) {
            initialized = true;
            child.stdin.end();
          }
        } catch {
          /* Electron diagnostics are not MCP responses. */
        }
      }
    });
    child.stdin.write(
      JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "cadkit-release-smoke", version: "1" },
        },
      }) + "\n",
    );
  });
  console.log(
    "Packaged app, bundled Python, example scene, renderer, and MCP passed.",
  );
} finally {
  await rm(temporary, { recursive: true, force: true });
}
