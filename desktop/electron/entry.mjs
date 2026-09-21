// The packaged executable is also the MCP stdio command; Node is bundled.
if (process.argv.includes("--mcp")) {
  const { app } = await import("electron");
  app.dock?.hide();
  process.stdin.on("end", () => app.exit(0));
  try {
    await import("./mcp.mjs");
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    app.exit(1);
  }
} else {
  await import("./main.mjs");
}
