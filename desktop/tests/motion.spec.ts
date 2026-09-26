import { test, expect } from "@playwright/test";
import { Matrix4, Vector3 } from "three";
import {
  coordinates,
  controlRange,
  MotionPlayer,
  type MotionGraph,
} from "../src/motion";
import { transforms } from "../src/motionTransforms";
import { launchElectron } from "./electron";
import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
const graph: MotionGraph = {
  schema_version: 1,
  nodes: [
    { matrix: new Matrix4().makeTranslation(10, 0, 0).toArray() },
    { joint: "turn", kind: "revolute" },
    { product: [0, 1] },
  ],
  targets: {
    arm: {
      node: 2,
      inverse: new Matrix4().makeTranslation(-10, 0, 0).toArray(),
    },
  },
  joints: [
    {
      id: "turn",
      kind: "revolute",
      position: 0,
      limits: null,
      moving_components: ["arm"],
    },
  ],
  couplings: [],
};
test("world-space pivot, signed coupling limits and default pose", () => {
  const posed = transforms(graph, coordinates(graph, { turn: 90 }));
  const p = new Vector3(15, 0, 0).applyMatrix4(posed.get("arm")!);
  expect(p.x).toBeCloseTo(10);
  expect(p.y).toBeCloseTo(5);
  expect(
    transforms(graph, coordinates(graph, {})).get("arm")!.equals(new Matrix4()),
  ).toBeTruthy();
  const coupled: MotionGraph = {
    ...graph,
    joints: [
      ...graph.joints,
      {
        id: "driven",
        kind: "revolute",
        position: 10,
        limits: [-20, 40],
        moving_components: [],
      },
    ],
    couplings: [{ driver: "turn", driven: "driven", ratio: -2, offset: 10 }],
  };
  expect(controlRange(coupled, "turn")).toEqual([-15, 15]);
  expect(coordinates(coupled, { turn: 10 }).driven).toBe(-10);
  expect(() => coordinates(coupled, { turn: 16 })).toThrow(/limits/);
  expect(() => coordinates(coupled, { driven: 10 })).toThrow(/Invalid/);
});
for (const kind of ["revolute", "slider"] as const) {
  test(`${kind} preview moves displayed geometry without rebuilding or editing the project`, async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), "cadkit-motion-"));
    const code = `import cadkit as ck\nimport cadquery as cq\nfrom pathlib import Path\ndef body():\n    with Path(__file__).with_name('builds.txt').open('a') as f: f.write('build\\n')\n    return cq.Workplane('XY').box(24,6,4).translate((12,0,0)).val()\np=ck.Part('arm',body=body,manufacture=ck.FDM('PLA'),ports={'axis':ck.Frame()})\na=ck.Assembly('motion-fixture')\nbase=a.add('base',p)\narm=a.add('rotor',p)\na.fix(base,at=ck.Frame((0,0,-10)))\na.connect('spin',ck.${kind === "slider" ? "Slider(limits=(-100, 100))" : "Revolute()"},parent=base.port('axis'),child=arm.port('axis'))\nPROJECT=a.as_project()\n`;
    await writeFile(path.join(dir, "project.py"), code);
    const app = await launchElectron({
      args: [
        path.resolve("."),
        "--python",
        process.env.CADKIT_TEST_PYTHON ?? path.resolve("../.venv/bin/python"),
      ],
      env: { ...process.env, CADKIT_USER_DATA: path.join(dir, "profile") },
    });
    try {
      const page = await app.firstWindow();
      await app.evaluate(({ dialog }, folder) => {
        dialog.showOpenDialog = async () => ({
          canceled: false,
          filePaths: [folder],
        });
      }, dir);
      await page.getByRole("button", { name: "Open…", exact: true }).click();
      await expect(
        page.getByText("Build up to date", { exact: true }),
      ).toBeVisible({ timeout: 60000 });
      const builds = await readFile(path.join(dir, "builds.txt"), "utf8");
      const angle = page.getByRole("slider", {
        name: `spin ${kind === "slider" ? "position" : "angle"}`,
      });
      await expect(page.locator(".motion-playback label")).toContainText(
        kind === "slider" ? "mm/s" : "rpm",
      );
      const canvas = page.locator(".viewport-host canvas").first();
      const before = await canvas.screenshot();
      await angle.fill("90");
      await expect(page.locator(".motion-coordinate output")).toHaveText(
        kind === "slider" ? "90.0 mm" : "90.0°",
      );
      await page.getByLabel("spin speed").fill("-10");
      await expect(
        page.getByRole("button", { name: /Motion preview/ }),
      ).toBeVisible();
      const after = await canvas.screenshot();
      expect(after.equals(before)).toBe(false);
      await expect(page.getByLabel("Measurement object A")).toBeDisabled();
      await page
        .getByRole("button", { name: "Play spin", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Pause spin", exact: true }),
      ).toBeVisible();
      await expect
        .poll(async () => Number(await angle.inputValue()))
        .not.toBe(90);
      await page
        .getByRole("button", { name: "Pause spin", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Reset motion", exact: true })
        .click();
      await expect(angle).toHaveValue("0");
      await expect(page.getByLabel("Measurement object A")).toBeEnabled();
      await page.screenshot({
        path: test.info().outputPath("motion-panel.png"),
      });
      expect(await readFile(path.join(dir, "project.py"), "utf8")).toBe(code);
      expect(await readFile(path.join(dir, "builds.txt"), "utf8")).toBe(builds);
    } finally {
      await app.close();
      await rm(dir, { recursive: true, force: true });
    }
  });
}

