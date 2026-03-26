import { defineConfig } from "@playwright/test";

const fallbackBaseUrl =
  process.env.TT_BASE_URL ||
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.FRONTEND_URL ||
  "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: fallbackBaseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 1440, height: 960 }
  }
});
