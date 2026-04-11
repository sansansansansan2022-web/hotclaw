import { defineConfig, devices } from "@playwright/test";

const frontendPort = Number(process.env.E2E_FRONTEND_PORT ?? "3107");
const backendPort = Number(process.env.E2E_BACKEND_PORT ?? "8107");
const apiBaseURL = process.env.E2E_API_BASE_URL ?? `http://127.0.0.1:${backendPort}`;
const baseURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${frontendPort}`;
const chromeExecutablePath =
  process.env.PLAYWRIGHT_EXECUTABLE_PATH ?? "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

process.env.E2E_API_BASE_URL = apiBaseURL;
process.env.E2E_BASE_URL = baseURL;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          executablePath: chromeExecutablePath,
        },
      },
    },
  ],
  webServer: [
    {
      command: `.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: "./backend",
      url: `${apiBaseURL}/api/v1/health`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        DATABASE_URL: process.env.E2E_DATABASE_URL ?? "sqlite+aiosqlite:///./hotclaw.e2e.db",
        HOTCLAW_AUTO_CREATE_TABLES: "1",
        HOTCLAW_E2E_TEST_MODE: "1",
        APP_DEBUG: "true",
      },
    },
    {
      command: `npm run build && npm run start -- --hostname 127.0.0.1 --port ${frontendPort}`,
      cwd: "./frontend",
      url: `${baseURL}/accounts`,
      reuseExistingServer: true,
      timeout: 240_000,
      env: {
        HOTCLAW_API_ORIGIN: apiBaseURL,
        NEXT_PUBLIC_HOTCLAW_API_ORIGIN: apiBaseURL,
      },
    },
  ],
});
