import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const python =
  process.env.LOCAL_PYTHON ||
  (existsSync("../.tools/python/python.exe")
    ? `"${resolve("../.tools/python/python.exe")}"`
    : process.platform === "win32"
      ? "py -3.12"
      : "python3.12");
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 30000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5174",
    channel: "msedge",
    headless: true,
    viewport: { width: 1440, height: 1100 },
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `${python} ../scripts/browser_backend.py`,
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --mode test --port 5174",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
    },
  ],
});