test("playback stops at a limit and reset cancels outstanding frames", () => {
  const callbacks = new Map<number, FrameRequestCallback>();
  const originalRequest = globalThis.requestAnimationFrame;
  const originalCancel = globalThis.cancelAnimationFrame;
  let sequence = 0;
  globalThis.requestAnimationFrame = (callback) => {
    callbacks.set(++sequence, callback);
    return sequence;
  };
  globalThis.cancelAnimationFrame = (id) => {
    callbacks.delete(id);
  };
  const player = new MotionPlayer({
    ...graph,
    joints: [{ ...graph.joints[0], limits: [0, 5] }],
  });
  try {
    player.toggle("turn");
    const step = (time: number) => {
      const [id, callback] = [...callbacks][0];
      callbacks.delete(id);
      callback(time);
    };
    step(1000);
    step(1100);
    expect(player.getSnapshot().values.turn).toBe(5);
    expect(player.getSnapshot().playing.turn).toBe(false);
    expect(callbacks.size).toBe(0);
    player.reset();
    expect(player.getSnapshot().active).toBe(false);
    expect(player.getSnapshot().values.turn).toBe(0);
    player.toggle("turn");
    player.dispose();
    expect(callbacks.size).toBe(0);
  } finally {
    player.dispose();
    globalThis.requestAnimationFrame = originalRequest;
    globalThis.cancelAnimationFrame = originalCancel;
  }
});

test("slider playback uses signed mm/s, retains linear coordinates and stops exactly at limits", () => {
  const callbacks = new Map<number, FrameRequestCallback>();
  const originalRequest = globalThis.requestAnimationFrame;
  const originalCancel = globalThis.cancelAnimationFrame;
  let sequence = 0;
  globalThis.requestAnimationFrame = (callback) => {
    callbacks.set(++sequence, callback);
    return sequence;
  };
  globalThis.cancelAnimationFrame = (id) => {
    callbacks.delete(id);
  };
  const player = new MotionPlayer({
    ...graph,
    joints: [
      { ...graph.joints[0], kind: "slider", position: 250, limits: [249, 252] },
    ],
  });
  const step = (time: number) => {
    const [id, callback] = [...callbacks][0];
    callbacks.delete(id);
    callback(time);
  };
  try {
    let displayed = 250;
    player.onFrame((values) => {
      displayed = values.turn;
    });
    player.speed("turn", 10);
    player.toggle("turn");
    step(1000);
    step(1100);
    expect(displayed).toBe(251);
    step(1200);
    expect(player.getSnapshot().values.turn).toBe(252);
    expect(player.getSnapshot().playing.turn).toBe(false);
    expect(callbacks.size).toBe(0);
    player.speed("turn", -10);
    player.toggle("turn");
    step(2000);
    step(2100);
    step(2200);
    step(2300);
    expect(player.getSnapshot().values.turn).toBe(249);
    expect(player.getSnapshot().playing.turn).toBe(false);
    expect(callbacks.size).toBe(0);
    player.reset();
    expect(player.getSnapshot().values.turn).toBe(250);
    expect(player.getSnapshot().active).toBe(false);
  } finally {
    player.dispose();
    globalThis.requestAnimationFrame = originalRequest;
    globalThis.cancelAnimationFrame = originalCancel;
  }
});
