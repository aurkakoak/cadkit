import { test, expect, type ElectronApplication } from "@playwright/test";
import { launchElectron } from "./electron";
import {
  mkdtemp,
  mkdir,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const python =
  process.env.CADKIT_TEST_PYTHON ?? path.resolve("../.venv/bin/python");
const fixture = (name: string) => `
import cadquery as cq
import cadkit as ck
from pathlib import Path
Path(__file__).with_name('opened.txt').write_text('opened')
part = ck.Part('block', body=lambda: cq.Workplane('XY').box(20, 15, 8).val(), manufacture=ck.FDM('PLA'))
assembly = ck.Assembly(${JSON.stringify(name)})
assembly.fix(assembly.add(part))
PROJECT = assembly.as_project()
`;
async function chooseFolder(
  app: ElectronApplication,
  directory: string | null,
) {
  await app.evaluate(({ dialog }, selected) => {
    dialog.showOpenDialog = async () => ({
      canceled: selected === null,
      filePaths: selected === null ? [] : [selected],
    });
  }, directory);
}
const launchHome = (directory: string) =>
  launchElectron({
    args: [path.resolve("."), "--python", python],
    env: { ...process.env, CADKIT_USER_DATA: path.join(directory, "profile") },
  });

test("Home opens folders without building recents, remembers previews, and recovers moved projects", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "cadkit-launcher-"));
  const model = path.join(directory, "model");
  await mkdir(model);
  await writeFile(path.join(model, "project.py"), fixture("home-fixture"));
  let app = await launchHome(directory);
  try {
    let page = await app.firstWindow();
    await expect(page.getByTestId("project-home")).toBeVisible();
    await expect(page.locator(".viewport-host")).toHaveCount(0);
    await chooseFolder(app, null);
    await page.getByRole("button", { name: "Open…", exact: true }).click();
    await expect(page.getByTestId("project-home")).toBeVisible();
    await chooseFolder(app, model);
    await page.getByRole("button", { name: "Open…", exact: true }).click();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(async () =>
          (
            await window.cadkit.launcherState()
          ).recents[0]?.thumbnail?.startsWith("data:image/"),
        ),
      )
      .toBe(true);
    await page.locator(".project-menu > summary").click();
    await page
      .getByRole("button", { name: "Use current view as preview", exact: true })
      .click();
    await expect(
      page.getByText("Project preview saved", { exact: true }),
    ).toBeVisible();
    const initial = await page.evaluate(() => window.cadkit.launcherState());
    const id = initial.active!.id;
    const preview = initial.recents[0].thumbnail;
    await page.getByRole("button", { name: "Home", exact: true }).click();
    await expect(page.getByTestId("project-home")).toBeVisible();
    const card = page.locator(`[data-project-id="${id}"]`);
    await expect(card.locator("img")).toBeVisible();
    await card
      .getByRole("button", { name: "Pin home-fixture", exact: true })
      .click();
    await expect(
      card.getByRole("button", { name: "Unpin home-fixture", exact: true }),
    ).toBeVisible();
    await app.close();
    // Home must not import saved entries or rebuild thumbnails on launch.
    await rm(path.join(model, "opened.txt"));
    app = await launchHome(directory);
    page = await app.firstWindow();
    await expect(page.getByTestId("project-home")).toBeVisible();
    const saved = await page.evaluate(() => window.cadkit.launcherState());
    expect(saved.active).toBeNull();
    expect(saved.recents[0].pinned).toBe(true);
    expect(saved.recents[0].thumbnail).toBe(preview);
    await expect(
      readFile(path.join(model, "opened.txt")),
    ).rejects.toMatchObject({ code: "ENOENT" });
    const moved = path.join(directory, "moved-model");
    await rename(model, moved);
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Locate home-fixture", exact: true }),
    ).toBeVisible();
    await chooseFolder(app, moved);
    await page
      .getByRole("button", { name: "Locate home-fixture", exact: true })
      .click();
    await page.getByRole("button", { name: "Open", exact: true }).click();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    const relocated = await page.evaluate(() => window.cadkit.launcherState());
    expect(relocated.recents).toHaveLength(1);
    expect(relocated.recents[0].pinned).toBe(true);
    expect(relocated.recents[0].thumbnail).toBe(preview);
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});

