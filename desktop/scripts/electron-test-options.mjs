// Opt in only for trusted test fixtures on hosts without a usable GPU.
// Normal application launches retain Chromium's default graphics and sandbox.
export function electronTestArgs(args, env = process.env) {
  const switches = [];
  if (env.CADKIT_TEST_NO_SANDBOX === "1") switches.push("--no-sandbox");
  if (env.CADKIT_TEST_SOFTWARE_RENDERING === "1")
    switches.push(
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    );
  return [...switches, ...args];
}
