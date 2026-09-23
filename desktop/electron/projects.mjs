// App-owned project history and metadata. Discovery parses Python but never imports it.
import { execFile } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import {
  mkdir,
  readFile,
  readdir,
  realpath,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execute = promisify(execFile);
const pause = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));
const identifier = /^[\p{ID_Start}_][\p{ID_Continue}]*$/u;
const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const pythonExecutable = (directory) =>
  path.join(
    directory,
    ...(process.platform === "win32" ? ["python.exe"] : ["bin", "python3"]),
  );

function defaultName(target) {
  const modules = target.reference.split(":")[0].split(".");
  return modules.at(-1) === "project"
    ? modules.at(-2) || path.basename(target.projectDir)
    : modules.at(-1);
}

export function normalizeReference(reference = "project:PROJECT") {
  if (typeof reference !== "string")
    throw new Error("Choose a Python module:attribute reference.");
  const fields = reference.trim().split(":");
  const module = fields[0].trim();
  const attribute = fields[1]?.trim() || "PROJECT";
  if (
    fields.length > 2 ||
    !module.split(".").every((part) => identifier.test(part)) ||
    !identifier.test(attribute)
  ) {
    throw new Error("Use a Python import reference such as project:PROJECT.");
  }
  return `${module}:${attribute}`;
}

async function canonicalDirectory(directory) {
  if (typeof directory !== "string" || !directory.trim())
    throw new Error("Choose a project folder.");
  const absolute = path.resolve(directory);
  try {
    return await realpath(absolute);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    return absolute;
  }
}

async function normalizeTarget(target) {
  const normalized = {
    projectDir: await canonicalDirectory(target.projectDir),
    reference: normalizeReference(target.reference),
  };
  if (Object.hasOwn(target, "python")) {
    if (target.python !== undefined && typeof target.python !== "string")
      throw new Error("Choose a Python interpreter.");
    normalized.python = target.python?.trim() || undefined;
  }
  return normalized;
}

export async function projectIdentity(target) {
  const normalized = await normalizeTarget(target);
  return createHash("sha256")
    .update(`${normalized.projectDir}\0${normalized.reference}`)
    .digest("hex")
    .slice(0, 24);
}

