import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdtemp,
  mkdir,
  readFile,
  rename,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import test from "node:test";
import {
  ProjectLibrary,
  normalizeReference,
  projectIdentity,
} from "../electron/projects.mjs";

const execute = promisify(execFile);
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXTkAAAAASUVORK5CYII=",
  "base64",
);

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), "cadkit projects "));
  t.after(() => rm(root, { recursive: true, force: true }));
  const options = {
    userData: path.join(root, "profile"),
    framework: root,
    resourcesPath: path.join(root, "resources"),
    isPackaged: false,
  };
  await mkdir(path.join(root, "examples"));
  await writeFile(
    path.join(root, "examples", "bracket.py"),
    "PROJECT = make_bracket()\n",
  );
  return { root, options, library: new ProjectLibrary(options) };
}

test("canonical identity deduplicates symlinks and default attributes, independent of Python", async (t) => {
  const { root, library } = await fixture(t);
  const folder = path.join(root, "model");
  await mkdir(folder);
  const alias = path.join(root, "alias");
  await symlink(folder, alias, "dir");
  assert.equal(
    normalizeReference(" package.project : "),
    "package.project:PROJECT",
  );
  assert.throws(
    () => normalizeReference("project.py/file:PROJECT"),
    /import reference/,
  );
  const expected = createHash("sha256")
    .update(`${folder}\0project:PROJECT`)
    .digest("hex")
    .slice(0, 24);
  assert.equal(
    await projectIdentity({ projectDir: alias, reference: "project" }),
    expected,
  );
  await library.remember(
    { projectDir: alias, reference: "project", python: "/custom/python" },
    { name: "First name" },
  );
  await library.remember(
    { projectDir: folder, reference: "project:PROJECT" },
    { name: "Renamed" },
  );
  let [recent] = await library.list();
  assert.equal(recent.name, "Renamed");
  assert.equal(recent.python, "/custom/python");
  assert.equal(recent.id, expected);
  await library.remember({
    projectDir: folder,
    reference: "project",
    python: undefined,
  });
  [recent] = await library.list();
  assert.equal(recent.python, undefined);
  assert.equal((await library.list()).length, 1);
  await library.remember({
    projectDir: folder,
    reference: "project:OPEN_PROJECT",
  });
  assert.equal((await library.list()).length, 2);
});

test("recents persist pins, missing folders, previews and metadata without reading project code", async (t) => {
  const { root, options, library } = await fixture(t);
  const first = await library.create(path.join(root, "first"));
  const second = await library.create(path.join(root, "second"));
  const a = await library.remember(first);
  await library.remember(second);
  await library.pin(a.id, true);
  await library.writePreview(a.id, png, { manual: true });
  const alternative = Buffer.concat([png, Buffer.from("different")]);
  await library.writePreview(a.id, alternative);
  await assert.rejects(
    library.writePreview(a.id, Buffer.from("broken")),
    /PNG/,
  );
  await rename(first.projectDir, `${first.projectDir}-moved`);
  const reloaded = new ProjectLibrary(options);
  const records = await reloaded.list();
  assert.equal(records[0].id, a.id);
  assert.equal(records[0].pinned, true);
  assert.equal(records[0].missing, true);
  assert.equal(
    records[0].thumbnail,
    `data:image/png;base64,${png.toString("base64")}`,
  );
  assert.equal(records[1].missing, false);
  await reloaded.remove(a.id);
  assert.equal((await library.list()).length, 1);
  assert.ok(
    await readFile(
      path.join(`${first.projectDir}-moved`, "project.py"),
      "utf8",
    ),
  );
});

test("independent app processes merge concurrent changes instead of overwriting recents", async (t) => {
  const { root, options, library } = await fixture(t);
  const module = new URL("../electron/projects.mjs", import.meta.url).href;
  const script = `import { ProjectLibrary } from ${JSON.stringify(module)};
const library = new ProjectLibrary(JSON.parse(process.argv[1]));
for (let index = 0; index < 8; index++) {
  const record = await library.remember({projectDir: process.argv[2] + '/' + index, reference:'project'});
  await library.pin(record.id, true);
}`;
  await Promise.all(
    ["left", "right"].map((name) =>
      execute(process.execPath, [
        "--input-type=module",
        "-e",
        script,
        JSON.stringify(options),
        path.join(root, name),
      ]),
    ),
  );
  const records = await library.list();
  assert.equal(records.length, 16);
  assert.ok(records.every((record) => record.pinned));
});

