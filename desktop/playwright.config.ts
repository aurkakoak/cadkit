import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.ts",
  timeout: 120_000,
  workers: 1,
  expect: { timeout: 20_000 },
  reporter: "list",
});
