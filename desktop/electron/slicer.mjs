import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile, readdir } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { randomUUID } from "node:crypto";
import { z } from "zod";

const configSchema = z.object({
  kind: z.enum(["bambu", "orca", "prusa"]).default("bambu"),
  executable: z.string().default(""),
  profile: z.string().default(""),
  machine: z.string().default(""),
  process: z.string().default(""),
  filament: z.string().default(""),
  bed: z
    .enum([
      "",
      "Cool Plate",
      "Engineering Plate",
      "High Temp Plate",
      "Textured PEI Plate",
    ])
    .default(""),
  price: z
    .string()
    .refine(
      (s) => s === "" || (Number.isFinite(Number(s)) && Number(s) >= 0),
      "Price must be non-negative",
    )
    .default(""),
  currency: z.string().min(1).max(8).default("GBP"),
});
export class Slicer {
  constructor({ userData, projectDir, python, env, exportParts, publish }) {
    Object.assign(this, { projectDir, python, env, exportParts, publish });
    this.configPath = path.join(userData, "slicer.json");
    this.jobs = new Map();
    this.processes = new Map();
  }
  async settings() {
    if (!this.config) {
      const detected = {
        executable: path.join(
          os.homedir(),
          ".local/share/flatpak/exports/bin/com.bambulab.BambuStudio",
        ),
      };
      try {
        this.config = configSchema.parse(
          JSON.parse(await readFile(this.configPath, "utf8")),
        );
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
        this.config = configSchema.parse(
          Object.fromEntries(
            Object.entries(detected).filter(([, p]) => existsSync(p)),
          ),
        );
      }
    }
    const required =
      this.config.kind === "prusa"
        ? ["executable", "profile"]
        : ["executable", "machine", "process", "filament"];
    const missing = required.filter(
      (key) => !this.config[key] || !existsSync(this.config[key]),
    );
    return { ...this.config, ready: missing.length === 0, missing };
  }
  async save(values) {
    await this.settings();
    const config = configSchema.parse({ ...this.config, ...values });
    await mkdir(path.dirname(this.configPath), { recursive: true });
    await writeFile(this.configPath, JSON.stringify(config, null, 2) + "\n", {
      mode: 0o600,
    });
    this.config = config;
    return this.settings();
  }
  update(job, values) {
    Object.assign(job, values, { updated: new Date().toISOString() });
    this.publish({ type: "slice", job: { ...job } });
  }
  list(id) {
    if (!id) return { jobs: [...this.jobs.values()].reverse() };
    const job = this.jobs.get(id);
    if (!job) throw new Error("Unknown slicer job");
    return job;
  }
  async start({ revision, parts, validation_override }, mode = "slice") {
    const config = await this.settings();
    if (mode === "slice" && !config.ready)
      throw new Error(
        `Configure slicer ${config.missing.join(", ")} in Print settings`,
      );
    if (!config.executable || !existsSync(config.executable))
      throw new Error("Choose a slicer executable in Print settings");
    if (
      [...this.jobs.values()].some((j) =>
        ["exporting", "running"].includes(j.phase),
      )
    )
      throw new Error("A slicer job is already running");
    const id = randomUUID();
    const directory = path.join(this.projectDir, "build", "desktop-slices", id);
    const job = {
      id,
      revision,
      validation_override,
      parts: [...new Set(parts)],
      mode,
      phase: "exporting",
      directory,
      artifacts: [],
      config,
      created: new Date().toISOString(),
    };
    this.jobs.set(id, job);
    this.update(job, {});
    void this.run(job).catch((error) => {
      if (job.phase !== "cancelled")
        this.update(job, { phase: "error", error: error.message });
    });
    return { ...job };
  }
  async run(job) {
    await mkdir(job.directory, { recursive: true });
    await writeFile(
      path.join(job.directory, "request.json"),
      JSON.stringify(
        {
          revision: job.revision,
          validation_override: job.validation_override,
          parts: job.parts,
          mode: job.mode,
          config: job.config,
          created: job.created,
        },
        null,
        2,
      ) + "\n",
    );
    const exported = await this.exportParts(
      job.revision,
      job.parts,
      path.join(job.directory, "parts"),
      job.validation_override,
    );
    this.update(job, {
      assembly_validation: exported.manifest.assembly_validation ?? null,
    });
    if (job.phase === "cancelled") return;
    if (job.mode === "prepare") {
      const artifacts = exported.manifest.parts.map((p) =>
        path.join(exported.directory, p.files.stl),
      );
      this.update(job, { phase: "complete", artifacts });
      await this.open(job.id);
      return;
    }
    const config = job.config;
    const args = [
      "-u",
      "-m",
      "cadkit.slice_build",
      "--manifest",
      path.join(exported.directory, "manifest.json"),
      "--slicer",
      config.executable,
      "--slicer-kind",
      config.kind,
      "--profile",
      config.profile,
      "--machine-profile",
      config.machine,
      "--process-profile",
      config.process,
      "--filament-profile",
      config.filament,
      "--filament-price-per-kg",
      config.price,
      "--currency",
      config.currency,
      "--work-dir",
      path.join(job.directory, "work"),
      "--artifact-dir",
      path.join(job.directory, "sliced"),
      "--output-json",
      path.join(job.directory, "report.json"),
      "--output-markdown",
      path.join(job.directory, "report.md"),
    ];
    if (config.kind !== "prusa" && config.bed)
      args.push(`--extra-args=--curr-bed-type ${JSON.stringify(config.bed)}`);
    this.update(job, { phase: "running" });
    const child = spawn(this.python, args, {
      cwd: this.projectDir,
      env: this.env,
      stdio: ["ignore", "pipe", "pipe"],
      detached: process.platform !== "win32",
      windowsHide: true,
    });
    this.processes.set(job.id, child);
    let log = "",
      pendingLine = "";
    const capture = (data) => {
      log = (log + data).slice(-60000);
      pendingLine += data;
      const lines = pendingLine.split("\n");
      pendingLine = lines.pop();
      for (const line of lines)
        if (/^\[\d+\/\d+\]/.test(line)) this.update(job, { progress: line });
    };
    child.stdout.on("data", capture);
    child.stderr.on("data", capture);
    const timeout = setTimeout(() => this.cancel(job.id), 30 * 60 * 1000);
    try {
      const code = await new Promise((resolve, reject) => {
        child.once("error", reject);
        child.once("close", resolve);
      });
      await writeFile(path.join(job.directory, "slicer.log"), log);
      if (job.phase === "cancelled") return;
      if (code !== 0)
        throw new Error(
          log.trim().slice(-6000) || `Slicer exited with code ${code}`,
        );
      const report = JSON.parse(
        await readFile(path.join(job.directory, "report.json"), "utf8"),
      );
      const artifacts = (await readdir(path.join(job.directory, "sliced")))
        .filter((p) => /\.(?:gcode|3mf)$/.test(p))
        .map((p) => path.join(job.directory, "sliced", p));
      this.update(job, { phase: "complete", report, artifacts });
    } finally {
      clearTimeout(timeout);
      this.processes.delete(job.id);
    }
  }
  cancel(id) {
    const job = this.list(id);
    if (!["exporting", "running"].includes(job.phase)) return job;
    this.update(job, { phase: "cancelled" });
    const child = this.processes.get(id);
    if (child?.pid) {
      try {
        if (process.platform !== "win32") process.kill(-child.pid, "SIGKILL");
        else
          spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
            windowsHide: true,
          });
      } catch (error) {
        if (error.code !== "ESRCH") throw error;
      }
    }
    return job;
  }
  async open(id) {
    const job = this.list(id);
    if (job.phase !== "complete" || !job.artifacts.length)
      throw new Error("No completed slicer artifacts");
    await new Promise((resolve, reject) => {
      const child = spawn(job.config.executable, job.artifacts, {
        cwd: this.projectDir,
        stdio: "ignore",
        detached: true,
      });
      child.once("error", reject);
      child.once("spawn", () => {
        child.unref();
        resolve();
      });
    });
    return { id, opened: job.artifacts };
  }
  close() {
    for (const job of this.jobs.values()) this.cancel(job.id);
  }
}
