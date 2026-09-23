import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { z } from "zod";

const request = z.object({
  revision: z.string().min(1),
  ids: z.array(z.string()).min(1),
  mode: z.enum(["image", "animation", "scene"]),
  camera: z.enum(["Overview", "Front", "Rear"]),
  width: z.number().int().min(16).max(8192),
  height: z.number().int().min(16).max(8192),
  samples: z.number().int().min(1).max(4096),
  exploded: z.boolean(),
});
const busy = (j) => ["exporting", "running"].includes(j.phase);
export class Renderer {
  constructor({ userData, projectDir, python, env, exportAssets, publish }) {
    Object.assign(this, { projectDir, python, env, exportAssets, publish });
    this.configPath = path.join(userData, "renderer.json");
    this.jobs = new Map();
    this.processes = new Map();
    this.closed = false;
  }
  async settings() {
    try {
      return z
        .object({ executable: z.string().min(1) })
        .parse(JSON.parse(await readFile(this.configPath, "utf8")));
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      const candidates = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
      ];
      return { executable: candidates.find(existsSync) || "blender" };
    }
  }
  async save(executable) {
    const config = { executable: z.string().min(1).parse(executable) };
    await mkdir(path.dirname(this.configPath), { recursive: true });
    await writeFile(this.configPath, JSON.stringify(config));
    return config;
  }
  list(id) {
    if (!id) return [...this.jobs.values()].reverse();
    const job = this.jobs.get(id);
    if (!job) throw new Error("Unknown render");
    return job;
  }
  update(job, changes) {
    Object.assign(job, changes);
    if (!this.closed) this.publish({ type: "render", job: { ...job } });
  }
  async start(values) {
    const params = request.parse(values);
    const config = await this.settings();
    if (this.closed) throw new Error("Project closed");
    if ([...this.jobs.values()].some(busy))
      throw new Error("A render is already running");
    const id = randomUUID(),
      directory = path.join(this.projectDir, "build", "desktop-renders", id);
    const job = {
      id,
      directory,
      mode: params.mode,
      revision: params.revision,
      phase: "exporting",
      message: "Exporting",
      log: "",
      output: path.join(
        directory,
        params.mode === "scene"
          ? "scene.blend"
          : params.mode === "animation"
            ? "animation.mp4"
            : "image.png",
      ),
    };
    this.jobs.set(id, job);
    this.update(job, {});
    void this.run(job, params, config).catch((error) => {
      if (busy(job))
        this.update(job, { phase: "failed", message: error.message });
    });
    return job;
  }
  async run(job, params, config) {
    await mkdir(job.directory, { recursive: true });
    if (!busy(job) || this.closed) return;
    const assets = path.join(job.directory, "assets");
    await this.exportAssets({
      revision: params.revision,
      ids: params.ids,
      output_dir: assets,
      exploded: params.exploded,
      animation: params.mode === "animation",
    });
    if (!busy(job) || this.closed) return;
    await writeFile(
      path.join(job.directory, "request.json"),
      JSON.stringify({ ...params, ...config }, null, 2),
    );
    if (!busy(job) || this.closed) return;
    const args = [
      "-m",
      "cadkit.cli",
      "blender",
      "--blender",
      config.executable,
      "--assets",
      path.join(assets, "scene.json"),
      "--output",
      path.join(job.directory, "scene.blend"),
      "--samples",
      String(params.samples),
      "--width",
      String(params.width),
      "--height",
      String(params.height),
      "--camera",
      params.camera,
    ];
    if (params.mode !== "scene") args.push("--render", job.output);
    if (params.mode === "animation") args.push("--animation");
    this.update(job, { phase: "running", message: "Rendering" });
    await new Promise((resolve, reject) => {
      const child = spawn(this.python, args, {
        cwd: this.projectDir,
        env: this.env,
        stdio: ["ignore", "pipe", "pipe"],
        detached: process.platform !== "win32",
        windowsHide: true,
      });
      this.processes.set(job.id, child);
      let lastUpdate = 0;
      const log = (chunk) => {
        job.log = (job.log + chunk.toString()).slice(-60000);
        if (Date.now() - lastUpdate > 500 && busy(job)) {
          lastUpdate = Date.now();
          this.update(job, {
            message:
              job.log
                .trim()
                .split(/[\r\n]/)
                .pop()
                ?.slice(-200) || "Rendering",
          });
        }
      };
      child.stdout.on("data", log);
      child.stderr.on("data", log);
      child.once("error", reject);
      child.once("close", (code) => {
        this.processes.delete(job.id);
        code === 0 ? resolve() : reject(new Error("Blender failed. See log."));
      });
    }).finally(() =>
      writeFile(path.join(job.directory, "render.log"), job.log),
    );
    if (!busy(job) || this.closed) return;
    if (!(await stat(job.output)).size)
      throw new Error("Blender produced an empty output");
    this.update(job, { phase: "complete", message: "Complete" });
  }
  cancel(id) {
    const job = this.list(id);
    if (!busy(job)) return job;
    this.update(job, { phase: "cancelled", message: "Cancelled" });
    const child = this.processes.get(id);
    if (child?.pid) {
      if (process.platform === "win32")
        spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
          windowsHide: true,
        }).on("error", () => {});
      else {
        try {
          process.kill(-child.pid, "SIGKILL");
        } catch (e) {
          if (e.code !== "ESRCH") throw e;
        }
      }
    }
    return job;
  }
  async preview(id) {
    const job = this.list(id);
    if (job.phase !== "complete" || job.mode !== "image") return null;
    if ((await stat(job.output)).size > 32 * 1024 * 1024) return null;
    return `data:image/png;base64,${(await readFile(job.output)).toString("base64")}`;
  }
  close() {
    this.closed = true;
    for (const job of this.jobs.values()) this.cancel(job.id);
  }
}
