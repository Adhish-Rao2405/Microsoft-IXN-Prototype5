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

const replayScenarioId = "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY";
const replaySessionId = "mocked-replay-session-s1";
const replayKeySnapshotIndices = [0, 78, 118, 119, 157, 311, 351, 352, 390, 468];

type MockedReplayFrameIndex = 0 | 1 | 468;

function replayFrame(frameIndex: MockedReplayFrameIndex) {
  switch (frameIndex) {
    case 0:
      return {
        frame_index: 0,
        semantic_snapshot_index: 0,
        route_configuration_index: 0,
        route_state: "HOME",
        phase: "SOURCE_SUPPORTED",
        boundary_snapshot: "NONE",
        is_key_snapshot: true,
      };
    case 1:
      return {
        frame_index: 1,
        semantic_snapshot_index: 1,
        route_configuration_index: 1,
        route_state: "INTERPOLATED",
        phase: "SOURCE_SUPPORTED",
        boundary_snapshot: "NONE",
        is_key_snapshot: false,
      };
    case 468:
      return {
        frame_index: 468,
        semantic_snapshot_index: 468,
        route_configuration_index: 466,
        route_state: "HOME",
        phase: "DESTINATION_SUPPORTED",
        boundary_snapshot: "NONE",
        is_key_snapshot: true,
      };
    default: {
      const unsupportedFrameIndex: never = frameIndex;
      throw new Error(`Unsupported mocked replay frame: ${unsupportedFrameIndex}`);
    }
  }
}

function replayState(overrides: Record<string, unknown> = {}) {
  return {
    contract_id: "PROTOTYPE5_D3_REPLAY_STATE_V1",
    contract_version: "1.0.0",
    scenario_id: replayScenarioId,
    binding_id: "FROZEN_B2_B3_2_EVIDENCE_V1",
    session_id: null,
    control_version: 0,
    projection_version: 0,
    lifecycle_state: "IDLE",
    command_in_flight: false,
    current_frame: null,
    frame_count: 469,
    key_snapshot_indices: replayKeySnapshotIndices,
    allowed_controls: [
      "START",
      "PAUSE",
      "RESUME",
      "NEXT_SNAPSHOT",
      "PREVIOUS_SNAPSHOT",
      "STOP",
      "RESET_VIEW",
    ],
    available_controls: ["START"],
    presentation_cadence_ms: 50,
    b2_sha256: "a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554",
    b3_2_sha256: "11c8b83f8c4d0545c9a8df604046a335acb00121a51bf6e1d5b39504991c1798",
    qualification: {
      overall_result: "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION",
      scientific_failure_count: 118,
      forbidden_contact_failure_count: 0,
      support_material_penetration_failure_count: 118,
      required_support_missing_failure_count: 0,
      failure_codes_present: ["B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"],
      recorded_failure_example: {
        semantic_snapshot_index: 352,
        route_state: "DESTINATION_PLACE",
        phase: "RELEASE_BOUNDARY",
        boundary_snapshot: "POST",
        pair_index: 78,
        signed_distance_m: -9.290505685985613e-7,
        decision: "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION",
      },
    },
    presentation_labels: [
      "EVIDENCE REPLAY",
      "NOT PHYSICAL EXECUTION",
      "DISCRETE SAMPLED STATES — NO DYNAMIC TIMING",
    ],
    physical_execution_authority: "NOT_IMPLEMENTED",
    last_error_code: null,
    updated_at_utc: "2026-08-14T12:00:00Z",
    ...overrides,
  };
}

function activeReplayState({
  lifecycle,
  frameIndex,
  controlVersion,
  projectionVersion = controlVersion,
}: {
  lifecycle: "PAUSED" | "PLAYING" | "COMPLETED";
  frameIndex: MockedReplayFrameIndex;
  controlVersion: number;
  projectionVersion?: number;
}) {
  const availableControls = lifecycle === "PLAYING"
    ? ["PAUSE", "STOP", "RESET_VIEW"]
    : lifecycle === "COMPLETED"
      ? ["PREVIOUS_SNAPSHOT", "STOP", "RESET_VIEW"]
      : [
          "RESUME",
          "NEXT_SNAPSHOT",
          ...(frameIndex > 0 ? ["PREVIOUS_SNAPSHOT"] : []),
          "STOP",
          "RESET_VIEW",
        ];
  return replayState({
    session_id: replaySessionId,
    control_version: controlVersion,
    projection_version: projectionVersion,
    lifecycle_state: lifecycle,
    current_frame: replayFrame(frameIndex),
    available_controls: availableControls,
    updated_at_utc: `2026-08-14T12:00:${String(controlVersion).padStart(2, "0")}Z`,
  });
}

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
  await page.route("**/api/v1/replay/state", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(replayState()) }),
  );
});

