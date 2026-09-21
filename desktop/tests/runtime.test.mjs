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
  for (const platform of ["win32", "darwin"]) {
    const executable = pythonExecutable(
      path.join(resourcesPath, "python"),
      platform,
    );
    mkdirSync(path.dirname(executable), { recursive: true });
    writeFileSync(executable, "");
  }
  return {
    argv: [],
    cwd: root,
    framework: root,
    resourcesPath,
    userData: path.join(root, "profile"),
    isPackaged: true,
    env: {
      PYTHONHOME: "/wrong-python",
      PYTHONPATH: "/wrong-packages",
      VIRTUAL_ENV: "/wrong-venv",
      PATH: "/usr/bin",
    },
  };
}

test("packaged first launch creates editable example and preserves subsequent edits", (t) => {
  const options = fixture(t);
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

test("macOS and Windows bundled runtime wins over a project venv", (t) => {
  const options = fixture(t);
  for (const platform of ["darwin", "win32"]) {
    const venv = path.join(
      options.cwd,
      ".venv",
      ...(platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]),
    );
    mkdirSync(path.dirname(venv), { recursive: true });
    writeFileSync(venv, "");
    const runtime = resolveRuntime({
      ...options,
      platform,
      argv: ["--project-dir", options.cwd, "--project", "bracket:PROJECT"],
    });
    assert.equal(runtime.projectDir, options.cwd);
    assert.equal(runtime.reference, "bracket:PROJECT");
    assert.equal(
      runtime.python,
      pythonExecutable(path.join(options.resourcesPath, "python"), platform),
    );
  }
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
  assert.throws(() => resolveRuntime(options), /Bundled Python is missing/);
  assert.throws(() => argument(["--python"], "--python"), /requires a value/);
  assert.throws(
    () => argument(["--project", "--python", "python"], "--project"),
    /requires a value/,
  );
});
