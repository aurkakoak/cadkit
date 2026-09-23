import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  argument,
  pythonExecutable,
  resolveRuntime,
} from "../electron/runtime.mjs";

function fixture(t) {
  const root = mkdtempSync(path.join(os.tmpdir(), "cadkit runtime "));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const resourcesPath = path.join(root, "App Resources");
  mkdirSync(path.join(resourcesPath, "examples"), { recursive: true });
  writeFileSync(
    path.join(resourcesPath, "examples", "bracket.py"),
    "# original example\n",
  );
  const executable = pythonExecutable(
    path.join(resourcesPath, "python"),
    "darwin",
  );
  mkdirSync(path.dirname(executable), { recursive: true });
  writeFileSync(executable, "");
  return {
    argv: [],
    cwd: root,
    framework: root,
    resourcesPath,
    userData: path.join(root, "profile"),
    isPackaged: true,
    platform: "darwin",
    env: {
      PYTHONHOME: "/wrong-python",
      PYTHONPATH: "/wrong-packages",
      VIRTUAL_ENV: "/wrong-venv",
      PATH: "/usr/bin",
    },
  };
}

test("normal launch opens Home without creating a project or requiring Python", (t) => {
  const options = fixture(t);
  rmSync(path.join(options.resourcesPath, "python"), { recursive: true });
  assert.equal(resolveRuntime(options), null);
  assert.equal(resolveRuntime({ ...options, isPackaged: false }), null);
  assert.equal(
    resolveRuntime({ ...options, argv: ["--python", "/custom/python"] }),
    null,
  );
});

test("explicit smoke launch creates editable example and preserves subsequent edits", (t) => {
  const options = fixture(t);
  options.argv = ["--smoke-test"];
  const first = resolveRuntime(options);
  assert.equal(first.reference, "project:PROJECT");
  const project = path.join(first.projectDir, "project.py");
  assert.equal(readFileSync(project, "utf8"), "# original example\n");
  writeFileSync(project, "# user changes\n");
  resolveRuntime(options);
  assert.equal(readFileSync(project, "utf8"), "# user changes\n");
  assert.equal(first.workerEnv.PYTHONHOME, undefined);
  assert.equal(first.workerEnv.VIRTUAL_ENV, undefined);
  assert.equal(first.workerEnv.PYTHONPATH, first.projectDir);
  assert.equal(first.workerEnv.PYTHONNOUSERSITE, "1");
  assert.equal(first.workerEnv.PATH, "/usr/bin");
});

test("macOS bundled runtime wins over a project venv", (t) => {
  const options = fixture(t);
  const venv = path.join(options.cwd, ".venv", "bin", "python");
  mkdirSync(path.dirname(venv), { recursive: true });
  writeFileSync(venv, "");
  const runtime = resolveRuntime({
    ...options,
    argv: ["--project-dir", options.cwd, "--project", "bracket:PROJECT"],
  });
  assert.equal(runtime.projectDir, options.cwd);
  assert.equal(runtime.reference, "bracket:PROJECT");
  assert.equal(
    runtime.python,
    pythonExecutable(path.join(options.resourcesPath, "python"), "darwin"),
  );
});

test("Linux development uses the selected project's virtual environment", (t) => {
  const options = fixture(t);
  const python = path.join(options.cwd, ".venv", "bin", "python");
  mkdirSync(path.dirname(python), { recursive: true });
  writeFileSync(python, "");
  const runtime = resolveRuntime({
    ...options,
    platform: "linux",
    isPackaged: false,
    argv: ["--project-dir", options.cwd],
  });
  assert.equal(runtime.python, python);
  assert.equal(runtime.projectDir, options.cwd);
});

test("explicit Python override and development imports remain available", (t) => {
  const options = fixture(t);
  const runtime = resolveRuntime({
    ...options,
    isPackaged: false,
    argv: ["--project-dir", options.cwd, "--python", "/custom/python"],
  });
  assert.equal(runtime.python, "/custom/python");
  assert.equal(
    runtime.workerEnv.PYTHONPATH,
    [path.join(options.framework, "src"), options.cwd, "/wrong-packages"].join(
      path.delimiter,
    ),
  );
});

test("missing bundled runtime and malformed CLI options fail clearly", (t) => {
  const options = fixture(t);
  rmSync(path.join(options.resourcesPath, "python"), { recursive: true });
  assert.throws(
    () => resolveRuntime({ ...options, argv: ["--project-dir", options.cwd] }),
    /Bundled Python is missing/,
  );
  assert.throws(() => argument(["--python"], "--python"), /requires a value/);
  assert.throws(
    () => argument(["--project", "--python", "python"], "--project"),
    /requires a value/,
  );
});

test("explicit references normalize omitted attributes without changing import root", (t) => {
  const options = fixture(t);
  const runtime = resolveRuntime({
    ...options,
    argv: ["--project", " model.project "],
  });
  assert.equal(runtime.projectDir, options.cwd);
  assert.equal(runtime.reference, "model.project:PROJECT");
});