test("typed command renders a complete governance trace", async ({ page }, testInfo) => {
  const prematureReplayRequests: string[] = [];
  const forbiddenRuntimeRequests: string[] = [];
  let replayScenarioSelected = false;
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/replay/") && !replayScenarioSelected) {
      prematureReplayRequests.push(request.url());
    }
    if (/\/simulation\/|\/pybullet\//i.test(request.url())) {
      forbiddenRuntimeRequests.push(request.url());
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
  ).toContainText("PROHIBITED");
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

  expect(prematureReplayRequests).toEqual([]);
  replayScenarioSelected = true;
  const replayStateResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/replay/state"),
  );
  await scenarioSelector.click();
  await page
    .getByRole("option", { name: "Frozen B2 pick/place evidence replay" })
    .click();
  expect((await replayStateResponse).status()).toBe(200);
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
  for (const name of ["Start", "Pause", "Resume", "Next snapshot", "Previous snapshot", "Stop", "Reset view"]) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Start", exact: true })).toBeEnabled();
  expect(forbiddenRuntimeRequests).toEqual([]);
});

test("registered replay uses server state and bounded CAS controls", async ({ page }) => {
  await page.unroute("**/api/v1/replay/state");
  let projection = replayState();
  let completeOnNextRead = false;
  const postBodies: Array<{ path: string; body: Record<string, unknown> }> = [];

  await page.route("**/api/v1/replay/state", (route) => {
    if (completeOnNextRead) {
      projection = activeReplayState({
        lifecycle: "COMPLETED",
        frameIndex: 468,
        controlVersion: 8,
      });
      completeOnNextRead = false;
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(projection),
    });
  });
  await page.route("**/api/v1/replay/start", (route) => {
    postBodies.push({
      path: "/api/v1/replay/start",
      body: route.request().postDataJSON() as Record<string, unknown>,
    });
    projection = activeReplayState({ lifecycle: "PAUSED", frameIndex: 0, controlVersion: 1 });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(projection) });
  });
  await page.route("**/api/v1/replay/control", (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    postBodies.push({ path: "/api/v1/replay/control", body });
    switch (body.control) {
      case "RESET_VIEW":
        projection = activeReplayState({ lifecycle: "PAUSED", frameIndex: 0, controlVersion: 2 });
        break;
      case "NEXT_SNAPSHOT":
        projection = activeReplayState({ lifecycle: "PAUSED", frameIndex: 1, controlVersion: 3 });
        break;
      case "PREVIOUS_SNAPSHOT":
        projection = activeReplayState({ lifecycle: "PAUSED", frameIndex: 0, controlVersion: 4 });
        break;
      case "RESUME": {
        const nextVersion = (projection as { control_version: number }).control_version + 1;
        projection = activeReplayState({ lifecycle: "PLAYING", frameIndex: 0, controlVersion: nextVersion });
        completeOnNextRead = nextVersion === 7;
        break;
      }
      case "PAUSE":
        projection = activeReplayState({ lifecycle: "PAUSED", frameIndex: 0, controlVersion: 6 });
        break;
      case "STOP":
        projection = replayState();
        break;
      default:
        throw new Error(`Unexpected mocked replay control: ${String(body.control)}`);
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(projection) });
  });

  await page.goto("/");
  const scenarioSelector = page.getByRole("combobox", { name: "Scenario" });
  await scenarioSelector.click();
  await page.getByRole("option", { name: "Frozen B2 pick/place evidence replay" }).click();

  const controlNames = ["Start", "Pause", "Resume", "Next snapshot", "Previous snapshot", "Stop", "Reset view"];
  for (const name of controlNames) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Start", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeDisabled();
  await expect(page.getByRole("heading", { name: "EVIDENCE REPLAY" })).toBeVisible();
  await expect(page.getByText("NOT PHYSICAL EXECUTION", { exact: true })).toBeVisible();
  await expect(page.getByText("DISCRETE SAMPLED STATES — NO DYNAMIC TIMING", { exact: true })).toBeVisible();
  const replayEvidence = page.getByLabel("Frozen downstream qualification");
  await expect(replayEvidence.getByText("B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION", { exact: true })).toBeVisible();
  await expect(replayEvidence.getByText("118", { exact: true })).toHaveCount(2);
  await expect(replayEvidence.getByText("0", { exact: true })).toHaveCount(2);
  await expect(replayEvidence.getByText("NOT_IMPLEMENTED", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByText("Frame 1 of 469", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Resume", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Previous snapshot", exact: true })).toBeDisabled();

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
  await expect(page.getByText("Frame 469 of 469", { exact: true })).toBeVisible();
  await expect(replayEvidence.getByText("B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION", { exact: true })).toBeVisible();
  await expect(replayEvidence.getByText("NOT_IMPLEMENTED", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByRole("button", { name: "Start", exact: true })).toBeEnabled();

  expect(postBodies).toEqual([
    { path: "/api/v1/replay/start", body: { scenario_id: replayScenarioId } },
    { path: "/api/v1/replay/control", body: { scenario_id: replayScenarioId, session_id: replaySessionId, expected_control_version: 1, control: "RESET_VIEW" } },
    { path: "/api/v1/replay/control", body: { scenario_id: replayScenarioId, session_id: replaySessionId, expected_control_version: 2, control: "NEXT_SNAPSHOT" } },
    { path: "/api/v1/replay/control", body: { scenario_id: replayScenarioId, session_id: replaySessionId, expected_control_version: 3, control: "PREVIOUS_SNAPSHOT" } },
    { path: "/api/v1/replay/control", body: { scenario_id: replayScenarioId, session_id: replaySessionId, expected_control_version: 4, control: "RESUME" } },
    { path: "/api/v1/replay/control", body: { scenario_id: replayScenarioId, session_id: replaySessionId, expected_control_version: 5, control: "PAUSE" } },
    { path: "/api/v1/replay/control", body: { scenario_id: replayScenarioId, session_id: replaySessionId, expected_control_version: 6, control: "RESUME" } },
    { path: "/api/v1/replay/control", body: { scenario_id: replayScenarioId, session_id: replaySessionId, expected_control_version: 8, control: "STOP" } },
  ]);
});

