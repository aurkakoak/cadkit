import assert from "node:assert/strict";
import childProcess from "node:child_process";
import { createRequire } from "node:module";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const require = createRequire(import.meta.url);
const hookPath = require.resolve("../scripts/check-bundle.cjs");

async function fixture(t, result) {
  const directory = await mkdtemp(
    path.join(os.tmpdir(), "cadkit-bundle-check-"),
  );
  await mkdir(path.join(directory, "bundle"));
  await writeFile(
    path.join(directory, "bundle/runtime.json"),
    JSON.stringify({ platform: "linux", arch: "x64" }),
  );
  await writeFile(
    path.join(directory, "package.json"),
    JSON.stringify({ version: "0.5.0" }),
  );
  t.after(async () => {
    delete require.cache[hookPath];
    await rm(directory, { recursive: true, force: true });
  });
  const runtime = t.mock.method(childProcess, "spawnSync", () => result);
  delete require.cache[hookPath];
  const checkBundle = require(hookPath);
  return {
    check: () =>
      checkBundle({
        packager: { info: { appDir: directory } },
        electronPlatformName: "linux",
        arch: 1,
      }),
    runtime,
    directory,
  };
}

test("packaging verifies matching installed and imported CadKit with isolated bundled Python", async (t) => {
  const { check, runtime, directory } = await fixture(t, {
    status: 0,
    stdout: JSON.stringify({ distribution: "0.5.0", module: "0.5.0" }),
  });
  await check();
  const [executable, args, options] = runtime.mock.calls[0].arguments;
  assert.equal(executable, path.join(directory, "bundle/python/bin/python3"));
  assert.deepEqual(args.slice(0, 2), ["-I", "-c"]);
  assert.match(args[2], /importlib\.metadata\.version\('cadkit'\)/);
  assert.match(args[2], /cadkit\.__version__/);
  assert.equal(options.env, undefined);
  assert.equal(runtime.mock.calls.length, 1);
});

test("packaging rejects a stale distribution or an inconsistent imported module", async (t) => {
  for (const versions of [
    { distribution: "0.2.0", module: "0.2.0" },
    { distribution: "0.5.0", module: "0.2.0" },
    { distribution: "0.2.0", module: "0.5.0" },
  ]) {
    await t.test(JSON.stringify(versions), async (t) => {
      const { check } = await fixture(t, {
        status: 0,
        stdout: JSON.stringify(versions),
      });
      await assert.rejects(
        check(),
        /does not match desktop 0\.5\.0.*npm run bundle:python/,
      );
    });
  }
});

test("packaging reports missing, broken and invalid bundle checks with rebuild guidance", async (t) => {
  for (const [name, result] of [
    ["missing interpreter", { error: new Error("spawn ENOENT"), status: null }],
    ["broken import", { status: 1, stderr: "ModuleNotFoundError: cadkit" }],
    ["invalid report", { status: 0, stdout: "not JSON" }],
  ]) {
    await t.test(name, async (t) => {
      const { check } = await fixture(t, result);
      await assert.rejects(check(), /Bundled CadKit.*npm run bundle:python/);
    });
  }
});
