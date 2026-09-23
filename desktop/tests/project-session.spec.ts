import { test, expect } from "@playwright/test";
import { launchElectron } from "./electron";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { callApp, connectionFile } from "../electron/local-bridge.mjs";

const slowFixture = `
import os
import time
from pathlib import Path
import cadquery as cq
import cadkit as ck

def body():
    Path(__file__).with_name('building.pid').write_text(str(os.getpid()))
    time.sleep(30)
    return cq.Workplane('XY').box(10, 10, 10).val()

assembly = ck.Assembly('slow-project')
assembly.fix(assembly.add(ck.Part('slow-block', body, ck.FDM('PLA'))))
PROJECT = assembly.as_project()
`;
const fastFixture = `
import cadquery as cq
import cadkit as ck
assembly = ck.Assembly('replacement-project')
assembly.fix(assembly.add(ck.Part('replacement-block', lambda: cq.Workplane('XY').box(10, 10, 10).val(), ck.FDM('PLA'))))
PROJECT = assembly.as_project()
`;

test("Home stops an in-flight build and isolates the next project session", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "cadkit-session-"));
  const slow = path.join(directory, "slow");
  const fast = path.join(directory, "fast");
  await Promise.all([mkdir(slow), mkdir(fast)]);
  await Promise.all([
    writeFile(path.join(slow, "project.py"), slowFixture),
    writeFile(path.join(fast, "project.py"), fastFixture),
  ]);
  const app = await launchElectron({
    args: [
      path.resolve("."),
      "--python",
      process.env.CADKIT_TEST_PYTHON ?? path.resolve("../.venv/bin/python"),
    ],
    env: { ...process.env, CADKIT_USER_DATA: path.join(directory, "profile") },
  });
  try {
    const page = await app.firstWindow();
    await expect(page.getByTestId("project-home")).toBeVisible();
    const opened = await page.evaluate(
      (projectDir) =>
        window.cadkit.openProject({ projectDir, reference: "project:PROJECT" }),
      slow,
    );
    const oldSession = opened.active!.sessionId;
    await expect
      .poll(async () =>
        readFile(path.join(slow, "building.pid"), "utf8").catch(() => ""),
      )
      .toMatch(/^\d+$/);
    const pid = Number(await readFile(path.join(slow, "building.pid"), "utf8"));
    // Keep a real load waiting on the native worker when Home interrupts it.
    await page.evaluate(() => {
      (window as any).interruptedLoad = window.cadkit.load().then(
        () => "unexpected success",
        (error: Error) => error.message,
      );
    });
    const closed = await page.evaluate(() => window.cadkit.closeProject());
    expect(closed.active).toBeNull();
    expect(await page.evaluate(() => (window as any).interruptedLoad)).toMatch(
      /replaced|changed|stopped/i,
    );
    await expect(page.getByTestId("project-home")).toBeVisible();
    await expect
      .poll(() => {
        try {
          process.kill(pid, 0);
          return true;
        } catch (error: any) {
          if (error.code === "ESRCH") return false;
          throw error;
        }
      })
      .toBe(false);
    await expect(
      callApp(await connectionFile(slow, "project:PROJECT"), "get_state"),
    ).rejects.toThrow(/not running|disconnected|ENOENT|ECONNREFUSED/);
    await page.evaluate(() => {
      (window as any).lateEvents = [];
      window.cadkit.onEvent((event) => (window as any).lateEvents.push(event));
    });
    await rm(path.join(slow, "building.pid"));
    // A Python edit in the closed project must not restart its old watcher.
    await writeFile(
      path.join(slow, "project.py"),
      slowFixture + "\n# edited after closing\n",
    );
    const replacement = await page.evaluate(
      (projectDir) =>
        window.cadkit.openProject({ projectDir, reference: "project:PROJECT" }),
      fast,
    );
    expect(replacement.active!.sessionId).not.toBe(oldSession);
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    const current = await page.evaluate(() => window.cadkit.load());
    expect(current.scene!.project.name).toBe("replacement-project");
    expect(current.scene!.components.map((item) => item.name)).toEqual([
      "replacement-block",
    ]);
    expect(
      await page.evaluate(
        (sessionId) =>
          (window as any).lateEvents.filter(
            (event: any) => event.sessionId === sessionId,
          ),
        oldSession,
      ),
    ).toEqual([]);
    await expect(
      readFile(path.join(slow, "building.pid")),
    ).rejects.toMatchObject({ code: "ENOENT" });
    expect(
      (
        await callApp(
          await connectionFile(fast, "project:PROJECT"),
          "get_state",
        )
      ).project.name,
    ).toBe("replacement-project");
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
