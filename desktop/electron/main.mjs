import {
  app,
  BrowserWindow,
  clipboard,
  dialog,
  ipcMain,
  shell,
} from "electron";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import chokidar from "chokidar";
import { startBridge } from "./local-bridge.mjs";
import { validateCommand } from "./control-schema.mjs";
import { Slicer } from "./slicer.mjs";

const desktop = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const framework = path.resolve(desktop, "..");
const argument = (name, fallback) => {
  const index = process.argv.indexOf(name);
  return index < 0 ? fallback : process.argv[index + 1];
};
const projectDir = path.resolve(argument("--project-dir", process.cwd()));
const reference = argument("--project", "project:PROJECT");
const defaultPython = path.join(
  projectDir,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const python = argument(
  "--python",
  existsSync(defaultPython) ? defaultPython : "python3",
);
// Tests use their own profile; the normal app retains its theme preference.
if (process.env.CADKIT_USER_DATA)
  app.setPath("userData", process.env.CADKIT_USER_DATA);
let window, current, candidate, snapshot, building;
let queued = false;
let status = { phase: "idle", message: "Ready to build" };
let watcher, debounce;
let bridge, slicer;
const rendererRequests = new Map();
let rendererSequence = 0;
const workerEnv = () => ({
  ...process.env,
  PYTHONPATH: [path.join(framework, "src"), projectDir, process.env.PYTHONPATH]
    .filter(Boolean)
    .join(path.delimiter),
});

function control(method, params = {}) {
  if (!window || window.isDestroyed())
    throw new Error("CadKit window is unavailable");
  return new Promise((resolve, reject) => {
    const id = ++rendererSequence;
    const timer = setTimeout(() => {
      rendererRequests.delete(id);
      reject(new Error("CadKit view did not respond"));
    }, 30000);
    rendererRequests.set(id, { resolve, reject, timer });
    window.webContents.send("cadkit:control", { id, method, params });
  });
}
ipcMain.on("cadkit:control-result", (event, response) => {
  if (event.sender !== window?.webContents) return;
  const pending = rendererRequests.get(response.id);
  if (!pending) return;
  rendererRequests.delete(response.id);
  clearTimeout(pending.timer);
  response.error
    ? pending.reject(new Error(response.error))
    : pending.resolve(response.result);
});

function checkRevision(revision) {
  if (!snapshot || snapshot.revision !== revision)
    throw new Error("Stale build revision. Read get_state again.");
}
async function executeTool(method, raw) {
  const params = validateCommand(method, raw);
  if (params.revision) checkRevision(params.revision);
  if (method === "get_state") {
    const ui = await control("get_state");
    if (!snapshot || ui.revision !== snapshot.revision)
      throw new Error("View is rebuilding; retry get_state");
    return {
      ...ui,
      project: snapshot.project,
      tree: snapshot.tree,
      components: snapshot.components,
      status,
      projectDir,
      reference,
    };
  }
  if (method === "measure") {
    const result = await current.call("measure", {
      revision: params.revision,
      ids: params.ids,
    });
    if (params.show) {
      checkRevision(params.revision);
      await control("show_measurement", result);
    }
    return result;
  }
  if (method === "screenshot") {
    const state = await control("get_state");
    const rect = params.target === "viewport" ? state.viewport : undefined;
    if (params.target === "viewport" && !rect)
      throw new Error("Viewport is not ready");
    let image = await window.webContents.capturePage(rect);
    if (image.isEmpty()) throw new Error("CadKit window could not be captured");
    if (image.getSize().width > params.max_width)
      image = image.resize({ width: params.max_width });
    return { data: image.toPNG().toString("base64"), mimeType: "image/png" };
  }
  if (method === "slicer_settings") return slicer.settings();
  if (method === "slice_parts" || method === "prepare_parts") {
    for (const name of params.parts)
      if (!snapshot.project.parts.some((p) => p.name === name))
        throw new Error(`Unknown Part: ${name}`);
    return slicer.start(params, method === "slice_parts" ? "slice" : "prepare");
  }
  if (method === "slice_status") return slicer.list(params.id);
  if (method === "cancel_slice") return slicer.cancel(params.id);
  if (method === "open_in_slicer") return slicer.open(params.id);
  return control(method, params);
}
// Serialize UI operations so each acknowledgement describes a committed view.
let commandQueue = Promise.resolve();
function dispatch(method, params) {
  const result = commandQueue.then(() => executeTool(method, params));
  commandQueue = result.catch(() => {});
  return result;
}

function publish(event) {
  if (event.type === "status") status = event;
  if (window && !window.isDestroyed())
    window.webContents.send("cadkit:event", event);
}

class Worker {
  constructor() {
    this.sequence = 0;
    this.pending = new Map();
    this.log = "";
    this.closed = false;
    this.process = spawn(
      python,
      ["-u", "-m", "cadkit.desktop", "--project", reference],
      {
        cwd: projectDir,
        env: workerEnv(),
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
      },
    );
    this.process.stderr.on("data", (data) => {
      this.log = (this.log + data).slice(-12000);
    });
    const lines = createInterface({ input: this.process.stdout });
    lines.on("line", (line) => {
      let response;
      try {
        response = JSON.parse(line);
      } catch {
        this.fail(new Error("Invalid response from CAD worker"));
        return;
      }
      if (response.event === "progress") {
        if (candidate === this)
          publish({
            type: "status",
            phase: "building",
            message: response.message,
          });
        return;
      }
      const request = this.pending.get(response.id);
      if (!request) return;
      clearTimeout(request.timer);
      this.pending.delete(response.id);
      if (response.error) request.reject(new Error(response.error));
      else request.resolve(response.result);
    });
    this.process.on("error", (error) =>
      this.fail(new Error(`Cannot start ${python}: ${error.message}`)),
    );
    this.process.on("exit", (code, signal) => {
      this.closed = true;
      this.fail(
        new Error(
          `CAD worker stopped (${signal ?? code}). ${this.log.trim().slice(-3000)}`,
        ),
      );
    });
    this.process.stdin.on("error", (error) => this.fail(error));
  }
  fail(error) {
    for (const { reject, timer } of this.pending.values()) {
      clearTimeout(timer);
      reject(error);
    }
    this.pending.clear();
  }
  call(method, params = {}) {
    if (this.closed)
      return Promise.reject(
        new Error("CAD worker is unavailable. Rebuild the project."),
      );
    return new Promise((resolve, reject) => {
      const id = ++this.sequence;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("CAD operation timed out after five minutes"));
      }, 300000);
      this.pending.set(id, { resolve, reject, timer });
      this.process.stdin.write(JSON.stringify({ id, method, params }) + "\n");
    });
  }
  close() {
    this.closed = true;
    this.fail(new Error("Build was replaced"));
    this.process.kill();
  }
}

