import { _electron as electron, test, type Page } from "@playwright/test";
import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { electronTestArgs } from "../scripts/electron-test-options.mjs";

export async function launchElectron(
  options: Parameters<typeof electron.launch>[0],
) {
  const log = test.info().outputPath("electron.log");
  mkdirSync(path.dirname(log), { recursive: true });
  const record = (source: string, message: string) => {
    appendFileSync(log, `[${source}] ${message.trimEnd()}\n`);
  };
  const app = await electron.launch({
    ...options,
    args: electronTestArgs(options?.args ?? [], options?.env ?? process.env),
  });
  // Surface renderer/GPU startup errors instead of reporting only a later
  // timeout waiting for the ready label on an empty page.
  app.process().stderr?.on("data", (data) => {
    record("electron stderr", String(data));
    process.stderr.write(data);
  });
  const reportErrors = (page: Page) => {
    page.on("console", (message) =>
      record(`renderer ${message.type()}`, message.text()),
    );
    page.on("pageerror", (error) => {
      const detail = error.stack ?? error.message;
      record("renderer error", detail);
      process.stderr.write(`CadKit renderer error: ${detail}\n`);
    });
  };
  app.on("window", reportErrors);
  app.windows().forEach(reportErrors);
  return app;
}
