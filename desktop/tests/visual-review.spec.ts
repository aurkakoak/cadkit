import { test, expect } from "@playwright/test";
import { launchElectron } from "./electron";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

test("MCP reviews preserve notes and selection, show native sections, and invalidate drawings on rebuild", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "cadkit-review-"));
  const source = `import cadquery as cq
import cadkit as ck
a = ck.Assembly('fixture')
a.fix(a.add('ring', ck.Part('ring', lambda: cq.Workplane('XY').circle(10).circle(5).extrude(8), ck.FDM('PETG'))))
a.fix(a.add('pin', ck.Part('pin', lambda: cq.Workplane('XY').circle(4).extrude(8), ck.FDM('PETG'))))
PROJECT = a.as_project()
`;
  await writeFile(path.join(dir, "project.py"), source);
  const app = await launchElectron({
    args: [
      path.resolve("."),
      "--project-dir",
      dir,
      "--python",
      path.resolve("../.venv/bin/python"),
    ],
    env: { ...process.env, CADKIT_USER_DATA: path.join(dir, "profile") },
  });
  const page = await app.firstWindow();
  const client = new Client({ name: "visual-review-test", version: "1" });
  const call = async (name: string, args = {}) => {
    const r = await client.callTool({ name, arguments: args });
    expect(r.isError, JSON.stringify(r)).not.toBe(true);
    return r.structuredContent as any;
  };
  try {
    await expect(page.getByText("Build up to date")).toBeVisible();
    await client.connect(
      new StdioClientTransport({
        command: process.execPath,
        args: [path.resolve("electron/mcp.mjs"), "--project-dir", dir],
      }),
    );
    const { revision, components } = await call("get_state");
    const cli = (...args: string[]) =>
      promisify(execFile)(process.execPath, [
        path.resolve("electron/mcp-client.mjs"),
        "--project-dir",
        dir,
        ...args,
      ]);
    const diagnostic = JSON.parse((await cli("doctor")).stdout);
    expect(diagnostic.connected).toBe(true);
    expect(diagnostic.projectDir).toBe(dir);
    expect(diagnostic.tools).toContain("section_view");
    await expect(
      cli("doctor", "--project", "missing:PROJECT"),
    ).rejects.toMatchObject({
      code: 1,
      stderr: expect.stringContaining(
        "Open CadKit for this exact project directory",
      ),
    });
    const [ring, pin] = components.map((c: any) => c.id);
    await call("select", { revision, ids: [pin] });
    await call("annotate", {
      revision,
      id: "user-note",
      target: ring,
      text: "Existing note",
    });
    const note = {
      id: "fit-ring",
      target: ring,
      text: "**Fit**\n1 mm radial clearance; verify print allowance.",
    };
    const review = await call("present_review", { revision, notes: [note] });
    expect(review.selected).toEqual([pin]);
    expect(review.camera.target[0]).toBeCloseTo(0, 1);
    expect(review.camera.target[1]).toBeCloseTo(0, 1);
    expect(review.camera.target[2]).toBeCloseTo(4, 1);
    expect(review.annotations.map((a: any) => a.id)).toEqual([
      "user-note",
      "fit-ring",
    ]);
    await call("present_review", {
      revision,
      notes: [{ ...note, text: "Updated fit note" }],
      focus: false,
    });
    const before = await call("get_state");
    expect(
      (
        await client.callTool({
          name: "present_review",
          arguments: {
            revision,
            notes: [note, { ...note, id: "bad", target: "/missing" }],
          },
        })
      ).isError,
    ).toBe(true);
    expect((await call("get_state")).annotations).toEqual(before.annotations);
    expect(
      (
        await client.callTool({
          name: "present_review",
          arguments: { revision, notes: [note, note] },
        })
      ).isError,
    ).toBe(true);
    const section = await call("section_view", {
      revision,
      ids: ["/fixture"],
      offset: 4,
    });
    expect(section.components).toHaveLength(2);
    expect(section.components[0].lines).toHaveLength(2);
    await expect(page.getByRole("region", { name: "2D review" })).toBeVisible();
    await expect(page.locator(".section-notes")).toContainText(
      "Updated fit note",
    );
    const state = await call("get_state");
    expect(state.sectionView.components[0]).not.toHaveProperty("lines");
    await call("section_view", {
      revision,
      ids: [ring],
      plane: "XZ",
      mode: "projection",
      show: false,
    });
    expect((await call("get_state")).sectionView.plane).toBe("XY");
    await page
      .getByRole("button", { name: "Highlight pin in 2D view" })
      .click();
    expect((await call("get_state")).highlights.ids).toEqual([pin]);
    expect((await call("get_state")).selected).toEqual([pin]);
    const shot = await client.callTool({
      name: "screenshot",
      arguments: { target: "viewport" },
    });
    expect(shot.content[0].type).toBe("image");
    await cli(
      "screenshot",
      "--output",
      test.info().outputPath("mcp-review.png"),
    );
    await page.screenshot({
      path: test.info().outputPath("visual-review.png"),
    });
    await call("clear_section_view");
    await expect(page.getByRole("region", { name: "2D review" })).toHaveCount(
      0,
    );
    await call("section_view", { revision, ids: [ring], offset: 50 });
    await expect(
      page.getByText("No intersection", { exact: true }),
    ).toBeVisible();
    await writeFile(
      path.join(dir, "project.py"),
      source.replace("circle(5)", "circle(6)"),
    );
    await expect
      .poll(async () => (await call("get_state")).revision)
      .not.toBe(revision);
    const rebuilt = await call("get_state");
    expect(rebuilt.sectionView).toBeNull();
    expect(rebuilt.annotations).toHaveLength(2);
    expect(
      (
        await client.callTool({
          name: "section_view",
          arguments: { revision, ids: [ring] },
        })
      ).isError,
    ).toBe(true);
  } finally {
    await client.close();
    await app.close();
    await rm(dir, { recursive: true, force: true });
  }
});
