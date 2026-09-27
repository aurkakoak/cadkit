import { test, expect } from "@playwright/test";
import { launchElectron } from "./electron";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

test("reopening restores native geometry and watches skipped lazy imports", async () => {
  const directory = await mkdtemp(
    path.join(os.tmpdir(), "cadkit-native-cache-"),
  );
  const projectDir = path.join(directory, "project");
  const external = path.join(directory, "external");
  await mkdir(projectDir);
  await mkdir(external);
  const dimensions = path.join(external, "dimensions.py");
  await writeFile(dimensions, "WIDTH = 10\n");
  await writeFile(
    path.join(projectDir, "project.py"),
    `
from pathlib import Path
import sys
import cadquery as cq
import cadkit as ck

def body():
    sys.path.insert(0, ${JSON.stringify(external)})
    import dimensions
    with Path('calls.txt').open('a') as f:
        f.write('built\\n')
    return cq.Solid.makeBox(dimensions.WIDTH, 2, 3)
a = ck.Assembly('fixture')
a.fix(a.add(ck.Part('part', body, ck.FDM('PETG'))))
PROJECT = a.as_project()
`,
  );
  const options = {
    args: [
      path.resolve("."),
      "--project-dir",
      projectDir,
      "--project",
      "project:PROJECT",
      "--python",
      path.resolve("../.venv/bin/python"),
    ],
    env: {
      ...process.env,
      CADKIT_USER_DATA: path.join(directory, "profile"),
      CADKIT_GEOMETRY_CACHE: "1",
      PYTHONDONTWRITEBYTECODE: "1",
    },
  };
  let app = await launchElectron(options);
  try {
    let page = await app.firstWindow();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    const first = (await page.evaluate(() => window.cadkit.load())).scene!;
    expect(first.performance?.geometry_cache?.misses).toBe(1);
    await app.close();
    app = await launchElectron(options);
    page = await app.firstWindow();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    const second = (await page.evaluate(() => window.cadkit.load())).scene!;
    expect(second.performance?.geometry_cache?.status).toBe("warm");
    expect(second.performance?.geometry_cache?.hits).toBe(1);
    expect(second.revision).not.toBe(first.revision);
    expect(second.components[0].volume_mm3).toBeCloseTo(60);
    expect(await readFile(path.join(projectDir, "calls.txt"), "utf8")).toBe(
      "built\n",
    );
    await writeFile(dimensions, "WIDTH = 30\n");
    await expect
      .poll(
        async () =>
          (await page.evaluate(() => window.cadkit.load())).scene?.components[0]
            .volume_mm3,
      )
      .toBeCloseTo(180);
    const changed = (await page.evaluate(() => window.cadkit.load())).scene!;
    expect(changed.performance?.geometry_cache?.hits).toBe(0);
    expect(changed.performance?.geometry_cache?.misses).toBe(1);
    expect(await readFile(path.join(projectDir, "calls.txt"), "utf8")).toBe(
      "built\nbuilt\n",
    );
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
