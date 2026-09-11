import { test, expect, _electron as electron } from "@playwright/test";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const fixture = `
import cadquery as cq
from cadkit import Project, Part, Component, Joint, Interface, Fastening, FastenerSpec, FastenerSite, HardwareItem

def plate(z):
    return cq.Solid.makeBox(24,16,2).translate((-12,-8,z))
def components(**options):
    return [Component('top',plate(0),'plates',part='top'),Component('base',plate(2),'plates',part='base')]
bolt = FastenerSpec('socket_head_cap_screw','M3-0.5',length_mm=8)
PROJECT = Project('fixture',(Part('top',lambda:plate(0),'plates'),Part('base',lambda:plate(2),'plates')),components,
    joints=(Joint('plate-joint',('top','base'),interfaces=('plate-contact',),fastenings=('left-bolt','right-bolt')),),
    interfaces=(Interface('plate-contact',('top','base'),'contact'),),
    fastenings=tuple(Fastening(name,('top','base'),sites=(FastenerSite('site',(x,0,0)),),
        hardware=(HardwareItem('bolt',bolt),),joint='plate-joint',insertion_distance_mm=20)
        for name,x in [('left-bolt',-5),('right-bolt',5)]))
`;

test("connections, selective hardware presentation and pre-print review stay distinct from native geometry", async () => {
  const directory = await mkdtemp(
    path.join(os.tmpdir(), "cadkit-mechanics-ui-"),
  );
  const projectFile = path.join(directory, "project.py");
  await writeFile(projectFile, fixture);
  const app = await electron.launch({
    args: [
      path.resolve("."),
      "--project-dir",
      directory,
      "--project",
      "project:PROJECT",
      "--python",
      process.env.CADKIT_TEST_PYTHON ??
        path.resolve("../../grinder/.venv/bin/python"),
    ],
    env: { ...process.env, CADKIT_USER_DATA: path.join(directory, "profile") },
  });
  const page = await app.firstWindow();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("4 visible", { exact: true })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page
      .getByRole("button", { name: "Connections", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Inspect joint plate-joint", exact: true })
      .click();
    await expect(
      page.locator('[data-inspected-connection="plate-joint"]'),
    ).toContainText("Limits");
    await expect(
      page.locator('[data-inspected-connection="plate-joint"]'),
    ).toContainText("Not declared");
    await page
      .getByRole("button", {
        name: "Inspect interface plate-contact",
        exact: true,
      })
      .click();
    await expect(
      page.locator('[data-inspected-connection="plate-contact"]'),
    ).toContainText("Maximum overlap");
    await page
      .getByRole("button", { name: "Inspect fastening left-bolt", exact: true })
      .click();
    await expect(page.getByLabel("Hardware visibility")).toHaveValue(
      "selected",
    );
    await expect(page.getByText("3 visible", { exact: true })).toBeVisible();
    await expect(
      page.locator('[data-inspected-connection="left-bolt"]'),
    ).toContainText("M3-0.5 × 8 mm");
    await page.getByLabel("Hardware visibility").selectOption("hidden");
    await expect(page.getByText("2 visible", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Hardware assembly preview")).toBeDisabled();
    await page.getByLabel("Hardware visibility").selectOption("selected");
    const preview = page.getByLabel("Hardware assembly preview");
    await preview.press("End");
    await expect(page.locator(".assembly-preview-badge")).toBeVisible();
    await expect(page.getByLabel("Measurement object A")).toBeDisabled();
    await page
      .getByRole("button", { name: "Check assembly", exact: true })
      .click();
    await expect(
      page.locator('.validation-counts[data-validation-status="fail"]'),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Fit visible objects", exact: true })
      .click();
    await page.screenshot({ path: "test-results/mechanics-dark.png" });
    await page
      .getByRole("button", { name: "Switch to light mode", exact: true })
      .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.screenshot({ path: "test-results/mechanics-light.png" });
    await page
      .getByRole("button", { name: "Reset assembly preview", exact: true })
      .click();
    await expect(page.locator(".assembly-preview-badge")).not.toBeVisible();
    await expect(page.getByLabel("Measurement object A")).toBeEnabled();
    // Selecting another fastening reveals only its own hardware.
    await page
      .getByRole("button", {
        name: "Inspect fastening right-bolt",
        exact: true,
      })
      .click();
    await expect(page.getByText("3 visible", { exact: true })).toBeVisible();
    await page
      .getByRole("button", { name: "Isolate connection", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Restore visibility", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await page
      .getByRole("button", { name: "Restore visibility", exact: true })
      .click();
    await preview.press("End");
    await page.getByRole("button", { name: "Rebuild", exact: true }).click();
    await expect(preview).toHaveValue("0");
    await expect(
      page.getByText("Build up to date", { exact: true }),
    ).toBeVisible();
    // Failed installation checks are visible before fabrication and cannot be
    // acknowledged accidentally by choosing a filament profile.
    await page.getByRole("button", { name: "Print", exact: true }).click();
    await expect(
      page.getByLabel("Slice validation override reason"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Slice", exact: true }),
    ).toBeDisabled();
    await expect(
      page.locator('.print-validation [data-validation-status="fail"]'),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Close Print", exact: true })
      .click();
    expect(errors).toEqual([]);
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
