import { spawnSync } from "node:child_process";
import { test, expect } from "@playwright/test";
import { launchElectron } from "./electron";
import { mkdtemp, mkdir, writeFile, rm, stat } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
test("renders through Blender and keeps results when reopened", async () => {
  test.skip(
    spawnSync("blender", ["--version"]).status !== 0,
    "Blender is not installed",
  );
  test.setTimeout(120000);
  const directory = await mkdtemp(path.join(os.tmpdir(), "cadkit-render-"));
  const model = path.join(directory, "model");
  await mkdir(model);
  await writeFile(
    path.join(model, "project.py"),
    `import cadkit as ck\nimport cadquery as cq\np=ck.Part('block', body=lambda:cq.Workplane('XY').box(20,15,8).val(), manufacture=ck.FDM('PLA'))\na=ck.Assembly('render-fixture')\na.fix(a.add(p))\nPROJECT=a.as_project()\n`,
  );
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
    await app.evaluate(({ dialog }, folder) => {
      dialog.showOpenDialog = async () => ({
        canceled: false,
        filePaths: [folder],
      });
    }, model);
    await page.getByRole("button", { name: "Open…", exact: true }).click();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible({ timeout: 60000 });
    await page.getByRole("button", { name: "Render", exact: true }).click();
    const panel = page.getByRole("dialog", { name: "Render", exact: true });
    await panel.getByLabel("Width", { exact: true }).fill("128");
    await panel.getByLabel("Height", { exact: true }).fill("96");
    await panel.getByLabel("Samples", { exact: true }).fill("8");
    await panel.getByRole("button", { name: "Render", exact: true }).click();
    await expect(panel.getByAltText("Rendered assembly")).toBeVisible({
      timeout: 60000,
    });
    const jobs = await page.evaluate(() => window.cadkit.renderAction("list"));
    expect((await stat(jobs[0].output)).size).toBeGreaterThan(100);
    await page.screenshot({ path: test.info().outputPath("render-panel.png") });
    await panel.getByRole("button", { name: "Close Render" }).click();
    await page.getByRole("button", { name: "Render", exact: true }).click();
    await expect(panel.getByAltText("Rendered assembly")).toBeVisible();
    await panel.getByLabel("Output", { exact: true }).selectOption("scene");
    await panel.getByRole("button", { name: "Render", exact: true }).click();
    await expect
      .poll(
        async () =>
          (await page.evaluate(() => window.cadkit.renderAction("list")))[0]
            .phase,
      )
      .toBe("complete");
    const scenes = await page.evaluate(() =>
      window.cadkit.renderAction("list"),
    );
    expect((await stat(scenes[0].output)).size).toBeGreaterThan(100);
    await panel.getByLabel("Output", { exact: true }).selectOption("animation");
    await panel.getByRole("button", { name: "Render", exact: true }).click();
    await expect(
      panel.getByText("Selected components have no explosion offsets", {
        exact: true,
      }),
    ).toBeVisible();
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
