import {
  app,
  BrowserWindow,
  clipboard,
  dialog,
  ipcMain,
  Menu,
  shell,
} from "electron";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { createInterface } from "node:readline";
import { writeFileSync } from "node:fs";
import { realpath, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import chokidar from "chokidar";
import { startBridge } from "./local-bridge.mjs";
import { validateCommand } from "./control-schema.mjs";
import { Renderer } from "./renderer.mjs";
import { Slicer } from "./slicer.mjs";
import { argument, resolveRuntime } from "./runtime.mjs";
import {
  ProjectLibrary,
  normalizeReference,
  projectIdentity,
} from "./projects.mjs";

const desktop = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const framework = path.resolve(desktop, "..");
if (process.env.CADKIT_USER_DATA)
  app.setPath("userData", process.env.CADKIT_USER_DATA);
const smokeTest = process.argv.includes("--smoke-test");
const smokeOutput = argument(process.argv, "--smoke-output");
const startupPython = argument(process.argv, "--python");
const runtimeOptions = {
  isPackaged: app.isPackaged,
  resourcesPath: process.resourcesPath,
  userData: app.getPath("userData"),
  framework,
};
const library = new ProjectLibrary(runtimeOptions);
let window, active;
let transitions = Promise.resolve();
const rendererRequests = new Map();
let rendererSequence = 0;
const homeStatus = { phase: "idle", message: "Open a project to begin" };

function assertSession(session) {
  if (!session || active !== session || session.closed)
    throw new Error("Project session changed. Open the current project again.");
}
function requireSession() {
  assertSession(active);
  return active;
}
function checkRevision(session, revision) {
  assertSession(session);
  if (!session.snapshot || session.snapshot.revision !== revision)
    throw new Error("Stale build revision. Read get_state again.");
}
function send(event) {
  if (window && !window.isDestroyed())
    window.webContents.send("cadkit:event", event);
}
function publish(session, event) {
  if (active !== session || session.closed) return;
  if (event.type === "status") session.status = event;
  send({ ...event, sessionId: session.sessionId });
}
function rejectControls(message, session) {
  for (const [id, pending] of rendererRequests) {
    if (session && pending.session !== session) continue;
    clearTimeout(pending.timer);
    pending.reject(new Error(message));
    rendererRequests.delete(id);
  }
}
function control(session, method, params = {}) {
  assertSession(session);
  if (!window || window.isDestroyed())
    throw new Error("CadKit window is unavailable");
  return new Promise((resolve, reject) => {
    const id = ++rendererSequence;
    const timer = setTimeout(() => {
      rendererRequests.delete(id);
      reject(new Error("CadKit view did not respond"));
    }, 30000);
    rendererRequests.set(id, { resolve, reject, timer, session });
    window.webContents.send("cadkit:control", {
      id,
      method,
      params,
      sessionId: session.sessionId,
    });
  });
}
ipcMain.on("cadkit:control-result", (event, response) => {
  if (
    event.sender !== window?.webContents ||
    !response ||
    typeof response.id !== "number"
  )
    return;
  const pending = rendererRequests.get(response.id);
  if (!pending) return;
  rendererRequests.delete(response.id);
  clearTimeout(pending.timer);
  if (active !== pending.session || pending.session.closed) {
    pending.reject(new Error("Project session changed"));
  } else if (response.error) pending.reject(new Error(String(response.error)));
  else pending.resolve(response.result);
});
function dispatch(session, method, params) {
  const result = session.commandQueue.then(async () => {
    assertSession(session);
    const result = await executeTool(session, method, params);
    assertSession(session);
    if (params?.revision) checkRevision(session, params.revision);
    return result;
  });
  session.commandQueue = result.catch(() => {});
  return result;
}

async function executeTool(session, method, raw) {
  assertSession(session);
  const { snapshot, current, status, mechanicalReport, slicer } = session;
  const { projectDir, reference } = session.target;
  if (
    !snapshot &&
    ![
      "slicer_settings",
      "slice_status",
      "cancel_slice",
      "open_in_slicer",
    ].includes(method)
  )
    throw new Error("Build a project first");
  const params = validateCommand(method, raw);
  if (params.revision) checkRevision(session, params.revision);
  if (method === "get_state") {
    const ui = await control(session, "get_state");
    if (!snapshot || ui.revision !== snapshot.revision)
      throw new Error("View is rebuilding; retry get_state");
    return {
      ...ui,
      project: snapshot.project,
      tree: snapshot.tree,
      components: snapshot.components,
      mechanics: snapshot.mechanics,
      mechanicalReport,
      status,
      projectDir,
      reference,
    };
  }
  if (method === "mechanical_report") {
    const worker = current;
    const result = await worker.call("mechanical_report", params);
    checkRevision(session, params.revision);
    session.mechanicalReport = result;
    await control(session, "show_mechanical_report", result);
    return result;
  }
  if (method === "inspect_connection") {
    const collection =
      snapshot.mechanics[
        params.kind === "interface" ? "interfaces" : params.kind + "s"
      ];
    const connection = collection.find(
      (item) => (item.id ?? item.name) === params.id,
    );
    if (!connection) throw new Error(`Unknown ${params.kind}: ${params.id}`);
    const componentIds = [
      ...connection.component_ids,
      ...(connection.hardware_ids ?? []),
    ];
    const findings =
      mechanicalReport?.findings?.filter(
        (f) =>
          (f.concept === params.kind && f.entity === params.id) ||
          (f.concept === "assembly" &&
            f.component_ids.some((id) => componentIds.includes(id))),
      ) ?? [];
    const direct = findings.filter(
      (f) => f.concept === params.kind && f.entity === params.id,
    );
    return {
      revision: snapshot.revision,
      kind: params.kind,
      connection,
      components: snapshot.components.filter((c) =>
        componentIds.includes(c.id),
      ),
      findings,
      validation_scope: mechanicalReport?.scope ?? null,
      validation_status: findings.some((f) => f.status === "fail")
        ? "fail"
        : !direct.length
          ? "not_checked"
          : findings.some((f) => f.status === "unverified")
            ? "incomplete"
            : "pass",
    };
  }
  if (method === "measure") {
    const ui = await control(session, "get_state");
    if (ui.hardwareView?.previewProgress > 0)
      throw new Error(
        "Restore installed hardware (previewProgress=0) before measuring native geometry",
      );
    const result = await current.call("measure", {
      revision: params.revision,
      ids: params.ids,
    });
    if (params.show) {
      checkRevision(session, params.revision);
      await control(session, "show_measurement", result);
    }
    return result;
  }
  if (method === "screenshot") {
    const state = await control(session, "get_state");
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
    if (status.phase !== "ready")
      throw new Error(
        "Wait for a successful current build before exporting or slicing",
      );
    return slicer.start(params, method === "slice_parts" ? "slice" : "prepare");
  }
  if (method === "slice_status") return slicer.list(params.id);
  if (method === "cancel_slice") return slicer.cancel(params.id);
  if (method === "open_in_slicer") return slicer.open(params.id);
  return control(session, method, params);
}

class Worker {
  constructor(session) {
    const { python, projectDir, reference, workerEnv } = session.runtime;
    this.sequence = 0;
    this.pending = new Map();
    this.log = "";
    this.closed = false;
    this.process = spawn(
      python,
      ["-u", "-m", "cadkit.desktop", "--project", reference],
      {
        cwd: projectDir,
        env: { ...workerEnv },
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
        if (active === session && session.candidate === this)
          publish(session, {
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

async function rebuild(session = requireSession()) {
  assertSession(session);
  if (session.building) {
    session.queued = true;
    return session.building;
  }
  const task = (async () => {
    publish(session, {
      type: "status",
      phase: "building",
      message: "Starting CadQuery…",
    });
    const candidate = new Worker(session);
    session.candidate = candidate;
    try {
      const next = await candidate.call("scene");
      assertSession(session);
      const previous = session.current;
      session.current = candidate;
      session.candidate = undefined;
      session.snapshot = next;
      session.mechanicalReport = null;
      previous?.close();
      publish(session, { type: "scene", scene: next });
      publish(session, {
        type: "status",
        phase: "ready",
        message: `Built in ${next.build_seconds.toFixed(1)}s`,
      });
      void library
        .rename(session.id, next.project.name)
        .then(() => publishLauncher())
        .catch((error) =>
          console.error("Could not update recent project:", error),
        );
      return next;
    } catch (error) {
      candidate.close();
      if (session.candidate === candidate) session.candidate = undefined;
      publish(session, {
        type: "status",
        phase: "error",
        message: error.message,
      });
      throw error;
    }
  })();
  session.building = task;
  try {
    return await task;
  } finally {
    if (session.building === task) session.building = undefined;
    if (active === session && !session.closed && session.queued) {
      session.queued = false;
      void rebuild(session).catch(() => {});
    }
  }
}

async function launcherState() {
  const recents = await library.list();
  return {
    active: active
      ? { ...active.target, id: active.id, sessionId: active.sessionId }
      : null,
    recents,
  };
}
function updateMenu(state) {
  const open = () => send({ type: "open-project" });
  const act = (operation) => {
    void operation().catch((error) =>
      dialog.showErrorBox("CadKit", error.message),
    );
  };
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(process.platform === "darwin" ? [{ role: "appMenu" }] : []),
      {
        label: "File",
        submenu: [
          {
            label: "Home",
            accelerator: "CmdOrCtrl+Shift+H",
            click: () => act(() => transition(closeProject)),
          },
          { label: "Open Project…", accelerator: "CmdOrCtrl+O", click: open },
          {
            label: "Open Recent",
            submenu: state.recents.length
              ? state.recents.slice(0, 15).map((recent) => ({
                  label: `${recent.name} — ${recent.reference}`,
                  click: () => act(() => openRecent(recent.id)),
                }))
              : [{ label: "No recent projects", enabled: false }],
          },
          { type: "separator" },
          { role: process.platform === "darwin" ? "close" : "quit" },
        ],
      },
      { role: "editMenu" },
      { role: "viewMenu" },
      { role: "windowMenu" },
    ]),
  );
}
async function publishLauncher() {
  const state = await launcherState();
  updateMenu(state);
  send({ type: "launcher", state });
  return state;
}
function transition(operation) {
  const result = transitions.then(operation);
  transitions = result.catch(() => {});
  return result;
}
async function stopSession(session = active) {
  if (!session) return;
  if (active === session) active = undefined;
  session.closed = true;
  session.queued = false;
  clearTimeout(session.debounce);
  rejectControls("Project session changed", session);
  session.current?.close();
  session.candidate?.close();
  session.slicer?.close();
  session.renderer?.close();
  const stopped = await Promise.allSettled([
    session.watcher?.close(),
    session.bridge?.close(),
  ]);
  const failed = stopped.find((result) => result.status === "rejected");
  if (failed) throw failed.reason;
}
async function closeProject() {
  try {
    await stopSession();
  } finally {
    await publishLauncher();
  }
  return launcherState();
}
function checkedString(value, label) {
  if (
    typeof value !== "string" ||
    !value.trim() ||
    value.length > 16384 ||
    value.includes("\0")
  )
    throw new Error(`Invalid ${label}`);
  return value.trim();
}
function checkedId(value) {
  if (typeof value !== "string" || !/^[a-f0-9]{24}$/.test(value))
    throw new Error("Invalid project ID");
  return value;
}
async function checkedTarget(value) {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Invalid project target");
  const projectDir = await realpath(
    checkedString(value.projectDir, "project folder"),
  );
  if (!(await stat(projectDir)).isDirectory())
    throw new Error("Choose a project folder");
  const reference = normalizeReference(
    checkedString(value.reference, "project reference"),
  );
  const python =
    value.python === ""
      ? undefined
      : value.python === undefined
        ? startupPython
        : checkedString(value.python, "Python executable");
  if (value.replaceRecentId !== undefined) checkedId(value.replaceRecentId);
  return { projectDir, reference, python };
}
async function activate(value) {
  const target = await checkedTarget(value);
  const id = await projectIdentity(target);
  if (active?.id === id && active.target.python === target.python) {
    await library.remember(target, { replaceRecentId: value.replaceRecentId });
    if (active.status.phase === "error") void rebuild(active).catch(() => {});
    window?.focus();
    return publishLauncher();
  }
  const runtime = resolveRuntime({
    ...runtimeOptions,
    argv: [
      "--project-dir",
      target.projectDir,
      "--project",
      target.reference,
      ...(target.python ? ["--python", target.python] : []),
    ],
  });
  const session = {
    id,
    sessionId: randomUUID(),
    target,
    runtime,
    status: { phase: "idle", message: "Ready to build" },
    snapshot: null,
    mechanicalReport: null,
    current: undefined,
    candidate: undefined,
    building: undefined,
    queued: false,
    closed: false,
    commandQueue: Promise.resolve(),
    watcher: undefined,
    bridge: undefined,
    slicer: undefined,
    debounce: undefined,
  };
  // Reserve the new bridge before closing a different project. A project that
  // is already open in another app cannot displace this window's working session.
  if (active?.id === id) await stopSession();
  try {
    session.bridge = await startBridge(
      target.projectDir,
      target.reference,
      (method, params) => dispatch(session, method, params),
    );
    await stopSession();
    active = session;
    await library.remember(target, { replaceRecentId: value.replaceRecentId });
    session.slicer = new Slicer({
      userData: app.getPath("userData"),
      projectDir: runtime.projectDir,
      python: runtime.python,
      env: { ...runtime.workerEnv },
      publish: (event) => publish(session, event),
      exportParts: async (revision, names, output_dir, validation_override) => {
        checkRevision(session, revision);
        if (session.status.phase !== "ready")
          throw new Error(
            "Wait for a successful current build before exporting",
          );
        const result = await session.current.call("export_parts", {
          revision,
          names,
          output_dir,
          validation_override,
        });
        checkRevision(session, revision);
        return result;
      },
    });
    session.renderer = new Renderer({
      userData: app.getPath("userData"),
      projectDir: runtime.projectDir,
      python: runtime.python,
      env: { ...runtime.workerEnv },
      publish: (event) => publish(session, event),
      exportAssets: async (params) => {
        checkRevision(session, params.revision);
        if (session.status.phase !== "ready")
          throw new Error("Wait for the current build");
        const result = await session.current.call("render_assets", params);
        checkRevision(session, params.revision);
        return result;
      },
    });
    session.watcher = chokidar.watch(
      app.isPackaged
        ? [target.projectDir]
        : [target.projectDir, path.join(framework, "src")],
      {
        ignored: (file, stats) =>
          /(?:^|[/\\])(?:\.git|\.venv|node_modules|__pycache__|build|dist|vendor|archive)(?:[/\\]|$)/.test(
            file,
          ) || Boolean(stats?.isFile() && !file.endsWith(".py")),
        ignoreInitial: true,
        awaitWriteFinish: { stabilityThreshold: 300, pollInterval: 100 },
      },
    );
    session.watcher.on("all", (_event, file) => {
      if (!file.endsWith(".py") || active !== session || session.closed) return;
      clearTimeout(session.debounce);
      session.debounce = setTimeout(() => {
        if (active === session) void rebuild(session).catch(() => {});
      }, 500);
    });
    session.watcher.on("error", (error) =>
      publish(session, {
        type: "status",
        phase: "error",
        message: `File watcher: ${error.message}`,
      }),
    );
    const state = await publishLauncher();
    void rebuild(session).catch(() => {});
    return state;
  } catch (error) {
    await stopSession(session).catch(() => {});
    await publishLauncher();
    throw error;
  }
}
async function chooseDirectory(title, properties = ["openDirectory"]) {
  const selected = await dialog.showOpenDialog(window, { title, properties });
  return selected.canceled ? null : selected.filePaths[0];
}
async function locateProject(id) {
  checkedId(id);
  const recent = (await library.list()).find((entry) => entry.id === id);
  if (!recent) throw new Error("Unknown recent project");
  const directory = await chooseDirectory(`Locate ${recent.name}`);
  if (!directory) return null;
  const choice = await library.inspect(directory);
  if (!choice.suggestedPython && recent.python) {
    // An environment inside a relocated project may have moved too. Prefer a
    // newly discovered environment; retain external interpreters still present.
    const available =
      !path.isAbsolute(recent.python) ||
      (await stat(recent.python).then(
        (entry) => entry.isFile(),
        () => false,
      ));
    if (available) choice.suggestedPython = recent.python;
  }
  return { ...choice, replaceRecentId: id };
}
async function openRecent(id) {
  const recent = (await library.list()).find((entry) => entry.id === id);
  if (!recent) throw new Error("Unknown recent project");
  if (recent.missing) {
    const choice = await locateProject(id);
    if (choice) send({ type: "open-project", choice });
    return;
  }
  return transition(() => activate(recent));
}
function handle(name, callback) {
  ipcMain.handle(name, (event, ...args) => {
    if (event.sender !== window?.webContents)
      throw new Error("Unknown CadKit window");
    return callback(...args);
  });
}
handle("cadkit:launcher-state", launcherState);
handle("cadkit:choose-project", async () => {
  const directory = await chooseDirectory("Open a CadKit project folder");
  return directory ? library.inspect(directory) : null;
});
handle("cadkit:open-project", (target) => transition(() => activate(target)));
handle("cadkit:close-project", () => transition(closeProject));
handle("cadkit:create-project", async (template) => {
  if (!["starter", "bracket"].includes(template))
    throw new Error("Unknown project template");
  const directory = await chooseDirectory(
    "Choose a folder for the new project",
    ["openDirectory", "createDirectory"],
  );
  if (!directory) return null;
  return transition(async () =>
    activate(await library.create(directory, template)),
  );
});
handle("cadkit:pin-project", async (id, pinned) => {
  if (typeof pinned !== "boolean") throw new Error("Invalid pin preference");
  await library.pin(checkedId(id), pinned);
  return publishLauncher();
});
handle("cadkit:remove-project", async (id) => {
  await library.remove(checkedId(id));
  return publishLauncher();
});
handle("cadkit:locate-project", locateProject);
handle("cadkit:pick-project-python", async () => {
  const selected = await dialog.showOpenDialog(window, {
    title: "Choose a Python executable",
    properties: ["openFile"],
  });
  return selected.canceled ? null : selected.filePaths[0];
});
handle("cadkit:save-project-preview", async (params) => {
  const session = requireSession();
  if (
    !params ||
    typeof params !== "object" ||
    typeof params.revision !== "string" ||
    (params.manual !== undefined && typeof params.manual !== "boolean")
  )
    throw new Error("Invalid project preview request");
  checkRevision(session, params.revision);
  if (session.status.phase !== "ready")
    throw new Error("A successful current build is required for a preview");
  const ui = await control(session, "get_state");
  checkRevision(session, params.revision);
  if (ui.revision !== params.revision || session.status.phase !== "ready")
    throw new Error("The viewport is not ready for this revision");
  const rect = ui.viewport;
  if (
    !rect ||
    ![rect.x, rect.y, rect.width, rect.height].every(Number.isFinite) ||
    rect.x < 0 ||
    rect.y < 0 ||
    rect.width < 1 ||
    rect.height < 1
  )
    throw new Error("Viewport is not ready");
  let image = await window.webContents.capturePage({
    x: Math.floor(rect.x),
    y: Math.floor(rect.y),
    width: Math.floor(rect.width),
    height: Math.floor(rect.height),
  });
  checkRevision(session, params.revision);
  if (session.status.phase !== "ready")
    throw new Error("The project changed during preview capture");
  if (image.isEmpty())
    throw new Error("Viewport preview could not be captured");
  if (image.getSize().width > 640) image = image.resize({ width: 640 });
  await library.writePreview(session.id, image.toPNG(), {
    manual: params.manual === true,
  });
  await publishLauncher();
});
handle("cadkit:load", async () => {
  const session = active;
  if (!session)
    return {
      scene: null,
      status: homeStatus,
      projectDir: null,
      reference: null,
      launcher: await launcherState(),
    };
  const scene =
    session.snapshot ?? (await (session.building ?? rebuild(session)));
  assertSession(session);
  const launcher = await launcherState();
  assertSession(session);
  return {
    scene,
    status: session.status,
    projectDir: session.target.projectDir,
    reference: session.target.reference,
    launcher,
  };
});
handle("cadkit:rebuild", () => rebuild());
handle("cadkit:open-link", (value) => {
  const url = new URL(checkedString(value, "link"));
  if (!["https:", "http:"].includes(url.protocol))
    throw new Error("Only web links are supported");
  return shell.openExternal(url.href);
});
handle("cadkit:slicer-settings", () => requireSession().slicer.settings());
handle("cadkit:slicer-save", async (values) => {
  const session = requireSession();
  if (!values || typeof values !== "object")
    throw new Error("Invalid slicer settings");
  const { kind, price, currency, bed } = values;
  const result = await session.slicer.save({ kind, price, currency, bed });
  assertSession(session);
  return result;
});
handle("cadkit:slicer-pick", async (key) => {
  const session = requireSession();
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
  assertSession(session);
  return selected.canceled
    ? session.slicer.settings()
    : session.slicer.save({ [key]: selected.filePaths[0] });
});
handle("cadkit:slicer-action", (method, params) => {
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
  return dispatch(requireSession(), method, params);
});
handle("cadkit:slicer-reveal", (id) =>
  shell.openPath(
    requireSession().slicer.list(checkedString(id, "slice ID")).directory,
  ),
);
handle("cadkit:mcp-config", () => {
  const session = requireSession();
  clipboard.writeText(
    JSON.stringify(
      {
        mcpServers: {
          cadkit: {
            command: app.isPackaged
              ? process.execPath
              : (process.env.npm_node_execpath ?? "node"),
            args: [
              app.isPackaged ? "--mcp" : path.join(desktop, "electron/mcp.mjs"),
              "--project-dir",
              session.target.projectDir,
              "--project",
              session.target.reference,
            ],
          },
        },
      },
      null,
      2,
    ),
  );
  return { copied: true };
});
handle("cadkit:mechanical-report", (params) =>
  dispatch(requireSession(), "mechanical_report", params),
);
handle("cadkit:measure", (params) =>
  dispatch(requireSession(), "measure", { ...params, show: false }),
);
handle("cadkit:export", async (name, validation_override) => {
  const session = requireSession();
  if (
    !session.current ||
    typeof name !== "string" ||
    !session.snapshot.project.parts.some((part) => part.name === name)
  )
    throw new Error("Unknown part");
  if (
    validation_override !== undefined &&
    (typeof validation_override !== "string" ||
      validation_override.trim().length < 3 ||
      validation_override.length > 1000)
  )
    throw new Error("Invalid validation override");
  if (session.status.phase !== "ready")
    throw new Error("Wait for a successful current build before exporting");
  const revision = session.snapshot.revision;
  const selected = await dialog.showOpenDialog(window, {
    title: `Export ${name} · choose a destination folder`,
    defaultPath: path.join(session.target.projectDir, "build"),
    properties: ["openDirectory", "createDirectory"],
  });
  if (selected.canceled) return null;
  checkRevision(session, revision);
  if (session.status.phase !== "ready")
    throw new Error("The model changed while choosing an export destination");
  const result = await session.current.call("export_part", {
    name,
    output_dir: path.join(selected.filePaths[0], name),
    validation_override,
  });
  checkRevision(session, revision);
  await shell.openPath(result.directory);
  return result;
});

app
  .whenReady()
  .then(async () => {
    window = new BrowserWindow({
      show: !smokeTest,
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
    window.webContents.on("did-start-loading", () =>
      rejectControls("CadKit view reloaded"),
    );
    window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    window.webContents.on("will-navigate", (event) => event.preventDefault());
    const initial = resolveRuntime(runtimeOptions);
    if (initial) {
      const explicitPython = argument(process.argv, "--python");
      await transition(() =>
        activate({
          projectDir: initial.projectDir,
          reference: initial.reference,
          python: explicitPython,
        }),
      );
    } else await publishLauncher();
    await window.loadFile(path.join(desktop, "dist/index.html"));
    if (!smokeTest) return;
    const session = requireSession();
    const scene =
      session.snapshot ?? (await (session.building ?? rebuild(session)));
    const deadline = Date.now() + 60000;
    let ui;
    do {
      ui = await control(session, "get_state");
      if (ui.revision === scene.revision) break;
      await new Promise((resolve) => setTimeout(resolve, 100));
    } while (Date.now() < deadline);
    if (ui.revision !== scene.revision)
      throw new Error("Packaged renderer did not load the CAD scene");
    if (!smokeOutput) throw new Error("--smoke-test requires --smoke-output");
    writeFileSync(
      smokeOutput,
      JSON.stringify({
        packaged: app.isPackaged,
        projectDir: session.target.projectDir,
        python: session.runtime.python,
        components: scene.components.length,
        workerRevision: scene.revision,
        rendererRevision: ui.revision,
      }),
    );
    app.quit();
  })
  .catch((error) => {
    if (smokeTest) {
      if (smokeOutput)
        writeFileSync(smokeOutput, JSON.stringify({ error: error.message }));
      active?.current?.close();
      active?.candidate?.close();
      app.exit(1);
      return;
    }
    // Keep Home usable even if an explicit CLI project cannot be opened.
    dialog.showErrorBox("CadKit could not open the project", error.message);
    void stopSession().finally(async () => {
      await publishLauncher();
      if (window && !window.isDestroyed())
        await window.loadFile(path.join(desktop, "dist/index.html"));
    });
  });
app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => {
  void stopSession().catch(() => {});
  rejectControls("CadKit closed");
});

handle("cadkit:render-action", async (action, params = {}) => {
  const session = requireSession();
  const renderer = session.renderer;
  if (action === "settings") return renderer.settings();
  if (action === "pick") {
    const selected = await dialog.showOpenDialog(window, {
      properties: ["openFile"],
    });
    assertSession(session);
    return selected.canceled
      ? renderer.settings()
      : renderer.save(selected.filePaths[0]);
  }
  if (action === "start") {
    checkRevision(session, params.revision);
    return renderer.start(params);
  }
  if (action === "list") return renderer.list();
  if (action === "cancel")
    return renderer.cancel(checkedString(params.id, "render ID"));
  if (action === "preview")
    return renderer.preview(checkedString(params.id, "render ID"));
  if (action === "folder")
    return shell.openPath(
      renderer.list(checkedString(params.id, "render ID")).directory,
    );
  if (action === "open") {
    const job = renderer.list(checkedString(params.id, "render ID"));
    if (job.phase !== "complete") throw new Error("Render is not complete");
    return shell.openPath(job.output);
  }
  throw new Error("Unknown render action");
});
