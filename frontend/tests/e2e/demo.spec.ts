import { expect, test } from "@playwright/test";

const status = {
  service_status: "READY",
  frozen_baseline_tag: "prototype5-governance-reproducibility-complete",
  frozen_baseline_commit: "7".repeat(40),
  software_commit: "a".repeat(40),
  evidence_schema_version: "2.0.0",
  supported_domains: ["MANUFACTURING"],
  supported_inference_modes: ["LOCAL", "CLOUD", "AUTO"],
  local_status: "AVAILABLE",
  cloud_status: "AVAILABLE",
  speech_status: "NOT_ASSESSED",
  simulator_status: "NOT_ASSESSED",
  local_health: {
    circuit_state: "CLOSED",
    local_available: true,
    local_model_ready: true,
    consecutive_failures: 0,
    rolling_sample_count: 0,
    rolling_structured_success_rate: null,
    rolling_p50_latency_ms: null,
    rolling_p95_latency_ms: null,
    last_failure_reason: "NONE",
    last_circuit_transition: null,
  },
};

const accepted = {
  routing_policy_id: "prototype5_hybrid_routing_policy_v1",
  routing_policy_version: "1.0.0",
  routing_policy_sha256: "d".repeat(64),
  local_health: { ...status.local_health, rolling_sample_count: 1 },
  canonical_result: {
    raw_response_text: '{"actions":[{"action":"MOVE"}]}',
    proposal: {
      actions: [
        {
          action: "MOVE",
          object_id: "blue_component",
          source_id: "input_tray_a",
          destination_id: "assembly_fixture_b",
        },
      ],
    },
    governance_record: {
      trace_id: "trace-e2e-001",
      timestamp_utc: "2026-07-30T12:00:00+00:00",
      normalised_command: "Move the blue component.",
      policy_id: "prototype5_manufacturing_policy_v2@2.0.0",
      evidence_schema_version: "2.0.0",
      parse_status: "PASSED",
      json_status: "PASSED",
      schema_status: "PASSED",
      plan_semantic_status: "VALID",
      ambiguity_status: "PASSED",
      safety_status: "PASSED",
      authority_status: "PASSED",
      final_decision: "ACCEPT",
      execution_eligible: true,
      decision_reason_codes: ["ALL_REQUIRED_GATES_PASSED"],
      provider_latency_ms: 12,
      validation_latency_ms: 2,
      total_pipeline_latency_ms: 14,
      execution_permit_id: null,
      simulation_status: "NOT_REQUESTED",
      routing: {
        requested_mode: "AUTO",
        selected_provider: "FOUNDRY_LOCAL",
        selected_model: "local-test-model",
        local_attempted: true,
        cloud_attempted: false,
        fallback_triggered: false,
        fallback_reason: "NONE",
        local_latency_ms: 12,
        cloud_latency_ms: null,
      },
    },
  },
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/status", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(status) }),
  );
  await page.route("**/api/v1/governance/typed", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(accepted) }),
  );
});

test("typed command renders a complete governance trace", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Operator command" }).fill(
    "Move the blue component from input tray A to assembly fixture B.",
  );
  await page.getByRole("button", { name: "Submit" }).click();

  await expect(page.getByText("Governance decision")).toBeVisible();
  await expect(page.getByText("Structured proposal")).toBeVisible();
  await expect(page.getByText("Execution eligibility")).toBeVisible();
  await expect(page.getByText("trace-e2e-001")).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop simulation" })).toBeDisabled();

  await page.screenshot({
    path: testInfo.outputPath("governance-trace.png"),
    fullPage: true,
  });
});
