import { test, expect } from "@playwright/test";
import { launchElectron } from "./electron";
import { callApp, connectionFile } from "../electron/local-bridge.mjs";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
const source = `
from pathlib import Path
import cadquery as cq
import cadkit as ck

def make():
    root = ck.Assembly('variants')
    width = root.variant('width', ck.Variant(('small','large'), default='small', label='Width'))
    a = ck.Assembly('base')
    base = a.variant('base', ck.Variant(('printed','hybrid','broken'), default='printed', label='Base'))
    if base == 'broken': raise ValueError('Alternative failed')
    for i, name in enumerate(['shell'] if base == 'printed' else ['top', 'bottom', 'skirt']):
        def body():
            with Path(__file__).with_name('build-count.txt').open('a') as f: f.write(f'{base}:{width}\\n')
            return cq.Workplane('XY').box((10 if width == 'small' else 20) + float(Path(__file__).with_name('width.dat').read_text()), 10, 2)
        a.fix(a.add(name, ck.Part(name, body, ck.FDM('PLA'))), at=ck.Frame((0,0,i*5)))
    root.fix(root.add(a))
    return root.as_project()
PROJECT = ck.Variants(make, dependencies=('width.dat',)).project()
`;
test("variants restore native geometry, survive failure, and invalidate on edits", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "cadkit-variants-"));
  await writeFile(path.join(directory, "project.py"), source);
  await writeFile(path.join(directory, "width.dat"), "0");
  const app = await launchElectron({
    args: [
      path.resolve("."),
      "--project-dir",
      directory,
      "--project",
      "project:PROJECT",
      "--python",
      path.resolve("../.venv/bin/python"),
    ],
    env: { ...process.env, CADKIT_USER_DATA: path.join(directory, ".cadkit") },
  });
  try {
    const page = await app.firstWindow();
    const selector = page.getByLabel("Variant Base");
    await expect(selector).toHaveValue("printed");
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    const first = (await page.evaluate(() => window.cadkit.load())).scene!;
    await expect(
      page
        .locator('[data-node-id="/variants/base"]')
        .getByLabel("Variant Base"),
    ).toBeVisible();
    await page.evaluate(
      (revision) => window.cadkit.warmVariants(revision),
      first.revision,
    );
    expect(
      (await page.evaluate(() => window.cadkit.load())).scene!.revision,
    ).toBe(first.revision);
    await expect(page.locator(".viewport-host canvas").first()).toBeVisible();
    await page.evaluate(() => {
      (window as any).firstCanvas = document.querySelector(
        ".viewport-host canvas",
      );
    });
    await callApp(
      await connectionFile(directory, "project:PROJECT"),
      "set_variants",
      { revision: first.revision, selection: { base: "hybrid" } },
    );
    await expect(selector).toHaveValue("hybrid");
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    let current = (await page.evaluate(() => window.cadkit.load())).scene!;
    expect(current.project.parts).toHaveLength(3);
    expect(current.cached).toBe(true);
    const countSmall = async () =>
      (await readFile(path.join(directory, "build-count.txt"), "utf8"))
        .split("\n")
        .filter((line) => line.endsWith(":small")).length;
    const count = await countSmall();
    await selector.selectOption("printed");
    await expect(selector).toHaveValue("printed");
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    current = (await page.evaluate(() => window.cadkit.load())).scene!;
    expect(current.cached).toBe(true);
    await expect
      .poll(() =>
        page.evaluate(() => {
          const canvas = (window as any).firstCanvas as HTMLCanvasElement;
          return canvas.isConnected && canvas.getBoundingClientRect().width > 0;
        }),
      )
      .toBe(true);
    expect(current.revision).not.toBe(first.revision);
    expect(await countSmall()).toBe(count);
    await selector.selectOption("hybrid");
    await expect(selector).toHaveValue("hybrid");
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    current = (await page.evaluate(() => window.cadkit.load())).scene!;
    const ids = current.components.slice(0, 2).map((c) => c.id) as [
      string,
      string,
    ];
    const result = await page.evaluate(
      ({ revision, ids }) => window.cadkit.measure({ revision, ids }),
      { revision: current.revision, ids },
    );
    expect(result.minimum_mm).toBeCloseTo(3);
    await expect(
      page.evaluate(
        ({ revision, ids }) => window.cadkit.measure({ revision, ids }),
        { revision: first.revision, ids },
      ),
    ).rejects.toThrow(/Stale/);
    await selector.selectOption("broken");
    await expect(page.getByText(/Alternative failed/).first()).toBeVisible();
    await expect(selector).toHaveValue("hybrid");
    // A failed choice must not remain hidden in the host's pending selection.
    await page.getByLabel("Variant Width").selectOption("large");
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    expect(
      (await page.evaluate(() => window.cadkit.load())).scene!.project
        .variant_selection,
    ).toEqual({ base: "hybrid", width: "large" });
    await selector.selectOption("printed");
    await expect(selector).toHaveValue("printed");
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    const before = (await page.evaluate(() => window.cadkit.load())).scene!
      .revision;
    await writeFile(
      path.join(directory, "project.py"),
      source + "\n# source revision\n",
    );
    await expect
      .poll(
        async () =>
          (await page.evaluate(() => window.cadkit.load())).scene!.revision,
      )
      .not.toBe(before);
    expect(
      (await page.evaluate(() => window.cadkit.load())).scene!.cached,
    ).toBe(false);
    const sourceRevision = (await page.evaluate(() => window.cadkit.load()))
      .scene!.revision;
    await writeFile(path.join(directory, "width.dat"), "1");
    await expect
      .poll(
        async () =>
          (await page.evaluate(() => window.cadkit.load())).scene!.revision,
      )
      .not.toBe(sourceRevision);
    expect(
      (await page.evaluate(() => window.cadkit.load())).scene!.cached,
    ).toBe(false);
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
