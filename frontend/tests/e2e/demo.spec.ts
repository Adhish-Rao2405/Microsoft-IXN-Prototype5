import { expect, test } from "@playwright/test";
import { Buffer } from "node:buffer";

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

const manifest = {
  contract_id: "PROTOTYPE5_FINAL_DEMONSTRATOR_D0",
  contract_version: "1.0.0",
  authority_taxonomy: [
    "UNTRUSTED_PROPOSAL",
    "GOVERNANCE_DECISION",
    "EXECUTION_ELIGIBILITY",
    "QUALIFICATION_REPLAY_ACCESS",
    "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
    "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
  ],
  physical_execution_authority_state: "NOT_IMPLEMENTED",
  healthcare_scope: "OUT_OF_SCOPE_FOR_FINAL_DEMO",
  d2_replay_enabled: false,
  scenarios: Array.from({ length: 10 }, (_, index) => {
    const identifiers = [
      "MANUFACTURING_TYPED_ACCEPT",
      "MANUFACTURING_UNSAFE_REJECT",
      "MANUFACTURING_AMBIGUOUS_CLARIFY",
      "MANUFACTURING_SCHEMA_VALID_INELIGIBLE",
      "MANUFACTURING_OBSERVER_ROLE_REJECT",
      "MODE_E_CONVEYOR_GOVERNANCE",
      "MODE_E_WAREHOUSE_GOVERNANCE",
      "MODE_E_HUMAN_PROXIMITY_GOVERNANCE",
      "MODE_E_RESTRICTED_ZONE_GOVERNANCE",
      "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    ];
    const live = index < 5;
    const replay = index === 9;
    return {
      scenario_id: identifiers[index],
      display_name: replay
        ? "Frozen B2 pick/place evidence replay"
        : `Manufacturing scenario ${index + 1}`,
      presentation_classification: replay
        ? "FROZEN_EVIDENCE_REPLAY"
        : live
          ? "SYNTHETIC_LIVE_DEMO"
          : "FROZEN_RESEARCH_EVIDENCE",
      model_input_enabled: live,
      allowed_inference_modes: live ? ["LOCAL", "CLOUD", "AUTO"] : [],
      registered_command:
        "Move the blue component from input tray A to assembly fixture B.",
      demonstration_purpose: "Demonstrate the frozen governance boundary.",
      evidence_classification: replay
        ? "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION"
        : live
          ? "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE"
          : "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT",
      replay_capability_classification: replay
        ? "FROZEN_B2_REPLAY_COMPATIBLE"
        : "GOVERNANCE_ONLY",
      qualification_replay_access: replay
        ? "SERVER_REGISTERED_ONLY"
        : "PROHIBITED",
      downstream_geometric_qualification: replay ? "FAIL" : "NOT_APPLICABLE",
      claim_boundary_note: "No physical execution authority.",
    };
  }),
};

const rawMoveResponse =
  '{"actions":[{"action":"MOVE","object_id":"blue_component",' +
  '"source_id":"input_tray_a","destination_id":"assembly_fixture_b",' +
  '"duration_ms":null}]}';

function accepted(inputMode: "TYPED" | "VOICE") {
  const voice = inputMode === "VOICE";
  const command = "Move the blue component.";
  const transcriptionId = voice ? "transcription-e2e-001" : null;
  const transcript = voice ? command : null;
  const transcriptStatus = voice ? "READY" : "NOT_APPLICABLE";
  const transcriptBackend = voice ? "foundry_nemotron" : null;
  const audioSha256 = voice ? "b".repeat(64) : null;
  const gates = [
    "PARSE",
    "JSON",
    "SCHEMA",
    "SEMANTICS",
    "AMBIGUITY",
    "SAFETY",
    "AUTHORITY",
  ];

  return {
    routing_policy_id: "prototype5_hybrid_routing_policy_v1",
    routing_policy_version: "1.0.0",
    routing_policy_sha256: "d".repeat(64),
    local_health: {
      ...status.local_health,
      rolling_sample_count: 1,
      rolling_structured_success_rate: 1,
      rolling_p50_latency_ms: 12,
      rolling_p95_latency_ms: 12,
    },
    canonical_result: {
      request: {
        input_mode: inputMode,
        typed_text: voice ? null : command,
        transcription_id: transcriptionId,
        original_transcript_text: transcript,
        transcript_text: transcript,
        transcript_status: transcriptStatus,
        transcript_backend: transcriptBackend,
        transcript_confidence: null,
        audio_sha256: audioSha256,
        domain_id: "MANUFACTURING",
        scene: {
          scene_id: "manufacturing_demo_scene",
          state_version: "1.0.0",
          objects: [
            { object_id: "blue_component", location_id: "input_tray_a" },
          ],
          human_obstruction: false,
          safety_interlock_enabled: true,
        },
        requester: { requester_id: "synthetic_operator_e2e", role: "operator" },
        requested_inference_mode: "AUTO",
        evaluation_mode: "LIVE",
        benchmark_id: null,
        benchmark_sha256: null,
        oracle_version: null,
        oracle_sha256: null,
        expected_decision: null,
      },
      raw_response_text: rawMoveResponse,
      proposal: {
        actions: [
          {
            action: "MOVE",
            object_id: "blue_component",
            source_id: "input_tray_a",
            destination_id: "assembly_fixture_b",
            duration_ms: null,
          },
        ],
      },
      governance_record: {
        record_id: "record-e2e-001",
        trace_id: "trace-e2e-001",
        timestamp_utc: "2026-07-30T12:00:00+00:00",
        evaluation_mode: "LIVE",
        input_mode: inputMode,
        normalised_command: command,
        typed_text: voice ? null : command,
        transcription_id: transcriptionId,
        original_transcript_text: transcript,
        transcript_text: transcript,
        transcript_status: transcriptStatus,
        transcript_backend: transcriptBackend,
        transcript_confidence: null,
        audio_sha256: audioSha256,
        domain_id: "MANUFACTURING",
        benchmark_id: null,
        policy_id: "prototype5_manufacturing_policy_v2@2.0.0",
        oracle_version: null,
        evidence_schema_version: "2.0.0",
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
        raw_response_sha256:
          "7cfabaee94153f7cbc5176cc888666da70968290fe7f240cc5ff5b1597df501a",
        raw_response_present: true,
        provider_latency_ms: 12,
        parse_status: "PASSED",
        json_status: "PASSED",
        schema_status: "PASSED",
        plan_semantic_status: "VALID",
        ambiguity_status: "PASSED",
        safety_status: "PASSED",
        authority_status: "PASSED",
        gate_reasons: gates.map((gate) => ({
          gate,
          reason_codes: [`${gate}_PASSED`],
        })),
        gate_latencies: gates.map((gate) => ({ gate, latency_ms: 0.1 })),
        expected_decision: null,
        decision_correctness_status: "NOT_EVALUATED",
        final_decision: "ACCEPT",
        execution_eligible: true,
        decision_reason_codes: ["ALL_REQUIRED_GATES_PASSED"],
        validation_latency_ms: 2,
        total_pipeline_latency_ms: 14,
        execution_permit_id: null,
        simulation_status: "NOT_REQUESTED",
        provenance: {
          source_repository: "repository",
          software_commit: "a".repeat(40),
          prompt_id: "prompt",
          prompt_version: "2.0.0",
          model_provider: "FOUNDRY_LOCAL",
          model_id: "local-test-model",
          benchmark_sha256: null,
          oracle_sha256: null,
          policy_sha256: "f".repeat(64),
        },
      },
    },
  };
}

const transcription = {
  result_schema_version: "1.0.0",
  transcription_id: "transcription-e2e-001",
  timestamp_utc: "2026-07-31T12:00:00Z",
  transcript_status: "READY",
  transcript_text: "Move the blue component.",
  transcript_backend: "foundry_nemotron",
  transcript_confidence: null,
  audio: {
    original_filename: "operator.wav",
    audio_sha256: "b".repeat(64),
    audio_bytes: 32044,
    sample_rate_hz: 16000,
    channels: 1,
    bits_per_sample: 16,
    frame_count: 16000,
    duration_ms: 1000,
  },
  requested_model_alias: "nemotron-speech-streaming-en-0.6b",
  resolved_model_id: "nemotron-speech-streaming-en-0.6b-generic-cpu:3",
  execution_provider: "CPUExecutionProvider",
  sdk_distribution: "foundry-local-sdk-winml",
  sdk_version: "1.2.3",
  core_distribution: "foundry-local-core-winml",
  core_version: "1.2.3",
  model_cached_before: true,
  model_loaded_before: false,
  model_downloaded_for_request: false,
  model_loaded_for_request: true,
  model_unloaded_after_request: true,
  segment_count: 1,
  transcription_latency_ms: 860,
  error_code: null,
  error_detail: null,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/demo/manifest", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(manifest) }),
  );
  await page.route("**/api/v1/status", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(status) }),
  );
  await page.route("**/api/v1/governance/typed", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(accepted("TYPED")) }),
  );
  await page.route("**/api/v1/speech/recorded", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(transcription) }),
  );
  await page.route("**/api/v1/governance/voice", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(accepted("VOICE")) }),
  );
});

