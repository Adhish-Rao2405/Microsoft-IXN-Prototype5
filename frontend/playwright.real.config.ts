import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/real-e2e",
  outputDir: "./test-results/real",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "real-stack-edge",
      use: {
        ...devices["Desktop Edge"],
        channel: "msedge",
      },
    },
  ],
});
