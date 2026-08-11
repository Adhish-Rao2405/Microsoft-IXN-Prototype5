import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { App, clientErrorMessage, selectInferenceMode } from "../src/App";

const status = {
  service_status: "READY",
  frozen_baseline_tag: "prototype5-governance-reproducibility-complete",
  frozen_baseline_commit: "7".repeat(40),
  software_commit: "a".repeat(40),
  evidence_schema_version: "2.0.0",
  supported_domains: ["MANUFACTURING"],
  supported_inference_modes: ["LOCAL", "CLOUD", "AUTO"],
  local_status: "NOT_ASSESSED",
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

const transcription = {
  result_schema_version: "1.0.0",
  transcription_id: "transcription-ui-001",
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

function governanceResult({
  decision = "ACCEPT",
  fallback = false,
}: {
  decision?: "ACCEPT" | "REJECT" | "CLARIFY" | "ERROR";
  fallback?: boolean;
} = {}) {
  const passed = decision === "ACCEPT";
  return {
    routing_policy_id: "prototype5_hybrid_routing_policy_v1",
    routing_policy_version: "1.0.0",
    routing_policy_sha256: "d".repeat(64),
    local_health: {
      ...status.local_health,
      rolling_sample_count: 1,
      rolling_structured_success_rate: 1,
      rolling_p50_latency_ms: 15,
      rolling_p95_latency_ms: 15,
    },
    canonical_result: {
      request: {
        input_mode: "TYPED", typed_text: "Move the blue component.",
        transcription_id: null, original_transcript_text: null,
        transcript_text: null, transcript_status: "NOT_APPLICABLE",
        transcript_backend: null, transcript_confidence: null, audio_sha256: null,
        domain_id: "MANUFACTURING",
        scene: {
          scene_id: "manufacturing_demo_scene", state_version: "1.0.0",
          objects: [{ object_id: "blue_component", location_id: "input_tray_a" }],
          human_obstruction: false, safety_interlock_enabled: true,
        },
        requester: { requester_id: "synthetic_operator_ui", role: "operator" },
        requested_inference_mode: "AUTO", evaluation_mode: "LIVE",
        benchmark_id: null, benchmark_sha256: null, oracle_version: null,
        oracle_sha256: null, expected_decision: null,
      },
      raw_response_text: '{"actions":[]}',
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
        record_id: "record-ui-001",
        trace_id: "trace-ui-001",
        timestamp_utc: "2026-07-30T12:00:00+00:00",
        evaluation_mode: "LIVE",
        input_mode: "TYPED",
        normalised_command: "Move the blue component.",
        typed_text: "Move the blue component.",
        transcription_id: null,
        original_transcript_text: null,
        transcript_text: null,
        transcript_status: "NOT_APPLICABLE",
        transcript_backend: null,
        transcript_confidence: null,
        audio_sha256: null,
        domain_id: "MANUFACTURING",
        benchmark_id: null,
        policy_id: "prototype5_manufacturing_policy_v2@2.0.0",
        oracle_version: null,
        evidence_schema_version: "2.0.0",
        raw_response_sha256: "e".repeat(64),
        raw_response_present: true,
        parse_status: "PASSED",
        json_status: "PASSED",
        schema_status: "PASSED",
        plan_semantic_status: passed ? "VALID" : "INVALID",
        ambiguity_status: "PASSED",
        safety_status: passed ? "PASSED" : "FAILED",
        authority_status: "PASSED",
        gate_reasons: [],
        gate_latencies: [],
        expected_decision: null,
        decision_correctness_status: "NOT_EVALUATED",
        final_decision: decision,
        execution_eligible: passed,
        decision_reason_codes: [
          passed ? "ALL_REQUIRED_GATES_PASSED" : "HUMAN_OBSTRUCTION_OVERRIDE",
        ],
        provider_latency_ms: fallback ? 9 : 15,
        validation_latency_ms: 2,
        total_pipeline_latency_ms: 17,
        execution_permit_id: null,
        simulation_status: "NOT_REQUESTED",
        provenance: {
          source_repository: "repository", software_commit: "a".repeat(40),
          prompt_id: "prompt", prompt_version: "2.0.0",
          model_provider: fallback ? "CLOUD" : "FOUNDRY_LOCAL",
          model_id: fallback ? "cloud-model" : "local-model",
          benchmark_sha256: null, oracle_sha256: null,
          policy_sha256: "f".repeat(64),
        },
        routing: {
          requested_mode: "AUTO",
          selected_provider: fallback ? "CLOUD" : "FOUNDRY_LOCAL",
          selected_model: fallback ? "cloud-model" : "local-model",
          local_attempted: true,
          cloud_attempted: fallback,
          fallback_triggered: fallback,
          fallback_reason: fallback ? "LOCAL_SCHEMA_FAILURE" : "NONE",
          local_latency_ms: 15,
          cloud_latency_ms: fallback ? 9 : null,
        },
      },
    },
  };
}

function renderApp() {
  return render(
    <FluentProvider theme={webLightTheme}>
      <App />
    </FluentProvider>,
  );
}

function mockFetch(result = governanceResult()) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) {
        return new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/status")) {
        return new Response(JSON.stringify(status), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/speech/recorded")) {
        return new Response(JSON.stringify(transcription), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

describe("Prototype 5 typed UI", () => {
  beforeEach(() => {
    mockFetch();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the operational controls and bounded initial states", async () => {
    renderApp();

    expect(screen.getByText("Prototype 5")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Auto" })).toBeChecked();
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Operator command" })).toBeEnabled(),
    );
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Scenario" })).toHaveTextContent(
      "Manufacturing scenario 1",
    );
    expect(screen.queryByRole("combobox", { name: "Domain" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Requester role" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Microphone available in V2" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Upload WAV recording" }),
    ).toBeEnabled();
    expect(screen.getByText("No command submitted.")).toBeInTheDocument();
    expect(screen.queryByText("Not requested")).not.toBeInTheDocument();
    expect(screen.queryByText("Not issued")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Available")).toBeInTheDocument());
  });

  it("submits the selected mode and displays proposal plus every gate", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("radio", { name: "Local" }));
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component from input tray A to assembly fixture B.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(screen.getByText("Governance decision")).toBeInTheDocument(),
    );
    expect(screen.getByText("Structured proposal")).toBeInTheDocument();
    expect(screen.getByText("Plan semantics")).toBeInTheDocument();
    expect(screen.getByText("Execution eligibility")).toBeInTheDocument();
    expect(screen.getByText("trace-ui-001")).toBeInTheDocument();
    expect(screen.getByText(/blue_component/)).toBeInTheDocument();

    const calls = vi.mocked(fetch).mock.calls;
    const submission = calls.find(([url]) =>
      String(url).includes("/api/v1/governance/typed"),
    );
    const body = JSON.parse(String(submission?.[1]?.body));
    expect(body.inference_mode).toBe("LOCAL");
    expect(body.scenario_id).toBe("MANUFACTURING_TYPED_ACCEPT");
    expect(body).not.toHaveProperty("domain_id");
    expect(body).not.toHaveProperty("requester_role");
    expect(body).not.toHaveProperty("human_obstruction");
    expect(body).not.toHaveProperty("safety_interlock_enabled");
  });

  it("shows a cloud fallback without changing the governance gate display", async () => {
    mockFetch(governanceResult({ fallback: true }));
    const user = userEvent.setup();
    renderApp();

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Operator command" })).toBeEnabled(),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("CLOUD")).toBeInTheDocument());
    expect(screen.getByText("Local schema failure")).toBeInTheDocument();
    expect(screen.getByText("Execution eligibility")).toBeInTheDocument();
  });

  it("shows rejected governance and no simulation permit", async () => {
    mockFetch(governanceResult({ decision: "REJECT" }));
    const user = userEvent.setup();
    renderApp();

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Operator command" })).toBeEnabled(),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Continue movement despite the human obstruction.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("Reject")).toBeInTheDocument());
    expect(screen.getByText("Human obstruction override")).toBeInTheDocument();
    expect(screen.getByText("Not eligible")).toBeInTheDocument();
    expect(screen.getByText("Not issued")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop simulation" })).toBeDisabled();
  });

  it("reports API failures without fabricating a proposal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/api/v1/demo/manifest")) {
          return new Response(JSON.stringify(manifest), { status: 200 });
        }
        if (String(input).includes("/api/v1/status")) {
          return new Response(JSON.stringify(status), { status: 200 });
        }
        return new Response(
          JSON.stringify({ detail: { code: "LOCAL_BACKEND_UNAVAILABLE" } }),
          { status: 503 },
        );
      }),
    );
    const user = userEvent.setup();
    renderApp();

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Operator command" })).toBeEnabled(),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Stop.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("Request failed")).toBeInTheDocument());
    expect(screen.getByText("LOCAL_BACKEND_UNAVAILABLE")).toBeInTheDocument();
    expect(screen.queryByText("Structured proposal")).not.toBeInTheDocument();
  });

  it("reviews a real recorded transcript before using the voice endpoint", async () => {
    const user = userEvent.setup();
    renderApp();
    const recording = new File([new Uint8Array([1, 2, 3])], "operator.wav", {
      type: "audio/wav",
    });

    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      recording,
    );

    await waitFor(() =>
      expect(screen.getByText("Nemotron transcript")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("textbox", { name: "Operator command" }),
    ).toHaveValue("Move the blue component.");
    expect(screen.getByText("operator.wav · 860.0 ms")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(screen.getByText("Reviewed voice transcript")).toBeInTheDocument(),
    );
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    const calls = vi.mocked(fetch).mock.calls;
    const transcriptionCall = calls.find(([url]) =>
      String(url).includes("/api/v1/speech/recorded"),
    );
    const governanceCall = calls.find(([url]) =>
      String(url).includes("/api/v1/governance/voice"),
    );
    expect(transcriptionCall?.[1]?.body).toBe(recording);
    const body = JSON.parse(String(governanceCall?.[1]?.body));
    expect(body.transcription_id).toBe("transcription-ui-001");
    expect(body.reviewed_transcript_text).toBe("Move the blue component.");
    expect(body.inference_mode).toBe("AUTO");
    expect(body.scenario_id).toBe("MANUFACTURING_TYPED_ACCEPT");
    expect(body).not.toHaveProperty("domain_id");
    expect(body).not.toHaveProperty("requester_role");
    expect(body).not.toHaveProperty("human_obstruction");
    expect(body).not.toHaveProperty("safety_interlock_enabled");
  });
  it("bounds non-Error failures and retains the current mode for invalid UI values", () => {
    expect(clientErrorMessage("opaque failure")).toBe("UNKNOWN_CLIENT_FAILURE");
    expect(selectInferenceMode("AUTO", "EDGE")).toBe("AUTO");
    expect(selectInferenceMode("AUTO", "LOCAL")).toBe("LOCAL");
  });

  it("renders a bounded failure when a request rejects with a non-Error value", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/demo/manifest")) {
          return new Response(JSON.stringify(manifest), { status: 200 });
        }
        if (url.includes("/api/v1/status")) {
          return new Response(JSON.stringify(status), { status: 200 });
        }
        throw "opaque failure";
      }),
    );
    const user = userEvent.setup();
    renderApp();
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Operator command" })).toBeEnabled(),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() =>
      expect(screen.getByText("UNKNOWN_CLIENT_FAILURE")).toBeInTheDocument(),
    );
  });

});