test("typed command renders a complete governance trace", async ({ page }, testInfo) => {
  const forbiddenCapabilityRequests: string[] = [];
  page.on("request", (request) => {
    if (/replay|simulation|pybullet/i.test(request.url())) {
      forbiddenCapabilityRequests.push(request.url());
    }
  });
  const manifestResponsePromise = page.waitForResponse(
    (response) => response.url().includes("/api/v1/demo/manifest"),
  );
  await page.goto("/");
  const manifestResponse = await manifestResponsePromise;
  expect(manifestResponse.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Zero-Trust Governance Demonstrator" }),
  ).toBeVisible();
  await expect(
    page.getByText("SYSTEM CAPABILITY / STATUS — NOT EXPERIMENTAL EVIDENCE"),
  ).toBeVisible();
  await expect(
    page.getByText("LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE"),
  ).toHaveCount(2);

  const authority = page.getByRole("list", {
    name: "Six-layer authority progression",
  });
  await expect(authority.getByRole("listitem")).toHaveCount(6);

  const scenarioSelector = page.getByRole("combobox", { name: "Scenario" });
  const command = page.getByRole("textbox", { name: "Operator command" });
  await scenarioSelector.focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("radio", { name: "Auto" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(command).toBeFocused();
  await expect(command).toBeEnabled();
  await command.fill(
    "Move the blue component from input tray A to assembly fixture B.",
  );
  const typedRequestPromise = page.waitForRequest("**/api/v1/governance/typed");
  await page.getByRole("button", { name: "Submit" }).click();
  const typedBody = (await typedRequestPromise).postDataJSON();
  expect(typedBody.scenario_id).toBe("MANUFACTURING_TYPED_ACCEPT");
  expect(typedBody).not.toHaveProperty("domain_id");
  expect(typedBody).not.toHaveProperty("requester_role");
  expect(typedBody).not.toHaveProperty("human_obstruction");
  expect(typedBody).not.toHaveProperty("safety_interlock_enabled");

  await expect(page.getByText("Untrusted model proposal")).toBeVisible();
  await expect(page.getByText("UNTRUSTED PROPOSAL — NO AUTHORITY")).toBeVisible();
  await expect(page.getByText("Schema: PASSED")).toBeVisible();
  await expect(
    authority.locator('[data-authority-state="GOVERNANCE_DECISION"]'),
  ).toContainText("ACCEPT");
  await expect(
    authority.locator('[data-authority-state="EXECUTION_ELIGIBILITY"]'),
  ).toContainText("ELIGIBLE");
  await expect(
    authority.locator('[data-authority-state="QUALIFICATION_REPLAY_ACCESS"]'),
  ).toContainText("NOT REQUESTED — NOT ENABLED IN D2");
  await expect(
    authority.locator(
      '[data-authority-state="PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED"]',
    ),
  ).toContainText("NOT_IMPLEMENTED");
  await expect(page.getByText("trace-e2e-001")).toBeVisible();
  await expect(page.getByText("2026-07-30T12:00:00+00:00")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Download live demo trace" }),
  ).toBeEnabled();
  await expect(page.getByRole("button", { name: "Stop simulation" })).toHaveCount(0);

  await page.screenshot({
    path: testInfo.outputPath("governance-trace.png"),
    fullPage: true,
  });

  await scenarioSelector.click();
  await page
    .getByRole("option", { name: "Frozen B2 pick/place evidence replay" })
    .click();
  await expect(page.getByText("FROZEN EVIDENCE REPLAY")).toBeVisible();
  await expect(
    page.getByText("FROZEN RESEARCH EVIDENCE — EXACT REGISTERED ARTIFACT"),
  ).toBeVisible();
  await expect(
    page.getByText("NOT APPLICABLE — FROZEN REGISTERED EVIDENCE"),
  ).toBeVisible();
  await expect(
    authority.locator('[data-authority-state="QUALIFICATION_REPLAY_ACCESS"]'),
  ).toContainText("Policy: SERVER_REGISTERED_ONLY");
  await expect(
    authority.locator('[data-authority-state="QUALIFICATION_REPLAY_ACCESS"]'),
  ).not.toContainText("GRANTED");
  await expect(
    authority.locator('[data-authority-state="DOWNSTREAM_GEOMETRIC_QUALIFICATION"]'),
  ).toContainText("FAIL");
  await expect(
    authority.locator('[data-authority-state="GOVERNANCE_DECISION"]'),
  ).toContainText("NOT REQUESTED");
  await expect(page.getByRole("radiogroup", { name: "Inference mode" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /replay/i })).toHaveCount(0);
  expect(forbiddenCapabilityRequests).toEqual([]);
});

test("recorded transcript is reviewable before voice governance", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByLabel("Recorded WAV file").setInputFiles({
    name: "operator.wav",
    mimeType: "audio/wav",
    buffer: Buffer.from([1, 2, 3]),
  });

  await expect(page.getByText("Nemotron transcript")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Operator command" })).toHaveValue(
    "Move the blue component.",
  );
  const voiceRequestPromise = page.waitForRequest("**/api/v1/governance/voice");
  await page.getByRole("button", { name: "Submit" }).click();
  const voiceBody = (await voiceRequestPromise).postDataJSON();
  expect(voiceBody.scenario_id).toBe("MANUFACTURING_TYPED_ACCEPT");
  expect(voiceBody).not.toHaveProperty("domain_id");
  expect(voiceBody).not.toHaveProperty("requester_role");
  expect(voiceBody).not.toHaveProperty("human_obstruction");
  expect(voiceBody).not.toHaveProperty("safety_interlock_enabled");

  await expect(page.getByText("Reviewed voice transcript")).toBeVisible();
  await expect(page.getByText("Submitted")).toBeVisible();
  await expect(
    page
      .getByRole("list", { name: "Six-layer authority progression" })
      .locator('[data-authority-state="GOVERNANCE_DECISION"]'),
  ).toContainText("ACCEPT");
  await page.screenshot({
    path: testInfo.outputPath("recorded-voice-governance.png"),
    fullPage: true,
  });
});