async function rebuild() {
  if (building) {
    queued = true;
    return building;
  }
  building = (async () => {
    publish({
      type: "status",
      phase: "building",
      message: "Starting CadQuery…",
    });
    candidate = new Worker();
    try {
      const next = await candidate.call("scene");
      const previous = current;
      current = candidate;
      candidate = undefined;
      snapshot = next;
      previous?.close();
      publish({ type: "scene", scene: next });
      publish({
        type: "status",
        phase: "ready",
        message: `Built in ${next.build_seconds.toFixed(1)}s`,
      });
      return next;
    } catch (error) {
      candidate?.close();
      candidate = undefined;
      publish({ type: "status", phase: "error", message: error.message });
      // Keep the last successful scene AND worker available for inspection.
      throw error;
    }
  })();
  try {
    return await building;
  } finally {
    building = undefined;
    if (queued) {
      queued = false;
      void rebuild().catch(() => {});
    }
  }
}

ipcMain.handle("cadkit:load", async () => {
  const scene = snapshot ?? (await (building ?? rebuild()));
  return { scene, status, projectDir, reference };
});
ipcMain.handle("cadkit:rebuild", () => rebuild());
ipcMain.handle("cadkit:open-link", (_event, value) => {
  if (typeof value !== "string") throw new Error("Invalid link");
  const url = new URL(value);
  if (!["https:", "http:"].includes(url.protocol))
    throw new Error("Only web links are supported");
  return shell.openExternal(url.href);
});
ipcMain.handle("cadkit:slicer-settings", () => slicer.settings());
ipcMain.handle("cadkit:slicer-save", (_event, values) => {
  // Executables and profile paths are picked through native dialogs only.
  const { kind, price, currency, bed } = values;
  return slicer.save({ kind, price, currency, bed });
});
ipcMain.handle("cadkit:slicer-pick", async (_event, key) => {
  if (
    !["executable", "profile", "machine", "process", "filament"].includes(key)
  )
    throw new Error("Unknown slicer setting");
  const selected = await dialog.showOpenDialog(window, {
    title: `Slicer · ${key}`,
    properties: ["openFile"],
    ...(key === "executable"
      ? {}
      : {
          filters: [
            {
              name: "Slicer profile",
              extensions: key === "profile" ? ["ini"] : ["json"],
            },
          ],
        }),
  });
  return selected.canceled
    ? slicer.settings()
    : slicer.save({ [key]: selected.filePaths[0] });
});
ipcMain.handle("cadkit:slicer-action", (_event, method, params) => {
  if (
    ![
      "slice_parts",
      "prepare_parts",
      "slice_status",
      "cancel_slice",
      "open_in_slicer",
    ].includes(method)
  )
    throw new Error("Unknown slicer operation");
  return dispatch(method, params);
});
ipcMain.handle("cadkit:slicer-reveal", (_event, id) =>
  shell.openPath(slicer.list(id).directory),
);
ipcMain.handle("cadkit:mcp-config", () => {
  const config = {
    mcpServers: {
      cadkit: {
        command: process.env.npm_node_execpath ?? "node",
        args: [
          path.join(desktop, "electron/mcp.mjs"),
          "--project-dir",
          projectDir,
          "--project",
          reference,
        ],
      },
    },
  };
  clipboard.writeText(JSON.stringify(config, null, 2));
  return { copied: true };
});
ipcMain.handle("cadkit:measure", (_event, params) => {
  if (!current) throw new Error("Build a project first");
  if (
    !params ||
    typeof params.revision !== "string" ||
    !Array.isArray(params.ids) ||
    params.ids.length !== 2 ||
    !params.ids.every((id) => typeof id === "string")
  ) {
    throw new Error("Invalid measurement request");
  }
  return current.call("measure", {
    revision: params.revision,
    ids: params.ids,
  });
});
ipcMain.handle("cadkit:export", async (_event, name) => {
  if (
    !current ||
    typeof name !== "string" ||
    !snapshot.project.parts.some((p) => p.name === name)
  ) {
    throw new Error("Unknown part");
  }
  const selected = await dialog.showOpenDialog(window, {
    title: `Export ${name} · choose a destination folder`,
    defaultPath: path.join(projectDir, "build"),
    properties: ["openDirectory", "createDirectory"],
  });
  if (selected.canceled) return null;
  // Each part gets its own directory so manifests for other exports survive.
  const output_dir = path.join(selected.filePaths[0], name);
  const result = await current.call("export_part", { name, output_dir });
  await shell.openPath(result.directory);
  return result;
});

