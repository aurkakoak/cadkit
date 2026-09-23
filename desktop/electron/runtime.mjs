import { constants, copyFileSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { normalizeReference } from "./projects.mjs";

export function argument(argv, name, fallback) {
  const index = argv.indexOf(name);
  if (index < 0) return fallback;
  const value = argv[index + 1];
  if (!value || value.startsWith("--"))
    throw new Error(`${name} requires a value`);
  return value;
}

export function pythonExecutable(directory, platform = process.platform) {
  return path.join(
    directory,
    ...(platform === "win32" ? ["python.exe"] : ["bin", "python3"]),
  );
}

export function resolveRuntime({
  argv = process.argv,
  cwd = process.cwd(),
  platform = process.platform,
  isPackaged,
  resourcesPath,
  userData,
  framework,
  env = process.env,
}) {
  const explicitDirectory = argument(argv, "--project-dir");
  const explicitReference = argument(argv, "--project");
  const useExample =
    argv.includes("--smoke-test") && !explicitDirectory && !explicitReference;
  if (!explicitDirectory && !explicitReference && !useExample) return null;
  const projectDir = path.resolve(
    explicitDirectory ??
      (useExample ? path.join(userData, "projects", "bracket") : cwd),
  );
  if (useExample) {
    mkdirSync(projectDir, { recursive: true });
    // Smoke tests use a real editable project without replacing previous work.
    try {
      copyFileSync(
        path.join(
          isPackaged ? resourcesPath : framework,
          "examples",
          "bracket.py",
        ),
        path.join(projectDir, "project.py"),
        constants.COPYFILE_EXCL,
      );
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
    }
  }
  const projectPython = path.join(
    projectDir,
    ".venv",
    ...(platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]),
  );
  const bundledPython = pythonExecutable(
    path.join(resourcesPath, "python"),
    platform,
  );
  const explicitPython = argument(argv, "--python");
  const python =
    explicitPython ??
    (isPackaged
      ? bundledPython
      : existsSync(projectPython)
        ? projectPython
        : platform === "win32"
          ? "python"
          : "python3");
  if (isPackaged && !explicitPython && !existsSync(python))
    throw new Error(`Bundled Python is missing: ${python}. Reinstall CadKit.`);
  const workerEnv = { ...env };
  if (isPackaged && !explicitPython) {
    // Shell activation must not redirect the bundled interpreter or its imports.
    delete workerEnv.PYTHONHOME;
    delete workerEnv.VIRTUAL_ENV;
    workerEnv.PYTHONNOUSERSITE = "1";
    workerEnv.PYTHONPATH = projectDir;
    workerEnv.PYTHONDONTWRITEBYTECODE = "1";
  } else {
    workerEnv.PYTHONPATH = [
      !isPackaged && path.join(framework, "src"),
      projectDir,
      env.PYTHONPATH,
    ]
      .filter(Boolean)
      .join(path.delimiter);
  }
  return {
    projectDir,
    reference: normalizeReference(explicitReference ?? "project:PROJECT"),
    python,
    workerEnv,
  };
}
