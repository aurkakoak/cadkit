const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

module.exports = async ({ packager, electronPlatformName, arch }) => {
  const manifest = JSON.parse(
    fs.readFileSync(
      path.join(packager.info.appDir, "bundle", "runtime.json"),
      "utf8",
    ),
  );
  const targetArch = {
    0: "ia32",
    1: "x64",
    2: "armv7l",
    3: "arm64",
    4: "universal",
  }[arch];
  if (
    manifest.platform !== electronPlatformName ||
    manifest.arch !== targetArch
  )
    throw new Error(
      `Python bundle is ${manifest.platform}/${manifest.arch}, requested ${electronPlatformName}/${targetArch}. Run npm run bundle:python on the target platform and architecture.`,
    );
  const expected = JSON.parse(
    fs.readFileSync(path.join(packager.info.appDir, "package.json"), "utf8"),
  ).version;
  const python = path.join(
    packager.info.appDir,
    "bundle",
    "python",
    ...(electronPlatformName === "win32" ? ["python.exe"] : ["bin", "python3"]),
  );
  // Isolated Python verifies the installed bundle without accepting the source
  // checkout or a developer's PYTHONPATH as evidence of a current installation.
  const result = spawnSync(
    python,
    [
      "-I",
      "-c",
      "import json, importlib.metadata, cadkit; print(json.dumps({'distribution': importlib.metadata.version('cadkit-py'), 'module': cadkit.__version__}))",
    ],
    {
      encoding: "utf8",
      timeout: 30000,
      maxBuffer: 1024 * 1024,
      windowsHide: true,
    },
  );
  const recovery = "Run npm run bundle:python before packaging CadKit.";
  if (result.error || result.status !== 0) {
    const detail =
      result.error?.message ||
      result.stderr?.trim() ||
      `exit status ${result.status}`;
    throw new Error(
      `Bundled CadKit could not run its version check: ${detail.slice(-2000)}. ${recovery}`,
    );
  }
  let versions;
  try {
    versions = JSON.parse(result.stdout);
  } catch {
    throw new Error(
      `Bundled CadKit returned an invalid version report. ${recovery}`,
    );
  }
  if (versions?.distribution !== expected || versions?.module !== expected)
    throw new Error(
      `Bundled CadKit version does not match desktop ${expected}: installed package ${versions?.distribution ?? "unknown"}, imported module ${versions?.module ?? "unknown"}. ${recovery}`,
    );
};
