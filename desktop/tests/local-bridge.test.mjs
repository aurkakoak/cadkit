import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  callApp,
  connectionFile,
  startBridge,
} from "../electron/local-bridge.mjs";

test("normalized project identity has one bridge, which can reopen after closing", async (t) => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "cadkit-bridge-"));
  let bridge;
  t.after(async () => {
    await bridge?.close();
    await rm(directory, { recursive: true, force: true });
  });
  bridge = await startBridge(directory, "project", async () => ({
    project: "first",
  }));
  assert.equal(
    bridge.file,
    await connectionFile(directory, " project:PROJECT "),
  );
  await assert.rejects(
    startBridge(directory, "project:PROJECT", async () => ({
      project: "duplicate",
    })),
    /already open|EADDRINUSE/,
  );
  assert.deepEqual(await callApp(bridge.file, "get_state"), {
    project: "first",
  });
  await bridge.close();
  bridge = await startBridge(directory, "project:PROJECT", async () => ({
    project: "reopened",
  }));
  assert.deepEqual(await callApp(bridge.file, "get_state"), {
    project: "reopened",
  });
});

test("closing a bridge rejects pending calls without leaking them into another target", async (t) => {
  const directory = await mkdtemp(
    path.join(os.tmpdir(), "cadkit-bridge-pending-"),
  );
  let bridge;
  let finish;
  t.after(async () => {
    finish?.({ stale: true });
    await bridge?.close();
    await rm(directory, { recursive: true, force: true });
  });
  let entered;
  const requested = new Promise((resolve) => {
    entered = resolve;
  });
  bridge = await startBridge(directory, "project:PROJECT", async () => {
    entered();
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  const pending = callApp(bridge.file, "get_state");
  const rejected = assert.rejects(pending, /disconnected|ECONNRESET/);
  await requested;
  await bridge.close();
  await rejected;
  bridge = await startBridge(directory, "project:OTHER", async () => ({
    current: true,
  }));
  finish({ stale: true });
  assert.deepEqual(await callApp(bridge.file, "get_state"), { current: true });
});
