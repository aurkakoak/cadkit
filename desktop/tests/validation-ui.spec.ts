import {
  test as base,
  expect,
  chromium,
  type Browser,
  type Page,
} from "@playwright/test";
import { createServer, type ViteDevServer } from "vite";
import { existsSync } from "node:fs";
import type { AddressInfo } from "node:net";
import path from "node:path";
import type {
  MechanicalFinding,
  MechanicalReport,
  Snapshot,
} from "../src/types";

const ids = [
  "/engine/low-pressure/shaft",
  "/engine/high-pressure/sleeve",
  "/engine/housing/casing",
];
const alignment =
  "Joint frame is authored intent; mate alignment and load capacity are not solved";
const movement = "Travel and swept operating collisions have not been checked";
const finding = (
  id: string,
  concept: MechanicalFinding["concept"],
  entity: string,
  code: string,
  status: MechanicalFinding["status"],
  message: string,
  component_ids = ids.slice(0, 2),
  evidence: Record<string, unknown> = {},
): MechanicalFinding => ({
  id,
  concept,
  entity,
  code,
  status,
  message,
  component_ids,
  evidence,
  severity:
    status === "fail" ? "error" : status === "pass" ? "info" : "warning",
});
const findings = [
  finding(
    "lp-alignment",
    "joint",
    "low-pressure/spool",
    "alignment",
    "unverified",
    alignment,
  ),
  finding(
    "hp-alignment",
    "joint",
    "high-pressure/spool",
    "alignment",
    "unverified",
    alignment,
    ids.slice(1),
  ),
  finding(
    "lp-motion",
    "joint",
    "low-pressure/spool",
    "movement",
    "unverified",
    movement,
  ),
  finding(
    "hp-motion",
    "joint",
    "high-pressure/spool",
    "movement",
    "unverified",
    movement,
    ids.slice(1),
  ),
  finding(
    "links-ok",
    "joint",
    "low-pressure/spool",
    "links",
    "pass",
    "Joint participants and contract links resolve",
  ),
  finding(
    "position-ok",
    "joint",
    "low-pressure/spool",
    "position",
    "pass",
    "Position checked",
    ids.slice(0, 2),
    { position: 0, limits: [-45, 45] },
  ),
  finding(
    "fit-failed",
    "interface",
    "concentric-shafts",
    "fit",
    "fail",
    "Installed clearance is below its limit",
    ids.slice(0, 2),
    {
      gap_mm: 0.125,
      min_clearance_mm: 0.25,
      max_gap_mm: 0.5,
      overlap_mm3: 0,
      max_overlap_mm3: 0,
      outside_region_mm3: 0,
    },
  ),
  finding(
    "kernel-error",
    "assembly",
    "installed",
    "geometry-9",
    "unverified",
    "BRep_API: intersection did not complete",
    ids.slice(1),
  ),
  finding(
    "unknown",
    "joint",
    "rear-bearing",
    "alignment",
    "unverified",
    "Unexpected constraint evaluation error",
    ids.slice(1),
  ),
];
const report: MechanicalReport = {
  revision: "fixture",
  schema_version: 1,
  status: "fail",
  findings,
  coverage: {
    component_count: 3,
    pairs_scanned: 3,
    installed_collisions: "partial",
    kernel_failures: 1,
    operating_motion: "unverified",
  },
};
const components = ids.map((id, index) => ({
  id,
  name: ["low-pressure-shaft", "high-pressure-sleeve", "outer-casing"][index],
  kind: "component" as const,
  group: "parts",
  part: `part-${index}`,
  material: "PLA",
  color: "#aaaaaa",
  geometry: "native" as const,
  volume_mm3: 100,
  bounds: [
    [0, 0, 0],
    [1, 1, 1],
  ] as [number[], number[]],
  size: [1, 1, 1],
}));
const scene: Snapshot = {
  revision: "fixture",
  shapes: {} as Snapshot["shapes"],
  components,
  build_seconds: 0,
  tree: {
    id: "/engine",
    name: "engine",
    kind: "assembly",
    description: "",
    children: components,
  },
  project: {
    name: "engine",
    description: "",
    units: "mm",
    parts: [],
    parameters: [],
  },
};
type PanelState = {
  report: MechanicalReport | null;
  scene?: Snapshot;
  busy?: boolean;
  error?: string;
  list?: boolean;
};
type Harness = {
  render: (state: PanelState) => void;
  picks: MechanicalFinding[];
  runs: number;
};

