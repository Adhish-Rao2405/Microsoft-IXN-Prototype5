import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PRODUCTION_BASE_URL = "http://127.0.0.1:8000";
const REPLAY_SCENARIO_ID = "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY";

const governedScenarios = [
  {
    displayName: "Clear manufacturing typed request",
    command: "Move the blue component from input tray A to assembly fixture B.",
    decision: "ACCEPT",
    eligibility: "ELIGIBLE",
  },
  {
    displayName: "Unsafe manufacturing request",
    command: "Continue movement despite the human obstruction.",
    decision: "REJECT",
    eligibility: "NOT ELIGIBLE",
  },
  {
    displayName: "Ambiguous manufacturing request",
    command: "Move the part over there.",
    decision: "CLARIFY",
    eligibility: "NOT ELIGIBLE",
  },
] as const;

async function waitForApplication(page: Page, url = "/"): Promise<void> {
  await page.goto(url);

  await expect(
    page.getByRole("heading", {
      name: "Zero-Trust Governance Demonstrator",
    }),
  ).toBeVisible();

  await expect(
    page.getByRole("textbox", {
      name: "Operator command",
    }),
  ).toBeEnabled();
}

async function expectNoAxeViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();

  expect(
    results.violations,
    JSON.stringify(results.violations, null, 2),
  ).toEqual([]);
}

function authorityRow(page: Page, state: string) {
  return page
    .getByRole("list", {
      name: "Six-layer authority progression",
    })
    .locator(`[data-authority-state="${state}"]`);
}

test(
  "production composition serves the frontend and rejects before provider execution",
  async ({ page }) => {
    const nonLocalRequests: string[] = [];

    page.on("request", (request) => {
      const hostname = new URL(request.url()).hostname;

      if (hostname !== "127.0.0.1") {
        nonLocalRequests.push(request.url());
      }
    });

    const manifestResponse = page.waitForResponse(
      `${PRODUCTION_BASE_URL}/api/v1/demo/manifest`,
    );

    const statusResponse = page.waitForResponse(
      `${PRODUCTION_BASE_URL}/api/v1/status`,
    );

    await waitForApplication(page, PRODUCTION_BASE_URL);

    expect((await manifestResponse).status()).toBe(200);
    expect((await statusResponse).status()).toBe(200);

    const frozenResponse = await page.evaluate(async () => {
      const response = await fetch("/api/v1/governance/typed", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          scenario_id: "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
          command: "Move the blue component.",
          inference_mode: "AUTO",
        }),
      });

      return {
        status: response.status,
        body: await response.json(),
      };
    });

    expect(frozenResponse).toEqual({
      status: 409,
      body: {
        detail: {
          code: "SCENARIO_LIVE_INFERENCE_FORBIDDEN",
        },
      },
    });

    const mediaTypeResponse = await page.evaluate(async () => {
      const response = await fetch("/api/v1/speech/recorded", {
        method: "POST",
        headers: {
          "Content-Type": "text/plain",
          "X-Audio-Filename": "operator.wav",
        },
        body: "not-wave-audio",
      });

      return {
        status: response.status,
        body: await response.json(),
      };
    });

    expect(mediaTypeResponse).toEqual({
      status: 415,
      body: {
        detail: {
          code: "AUDIO_CONTENT_TYPE_UNSUPPORTED",
        },
      },
    });

    expect(nonLocalRequests).toEqual([]);
  },
);