test("fatal replay exhaustion remains latched across scenario changes", async ({ page }) => {
  await page.unroute("**/api/v1/replay/state");
  const replayRequests: string[] = [];
  let fatalSettled = false;
  const replayRequestsAfterFatal: string[] = [];
  page.on("request", (request) => {
    if (!request.url().includes("/api/v1/replay/")) return;
    replayRequests.push(request.url());
    if (fatalSettled) replayRequestsAfterFatal.push(request.url());
  });
  await page.route("**/api/v1/replay/state", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(replayState()) }),
  );
  await page.route("**/api/v1/replay/start", (route) => {
    fatalSettled = true;
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ code: "REPLAY_VERSION_EXHAUSTED" }),
    });
  });
  await page.route("**/api/v1/replay/control", (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ code: "UNEXPECTED_CONTROL" }) }),
  );

  await page.goto("/");
  const scenarioSelector = page.getByRole("combobox", { name: "Scenario" });
  await scenarioSelector.click();
  await page.getByRole("option", { name: "Frozen B2 pick/place evidence replay" }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Replay restart required");
  await expect(page.getByRole("alert")).toContainText("REPLAY_VERSION_EXHAUSTED");
  for (const name of ["Start", "Pause", "Resume", "Next snapshot", "Previous snapshot", "Stop", "Reset view"]) {
    await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
  }

  const requestCountAtFatal = replayRequests.length;
  await scenarioSelector.click();
  await page.getByRole("option", { name: "Manufacturing scenario 1" }).click();
  await scenarioSelector.click();
  await page.getByRole("option", { name: "Frozen B2 pick/place evidence replay" }).click();
  await expect(page.getByRole("alert")).toContainText("Replay restart required");
  await expect(page.getByRole("alert")).toContainText("REPLAY_VERSION_EXHAUSTED");
  await expect(page.getByRole("heading", { name: "EVIDENCE REPLAY" })).toBeVisible();
  await page.waitForTimeout(650);
  expect(replayRequests.length).toBe(requestCountAtFatal);
  expect(replayRequestsAfterFatal).toEqual([]);
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
