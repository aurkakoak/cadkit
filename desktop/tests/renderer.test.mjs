import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Renderer } from "../electron/renderer.mjs";
const params = {
  revision: "r",
  ids: ["a"],
  mode: "image",
  camera: "Overview",
  width: 32,
  height: 32,
  samples: 1,
  exploded: false,
};
test("closing during export prevents Blender from starting", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "render-test-"));
  let finish, entered;
  const started = new Promise((r) => (entered = r));
  const renderer = new Renderer({
    userData: directory,
    projectDir: directory,
    python: "must-not-run",
    env: process.env,
    publish: () => {},
    exportAssets: () => {
      entered();
      return new Promise((r) => (finish = r));
    },
  });
  try {
    const job = await renderer.start(params);
    await started;
    renderer.close();
    finish();
    await new Promise((r) => setTimeout(r, 30));
    assert.equal(job.phase, "cancelled");
    assert.equal(renderer.processes.size, 0);
    await assert.rejects(renderer.start(params), /closed/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
test("invalid options and concurrent renders are rejected", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "render-test-"));
  const renderer = new Renderer({
    userData: directory,
    projectDir: directory,
    python: "missing",
    env: process.env,
    publish: () => {},
    exportAssets: async () => {
      throw new Error("stale revision");
    },
  });
  try {
    await assert.rejects(renderer.start({ ...params, width: 0 }));
    const job = await renderer.start(params);
    await assert.rejects(renderer.start(params), /already running/);
    await new Promise((r) => setTimeout(r, 30));
    assert.equal(job.phase, "failed");
    assert.equal(job.message, "stale revision");
  } finally {
    renderer.close();
    await rm(directory, { recursive: true, force: true });
  }
});
