import { spawnSync } from "node:child_process";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { pythonExecutable } from "../electron/runtime.mjs";

const desktop = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const root = path.dirname(desktop);
const bundle = path.join(desktop, "bundle");
const temporary = await mkdtemp(path.join(os.tmpdir(), "cadkit bundle "));
const env = {
  ...process.env,
  UV_PYTHON_INSTALL_DIR: path.join(temporary, "managed"),
  UV_PYTHON_INSTALL_BIN: "0",
  UV_LINK_MODE: "copy",
};
delete env.VIRTUAL_ENV;
delete env.PYTHONHOME;
delete env.PYTHONPATH;
const uv = process.env.CADKIT_UV ?? "uv";
function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    env,
    encoding: "utf8",
    stdio: "inherit",
    ...options,
  });
  if (result.error) throw result.error;
  if (result.status !== 0)
    throw new Error(`${command} failed with status ${result.status}`);
  return result.stdout?.trim();
}

try {
  const version = (
    await readFile(path.join(root, ".python-version"), "utf8")
  ).trim();
  run(uv, ["python", "install", "--no-bin", version]);
  const sourcePython = run(
    uv,
    ["python", "find", "--managed-python", version],
    { stdio: ["ignore", "pipe", "inherit"] },
  );
  const prefix = run(
    sourcePython,
    ["-I", "-c", "import sys; print(sys.base_prefix)"],
    { stdio: ["ignore", "pipe", "inherit"] },
  );
  const runtime = path.join(temporary, "runtime");
  // A venv alone retains links to its build machine's interpreter. Copy the full
  // standalone distribution, keeping its relative symlinks and license files.
  await cp(prefix, runtime, { recursive: true, verbatimSymlinks: true });
  const python = pythonExecutable(runtime);
  const requirements = path.join(temporary, "requirements.txt");
  run(uv, [
    "export",
    "--locked",
    "--extra",
    "desktop",
    "--no-dev",
    "--no-emit-project",
    "--no-hashes",
    "--output-file",
    requirements,
  ]);
  run(uv, [
    "pip",
    "install",
    "--python",
    python,
    "--system",
    "--break-system-packages",
    "--no-deps",
    "-r",
    requirements,
  ]);
  const wheels = path.join(temporary, "wheels");
  run(uv, ["build", "--wheel", "--out-dir", wheels]);
  const wheel = (await readdir(wheels)).find((name) => name.endsWith(".whl"));
  if (!wheel) throw new Error("CadKit wheel was not built");
  run(uv, [
    "pip",
    "install",
    "--python",
    python,
    "--system",
    "--break-system-packages",
    "--no-deps",
    path.join(wheels, wheel),
  ]);

  // Rename after installation to catch absolute paths and missing shared libs.
  const relocated = path.join(temporary, "Relocated Python with spaces");
  await rename(runtime, relocated);
  const project = path.join(temporary, "Example Project");
  await mkdir(project);
  await cp(
    path.join(root, "examples", "bracket.py"),
    path.join(project, "project.py"),
  );
  const smokeEnv = {
    ...env,
    PYTHONPATH: project,
    PYTHONNOUSERSITE: "1",
    PYTHONDONTWRITEBYTECODE: "1",
  };
  run(
    pythonExecutable(relocated),
    [
      "-I",
      "-c",
      "import pathlib,sys,cadkit,cq_warehouse,manifold3d,trimesh; assert pathlib.Path(cadkit.__file__).is_relative_to(pathlib.Path(sys.prefix)); print('Bundled imports OK:', sys.prefix)",
    ],
    { cwd: project, env: smokeEnv },
  );
  const result = run(
    pythonExecutable(relocated),
    ["-u", "-m", "cadkit.desktop", "--project", "project:PROJECT"],
    {
      cwd: project,
      env: smokeEnv,
      input: JSON.stringify({ id: 1, method: "scene" }) + "\n",
      stdio: ["pipe", "pipe", "inherit"],
      timeout: 180000,
      maxBuffer: 16 * 1024 * 1024,
    },
  );
  const response = result
    .split("\n")
    .map((line) => JSON.parse(line))
    .find((item) => item.id === 1);
  if (!response?.result?.components?.length || response.error)
    throw new Error(
      `Bundled CAD worker smoke test failed: ${JSON.stringify(response)}`,
    );
  await mkdir(bundle, { recursive: true });
  await rm(path.join(bundle, "python"), { recursive: true, force: true });
  await cp(relocated, path.join(bundle, "python"), {
    recursive: true,
    verbatimSymlinks: true,
  });
  await writeFile(
    path.join(bundle, "runtime.json"),
    JSON.stringify(
      {
        platform: process.platform,
        arch: process.arch,
        python: version,
        components: response.result.components.length,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    `Bundled Python ready for ${process.platform}/${process.arch}; relocated CAD scene passed.`,
  );
} finally {
  await rm(temporary, { recursive: true, force: true });
}
