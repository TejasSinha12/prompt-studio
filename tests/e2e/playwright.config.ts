// End-to-end tests against real servers:
// * fresh temporary database,
// * Ollama endpoint pointed at a closed loopback port (local AI unavailable),
// * no API keys,
// * the browser blocks every non-loopback request (see fixtures.ts).
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const ROOT = path.resolve(__dirname, "..", "..");
const API_PORT = Number(process.env.E2E_API_PORT ?? 8100);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3100);
const DATA_DIR = process.env.E2E_DATA_DIR ?? mkdtempSync(path.join(tmpdir(), "prompt-studio-e2e-"));
process.env.E2E_DATA_DIR = DATA_DIR; // reused by worker processes

const cleanEnv = Object.fromEntries(
  Object.entries(process.env).filter(([k]) => !/API_KEY|TOKEN/i.test(k)),
) as Record<string, string>;

export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  workers: 1,
  timeout: process.env.E2E_REAL_MODEL ? 600_000 : 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  outputDir: path.join(ROOT, "tests", "e2e", ".results"),
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    viewport: { width: 1440, height: 900 },
    acceptDownloads: true,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: `uv run uvicorn prompt_studio.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: path.join(ROOT, "apps", "api"),
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: process.env.E2E_REAL_MODEL ? 600_000 : 60_000,
      env: {
        ...cleanEnv,
        PROMPT_STUDIO_DATA_DIR: DATA_DIR,
        // Ollama is unreachable unless the opt-in real-model test is requested (npm run test:e2e:real-model).
        PROMPT_STUDIO_OLLAMA_URL: process.env.E2E_REAL_MODEL ? "http://127.0.0.1:11434" : "http://127.0.0.1:9",
        PROMPT_STUDIO_ALLOWED_ORIGINS: JSON.stringify([`http://127.0.0.1:${WEB_PORT}`]),
      },
    },
    {
      command: `npx next build && npx next start --hostname 127.0.0.1 --port ${WEB_PORT}`,
      cwd: path.join(ROOT, "apps", "web"),
      url: `http://127.0.0.1:${WEB_PORT}/`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: { ...cleanEnv, NEXT_TELEMETRY_DISABLED: "1", PROMPT_STUDIO_API_URL: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