test("Home creates editable Python projects and examples without replacing existing files", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "cadkit-create-"));
  const starter = path.join(directory, "starter");
  const example = path.join(directory, "example");
  await Promise.all([mkdir(starter), mkdir(example)]);
  const app = await launchHome(directory);
  try {
    const page = await app.firstWindow();
    await expect(page.getByTestId("project-home")).toBeVisible();
    await chooseFolder(app, starter);
    await page.getByRole("button", { name: "New", exact: true }).click();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    const original = await readFile(path.join(starter, "project.py"), "utf8");
    expect(original).toContain("PROJECT = assembly.as_project()");
    await page.getByRole("button", { name: "Home", exact: true }).click();
    await page.getByRole("button", { name: "New", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText(/empty folder/i);
    expect(await readFile(path.join(starter, "project.py"), "utf8")).toBe(
      original,
    );
    await chooseFolder(app, example);
    await page.getByRole("button", { name: "Examples", exact: true }).click();
    await page.getByRole("button", { name: "Create", exact: true }).click();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    expect(await readFile(path.join(example, "project.py"), "utf8")).toBe(
      await readFile(path.resolve("../examples/bracket.py"), "utf8"),
    );
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});

test("project switching handles failed builds, namespace entry points and fresh UI state", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "cadkit-switch-"));
  const broken = path.join(directory, "broken");
  const model = path.join(directory, "namespace_model");
  await mkdir(broken);
  await mkdir(model);
  await writeFile(
    path.join(broken, "project.py"),
    'raise RuntimeError("Missing model dependency. " * 110)\nPROJECT = None\n',
  );
  await writeFile(
    path.join(model, "parts.py"),
    'import cadquery as cq\ndef body():\n    return cq.Workplane("XY").box(12, 10, 8).val()\n',
  );
  await writeFile(
    path.join(model, "project.py"),
    `from .parts import body\nimport cadkit as ck\nassembly = ck.Assembly('namespace-fixture')\nassembly.fix(assembly.add(ck.Part('block', body=body, manufacture=ck.FDM('PLA'))))\nPROJECT = assembly.as_project()\nOPEN_PROJECT = PROJECT\n`,
  );
  const app = await launchHome(directory);
  const page = await app.firstWindow();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await expect(page.getByTestId("project-home")).toBeVisible();
    await app.evaluate(({ BrowserWindow }) => {
      BrowserWindow.getAllWindows()[0].setSize(1050, 680);
    });
    await page.evaluate((target) => window.cadkit.openProject(target), {
      projectDir: broken,
      reference: "project:PROJECT",
      python,
    });
    await expect(
      page.getByRole("heading", { name: "Build failed", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Missing model dependency", { exact: false }).first(),
    ).toBeVisible();
    const recovery = page.locator(".project-recovery-actions");
    await expect(
      recovery.getByRole("button", { name: "Project settings…", exact: true }),
    ).toBeInViewport();
    await expect(
      recovery.getByRole("button", { name: "Home", exact: true }),
    ).toBeInViewport();
    expect(
      await page
        .locator(".loading-scene p")
        .evaluate((element) => element.scrollHeight > element.clientHeight),
    ).toBe(true);
    await recovery.getByRole("button", { name: "Home", exact: true }).click();
    await app.evaluate(({ BrowserWindow }) => {
      BrowserWindow.getAllWindows()[0].setSize(1500, 980);
    });
    await expect(page.getByTestId("project-home")).toBeVisible();
    await chooseFolder(app, model);
    await page.getByRole("button", { name: "Open…", exact: true }).click();
    // PROJECT and OPEN_PROJECT belong to a namespace package with no __init__.py.
    await page.getByRole("button", { name: "Open", exact: true }).click();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Select block", exact: true })
      .click();
    await expect(page.getByText("CADKIT PART", { exact: true })).toBeVisible();
    const current = await page.evaluate(() => window.cadkit.launcherState());
    expect(current.active!.reference).toBe("namespace_model.project:PROJECT");
    await page.getByRole("button", { name: "Home", exact: true }).click();
    await expect(page.getByTestId("project-home")).toBeVisible();
    await page
      .locator(`[data-project-id="${current.active!.id}"]`)
      .getByRole("button", { name: "Open namespace-fixture", exact: true })
      .click();
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByLabel("No selection", { exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Home", exact: true }).click();
    await expect(page.getByTestId("project-home")).toBeVisible();
    await page.screenshot({ path: "test-results/project-home-dark.png" });
    await page
      .getByRole("button", { name: "Switch to light mode", exact: true })
      .click();
    await page.screenshot({ path: "test-results/project-home-light.png" });
    expect(errors).toEqual([]);
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