let server: ViteDevServer;
let browser: Browser;
let url: string;
const entry = `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
import {ValidationPanel, FindingList} from '/src/ValidationPanel.tsx';
import '/src/style.css';
const root = createRoot(document.getElementById('root'));
window.validationHarness = {
  picks: [], runs: 0,
  render(state) {
    this.picks = []; this.runs = 0;
    const onPick = finding => this.picks.push(finding);
    flushSync(() => root.render(React.createElement('aside', {className:'inspector', style:{width:310,height:'100vh',overflowY:'auto'}},
      state.list ? React.createElement(FindingList, {findings:state.report?.findings || [],scene:state.scene,onPick})
      : React.createElement(ValidationPanel, {...state,busy:!!state.busy,onPick,onRun:()=>this.runs++}))));
  }
};
`;
const test = base.extend<{ panelPage: Page }>({
  panelPage: async ({}, use) => {
    const page = await browser.newPage({
      viewport: { width: 900, height: 1000 },
    });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(url);
    await page.waitForFunction(() =>
      Boolean(
        (window as Window & { validationHarness?: Harness }).validationHarness,
      ),
    );
    await use(page);
    expect(errors).toEqual([]);
    await page.close();
  },
});
async function render(page: Page, state: PanelState) {
  await page.evaluate(
    (value) =>
      (
        window as Window & { validationHarness: Harness }
      ).validationHarness.render(value),
    state,
  );
}

test.beforeAll(async () => {
  server = await createServer({
    root: path.resolve("."),
    configFile: false,
    appType: "custom",
    server: { host: "127.0.0.1", port: 0 },
    plugins: [
      {
        name: "validation-test-harness",
        resolveId(id) {
          if (id === "/__validation.tsx") return "\0validation.tsx";
        },
        load(id) {
          if (id === "\0validation.tsx") return entry;
        },
        configureServer(vite) {
          vite.middlewares.use((request, response, next) => {
            if (request.url !== "/") return next();
            response.setHeader("Content-Type", "text/html");
            response.end(
              '<html data-theme="dark"><body><div id="root"></div><script type="module" src="/__validation.tsx"></script></body></html>',
            );
          });
        },
      },
    ],
  });
  await server.listen();
  url = `http://127.0.0.1:${(server.httpServer!.address() as AddressInfo).port}`;
  const executablePath =
    process.env.CADKIT_TEST_BROWSER ??
    [
      chromium.executablePath(),
      "/usr/bin/chromium-browser",
      "/usr/bin/chromium",
      "/opt/google/chrome/chrome",
    ].find(existsSync);
  browser = await chromium.launch({ executablePath });
});

test.afterAll(async () => {
  await browser?.close();
  await server?.close();
});

test("failures lead with named participants and select the exact finding", async ({
  panelPage: page,
}) => {
  await render(page, { report, scene });
  const first = page.locator(".mechanical-finding").first();
  await expect(first).toHaveClass(/fail/);
  await expect(first).toHaveAttribute("open", "");
  await expect(first.locator(".finding-components li")).toHaveText([
    "low pressure shaft",
    "high pressure sleeve",
  ]);
  await first.getByRole("button", { name: /^Show parts/ }).click();
  expect(
    await page.evaluate(
      () =>
        (window as Window & { validationHarness: Harness }).validationHarness
          .picks,
    ),
  ).toEqual([findings[6]]);
  const passed = page.locator("details.validation-passed");
  await expect(passed).not.toHaveAttribute("open", "");
  await expect(
    passed.locator("[data-finding-id='links-ok']"),
  ).not.toBeVisible();
  await passed.locator(":scope > summary").click();
  await expect(passed.locator(".mechanical-finding")).toHaveCount(2);
  await passed
    .locator(".mechanical-finding")
    .first()
    .locator(":scope > summary")
    .click();
  await expect(passed.locator("[data-finding-id='links-ok']")).toBeVisible();
  await render(page, { report, scene, list: true });
  await expect(page.locator(".mechanical-finding").first()).toHaveClass(/fail/);
});

test("shared limitations keep every joint and its own Show parts action", async ({
  panelPage: page,
}) => {
  await render(page, { report, scene });
  const unverified = page.getByRole("region", {
    name: "Not verified",
    exact: true,
  });
  await expect(unverified.locator(".mechanical-finding")).toHaveCount(4);
  for (const title of [
    "Alignment and load capacity",
    "Clearance during motion",
  ]) {
    const group = unverified
      .locator(".mechanical-finding")
      .filter({ has: page.locator("summary strong", { hasText: title }) });
    await expect(group).toHaveCount(1);
    await group.locator(":scope > summary").click();
    await expect(group.locator(".finding-subject")).toHaveText([
      "low pressure › spool",
      "high pressure › spool",
    ]);
  }
  await page
    .locator("[data-finding-id='hp-alignment']")
    .getByRole("button", { name: /^Show parts/ })
    .click();
  expect(
    await page.evaluate(
      () =>
        (window as Window & { validationHarness: Harness }).validationHarness
          .picks,
    ),
  ).toEqual([findings[1]]);
  await expect(
    unverified.locator("summary strong", {
      hasText: "Unexpected constraint evaluation error",
    }),
  ).toBeVisible();
  const kernel = unverified
    .locator(".mechanical-finding")
    .filter({ hasText: "A geometry check could not finish" });
  await kernel.locator(":scope > summary").click();
  await expect(kernel.locator(".finding-description")).toHaveText(
    "BRep_API: intersection did not complete",
  );
});

