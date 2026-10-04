import { defineConfig, devices } from "@playwright/test";
const backendPort = process.env.JA_E2E_BACKEND_PORT ?? "8000";
const frontendPort = process.env.JA_E2E_FRONTEND_PORT ?? "5173";
const backendUrl = `http://127.0.0.1:${backendPort}`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  use: { baseURL: frontendUrl, trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.env.PLAYWRIGHT_CHANNEL,
      },
    },
  ],
  webServer: [
    {
      command: `uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port ${backendPort}`,
      cwd: "..",
      url: `${backendUrl}/ready`,
      env: {
        JA_DATA_DIR: "data/e2e",
        OPENAI_API_KEY: "",
        ELEVENLABS_API_KEY: "",
        ELEVENLABS_INTERVIEWER_AGENT_ID: "",
        ELEVENLABS_TUTOR_AGENT_ID: "",
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: frontendUrl,
      env: { JA_BACKEND_URL: backendUrl },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
