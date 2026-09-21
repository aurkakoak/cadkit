const fs = require("node:fs");
const path = require("node:path");

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
};