test("empty, pending, failed and scoped incomplete states do not imply full verification", async ({
  panelPage: page,
}) => {
  await render(page, { report: null, scene });
  await expect(
    page.getByText("Run assembly checks to inspect connections and fit."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Run assembly checks" }).click();
  expect(
    await page.evaluate(
      () =>
        (window as Window & { validationHarness: Harness }).validationHarness
          .runs,
    ),
  ).toBe(1);
  await render(page, { report, scene, busy: true, error: "stale failure" });
  await expect(page.getByRole("status")).toHaveText("Checking assembly…");
  await expect(
    page.getByRole("button", { name: "Run assembly checks" }),
  ).toBeDisabled();
  await expect(page.locator(".validation-counts")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await render(page, { report, scene, error: "Kernel worker disconnected" });
  await expect(page.getByRole("alert")).toContainText(
    "Checks could not finish. Kernel worker disconnected",
  );
  await expect(page.locator(".validation-counts")).toHaveCount(0);
  await render(page, {
    report: { ...report, status: "incomplete", findings: [] },
    scene,
  });
  await expect(page.getByText(/No checks reported/)).toContainText(
    "does not establish that the assembly fits",
  );
  await expect(page.locator(".validation-passed")).toHaveCount(0);
  await render(page, {
    report: { ...report, status: "incomplete", findings: findings.slice(0, 4) },
    scene,
  });
  await expect(page.locator(".validation-counts")).toContainText(
    "4 not verified",
  );
  await expect(page.locator(".validation-passed")).toHaveCount(0);
  await render(page, {
    report: {
      ...report,
      status: "incomplete",
      findings: [findings[4]],
      scope: { parts: ["shaft"], component_ids: [ids[0]] },
    },
    scene,
  });
  await expect(
    page.getByRole("region", { name: "Selected part checks" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "The whole assembly review is incomplete, even though the checks shown here passed.",
    ),
  ).toBeVisible();
  await expect(page.locator(".validation-counts")).toContainText(
    "0 not verified",
  );
});

test("measurements fit a padded 310px inspector without overlapping actual and limit values", async ({
  panelPage: page,
}) => {
  await render(page, { report, scene });
  const panel = page.getByRole("region", {
    name: "Assembly checks",
    exact: true,
  });
  const padding = await panel.evaluate((element) => ({
    left: parseFloat(getComputedStyle(element).paddingLeft),
    right: parseFloat(getComputedStyle(element).paddingRight),
  }));
  expect(padding.left).toBe(22);
  expect(padding.right).toBe(22);
  const measurements = page.locator(
    "[data-finding-id='fit-failed'] .finding-measurements",
  );
  await expect(
    measurements.getByText("Measured gap", { exact: true }),
  ).toBeVisible();
  await expect(
    measurements.getByText("0.125 mm", { exact: true }),
  ).toBeVisible();
  await expect(
    measurements.getByText("Minimum required gap", { exact: true }),
  ).toBeVisible();
  await expect(
    measurements.getByText("0.25 mm", { exact: true }),
  ).toBeVisible();
  const boxes = await measurements.locator(":scope > div").evaluateAll((rows) =>
    rows.map((row) => {
      const rect = (element: Element) => {
        const r = element.getBoundingClientRect();
        return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
      };
      return {
        row: rect(row),
        label: rect(row.querySelector("dt")!),
        value: rect(row.querySelector("dd")!),
      };
    }),
  );
  for (const [index, box] of boxes.entries()) {
    expect(box.label.right).toBeLessThanOrEqual(box.value.left);
    expect(box.value.right).toBeLessThanOrEqual(box.row.right + 1);
    if (index)
      expect(box.row.top).toBeGreaterThanOrEqual(boxes[index - 1].row.bottom);
  }
  const overflow = await page
    .locator(".inspector")
    .evaluate((element) => element.scrollWidth - element.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page
    .locator(".inspector")
    .screenshot({ path: "test-results/validation-fixture-310px.png" });
});