app
  .whenReady()
  .then(async () => {
    slicer = new Slicer({
      userData: app.getPath("userData"),
      projectDir,
      python,
      env: workerEnv(),
      publish,
      exportParts: (revision, names, output_dir) => {
        checkRevision(revision);
        return current.call("export_parts", { revision, names, output_dir });
      },
    });
    bridge = await startBridge(projectDir, reference, dispatch);
    window = new BrowserWindow({
      width: 1500,
      height: 980,
      minWidth: 1050,
      minHeight: 680,
      title: "CadKit",
      backgroundColor: "#15191d",
      autoHideMenuBar: true,
      webPreferences: {
        preload: path.join(desktop, "electron/preload.cjs"),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });
    window.webContents.on("did-start-loading", () => {
      for (const pending of rendererRequests.values()) {
        clearTimeout(pending.timer);
        pending.reject(new Error("CadKit view reloaded"));
      }
      rendererRequests.clear();
    });
    window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    window.webContents.on("will-navigate", (event) => event.preventDefault());
    await window.loadFile(path.join(desktop, "dist/index.html"));
    watcher = chokidar.watch([projectDir, path.join(framework, "src")], {
      ignored: (file, stats) =>
        /(?:^|[/\\])(?:\.git|\.venv|node_modules|__pycache__|build|dist|vendor|archive)(?:[/\\]|$)/.test(
          file,
        ) || Boolean(stats?.isFile() && !file.endsWith(".py")),
      ignoreInitial: true,
      awaitWriteFinish: { stabilityThreshold: 300, pollInterval: 100 },
    });
    watcher.on("all", (_event, file) => {
      if (!file.endsWith(".py")) return;
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        void rebuild().catch(() => {});
      }, 500);
    });
  })
  .catch((error) => {
    dialog.showErrorBox("CadKit could not start", error.message);
    app.quit();
  });
app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => {
  clearTimeout(debounce);
  void watcher?.close();
  current?.close();
  candidate?.close();
  slicer?.close();
  void bridge?.close();
  for (const pending of rendererRequests.values()) {
    clearTimeout(pending.timer);
    pending.reject(new Error("CadKit closed"));
  }
  rendererRequests.clear();
});