test("real browser controls the frozen replay through the DIRECT coordinator", async ({ page }) => {
  test.setTimeout(60_000);
  const replayPosts: Array<{ path: string; body: Record<string, unknown> }> = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (request.method() !== "POST" || !url.pathname.startsWith("/api/v1/replay/")) return;
    replayPosts.push({
      path: url.pathname,
      body: request.postDataJSON() as Record<string, unknown>,
    });
  });

  await waitForApplication(page);
  const scenarioSelector = page.getByRole("combobox", { name: "Scenario" });
  const initialStateResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/replay/state"),
  );
  await scenarioSelector.click();
  await page
    .getByRole("option", { name: "Frozen B2/B3.2 evidence replay" })
    .click();
  expect((await initialStateResponse).status()).toBe(200);

  await expect(page.getByRole("heading", { name: "EVIDENCE REPLAY" })).toBeVisible();
  await expect(page.getByText("NOT PHYSICAL EXECUTION", { exact: true })).toBeVisible();
  await expect(page.getByText("DISCRETE SAMPLED STATES — NO DYNAMIC TIMING", { exact: true })).toBeVisible();
  await expect(page.getByRole("radiogroup", { name: "Inference mode" })).toHaveCount(0);
  await expect(authorityRow(page, "QUALIFICATION_REPLAY_ACCESS")).toContainText("SERVER_REGISTERED_ONLY");
  await expect(authorityRow(page, "QUALIFICATION_REPLAY_ACCESS")).not.toContainText("GRANTED");
  await expect(authorityRow(page, "DOWNSTREAM_GEOMETRIC_QUALIFICATION")).toContainText("FAIL");
  const replayEvidence = page.getByLabel("Frozen downstream qualification");
  await expect(replayEvidence.getByText("B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION", { exact: true })).toBeVisible();
  await expect(replayEvidence.getByText("118", { exact: true })).toHaveCount(2);
  await expect(replayEvidence.getByText("0", { exact: true })).toHaveCount(2);
  await expect(replayEvidence.getByText("NOT_IMPLEMENTED", { exact: true })).toBeVisible();

  const controlNames = ["Start", "Pause", "Resume", "Next snapshot", "Previous snapshot", "Stop", "Reset view"];
  for (const name of controlNames) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Start", exact: true })).toBeEnabled();

  const startResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/replay/start") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Start", exact: true }).click();
  const startResponse = await startResponsePromise;
  expect(startResponse.status()).toBe(200);
  const startProjection = (await startResponse.json()) as { session_id?: unknown };
  expect(typeof startProjection.session_id).toBe("string");
  expect(startProjection.session_id).not.toBe("");
  const serverSessionId = startProjection.session_id as string;
  await expect(page.getByText("Frame 1 of 469", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Resume", exact: true })).toBeEnabled();
  await expectNoAxeViolations(page);

  for (const width of [980, 600]) {
    await page.setViewportSize({ width, height: 1200 });
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
  }

  await page.getByRole("button", { name: "Reset view", exact: true }).click();
  await expect(page.getByText("Frame 1 of 469", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next snapshot", exact: true }).click();
  await expect(page.getByText("Frame 2 of 469", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Previous snapshot", exact: true }).click();
  await expect(page.getByText("Frame 1 of 469", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(page.getByRole("button", { name: "Resume", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Resume", exact: true }).click();

  await expect(page.getByText("Frame 469 of 469", { exact: true })).toBeVisible({ timeout: 35_000 });
  await expect(page.getByText("COMPLETED", { exact: true }).first()).toBeVisible();
  await expect(replayEvidence.getByText("B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION", { exact: true })).toBeVisible();
  await expect(replayEvidence.getByText("NOT_IMPLEMENTED", { exact: true })).toBeVisible();
  await expectNoAxeViolations(page);

  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText("IDLE", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("NO ACTIVE FRAME", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start", exact: true })).toBeEnabled();

  expect(replayPosts).toEqual([
    { path: "/api/v1/replay/start", body: { scenario_id: REPLAY_SCENARIO_ID } },
    { path: "/api/v1/replay/control", body: { scenario_id: REPLAY_SCENARIO_ID, session_id: serverSessionId, expected_control_version: 1, control: "RESET_VIEW" } },
    { path: "/api/v1/replay/control", body: { scenario_id: REPLAY_SCENARIO_ID, session_id: serverSessionId, expected_control_version: 2, control: "NEXT_SNAPSHOT" } },
    { path: "/api/v1/replay/control", body: { scenario_id: REPLAY_SCENARIO_ID, session_id: serverSessionId, expected_control_version: 3, control: "PREVIOUS_SNAPSHOT" } },
    { path: "/api/v1/replay/control", body: { scenario_id: REPLAY_SCENARIO_ID, session_id: serverSessionId, expected_control_version: 4, control: "RESUME" } },
    { path: "/api/v1/replay/control", body: { scenario_id: REPLAY_SCENARIO_ID, session_id: serverSessionId, expected_control_version: 5, control: "PAUSE" } },
    { path: "/api/v1/replay/control", body: { scenario_id: REPLAY_SCENARIO_ID, session_id: serverSessionId, expected_control_version: 6, control: "RESUME" } },
    { path: "/api/v1/replay/control", body: { scenario_id: REPLAY_SCENARIO_ID, session_id: serverSessionId, expected_control_version: 8, control: "STOP" } },
  ]);
  const sessionIds = replayPosts
    .filter((entry) => entry.path === "/api/v1/replay/control")
    .map((entry) => entry.body.session_id);
  expect(new Set(sessionIds).size).toBe(1);
});

for (const scenario of governedScenarios) {
  test(
    `real governance derives ${scenario.decision} for ${scenario.displayName}`,
    async ({ page }) => {
      await waitForApplication(page);

      const scenarioSelector = page.getByRole("combobox", {
        name: "Scenario",
      });

      if (scenario.displayName !== governedScenarios[0].displayName) {
        await scenarioSelector.click();

        await page
          .getByRole("option", {
            name: scenario.displayName,
          })
          .click();
      }

      const command = page.getByRole("textbox", {
        name: "Operator command",
      });

      await command.fill(scenario.command);
      await expect(command).toHaveValue(scenario.command);

      if (scenario.decision === "ACCEPT") {
        await expectNoAxeViolations(page);

        await expect(
          page.getByRole("status", {
            name: "Runtime status update",
          }),
        ).toHaveAttribute("aria-live", "polite");

        await command.focus();
        await page.keyboard.press("Tab");

        await expect(
          page.getByRole("button", {
            name: "Upload WAV recording",
          }),
        ).toBeFocused();
      }

      const responsePromise = page.waitForResponse(
        (response) =>
          response.url().endsWith("/api/v1/governance/typed") &&
          response.request().method() === "POST",
      );

      await page
        .getByRole("button", {
          name: "Submit",
        })
        .click();

      const response = await responsePromise;

      expect(response.status()).toBe(200);

      const body = await response.json();

      expect(
        body.canonical_result.governance_record.final_decision,
      ).toBe(scenario.decision);

      const authority = page.getByRole("list", {
        name: "Six-layer authority progression",
      });

      await expect(
        authority.getByRole("listitem"),
      ).toHaveCount(6);

      await expect(
        authorityRow(page, "GOVERNANCE_DECISION"),
      ).toContainText(scenario.decision);

      await expect(
        authorityRow(page, "EXECUTION_ELIGIBILITY"),
      ).toContainText(scenario.eligibility);

      const replayRow = authorityRow(
        page,
        "QUALIFICATION_REPLAY_ACCESS",
      );

      await expect(replayRow).toContainText("PROHIBITED");
      await expect(replayRow).not.toContainText("GRANTED");

      await expect(
        authorityRow(
          page,
          "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
        ),
      ).toContainText("NOT_IMPLEMENTED");

      if (scenario.decision === "ACCEPT") {
        await expectNoAxeViolations(page);

        for (const width of [980, 600]) {
          await page.setViewportSize({
            width,
            height: 1200,
          });

          await expect(authority).toBeVisible();

          const dimensions = await page.evaluate(() => ({
            clientWidth: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
          }));

          expect(
            dimensions.scrollWidth,
          ).toBeLessThanOrEqual(dimensions.clientWidth);
        }
      }
    },
  );
}
