import { test, expect } from "@playwright/test";
import { launchElectron } from "./electron";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const fixture = `
import cadquery as cq
import cadkit as ck
a = cq.Workplane('XY').box(10, 10, 10).val()
part = ck.Part('block', lambda: a, ck.FDM('PETG'), group='blocks')
reference = ck.Purchased('reference', lambda: a)
left = ck.Assembly('left-assembly')
left.fix(left.add('left-block', part, group='blocks', color=(0.4,0.75,0.6)))
right = ck.Assembly('right-assembly')
right.fix(right.add('right-block', reference, group='blocks', color=(0.6,0.65,0.7)), at=ck.Frame((15, 0, 0)))
assembly = ck.Assembly('fixture')
assembly.fix(assembly.add('left-assembly', left))
assembly.fix(assembly.add('right-assembly', right))
PROJECT = assembly.as_project()
`;

test("desktop visibility, Parts, measurements, theme persistence and rebuild recovery", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "cadkit-ui-test-"));
  const project = path.join(dir, "project.py");
  await writeFile(project, fixture);
  const args = [
    path.resolve("."),
    "--project-dir",
    dir,
    "--project",
    "project:PROJECT",
    "--python",
    process.env.CADKIT_TEST_PYTHON ?? path.resolve("../.venv/bin/python"),
  ];
  const launch = () =>
    launchElectron({
      args,
      env: { ...process.env, CADKIT_USER_DATA: path.join(dir, "profile") },
    });
  const app = await launch();
  const page = await app.firstWindow();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await expect(page.getByText("Build up to date")).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator(".viewport-host canvas")).toBeVisible();
    const canvas = await page.locator(".viewport-host canvas").boundingBox();
    if (!canvas) throw new Error("No CAD canvas");
    await page.mouse.move(
      canvas.x + canvas.width * 0.34,
      canvas.y + canvas.height * 0.4,
    );
    await page.mouse.click(
      canvas.x + canvas.width * 0.34,
      canvas.y + canvas.height * 0.4,
    );
    await expect(page.getByText("CADKIT PART", { exact: true })).toBeVisible();
    await page
      .getByRole("button", { name: "Hide left-assembly", exact: true })
      .click();
    await expect(page.getByText("1 visible", { exact: true })).toBeVisible();
    const leftRow = page.locator('[data-node-id="/fixture/left-assembly"]');
    const rightRow = page.locator('[data-node-id="/fixture/right-assembly"]');
    const leftSolo = page.getByRole("button", {
      name: "Isolate left-assembly",
      exact: true,
      includeHidden: true,
    });
    const rightSolo = page.getByRole("button", {
      name: "Isolate right-assembly",
      exact: true,
      includeHidden: true,
    });
    const inspectorSolo = page.getByRole("button", {
      name: "Isolate",
      exact: true,
    });
    // Isolating a hidden branch reveals it, and restores its previous hidden state.
    await leftRow.hover();
    await leftSolo.click();
    await page.mouse.move(canvas.x + canvas.width / 2, canvas.y + 20);
    await expect(leftSolo).toBeVisible();
    await expect(leftSolo).toHaveAttribute("aria-pressed", "true");
    await expect(inspectorSolo).toHaveAttribute("aria-pressed", "true");
    await page.screenshot({ path: "test-results/desktop-solo.png" });
    await expect(
      page.getByRole("button", { name: "Show right-assembly", exact: true }),
    ).toBeVisible();
    await inspectorSolo.click();
    await expect(inspectorSolo).toHaveAttribute("aria-pressed", "false");
    await expect(
      page.getByRole("button", { name: "Show left-assembly", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Hide right-assembly", exact: true }),
    ).toBeVisible();
    // Switching solo targets keeps the original snapshot, including hidden branches.
    await leftRow.hover();
    await leftSolo.click();
    await rightRow.hover();
    await rightSolo.click();
    await expect(leftSolo).toHaveAttribute("aria-pressed", "false");
    await expect(rightSolo).toHaveAttribute("aria-pressed", "true");
    await rightSolo.click();
    await expect(
      page.getByRole("button", { name: "Show left-assembly", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Hide right-assembly", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Show left-assembly", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Select left-block", exact: true })
      .click();
    await expect(page.getByText("CADKIT PART", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Block", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Select right-block", exact: true })
      .click({ modifiers: ["Shift"] });
    await expect(page.getByTestId("measurement-result")).toContainText("5.000");
    await expect(page.getByTestId("measurement-result")).toContainText(
      "15.000",
    );
    await expect(page.locator(".dimension-label")).toBeVisible();
    const pairSolo = page.getByRole("button", {
      name: "Isolate pair",
      exact: true,
    });
    await pairSolo.click();
    await expect(pairSolo).toHaveAttribute("aria-pressed", "true");
    await pairSolo.click();
    await expect(pairSolo).toHaveAttribute("aria-pressed", "false");
    const dimensionPosition = () =>
      page
        .locator(".dimension-label")
        .evaluate((element) => [element.style.left, element.style.top]);
    const beforeTheme = await dimensionPosition();
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect.poll(dimensionPosition).toEqual(beforeTheme);
    await page.reload();
    await expect(page.getByText("Build up to date")).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
    await page
      .getByRole("button", { name: "Hide right-assembly", exact: true })
      .click();
    await rightRow.hover();
    await rightSolo.click();
    await writeFile(
      project,
      fixture + '\nraise RuntimeError("intentional build failure")\n',
    );
    await expect(
      page.getByText("Build failed · showing the last successful model"),
    ).toBeVisible();
    await expect(page.locator(".viewport-host canvas")).toBeVisible();
    await expect(page.getByText("1 visible", { exact: true })).toBeVisible();
    await writeFile(project, fixture.replace("(15, 0, 0)", "(18, 0, 0)"));
    await expect(page.getByText("Build up to date")).toBeVisible();
    await expect(page.getByText("1 visible", { exact: true })).toBeVisible();
    await expect(rightSolo).toHaveAttribute("aria-pressed", "true");
    await rightSolo.click();
    await expect(rightSolo).toHaveAttribute("aria-pressed", "false");
    await page
      .getByRole("button", { name: "Show right-assembly", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Select left-block", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Select right-block", exact: true })
      .click({ modifiers: ["Shift"] });
    await expect(page.getByTestId("measurement-result")).toContainText("8.000");
    await expect(page.locator(".dimension-label")).toBeVisible();
    expect(errors).toEqual([]);
    await page.screenshot({ path: "test-results/desktop-dark.png" });
  } finally {
    await app.close();
    await rm(dir, { recursive: true, force: true });
  }
});