async function atomicWrite(filename, content) {
  const temporary = `${filename}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, content, { flag: "wx", mode: 0o600 });
    await rename(temporary, filename);
  } finally {
    await rm(temporary, { force: true });
  }
}

async function isDirectory(directory) {
  try {
    return (await stat(directory)).isDirectory();
  } catch (error) {
    if (["ENOENT", "ENOTDIR", "EACCES", "EPERM"].includes(error.code))
      return false;
    throw error;
  }
}

async function isFile(filename) {
  try {
    return (await stat(filename)).isFile();
  } catch (error) {
    if (["ENOENT", "ENOTDIR", "EACCES", "EPERM"].includes(error.code))
      return false;
    throw error;
  }
}

async function knownEntryFile(target) {
  const module = target.reference.split(":")[0].split(".");
  for (const root of [target.projectDir, path.join(target.projectDir, "src")]) {
    const base = path.join(root, ...module);
    for (const candidate of [`${base}.py`, path.join(base, "__init__.py")]) {
      if (await isFile(candidate)) return candidate;
    }
  }
}

const STARTER = `"""A local part, its manufacturing intent and an installed instance."""
import cadquery as cq
import cadkit as ck

WIDTH = 40
DEPTH = 24
THICKNESS = 6


def plate_body():
    # Millimetres; the origin is the centre of the bottom face.
    return cq.Workplane("XY").box(WIDTH, DEPTH, THICKNESS, centered=(True, True, False))


plate = ck.Part("plate", body=plate_body, manufacture=ck.FDM("PLA"))
assembly = ck.Assembly("my-project")
installed_plate = assembly.add(plate)
assembly.fix(installed_plate)
PROJECT = assembly.as_project()
`;

export class ProjectLibrary {
  constructor({ userData, framework, resourcesPath, isPackaged }) {
    this.directory = userData;
    this.filename = path.join(userData, "projects.json");
    this.lock = `${this.filename}.lock`;
    this.previews = path.join(userData, "project-previews");
    this.framework = framework;
    this.resourcesPath = resourcesPath;
    this.isPackaged = isPackaged;
  }

  async read() {
    try {
      const data = JSON.parse(await readFile(this.filename, "utf8"));
      if (data.schemaVersion !== 1 || !Array.isArray(data.projects)) {
        throw new Error("Project history has an unsupported format.");
      }
      return data;
    } catch (error) {
      if (error.code === "ENOENT") return { schemaVersion: 1, projects: [] };
      throw error;
    }
  }

  async update(change, afterCommit) {
    await mkdir(this.directory, { recursive: true });
    const deadline = Date.now() + 10000;
    const token = randomUUID();
    while (true) {
      try {
        await mkdir(this.lock, { mode: 0o700 });
        await atomicWrite(
          path.join(this.lock, "owner.json"),
          JSON.stringify({ pid: process.pid, token }),
        );
        break;
      } catch (error) {
        if (error.code !== "EEXIST") throw error;
        await this.recoverLock();
        if (Date.now() > deadline)
          throw new Error("Project history is busy. Try again.");
        await pause(25);
      }
    }
    try {
      const data = await this.read();
      const result = await change(data);
      await atomicWrite(this.filename, JSON.stringify(data, null, 2) + "\n");
      await afterCommit?.();
      return result;
    } finally {
      const owner = JSON.parse(
        await readFile(path.join(this.lock, "owner.json"), "utf8"),
      );
      if (owner.token === token)
        await rm(this.lock, {
          recursive: true,
          force: true,
          maxRetries: 3,
          retryDelay: 10,
        });
    }
  }

  async recoverLock() {
    // Only one contender may reclaim a crashed writer. Re-read its owner after
    // claiming recovery so a stale observation cannot remove a replacement lock.
    const marker = path.join(this.lock, "reclaim");
    try {
      await mkdir(marker);
    } catch (error) {
      if (["ENOENT", "EEXIST"].includes(error.code)) return;
      throw error;
    }
    let stale = false;
    try {
      const owner = JSON.parse(
        await readFile(path.join(this.lock, "owner.json"), "utf8"),
      );
      try {
        process.kill(owner.pid, 0);
      } catch (error) {
        if (error.code === "ESRCH") stale = true;
      }
    } catch (error) {
      if (error.code !== "ENOENT") {
        await rm(marker, { recursive: true, force: true });
        throw error;
      }
      const info = await stat(this.lock).catch(() => null);
      // Creating the reclaim marker updates mtime; birthtime still identifies
      // the lock's age when a writer died before recording its PID.
      stale = info && Date.now() - info.birthtimeMs > 30000;
    }
    if (stale)
      await rm(this.lock, {
        recursive: true,
        force: true,
        maxRetries: 3,
        retryDelay: 10,
      });
    else await rm(marker, { recursive: true, force: true });
  }

  async recent(record) {
    const { preview, entryFile, ...result } = record;
    result.missing =
      !(await isDirectory(record.projectDir)) ||
      Boolean(entryFile && !(await isFile(entryFile)));
    if (preview) {
      try {
        result.thumbnail = `data:image/png;base64,${(await readFile(path.join(this.previews, `${record.id}.png`))).toString("base64")}`;
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
    }
    return result;
  }

  async list() {
    const data = await this.read();
    const projects = await Promise.all(
      data.projects.map((record) => this.recent(record)),
    );
    return projects.sort(
      (a, b) =>
        Number(b.pinned) - Number(a.pinned) ||
        b.lastOpened.localeCompare(a.lastOpened) ||
        a.id.localeCompare(b.id),
    );
  }

  async remember(target, { name, replaceRecentId } = {}) {
    const normalized = await normalizeTarget(target);
    const id = await projectIdentity(normalized);
    const entryFile = await knownEntryFile(normalized);
    let retiredPreview;
    const record = await this.update(
      async (data) => {
        const previous = data.projects.find((entry) => entry.id === id);
        const replaced =
          replaceRecentId !== id
            ? data.projects.find((entry) => entry.id === replaceRecentId)
            : undefined;
        // A moved import root cannot keep the source path from the old location.
        const { entryFile: oldEntryFile, ...movedMetadata } = replaced ?? {};
        const result = {
          ...movedMetadata,
          ...previous,
          ...normalized,
          ...(entryFile ? { entryFile } : {}),
          id,
          name:
            name?.trim() ||
            previous?.name ||
            replaced?.name ||
            defaultName(normalized),
          lastOpened: new Date().toISOString(),
          pinned: previous?.pinned ?? replaced?.pinned ?? false,
        };
        const previewOwner = previous?.preview?.manual
          ? previous
          : replaced?.preview?.manual
            ? replaced
            : previous?.preview
              ? previous
              : replaced?.preview
                ? replaced
                : undefined;
        if (previewOwner && previewOwner.id !== id) {
          try {
            const png = await readFile(
              path.join(this.previews, `${previewOwner.id}.png`),
            );
            await atomicWrite(path.join(this.previews, `${id}.png`), png);
            result.preview = previewOwner.preview;
          } catch (error) {
            if (error.code !== "ENOENT") throw error;
            delete result.preview;
          }
        }
        data.projects = [
          ...data.projects.filter(
            (entry) => entry.id !== id && entry.id !== replaced?.id,
          ),
          result,
        ];
        retiredPreview = replaced?.id;
        return result;
      },
      async () => {
        // Still inside the writer lock: another app cannot recreate this recent
        // and its preview between the metadata commit and cleanup.
        if (retiredPreview)
          await rm(path.join(this.previews, `${retiredPreview}.png`), {
            force: true,
          });
      },
    );
    return this.recent(record);
  }

  async pin(id, pinned) {
    await this.update((data) => {
      const record = data.projects.find((entry) => entry.id === id);
      if (!record)
        throw new Error("This project is no longer in recent projects.");
      record.pinned = Boolean(pinned);
    });
  }

  async rename(id, name) {
    if (typeof name !== "string" || !name.trim()) {
      throw new Error("Choose a project name.");
    }
    await this.update((data) => {
      const record = data.projects.find((entry) => entry.id === id);
      // A completed build may arrive after the user removed this recent.
      // Update an existing label only; opening is what creates a recent.
      if (record) record.name = name.trim();
    });
  }

  async remove(id) {
    await this.update(async (data) => {
      const record = data.projects.find((entry) => entry.id === id);
      if (!record) return;
      data.projects = data.projects.filter((entry) => entry.id !== id);
      await rm(path.join(this.previews, `${record.id}.png`), { force: true });
    });
  }

  async writePreview(id, pngBuffer, { manual = false } = {}) {
    const png = Buffer.from(pngBuffer);
    if (
      png.length > 8 * 1024 * 1024 ||
      !png.subarray(0, 8).equals(pngSignature)
    ) {
      throw new Error("Project preview must be a PNG image under 8 MB.");
    }
    await this.update(async (data) => {
      const record = data.projects.find((entry) => entry.id === id);
      if (!record || (record.preview?.manual && !manual)) return;
      await mkdir(this.previews, { recursive: true });
      await atomicWrite(path.join(this.previews, `${record.id}.png`), png);
      record.preview = { manual: Boolean(manual) };
    });
  }

  async inspect(directory) {
    const selected = await canonicalDirectory(directory);
    if (!(await isDirectory(selected)))
      throw new Error("Project folder could not be found.");
    const script = await readFile(
      new URL("./projects-discovery.py", import.meta.url),
      "utf8",
    );
    const candidates = this.isPackaged
      ? [pythonExecutable(path.join(this.resourcesPath, "python"))]
      : [
          path.join(
            this.framework,
            ".venv",
            process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
          ),
          "python3",
          "python",
        ];
    let choice;
    let failure;
    for (const python of candidates) {
      try {
        const { stdout } = await execute(
          python,
          ["-I", "-c", script, selected],
          {
            timeout: 10000,
            maxBuffer: 2 * 1024 * 1024,
          },
        );
        choice = JSON.parse(stdout);
        break;
      } catch (error) {
        failure = error;
      }
    }
    if (!choice)
      choice = {
        directory: selected,
        entries: [],
        warnings: [
          `Could not discover entry points. Enter an import reference manually. ${failure?.message ?? ""}`,
        ],
      };
    const directories = [
      selected,
      ...choice.entries.map((entry) => entry.projectDir),
    ];
    for (const root of [...new Set(directories)]) {
      const python = path.join(
        root,
        ".venv",
        process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
      );
      if (
        await stat(python)
          .then((info) => info.isFile())
          .catch(() => false)
      ) {
        choice.suggestedPython = python;
        break;
      }
    }
    return choice;
  }

  async create(directory, template = "starter") {
    if (!["starter", "bracket"].includes(template))
      throw new Error("Choose the starter or bracket template.");
    const selected = await canonicalDirectory(directory);
    await mkdir(selected, { recursive: true });
    if ((await readdir(selected)).length)
      throw new Error(
        "Choose a new or empty folder. Existing files will not be replaced.",
      );
    const content =
      template === "starter"
        ? STARTER
        : await readFile(
            path.join(
              this.isPackaged ? this.resourcesPath : this.framework,
              "examples",
              "bracket.py",
            ),
          );
    await writeFile(path.join(selected, "project.py"), content, { flag: "wx" });
    return { projectDir: selected, reference: "project:PROJECT" };
  }
}
