import { test, expect, _electron as electron } from "@playwright/test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import net from "node:net";

test("MCP controls the live view and slicer jobs without a second CAD session", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "cadkit-mcp-test-"));
  const profile = path.join(dir, "profile");
  await mkdir(profile);
  const fixture = `
import cadquery as cq
from cadkit import Assembly, Component, Part, Project
a = cq.Workplane('XY').box(10, 20, 30).val()
left = Component('left', a, 'blocks', part='block')
right = Component('right', a.translate((15, 0, 0)), 'blocks')
PROJECT = Project('fixture', (Part('block', lambda: a, 'blocks', material='PETG', quantity=2, print_rotation=(90,0,0)),), lambda: [left,right], assembly=lambda: Assembly('fixture',(Assembly('blocks',(left,right)),)))
`;
  await writeFile(path.join(dir, "project.py"), fixture);
  const mock = path.join(dir, "mock-slicer");
  await writeFile(
    mock,
    `#!/usr/bin/env python3
import sys, pathlib, time, json
root = pathlib.Path(__file__).parent
if '--output' not in sys.argv:
    (root / 'opened.json').write_text(json.dumps(sys.argv[1:]))
    sys.exit(0)
if (root / 'fail').exists():
    print('intentional slicer failure', flush=True)
    sys.exit(3)
if (root / 'slow').exists():
    (root / 'slicer.pid').write_text(str(__import__('os').getpid()))
    time.sleep(120)
output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
output.write_text('; filament used [g] = 12.5\\n; estimated printing time (normal mode) = 1h 2m\\n')
`,
    { mode: 0o755 },
  );
  await writeFile(path.join(dir, "printer.ini"), "# fixture profile\n");
  await writeFile(
    path.join(profile, "slicer.json"),
    JSON.stringify({
      kind: "prusa",
      executable: mock,
      profile: path.join(dir, "printer.ini"),
      price: "20",
      currency: "GBP",
    }),
  );
  const app = await electron.launch({
    args: [
      path.resolve("."),
      "--project-dir",
      dir,
      "--project",
      "project:PROJECT",
      "--python",
      process.env.CADKIT_TEST_PYTHON ??
        path.resolve("../../grinder/.venv/bin/python"),
    ],
    env: { ...process.env, CADKIT_USER_DATA: profile },
  });
  const page = await app.firstWindow();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const client = new Client({
    name: "cadkit-integration-test",
    version: "1.0.0",
  });
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [
      path.resolve("electron/mcp.mjs"),
      "--project-dir",
      dir,
      "--project",
      "project:PROJECT",
    ],
  });
  const call = async (name: string, args = {}) => {
    const result = await client.callTool({ name, arguments: args });
    expect(result.isError, JSON.stringify(result)).not.toBe(true);
    return result.structuredContent as any;
  };
  try {
    await expect(page.getByText("Build up to date")).toBeVisible();
    await client.connect(transport);
    expect((await client.listTools()).tools.map((t) => t.name)).toEqual(
      expect.arrayContaining([
        "get_state",
        "inspect",
        "camera",
        "annotate",
        "screenshot",
        "slice_parts",
      ]),
    );
    const state = await call("get_state");
    expect(state.components).toHaveLength(2);
    expect(state.project.parts[0].quantity).toBe(2);
    expect(state).not.toHaveProperty("shapes");
    const revision = state.revision,
      left = state.components[0].id,
      right = state.components[1].id;
    await page
      .getByRole("button", { name: "Select left", exact: true })
      .click();
    expect((await call("get_state")).selected).toEqual([left]);
    expect((await call("inspect")).parts[0].material).toBe("PETG");
    const invalid = await client.callTool({
      name: "select",
      arguments: { revision: "stale", ids: [right] },
    });
    expect(invalid.isError).toBe(true);
    expect((await call("get_state")).selected).toEqual([left]);
    expect(
      (
        await client.callTool({
          name: "visibility",
          arguments: { revision, action: "hide", ids: ["/missing"] },
        })
      ).isError,
    ).toBe(true);
    await call("select", { revision, ids: [right] });
    await expect(
      page.getByRole("heading", { name: "Right", exact: true }),
    ).toBeVisible();
    await call("visibility", {
      revision,
      action: "hide",
      ids: ["/fixture/blocks"],
    });
    await expect(page.getByText("0 visible", { exact: true })).toBeVisible();
    await call("visibility", { revision, action: "show" });
    await call("visibility", { revision, action: "hide", ids: [left] });
    await call("visibility", { revision, action: "isolate", ids: [left] });
    expect(await call("get_state")).toMatchObject({
      hidden: [right],
      isolation: { ids: [left], previousHidden: [left] },
    });
    await call("visibility", { revision, action: "isolate", ids: [right] });
    await call("visibility", { revision, action: "isolate", ids: [right] });
    expect(await call("get_state")).toMatchObject({
      hidden: [left],
      isolation: null,
    });
    await call("visibility", {
      revision,
      action: "isolate",
      ids: ["/fixture/blocks"],
    });
    // The expanded target set identifies solo, regardless of order or tree level.
    await call("visibility", {
      revision,
      action: "isolate",
      ids: [right, left],
    });
    expect(await call("get_state")).toMatchObject({
      hidden: [left],
      isolation: null,
    });
    await call("visibility", { revision, action: "isolate", ids: [left] });
    await call("visibility", { revision, action: "show" });
    expect(await call("get_state")).toMatchObject({
      hidden: [],
      isolation: null,
    });
    await call("visibility", { revision, action: "isolate", ids: [left] });
    await call("visibility", { revision, action: "isolate", ids: [left] });
    expect(await call("get_state")).toMatchObject({
      hidden: [],
      isolation: null,
    });
    await call("highlight", {
      revision,
      ids: ["/fixture/blocks"],
      color: "#ff5599",
    });
    expect((await call("get_state")).highlights.ids).toHaveLength(2);
    const camera = (
      await call("camera", { preset: "front", fit: true, zoom: 1.5 })
    ).camera;
    expect(camera.zoom).toBeCloseTo(1.5);
    await call("camera", { preset: "top" });
    expect((await call("get_state")).camera.quaternion).not.toEqual(
      camera.quaternion,
    );
    await call("camera", { pose: camera });
    const restored = (await call("get_state")).camera;
    for (const key of ["position", "quaternion", "target"])
      camera[key].forEach((v: number, i: number) =>
        expect(restored[key][i]).toBeCloseTo(v, 8),
      );
    expect(restored.zoom).toBeCloseTo(camera.zoom, 8);
    await call("camera", { zoom: 0.6 });
    const measure = await call("measure", { revision, ids: [left, right] });
    expect(measure.minimum_mm).toBeCloseTo(5);
    expect(measure.method).toBe("native");
    await expect(page.getByTestId("measurement-result")).toContainText("5.000");
    await expect(page.locator(".dimension-label")).toBeVisible();
    await call("annotate", {
      revision,
      id: "gap",
      text: "5 mm clearance",
      point: measure.points[0],
      from: [-20, 0, 40],
    });
    await call("annotate", {
      revision,
      id: "screen",
      space: "screen",
      text: "Check fit",
      point: [0.5, 0.5, 0],
      from: [0.8, 0.2, 0],
    });
    await expect(page.locator('[data-annotation-id="gap"]')).toBeVisible();
    await expect(
      page.locator('[data-annotation-card="screen"] .annotation-markdown'),
    ).toHaveText("Check fit");
    const before = await page
      .locator('[data-annotation-id="gap"] circle')
      .getAttribute("cx");
    await call("camera", { preset: "iso", zoom: 0.6 });
    expect(
      await page
        .locator('[data-annotation-id="gap"] circle')
        .getAttribute("cx"),
    ).not.toBe(before);
    const screenshot = await client.callTool({
      name: "screenshot",
      arguments: { target: "viewport", max_width: 800 },
    });
    const image = (screenshot.content as any[])[0];
    expect(image.type).toBe("image");
    const png = Buffer.from(image.data, "base64");
    expect(png.subarray(1, 4).toString()).toBe("PNG");
    expect(png.readUInt32BE(16)).toBeLessThanOrEqual(800);
    await writeFile("test-results/mcp-annotations.png", png);
    expect(
      JSON.parse(
        (await client.readResource({ uri: "cadkit://state" })).contents[0]
          .text as string,
      ).annotations,
    ).toHaveLength(2);
    await page
      .getByRole("button", { name: "Clear annotations", exact: true })
      .click();
    expect((await call("get_state")).annotations).toHaveLength(0);
    await call("annotate", { revision, id: "temporary", point: [0, 0, 0] });
    await call("clear_annotations", { id: "temporary" });
    expect((await call("get_state")).annotations).toHaveLength(0);

    // Markdown notes are shared between the viewport, assembly tree and MCP.
    const remoteRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().startsWith("https://example.invalid"))
        remoteRequests.push(request.url());
    });
    const markdown =
      "**Fit check**\n\n- [ ] Verify the bore\n- Keep `0.2 mm` clearance\n\n| Dimension | mm |\n| --- | --- |\n| Bore | 10 |\n\n" +
      "A long engineering note with enough detail to expand. ".repeat(12) +
      '\n\n![probe](https://example.invalid/probe.png)\n\n<img src="https://example.invalid/raw.png" onerror="window.noteInjected=true">\n\n[bad](javascript:alert(1))';
    await call("annotate", {
      revision,
      id: "attached",
      target: right,
      text: markdown,
    });
    const card = page.locator('[data-annotation-card="attached"]');
    await expect(card.locator("strong")).toHaveText("Fit check");
    await expect(
      card.getByRole("button", { name: "Expand annotation attached" }),
    ).toBeVisible();
    const beforeCard = (await call("get_state")).camera;
    await card
      .getByRole("button", { name: "Expand annotation attached" })
      .click();
    await expect(card.locator("table")).toBeVisible();
    await expect(
      card.getByRole("button", { name: "Collapse annotation attached" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect((await call("get_state")).camera).toEqual(beforeCard);
    expect(await card.locator("img, script").count()).toBe(0);
    expect(await card.locator('a[href^="javascript:"]').count()).toBe(0);
    expect(remoteRequests).toEqual([]);
    await card
      .getByRole("button", { name: "Collapse annotation attached" })
      .click();
    const positionBefore = await card.getAttribute("style");
    await card
      .getByRole("button", { name: "Move annotation attached" })
      .focus();
    await page.keyboard.press("Shift+ArrowDown");
    expect(await card.getAttribute("style")).not.toBe(positionBefore);
    expect((await call("get_state")).annotations[0].offset).toHaveLength(2);
    await page
      .getByRole("button", { name: "Notes for right", exact: true })
      .click();
    const treeNotes = page.locator(`[data-notes-for="${right}"]`);
    await expect(treeNotes.locator("strong")).toHaveText("Fit check");
    await treeNotes
      .getByRole("button", { name: "Edit annotation attached" })
      .click();
    await page
      .getByRole("textbox", { name: "Annotation Markdown" })
      .fill("**Updated fit**\n\nCheck the `10 mm` bore.");
    await page.getByRole("button", { name: "Preview Markdown" }).click();
    await expect(page.locator(".annotation-editor-preview strong")).toHaveText(
      "Updated fit",
    );
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(card.locator("strong")).toHaveText("Updated fit");
    expect(
      (await call("inspect", { ids: [right] })).annotations[0].text,
    ).toContain("Updated fit");
    await page.getByRole("button", { name: "Hide right", exact: true }).click();
    await expect(card).toBeHidden();
    await expect(treeNotes).toBeVisible();
    await page.getByRole("button", { name: "Show right", exact: true }).click();
    await expect(card).toBeVisible();
    expect(
      (
        await client.callTool({
          name: "annotate",
          arguments: {
            revision,
            id: "invalid",
            target: "/missing",
            text: "bad target",
          },
        })
      ).isError,
    ).toBe(true);
    await page
      .getByRole("button", { name: "Annotate left", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "Annotation Markdown" })
      .fill("User-created **note**");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    const userNote = (await call("get_state")).annotations.find(
      (a: any) => a.target === left,
    );
    expect(userNote.text).toContain("User-created");
    await page
      .locator(`[data-notes-for="${left}"]`)
      .getByRole("button", { name: `Delete annotation ${userNote.id}` })
      .click();
    expect((await call("get_state")).annotations).toHaveLength(1);
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await expect(card).toBeVisible();
    await page.screenshot({ path: "test-results/annotation-cards-light.png" });
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
    expect((await call("slicer_settings")).ready).toBe(true);
    await page.getByRole("button", { name: "Print", exact: true }).click();
    await page.getByRole("button", { name: "Slice", exact: true }).click();
    await expect
      .poll(async () => (await call("slice_status")).jobs[0].phase)
      .toBe("complete");
    const job = (await call("slice_status")).jobs[0];
    expect(job.report.totals.filament_g).toBe(25);
    expect(job.report.totals.copies).toBe(2);
    expect(job.report.totals.cost).toBe(0.5);
    await expect(page.locator(".slice-totals")).toContainText("25.00 g");
    expect(await readFile(job.artifacts[0], "utf8")).toContain("12.5");
    await call("open_in_slicer", { id: job.id });
    await expect
      .poll(async () => {
        try {
          return JSON.parse(
            await readFile(path.join(dir, "opened.json"), "utf8"),
          );
        } catch {
          return [];
        }
      })
      .toEqual(job.artifacts);
    const prepared = await call("prepare_parts", {
      revision,
      parts: ["block"],
    });
    await expect
      .poll(async () => (await call("slice_status", { id: prepared.id })).phase)
      .toBe("complete");
    const stls = (await call("slice_status", { id: prepared.id })).artifacts;
    expect(stls[0]).toMatch(/block\.stl$/);
    await expect
      .poll(async () =>
        JSON.parse(await readFile(path.join(dir, "opened.json"), "utf8")),
      )
      .toEqual(stls);
    await writeFile(path.join(dir, "fail"), "");
    const failed = await call("slice_parts", { revision, parts: ["block"] });
    await expect
      .poll(async () => (await call("slice_status", { id: failed.id })).phase)
      .toBe("error");
    await expect(page.getByRole("alert").last()).toContainText(
      "intentional slicer failure",
    );
    await rm(path.join(dir, "fail"));
    await writeFile(path.join(dir, "slow"), "");
    const slow = await call("slice_parts", { revision, parts: ["block"] });
    await expect
      .poll(async () => {
        try {
          return Number(await readFile(path.join(dir, "slicer.pid"), "utf8"));
        } catch {
          return 0;
        }
      })
      .toBeGreaterThan(0);
    await call("cancel_slice", { id: slow.id });
    expect((await call("slice_status", { id: slow.id })).phase).toBe(
      "cancelled",
    );
    const pid = Number(await readFile(path.join(dir, "slicer.pid"), "utf8"));
    await expect
      .poll(() => {
        try {
          process.kill(pid, 0);
          return true;
        } catch {
          return false;
        }
      })
      .toBe(false);
    await page.getByRole("button", { name: "Close Print" }).click();
    await call("annotate", {
      revision,
      id: "old",
      point: [0, 0, 0],
      text: "Old build",
    });
    await writeFile(
      path.join(dir, "project.py"),
      fixture.replace("(15, 0, 0)", "(18, 0, 0)"),
    );
    await expect
      .poll(async () => {
        try {
          return (await call("get_state")).revision;
        } catch {
          return revision;
        }
      })
      .not.toBe(revision);
    expect((await call("get_state")).annotations.map((a: any) => a.id)).toEqual(
      ["attached"],
    );
    await expect(card).toBeVisible();
    expect(errors).toEqual([]);
    // The private socket also rejects requests that bypass the MCP SDK.
    const { connectionFile } = await import("../electron/local-bridge.mjs");
    const discovery = JSON.parse(
      await readFile(await connectionFile(dir, "project:PROJECT"), "utf8"),
    );
    const response = await new Promise<string>((resolve, reject) => {
      const socket = net.createConnection(discovery.socket);
      socket.on("connect", () =>
        socket.write(
          JSON.stringify({ token: "wrong", method: "get_state" }) + "\n",
        ),
      );
      socket.on("data", (chunk) => {
        resolve(String(chunk));
        socket.end();
      });
      socket.on("error", reject);
    });
    expect(JSON.parse(response).error).toBe("Unauthorized");
  } finally {
    await client.close();
    await app.close();
    await rm(dir, { recursive: true, force: true });
  }
});
