import { test, expect, _electron as electron } from "@playwright/test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

test("mechanical contracts share live state, hardware presentation and revision-scoped validation over MCP", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "cadkit-mechanical-mcp-"));
  const source = await readFile(
    path.resolve("../examples/mechanical_joint.py"),
    "utf8",
  );
  await writeFile(path.join(dir, "project.py"), source);
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
    env: { ...process.env, CADKIT_USER_DATA: path.join(dir, "profile") },
  });
  const page = await app.firstWindow();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const client = new Client({
    name: "mechanical-contract-test",
    version: "1.0.0",
  });
  const call = async (name: string, args: object = {}) => {
    const result = await client.callTool({ name, arguments: args });
    expect(result.isError, JSON.stringify(result)).not.toBe(true);
    return result.structuredContent as any;
  };
  try {
    await expect(page.getByText("Build up to date")).toBeVisible();
    await client.connect(
      new StdioClientTransport({
        command: process.execPath,
        args: [
          path.resolve("electron/mcp.mjs"),
          "--project-dir",
          dir,
          "--project",
          "project:PROJECT",
        ],
      }),
    );
    expect((await client.listTools()).tools.map((t) => t.name)).toEqual(
      expect.arrayContaining([
        "inspect_connection",
        "select_connection",
        "mechanical_report",
        "set_hardware_view",
      ]),
    );
    const state = await call("get_state"),
      revision = state.revision;
    expect(state.mechanics.joints).toHaveLength(1);
    expect(state.mechanics.interfaces).toHaveLength(1);
    expect(state.mechanics.fastenings).toHaveLength(1);
    expect(
      state.mechanics.hardware_bom.map((r: any) => r.quantity).sort(),
    ).toEqual([2, 2, 4]);
    const hardware = state.components.filter(
      (c: any) => c.metadata.role === "fastener",
    );
    expect(hardware).toHaveLength(8);
    const connection = await call("inspect_connection", {
      revision,
      kind: "fastening",
      id: "plate-bolts",
    });
    expect(connection.connection.hardware_ids).toHaveLength(8);
    expect(connection.components).toHaveLength(10);
    expect(
      (
        await call("inspect_connection", {
          revision,
          kind: "joint",
          id: "plate-joint",
        })
      ).connection.kind,
    ).toBe("rigid");
    expect(
      (
        await call("inspect_connection", {
          revision,
          kind: "interface",
          id: "plate-contact",
        })
      ).connection.kind,
    ).toBe("contact");
    const hidden = await call("set_hardware_view", {
      revision,
      mode: "hidden",
    });
    expect(hidden.hidden).toEqual(
      expect.arrayContaining(hardware.map((c: any) => c.id)),
    );
    expect(hidden.hidden).toHaveLength(8);
    await call("select_connection", {
      revision,
      kind: "fastening",
      id: "plate-bolts",
      focus: true,
    });
    await expect(
      page.getByRole("heading", { name: "plate bolts", exact: true }),
    ).toBeVisible();
    const preview = await call("set_hardware_view", {
      revision,
      mode: "selected",
      previewProgress: 1,
    });
    expect(preview.selectedConnection).toEqual({
      kind: "fastening",
      id: "plate-bolts",
    });
    expect(preview.presentation.pose).toBe("hardware-preview");
    expect(preview.presentation.offsetIds).toHaveLength(8);
    await expect(page.locator(".assembly-preview-badge")).toBeVisible();
    expect(
      (
        await client.callTool({
          name: "measure",
          arguments: {
            revision,
            ids: hardware.slice(0, 2).map((c: any) => c.id),
          },
        })
      ).isError,
    ).toBe(true);
    const png = await client.callTool({
      name: "screenshot",
      arguments: { target: "window", max_width: 1600 },
    });
    const image = (png.content as any[]).find((c) => c.type === "image");
    expect(image?.mimeType).toBe("image/png");
    await mkdir("test-results", { recursive: true });
    await writeFile(
      "test-results/mechanics-mcp-dark.png",
      Buffer.from(image.data, "base64"),
    );
    await call("set_hardware_view", {
      revision,
      previewProgress: 0,
      mode: "all",
    });
    const report = await call("mechanical_report", { revision });
    expect(report.summary.fail).toBe(0);
    expect(report.status).toBe("incomplete");
    expect(report.coverage.pairs_scanned).toBe(45);
    await expect(
      page.locator('[data-validation-status="incomplete"]'),
    ).toBeVisible();
    const resource = await client.readResource({ uri: "cadkit://mechanics" });
    const resourceState = JSON.parse((resource.contents[0] as any).text);
    expect(resourceState.mechanics.fastenings[0].id).toBe("plate-bolts");
    expect(resourceState.validation.revision).toBe(revision);
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await page.screenshot({ path: "test-results/mechanics-mcp-light.png" });
    await writeFile(
      path.join(dir, "project.py"),
      source +
        `
_original_components = components
def with_proxy(**options):
    return _original_components(**options) + [Component(
        "fixture-proxy", cq.Solid.makeBox(4, 4, 4).translate((-10, -2, 8)),
        "Reference", metadata={"representation": "envelope"})]
PROJECT.components = with_proxy
`,
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
    const fresh = await call("get_state");
    expect(fresh.mechanicalReport).toBeNull();
    expect(fresh.hardwareView.previewProgress).toBe(0);
    expect(
      (
        await client.callTool({
          name: "mechanical_report",
          arguments: { revision },
        })
      ).isError,
    ).toBe(true);
    await call("mechanical_report", { revision: fresh.revision });
    const qualified = await call("inspect_connection", {
      revision: fresh.revision,
      kind: "fastening",
      id: "plate-bolts",
    });
    expect(qualified.validation_status).toBe("incomplete");
    expect(
      qualified.findings.some(
        (f: any) =>
          f.concept === "assembly" &&
          f.code.startsWith("collision-") &&
          f.status === "unverified",
      ),
    ).toBe(true);
    expect(qualified.findings.some((f: any) => f.status === "fail")).toBe(
      false,
    );
    expect(errors).toEqual([]);
  } finally {
    await client.close();
    await app.close();
    await rm(dir, { recursive: true, force: true });
  }
});