test("discovery finds namespace entry points and variants without executing models", async (t) => {
  const { root, library } = await fixture(t);
  const unit = path.join(root, "engine");
  await mkdir(path.join(unit, "assemblies", "fan"), { recursive: true });
  const marker = path.join(root, "executed");
  await writeFile(
    path.join(unit, "project.py"),
    `from .assembly import make_assembly
from pathlib import Path
Path(${JSON.stringify(marker)}).write_text('must not execute')
PROJECT = make_assembly().as_project()
OPEN_PROJECT = make_assembly(covers=False).as_project()
def local():
    LOCAL_PROJECT = None
`,
  );
  await writeFile(
    path.join(unit, "assembly.py"),
    "from .assemblies.fan.parts import make_parts\n",
  );
  await writeFile(
    path.join(unit, "assemblies", "fan", "parts.py"),
    "from ...dimensions import LENGTH\n",
  );
  await mkdir(path.join(unit, ".venv", "bin"), { recursive: true });
  await writeFile(path.join(unit, ".venv", "bin", "python"), "never executed");
  await writeFile(path.join(unit, ".venv", "fake.py"), "FAKE_PROJECT = None\n");
  await mkdir(path.join(unit, "build"));
  await writeFile(
    path.join(unit, "build", "hidden.py"),
    "HIDDEN_PROJECT = None\n",
  );
  const choice = await library.inspect(unit);
  assert.deepEqual(
    choice.entries.map((entry) => entry.reference),
    ["engine.project:PROJECT", "engine.project:OPEN_PROJECT"],
  );
  assert.ok(choice.entries.every((entry) => entry.projectDir === root));
  assert.equal(
    choice.suggestedPython,
    path.join(unit, ".venv", "bin", "python"),
  );
  await assert.rejects(readFile(marker), { code: "ENOENT" });
  const parent = await library.inspect(root);
  assert.ok(
    parent.entries.some(
      (entry) =>
        entry.reference === "engine.project:PROJECT" &&
        entry.projectDir === root,
    ),
  );
});

test("discovery ignores nested declarations and offers multiple explicit entry points", async (t) => {
  const { root, library } = await fixture(t);
  const model = path.join(root, "model");
  await mkdir(model);
  await writeFile(
    path.join(model, "project.py"),
    "PROJECT: object = make_project()\n",
  );
  await writeFile(
    path.join(model, "alternate.py"),
    "from model import PROJECT\n",
  );
  await writeFile(
    path.join(model, "helpers.py"),
    "# PROJECT = fake\ntext = 'PROJECT = fake'\nclass Helper:\n    PROJECT = None\nif __name__ == '__main__':\n    MAIN_PROJECT = None\n",
  );
  await writeFile(path.join(model, "broken.py"), "PROJECT = (\n");
  const choice = await library.inspect(model);
  assert.deepEqual(
    choice.entries.map((entry) => entry.reference),
    ["project:PROJECT", "alternate:PROJECT"],
  );
  assert.ok(choice.warnings.some((warning) => warning.includes("broken.py")));
});

test("discovery handles package entry points and reports bounded scans", async (t) => {
  const { root, library } = await fixture(t);
  const unit = path.join(root, "unit");
  await mkdir(unit);
  await writeFile(
    path.join(unit, "__init__.py"),
    "from .project import PROJECT\n",
  );
  await writeFile(path.join(unit, "project.py"), "PROJECT = make_project()\n");
  let choice = await library.inspect(unit);
  assert.deepEqual(
    choice.entries.map((entry) => entry.reference),
    ["unit.project:PROJECT", "unit:PROJECT"],
  );
  assert.ok(choice.entries.every((entry) => entry.projectDir === root));
  await writeFile(path.join(unit, "too_large.py"), "#".repeat(513 * 1024));
  choice = await library.inspect(unit);
  assert.ok(choice.warnings.some((warning) => warning.includes("limit")));
  const recent = await library.remember(choice.entries[0]);
  assert.equal(recent.name, "unit");
});

test("new projects use public declarations and never replace existing files", async (t) => {
  const { root, options, library } = await fixture(t);
  const target = await library.create(path.join(root, "starter"), "starter");
  const source = await readFile(
    path.join(target.projectDir, "project.py"),
    "utf8",
  );
  assert.match(source, /ck\.Part\(/);
  assert.match(source, /ck\.FDM\(/);
  assert.match(source, /assembly\.add\(plate\)/);
  assert.match(source, /assembly\.as_project\(\)/);
  await assert.rejects(library.create(target.projectDir), /empty folder/);
  assert.equal(
    await readFile(path.join(target.projectDir, "project.py"), "utf8"),
    source,
  );
  const bracket = await library.create(path.join(root, "bracket"), "bracket");
  assert.equal(
    await readFile(path.join(bracket.projectDir, "project.py"), "utf8"),
    "PROJECT = make_bracket()\n",
  );
  await mkdir(path.join(options.resourcesPath, "examples"), {
    recursive: true,
  });
  await writeFile(
    path.join(options.resourcesPath, "examples", "bracket.py"),
    "PROJECT = packaged_bracket()\n",
  );
  const packaged = new ProjectLibrary({ ...options, isPackaged: true });
  const copied = await packaged.create(path.join(root, "packaged"), "bracket");
  assert.equal(
    await readFile(path.join(copied.projectDir, "project.py"), "utf8"),
    "PROJECT = packaged_bracket()\n",
  );
});

test("missing detection retains known namespace source paths and tolerates external imports", async (t) => {
  const { root, library } = await fixture(t);
  const unit = path.join(root, "engine");
  await mkdir(unit);
  await writeFile(path.join(unit, "project.py"), "PROJECT = make_project()\n");
  const target = { projectDir: root, reference: "engine.project:PROJECT" };
  const known = await library.remember(target);
  assert.equal(known.missing, false);
  assert.equal(known.entryFile, undefined);
  const external = await library.remember({
    projectDir: root,
    reference: "installed_package.project:PROJECT",
  });
  assert.equal(external.missing, false);
  await rename(unit, path.join(root, "moved-engine"));
  const absent = (await library.list()).find(
    (record) => record.id === known.id,
  );
  assert.equal(absent.missing, true);
  assert.equal((await library.remember(target)).missing, true);
  await rename(path.join(root, "moved-engine"), unit);
  assert.equal(
    (await library.list()).find((record) => record.id === known.id).missing,
    false,
  );
});

test("locating a moved project retains its name, pin and manual preview", async (t) => {
  const { root, library } = await fixture(t);
  const target = await library.create(path.join(root, "before"));
  const original = await library.remember(
    { ...target, python: "/shared/python" },
    { name: "My design" },
  );
  await library.pin(original.id, true);
  await library.writePreview(original.id, png, { manual: true });
  const movedDirectory = path.join(root, "after");
  await rename(target.projectDir, movedDirectory);
  const moved = await library.remember(
    { projectDir: movedDirectory, reference: target.reference },
    { replaceRecentId: original.id },
  );
  assert.notEqual(moved.id, original.id);
  assert.equal(moved.name, "My design");
  assert.equal(moved.pinned, true);
  assert.equal(moved.python, "/shared/python");
  assert.equal(moved.missing, false);
  assert.equal(
    moved.thumbnail,
    original.thumbnail ?? `data:image/png;base64,${png.toString("base64")}`,
  );
  assert.equal((await library.list()).length, 1);
  await library.writePreview(
    moved.id,
    Buffer.concat([png, Buffer.from("automatic update")]),
  );
  assert.equal((await library.list())[0].thumbnail, moved.thumbnail);
});

test("completed-build rename changes only an existing name and cannot restore a removed recent", async (t) => {
  const { root, library } = await fixture(t);
  const target = await library.create(path.join(root, "model"));
  const recent = await library.remember({
    ...target,
    python: "/custom/python",
  });
  await library.pin(recent.id, true);
  await library.writePreview(recent.id, png, { manual: true });
  const [before] = await library.list();
  await new Promise((resolve) => setTimeout(resolve, 5));
  await library.rename(recent.id, "Built assembly");
  assert.deepEqual(await library.list(), [
    { ...before, name: "Built assembly" },
  ]);
  await library.remove(recent.id);
  await library.rename(recent.id, "Late build result");
  assert.deepEqual(await library.list(), []);
});
