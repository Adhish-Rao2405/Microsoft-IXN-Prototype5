import { createHash } from "node:crypto";

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import {
  MicrophoneCaptureController,
  type MicrophoneCaptureOutcome,
} from "../src/microphoneCapture";
import * as replayApi from "../src/api";
import {
  App,
  BOOTSTRAP_CLIENT_DEADLINE_MS,
  GOVERNANCE_CLIENT_DEADLINE_MS,
  REPLAY_POLL_INTERVAL_MS,
  SPEECH_CLIENT_DEADLINE_MS,
  clientErrorMessage,
  selectInferenceMode,
} from "../src/App";
import { decodeReplayState } from "../src/runtimeContracts";

const microphoneCaptureMocks = vi.hoisted(() => ({
  createController: vi.fn(),
}));

vi.mock("../src/microphoneCapture", async () => {
  const actual = await vi.importActual<typeof import("../src/microphoneCapture")>(
    "../src/microphoneCapture",
  );
  return {
    ...actual,
    createMicrophoneCaptureController: microphoneCaptureMocks.createController,
  };
});

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

function fakeMicrophoneController() {
  const outcome = deferred<MicrophoneCaptureOutcome>();
  const start = vi.fn(async () => true);
  const stop = vi.fn(() => outcome.promise);
  const cancel = vi.fn(() => outcome.promise);

  class FakeMicrophoneCaptureController extends MicrophoneCaptureController {
    override readonly outcome = outcome.promise;

    override start(): Promise<boolean> {
      return start();
    }

    override stop(): Promise<MicrophoneCaptureOutcome> {
      return stop();
    }

    override cancel(): Promise<MicrophoneCaptureOutcome> {
      return cancel();
    }
  }

  const controller = new FakeMicrophoneCaptureController();
  return { controller, outcome, start, stop, cancel };
}

function jsonResponse(value: unknown, statusCode = 200): Response {
  return new Response(JSON.stringify(value), {
    status: statusCode,
    headers: { "Content-Type": "application/json" },
  });
}

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

const RAW_MOVE_RESPONSE =
  '{"actions":[{"action":"MOVE","object_id":"blue_component",' +
  '"source_id":"input_tray_a","destination_id":"assembly_fixture_b",' +
  '"duration_ms":null}]}';

const RAW_MOVE_RESPONSE_SHA256 =
  "7cfabaee94153f7cbc5176cc888666da70968290fe7f240cc5ff5b1597df501a";

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
      raw_response_text: RAW_MOVE_RESPONSE,
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
        raw_response_sha256: RAW_MOVE_RESPONSE_SHA256,
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

function governanceWithTrace(traceId: string) {
  const value = governanceResult();
  value.canonical_result.governance_record.trace_id = traceId;
  value.canonical_result.governance_record.record_id = `record-${traceId}`;
  return value;
}

function transcriptionWith(
  transcriptionId: string,
  transcriptText: string,
  filename: string,
) {
  return {
    ...transcription,
    transcription_id: transcriptionId,
    transcript_text: transcriptText,
    audio: {
      ...transcription.audio,
      original_filename: filename,
    },
  };
}

function replayState(overrides: Record<string, unknown> = {}) {
  return {
    contract_id: "PROTOTYPE5_D3_REPLAY_STATE_V1",
    contract_version: "1.0.0",
    scenario_id: "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    binding_id: "FROZEN_B2_B3_2_EVIDENCE_V1",
    session_id: null,
    control_version: 0,
    projection_version: 0,
    lifecycle_state: "IDLE",
    command_in_flight: false,
    current_frame: null,
    frame_count: 469,
    key_snapshot_indices: [0, 78, 118, 119, 157, 311, 351, 352, 390, 468],
    allowed_controls: ["START", "PAUSE", "RESUME", "NEXT_SNAPSHOT", "PREVIOUS_SNAPSHOT", "STOP", "RESET_VIEW"],
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
    presentation_labels: ["EVIDENCE REPLAY", "NOT PHYSICAL EXECUTION", "DISCRETE SAMPLED STATES — NO DYNAMIC TIMING"],
    physical_execution_authority: "NOT_IMPLEMENTED",
    last_error_code: null,
    updated_at_utc: "2026-08-14T10:00:00Z",
    ...overrides,
  };
}

function pausedReplayState(overrides: Record<string, unknown> = {}) {
  return replayState({
    session_id: "opaque-session-s1",
    control_version: 1,
    projection_version: 1,
    lifecycle_state: "PAUSED",
    current_frame: {
      frame_index: 0,
      semantic_snapshot_index: 0,
      route_configuration_index: 0,
      route_state: "HOME",
      phase: "SOURCE_SUPPORTED",
      boundary_snapshot: "NONE",
      is_key_snapshot: true,
    },
    available_controls: ["RESUME", "NEXT_SNAPSHOT", "STOP", "RESET_VIEW"],
    updated_at_utc: "2026-08-14T10:00:01Z",
    ...overrides,
  });
}

function playingReplayState(overrides: Record<string, unknown> = {}) {
  return pausedReplayState({
    control_version: 2,
    projection_version: 2,
    lifecycle_state: "PLAYING",
    current_frame: {
      frame_index: 10,
      semantic_snapshot_index: 10,
      route_configuration_index: 10,
      route_state: "INTERPOLATED",
      phase: "CARRIED",
      boundary_snapshot: "NONE",
      is_key_snapshot: false,
    },
    available_controls: ["PAUSE", "STOP", "RESET_VIEW"],
    updated_at_utc: "2026-08-14T10:00:02Z",
    ...overrides,
  });
}

function deferredFetch({
  governance = [],
  speech = [],
}: {
  governance?: Deferred<Response>[];
  speech?: Deferred<Response>[];
}) {
  const fetchMock = vi.fn(
    (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) {
        return Promise.resolve(jsonResponse(manifest));
      }
      if (url.includes("/api/v1/status")) {
        return Promise.resolve(jsonResponse(status));
      }
      if (url.includes("/api/v1/speech/recorded")) {
        const request = speech.shift();
        if (!request) throw new Error("UNEXPECTED_SPEECH_REQUEST");
        expect(init?.signal).toBeInstanceOf(AbortSignal);
        return request.promise;
      }
      const request = governance.shift();
      if (!request) throw new Error("UNEXPECTED_GOVERNANCE_REQUEST");
      expect(init?.signal).toBeInstanceOf(AbortSignal);
      return request.promise;
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function waitUntilReady(): Promise<void> {
  await waitFor(() =>
    expect(screen.getByRole("textbox", { name: "Operator command" })).toBeEnabled(),
  );
}

async function chooseScenario(
  user: ReturnType<typeof userEvent.setup>,
  name: string,
): Promise<void> {
  await user.click(screen.getByRole("combobox", { name: "Scenario" }));
  await user.click(await screen.findByRole("option", { name }));
}

function renderApp() {
  return render(
    <FluentProvider theme={webLightTheme}>
      <App />
    </FluentProvider>,
  );
}

function authorityListItems(): HTMLElement[] {
  return within(
    screen.getByRole("list", { name: "Six-layer authority progression" }),
  ).getAllByRole("listitem");
}

function mockFetch(result = governanceResult()) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
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
      if (url.includes("/api/v1/replay/state")) {
        return new Response(JSON.stringify(replayState()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/replay/start")) {
        return new Response(JSON.stringify(pausedReplayState()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/replay/control")) {
        return new Response(JSON.stringify(pausedReplayState({
          control_version: 2,
          projection_version: 2,
          lifecycle_state: "PLAYING",
          available_controls: ["PAUSE", "STOP", "RESET_VIEW"],
          updated_at_utc: "2026-08-14T10:00:02Z",
        })), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Prototype 5 typed UI", () => {
  beforeEach(() => {
    microphoneCaptureMocks.createController.mockReset();
    mockFetch();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("keeps raw provider evidence, parsed proposal, and digest coherent", () => {
    const value = governanceResult();

    expect(value.canonical_result.raw_response_text).toBe(RAW_MOVE_RESPONSE);
    expect(JSON.parse(RAW_MOVE_RESPONSE)).toEqual(
      value.canonical_result.proposal,
    );
    expect(createHash("sha256").update(RAW_MOVE_RESPONSE).digest("hex")).toBe(
      RAW_MOVE_RESPONSE_SHA256,
    );
    expect(
      value.canonical_result.governance_record.raw_response_sha256,
    ).toBe(RAW_MOVE_RESPONSE_SHA256);
  });

  it("renders the operational controls and bounded initial states", async () => {
    renderApp();

    expect(
      screen.getByRole("heading", { name: "Zero-Trust Governance Demonstrator" }),
    ).toBeInTheDocument();
    await waitUntilReady();
    expect(screen.getByRole("radio", { name: "Auto" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Scenario" })).toHaveTextContent(
      "Manufacturing scenario 1",
    );
    expect(screen.queryByRole("combobox", { name: "Domain" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Requester role" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start microphone recording" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Upload WAV recording" }),
    ).toBeEnabled();
    expect(screen.getByText("No command submitted.")).toBeInTheDocument();
    expect(screen.queryByText("Not issued")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "SYSTEM CAPABILITY / STATUS — NOT EXPERIMENTAL EVIDENCE",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE"),
    ).toHaveLength(2);

    const rows = authorityListItems();
    expect(rows).toHaveLength(6);
    expect(rows.map((row) => row.querySelector(".authority-label")?.textContent)).toEqual([
      "Untrusted proposal",
      "Governance decision",
      "Execution eligibility",
      "Qualification replay access",
      "Downstream geometric qualification",
      "Physical execution authority",
    ]);
    expect(rows[0]).toHaveTextContent("NOT REQUESTED");
    expect(rows[1]).toHaveTextContent("NOT REQUESTED");
    expect(rows[2]).toHaveTextContent("NOT REQUESTED");
    expect(rows[3]).toHaveTextContent("PROHIBITED");
    expect(rows[3]).toHaveTextContent("Policy: PROHIBITED");
    expect(rows[5]).toHaveTextContent("NOT_IMPLEMENTED");
    expect(
      screen.getByText("Passing layer N does not establish layer N+1."),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Configured")).toBeInTheDocument());
  });

  it("announces bounded runtime status updates without focusing the hidden file input", async () => {
    renderApp();

    const statusUpdate = screen.getByRole("status", {
      name: "System capability and runtime status update",
    });
    expect(statusUpdate).toHaveAttribute("aria-live", "polite");
    expect(statusUpdate).toHaveAttribute("aria-atomic", "true");

    await waitUntilReady();
    expect(statusUpdate).toHaveTextContent("Local Not assessed");
    expect(statusUpdate).toHaveTextContent("Cloud Configured");
    expect(statusUpdate).toHaveTextContent("Speech Not checked this session");
    expect(statusUpdate).toHaveTextContent("Evidence replay Implemented");
    expect(statusUpdate).toHaveTextContent("Physical execution Not implemented");
    const runtimeStatusRegion = screen.getByRole("region", {
      name: "System capability and runtime status",
    });
    expect(
      runtimeStatusRegion.querySelectorAll('[role="status"]'),
    ).toHaveLength(1);
    const replayStatus = within(runtimeStatusRegion)
      .getByText("Evidence replay")
      .closest(".runtime-status");
    expect(replayStatus).toHaveAttribute("data-status-kind", "capability");
    expect(within(replayStatus as HTMLElement).queryByText("Available")).toBeNull();

    expect(screen.getByLabelText("Recorded WAV file")).toHaveAttribute(
      "tabindex",
      "-1",
    );
    expect(
      screen.getByRole("button", { name: "Upload WAV recording" }),
    ).toBeEnabled();
  });

  it.each(["AVAILABLE", "UNAVAILABLE"] as const)(
    "does not treat bootstrap speech status %s as a client-session outcome",
    async (speechStatus) => {
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
        if (url.includes("/api/v1/status")) {
          return jsonResponse({ ...status, speech_status: speechStatus });
        }
        throw new Error("UNEXPECTED_REQUEST");
      });
      vi.stubGlobal("fetch", fetchMock);
      renderApp();

      await waitUntilReady();
      const statusRegion = screen.getByRole("region", {
        name: "System capability and runtime status",
      });
      expect(within(statusRegion).getByText("Not checked this session")).toBeVisible();
      expect(within(statusRegion).queryByText("Completed this session")).toBeNull();
      expect(within(statusRegion).queryByText("Unavailable this session")).toBeNull();
      expect(
        within(statusRegion).queryByText("Speech backend unavailable this session"),
      ).toBeNull();
    },
  );

  it("presents missing cloud configuration without claiming provider health", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) {
        return jsonResponse({ ...status, cloud_status: "UNAVAILABLE" });
      }
      throw new Error("UNEXPECTED_REQUEST");
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp();

    await waitUntilReady();
    const runtimeStatusRegion = screen.getByRole("region", {
      name: "System capability and runtime status",
    });
    expect(within(runtimeStatusRegion).getByText("Not configured")).toBeVisible();
    expect(within(runtimeStatusRegion).queryByText("Unavailable")).toBeNull();
  });

  it("presents an unchecked cloud configuration without claiming availability", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) {
        return jsonResponse({ ...status, cloud_status: "NOT_ASSESSED" });
      }
      throw new Error("UNEXPECTED_REQUEST");
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp();

    await waitUntilReady();
    const runtimeStatusRegion = screen.getByRole("region", {
      name: "System capability and runtime status",
    });
    expect(within(runtimeStatusRegion).getByText("Not checked")).toBeVisible();
  });

  it("disables and rejects recorded speech before bootstrap completes", async () => {
    const manifestRequest = deferred<Response>();
    const statusRequest = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      String(input).includes("/api/v1/demo/manifest")
        ? manifestRequest.promise
        : statusRequest.promise,
    );
    vi.stubGlobal("fetch", fetchMock);
    renderApp();

    expect(
      screen.getByRole("button", { name: "Upload WAV recording" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Recorded WAV file"), {
      target: {
        files: [
          new File([new Uint8Array([1])], "pre-bootstrap.wav", {
            type: "audio/wav",
          }),
        ],
      },
    });
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/api/v1/speech/recorded"),
      ),
    ).toHaveLength(0);
  });

  it("disables and rejects recorded speech for a non-model-input scenario", async () => {
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Manufacturing scenario 6");

    expect(
      screen.getByRole("button", { name: "Upload WAV recording" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Recorded WAV file"), {
      target: {
        files: [
          new File([new Uint8Array([1])], "frozen.wav", { type: "audio/wav" }),
        ],
      },
    });
    expect(
      vi.mocked(fetch).mock.calls.filter(([url]) =>
        String(url).includes("/api/v1/speech/recorded"),
      ),
    ).toHaveLength(0);
  });

  it("submits the selected mode and displays proposal plus every gate", async () => {
    const user = userEvent.setup();
    renderApp();

    await waitUntilReady();
    await user.click(screen.getByRole("radio", { name: "Local" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Operator command" }), {
      target: {
        value:
          "Move the blue component from input tray A to assembly fixture B.",
      },
    });
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("trace-ui-001")).toBeInTheDocument());
    expect(screen.getByText("Untrusted model proposal")).toBeInTheDocument();
    expect(screen.getByText("UNTRUSTED PROPOSAL — NO AUTHORITY")).toBeInTheDocument();
    expect(screen.getByText("Schema: PASSED")).toBeInTheDocument();
    expect(screen.getByText("Plan semantics")).toBeInTheDocument();
    expect(screen.getByText(/blue_component/)).toBeInTheDocument();

    const rows = authorityListItems();
    expect(rows[0]).toHaveTextContent("PRESENT — NO AUTHORITY");
    expect(rows[1]).toHaveTextContent("ACCEPT");
    expect(rows[2]).toHaveTextContent("ELIGIBLE");
    expect(rows[3]).toHaveTextContent("PROHIBITED");
    expect(rows[3]).not.toHaveTextContent("GRANTED");
    expect(rows[5]).toHaveTextContent("NOT_IMPLEMENTED");
    expect(screen.getByText("2026-07-30T12:00:00+00:00")).toBeInTheDocument();
    expect(screen.getAllByText("Foundry Local")).toHaveLength(2);
    expect(screen.getAllByText("local-model")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "Download live demo trace" }),
    ).toBeEnabled();

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

    await waitFor(() => expect(screen.getByText("trace-ui-001")).toBeInTheDocument());
    expect(screen.getAllByText("Cloud").length).toBeGreaterThan(0);
    expect(screen.getByText("Local schema failure")).toBeInTheDocument();
    expect(authorityListItems()[2]).toHaveTextContent("ELIGIBLE");
  });

  it("shows rejected governance without implying replay or physical authority", async () => {
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
    const rows = authorityListItems();
    expect(rows[1]).toHaveTextContent("REJECT");
    expect(rows[2]).toHaveTextContent("NOT ELIGIBLE");
    expect(rows[3]).not.toHaveTextContent("GRANTED");
    expect(rows[5]).toHaveTextContent("NOT_IMPLEMENTED");
    expect(screen.queryByText("Not issued")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop simulation" })).not.toBeInTheDocument();
  });

  it("keeps schema validity separate from execution eligibility", async () => {
    mockFetch(governanceResult({ decision: "REJECT" }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("Schema: PASSED")).toBeInTheDocument());
    expect(authorityListItems()[2]).toHaveTextContent("NOT ELIGIBLE");
  });

  it("shows frozen research evidence without active inference semantics", async () => {
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Manufacturing scenario 6");

    expect(
      screen.getByText("FROZEN RESEARCH EVIDENCE — EXACT REGISTERED ARTIFACT"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("NOT APPLICABLE — FROZEN REGISTERED EVIDENCE"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "Inference mode" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Operator command" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  it("presents registered frozen replay policy without granting replay", async () => {
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");

    expect(screen.getByText("FROZEN EVIDENCE REPLAY")).toBeInTheDocument();
    expect(screen.getByText("EVIDENCE REPLAY — NOT PHYSICAL EXECUTION")).toBeInTheDocument();
    const rows = authorityListItems();
    expect(rows[1]).toHaveTextContent("NOT REQUESTED");
    await waitFor(() => expect(rows[3]).toHaveTextContent("SERVER_REGISTERED_ONLY — IDLE"));
    expect(rows[3]).toHaveTextContent("Policy: SERVER_REGISTERED_ONLY");
    expect(rows[3]).toHaveTextContent("Capability class: FROZEN_B2_REPLAY_COMPATIBLE");
    expect(rows[3]).not.toHaveTextContent("GRANTED");
    expect(rows[4]).toHaveTextContent("FAIL");
    expect(rows[4]).toHaveTextContent("Independent of the governance decision");
    expect(rows[5]).toHaveTextContent("NOT_IMPLEMENTED");
    expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Pause" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /simulation/i })).not.toBeInTheDocument();
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
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Stop.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("Request failed")).toBeInTheDocument());
    expect(screen.getByText("LOCAL_BACKEND_UNAVAILABLE")).toBeInTheDocument();
    expect(screen.queryByText("Untrusted model proposal")).not.toBeInTheDocument();
    expect(clearTimeoutSpy).toHaveBeenCalled();
  });

  it("reviews a real recorded transcript before using the voice endpoint", async () => {
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    const recording = new File([new Uint8Array([1, 2, 3])], "operator.wav", {
      type: "audio/wav",
    });

    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      recording,
    );

    const reviewCommand = await screen.findByRole("textbox", {
      name: "Operator review command",
    });
    const runtimeStatusRegion = screen.getByRole("region", {
      name: "System capability and runtime status",
    });
    expect(
      within(runtimeStatusRegion).getByText("Completed this session"),
    ).toBeVisible();
    expect(screen.getByText("RAW ASR TRANSCRIPT — UNTRUSTED")).toBeInTheDocument();
    expect(reviewCommand).toHaveValue("Move the blue component.");
    expect(screen.getByText("Move the blue component.", { selector: "blockquote" })).toBeInTheDocument();
    expect(screen.getByText("operator.wav · 860.0 ms")).toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.filter(([url]) =>
        String(url).includes("/api/v1/governance/voice"),
      ),
    ).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(screen.getByText("Reviewed voice transcript")).toBeInTheDocument(),
    );
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    expect(reviewCommand).toBeDisabled();
    expect(reviewCommand).toHaveValue("Move the blue component.");
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Discard transcript" })).toBeEnabled();
    const calls = vi.mocked(fetch).mock.calls;
    const transcriptionCall = calls.find(([url]) =>
      String(url).includes("/api/v1/speech/recorded"),
    );
    const governanceCall = calls.find(([url]) =>
      String(url).includes("/api/v1/governance/voice"),
    );
    expect(
      calls.filter(([url]) => String(url).includes("/api/v1/governance/voice")),
    ).toHaveLength(1);
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

  it.each([
    {
      status: "PARTIAL",
      transcriptText: "Move the blue component",
      errorCode: "TRANSCRIPTION_PARTIAL",
      expectedFailure: "TRANSCRIPTION_PARTIAL",
      expectedSessionLabel: "Incomplete this session",
    },
    {
      status: "EMPTY",
      transcriptText: null,
      errorCode: "TRANSCRIPT_EMPTY",
      expectedFailure: "TRANSCRIPTION_EMPTY (TRANSCRIPT_EMPTY)",
      expectedSessionLabel: "Completed this session",
    },
    {
      status: "BACKEND_UNAVAILABLE",
      transcriptText: null,
      errorCode: "NEMOTRON_MODEL_NOT_CACHED",
      expectedFailure: "SPEECH_BACKEND_UNAVAILABLE (NEMOTRON_MODEL_NOT_CACHED)",
      expectedSessionLabel: "Speech backend unavailable this session",
    },
    {
      status: "FAILED",
      transcriptText: null,
      errorCode: "TRANSCRIPTION_TIMEOUT",
      expectedFailure: "TRANSCRIPTION_TIMEOUT",
      expectedSessionLabel: "Timed out this session",
    },
    {
      status: "FAILED",
      transcriptText: null,
      errorCode: "NEMOTRON_TRANSCRIPTION_FAILED",
      expectedFailure: "TRANSCRIPTION_FAILED (NEMOTRON_TRANSCRIPTION_FAILED)",
      expectedSessionLabel: "Failed this session",
    },
  ] as const)(
    "keeps $status speech results outside the operator review boundary",
    async ({
      status: transcriptStatus,
      transcriptText,
      errorCode,
      expectedFailure,
      expectedSessionLabel,
    }) => {
      const nonReady = {
        ...transcription,
        transcript_status: transcriptStatus,
        transcript_text: transcriptText,
        error_code: errorCode,
      };
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL) => {
          const url = String(input);
          if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
          if (url.includes("/api/v1/status")) return jsonResponse(status);
          if (url.includes("/api/v1/speech/recorded")) return jsonResponse(nonReady);
          throw new Error("UNEXPECTED_REQUEST");
        }),
      );
      renderApp();
      await waitUntilReady();
      await userEvent.upload(
        screen.getByLabelText("Recorded WAV file"),
        new File([new Uint8Array([1])], `${transcriptStatus}.wav`, {
          type: "audio/wav",
        }),
      );

      await waitFor(() =>
        expect(screen.getByRole("alert")).toHaveTextContent(expectedFailure),
      );
      const statusRegion = screen.getByRole("region", {
        name: "System capability and runtime status",
      });
      expect(within(statusRegion).getByText(expectedSessionLabel)).toBeVisible();
      if (transcriptStatus === "PARTIAL") {
        expect(within(statusRegion).queryByText("Unavailable this session")).toBeNull();
      }
      expect(screen.queryByText("RAW ASR TRANSCRIPT — UNTRUSTED")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("textbox", { name: "Operator review command" }),
      ).not.toBeInTheDocument();
      const calls = vi.mocked(fetch).mock.calls;
      expect(
        calls.filter(([url]) => String(url).includes("/api/v1/governance/voice")),
      ).toHaveLength(0);
      expect(
        calls.filter(([url]) => String(url).includes("/api/v1/governance/typed")),
      ).toHaveLength(0);
    },
  );

  it("requires explicit review after App-owned microphone capture", async () => {
    const microphone = fakeMicrophoneController();
    microphoneCaptureMocks.createController.mockReturnValue(microphone.controller);
    const speechRequest = deferred<Response>();
    const governanceRequest = deferred<Response>();
    const fetchMock = deferredFetch({
      speech: [speechRequest],
      governance: [governanceRequest],
    });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();

    await user.click(screen.getByRole("button", { name: "Start microphone recording" }));
    expect(microphoneCaptureMocks.createController).toHaveBeenCalledTimes(1);
    expect(microphone.start).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Stop microphone recording" })).toBeEnabled(),
    );

    const capturedWav = new File([new Uint8Array([82, 73, 70, 70])], "microphone.wav", {
      type: "audio/wav",
    });
    await act(async () => {
      microphone.outcome.resolve({ kind: "CAPTURED", file: capturedWav, frameCount: 2 });
      await microphone.outcome.promise;
    });
    const speechCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/api/v1/speech/recorded"),
      );
      expect(call).toBeDefined();
      return call;
    });
    expect(speechCall?.[1]?.body).toBe(capturedWav);

    await act(async () => {
      speechRequest.resolve(jsonResponse({
        ...transcription,
        audio: { ...transcription.audio, original_filename: "microphone.wav" },
      }));
      await speechRequest.promise;
    });
    await screen.findByText("RAW ASR TRANSCRIPT — UNTRUSTED");
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/api/v1/governance/voice"),
      ),
    ).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Submit" }));
    const voiceCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/api/v1/governance/voice"),
      );
      expect(call).toBeDefined();
      return call;
    });
    expect(JSON.parse(String(voiceCall?.[1]?.body))).toMatchObject({
      transcription_id: "transcription-ui-001",
      reviewed_transcript_text: "Move the blue component.",
    });
    await act(async () => {
      governanceRequest.resolve(jsonResponse(governanceResult()));
      await governanceRequest.promise;
    });
  });

  it("cancels active microphone capture on scenario change and ignores late outcome", async () => {
    const microphone = fakeMicrophoneController();
    microphoneCaptureMocks.createController.mockReturnValue(microphone.controller);
    const fetchMock = mockFetch();
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.click(screen.getByRole("button", { name: "Start microphone recording" }));
    await screen.findByRole("button", { name: "Stop microphone recording" });

    await chooseScenario(user, "Manufacturing scenario 2");
    expect(microphone.cancel).toHaveBeenCalledTimes(1);
    await act(async () => {
      microphone.outcome.resolve({
        kind: "CAPTURED",
        file: new File([new Uint8Array([1])], "late.wav", { type: "audio/wav" }),
        frameCount: 1,
      });
      await microphone.outcome.promise;
      await Promise.resolve();
    });

    expect(screen.getByRole("combobox", { name: "Scenario" })).toHaveTextContent(
      "Manufacturing scenario 2",
    );
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/api/v1/speech/recorded"),
      ),
    ).toHaveLength(0);
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/v1/governance/")),
    ).toHaveLength(0);
  });

  it("cancels active microphone capture on unmount and ignores late outcome", async () => {
    const microphone = fakeMicrophoneController();
    microphoneCaptureMocks.createController.mockReturnValue(microphone.controller);
    const fetchMock = mockFetch();
    const user = userEvent.setup();
    const view = renderApp();
    await waitUntilReady();
    await user.click(screen.getByRole("button", { name: "Start microphone recording" }));
    await screen.findByRole("button", { name: "Stop microphone recording" });

    view.unmount();
    expect(microphone.cancel).toHaveBeenCalledTimes(1);
    await act(async () => {
      microphone.outcome.resolve({
        kind: "CAPTURED",
        file: new File([new Uint8Array([1])], "late.wav", { type: "audio/wav" }),
        frameCount: 1,
      });
      await microphone.outcome.promise;
      await Promise.resolve();
    });

    expect(view.container).toBeEmptyDOMElement();
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/api/v1/speech/recorded"),
      ),
    ).toHaveLength(0);
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/v1/governance/")),
    ).toHaveLength(0);
  });
  it("bounds non-Error failures and retains the current mode for invalid UI values", () => {
    expect(clientErrorMessage("opaque failure")).toBe("UNKNOWN_CLIENT_FAILURE");
    expect(selectInferenceMode("AUTO", "EDGE")).toBe("AUTO");
    expect(selectInferenceMode("AUTO", "LOCAL")).toBe("LOCAL");
  });

  it("classifies a fetch rejection as NETWORK_FAILURE", async () => {
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
      expect(screen.getByText("NETWORK_FAILURE")).toBeInTheDocument(),
    );
  });

  it("uses validated server transcription failure codes without exposing detail", async () => {
    const serverFailure = {
      ...transcription,
      transcript_status: "FAILED",
      transcript_text: null,
      resolved_model_id: null,
      model_loaded_before: null,
      model_loaded_for_request: false,
      segment_count: 0,
      transcription_latency_ms: null,
      error_code: "TRANSCRIPTION_FAILED",
      error_detail: "sensitive server diagnostic",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
        if (url.includes("/api/v1/status")) return jsonResponse(status);
        if (url.includes("/api/v1/speech/recorded")) {
          return jsonResponse(serverFailure);
        }
        throw new Error("UNEXPECTED_REQUEST");
      }),
    );
    renderApp();
    await waitUntilReady();
    await userEvent.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "failed.wav", { type: "audio/wav" }),
    );

    await waitFor(() =>
      expect(screen.getByText("TRANSCRIPTION_FAILED")).toBeInTheDocument(),
    );
    expect(screen.queryByText("sensitive server diagnostic")).not.toBeInTheDocument();
  });

  it("keeps the newer governance owner when requests settle out of order", async () => {
    const requestA = deferred<Response>();
    const requestB = deferred<Response>();
    deferredFetch({ governance: [requestA, requestB] });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();

    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await user.click(screen.getByRole("radio", { name: "Local" }));
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await act(async () => {
      requestA.resolve(jsonResponse(governanceWithTrace("trace-a")));
      await requestA.promise;
    });
    expect(screen.getByText("Evaluating proposal")).toBeInTheDocument();
    expect(screen.queryByText("trace-a")).not.toBeInTheDocument();

    await act(async () => {
      requestB.resolve(jsonResponse(governanceWithTrace("trace-b")));
      await requestB.promise;
    });
    await waitFor(() => expect(screen.getByText("trace-b")).toBeInTheDocument());
    expect(screen.queryByText("trace-a")).not.toBeInTheDocument();
  });

  it("silently invalidates governance when its scenario changes", async () => {
    const request = deferred<Response>();
    const fetchMock = deferredFetch({ governance: [request] });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();

    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    const governanceCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/governance/typed"),
    );
    await chooseScenario(user, "Manufacturing scenario 2");

    expect(governanceCall?.[1]?.signal?.aborted).toBe(true);
    expect(screen.queryByText("Evaluating proposal")).not.toBeInTheDocument();
    expect(screen.queryByText("Request failed")).not.toBeInTheDocument();
    await act(async () => {
      request.resolve(jsonResponse(governanceWithTrace("stale-scenario-trace")));
      await request.promise;
    });
    expect(screen.queryByText("stale-scenario-trace")).not.toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Scenario" }),
    ).toHaveTextContent("Manufacturing scenario 2");
  });

  it("keeps DOMException AbortError silent when governance is intentionally superseded", async () => {
    const fetchMock = vi.fn(
      (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
        const url = String(input);
        if (url.includes("/api/v1/demo/manifest")) {
          return Promise.resolve(jsonResponse(manifest));
        }
        if (url.includes("/api/v1/status")) {
          return Promise.resolve(jsonResponse(status));
        }
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/governance/typed"),
    );

    await user.click(screen.getByRole("radio", { name: "Local" }));
    expect(call?.[1]?.signal?.aborted).toBe(true);
    await waitFor(() =>
      expect(screen.queryByText("Evaluating proposal")).not.toBeInTheDocument(),
    );
    expect(screen.queryByText("Request failed")).not.toBeInTheDocument();
    expect(screen.queryByText("NETWORK_FAILURE")).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Local" })).toBeChecked();
  });

  it("clears and aborts bootstrap ownership on unmount", async () => {
    const manifestRequest = deferred<Response>();
    const statusRequest = deferred<Response>();
    const bootstrapFetch = vi.fn((input: RequestInfo | URL, _init?: RequestInit) =>
      String(input).includes("/api/v1/demo/manifest")
        ? manifestRequest.promise
        : statusRequest.promise,
    );
    vi.stubGlobal("fetch", bootstrapFetch);
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    const view = renderApp();
    await waitFor(() => expect(bootstrapFetch).toHaveBeenCalledTimes(2));
    const signals = bootstrapFetch.mock.calls.map((call) => call[1]?.signal);
    const clearsBeforeUnmount = clearTimeoutSpy.mock.calls.length;

    view.unmount();
    expect(clearTimeoutSpy.mock.calls.length).toBeGreaterThan(clearsBeforeUnmount);
    expect(signals).toHaveLength(2);
    expect(signals.every((signal) => signal?.aborted)).toBe(true);
    await act(async () => {
      manifestRequest.resolve(jsonResponse(manifest));
      statusRequest.resolve(jsonResponse(status));
      await Promise.all([manifestRequest.promise, statusRequest.promise]);
      await Promise.resolve();
    });
    expect(view.container).toBeEmptyDOMElement();
  });

  it("clears and aborts governance ownership on unmount", async () => {
    const request = deferred<Response>();
    const fetchMock = deferredFetch({ governance: [request] });
    const user = userEvent.setup();
    const view = renderApp();
    await waitUntilReady();
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/governance/typed"),
    );
    const clearsBeforeUnmount = clearTimeoutSpy.mock.calls.length;

    view.unmount();
    expect(clearTimeoutSpy.mock.calls.length).toBeGreaterThan(clearsBeforeUnmount);
    expect(call?.[1]?.signal?.aborted).toBe(true);
    await act(async () => {
      request.resolve(jsonResponse(governanceWithTrace("late-unmounted-trace")));
      await request.promise;
      await Promise.resolve();
    });
    expect(view.container).toBeEmptyDOMElement();
  });

  it("clears and aborts transcription ownership on unmount", async () => {
    const request = deferred<Response>();
    const fetchMock = deferredFetch({ speech: [request] });
    const view = renderApp();
    await waitUntilReady();
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    await userEvent.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "owned.wav", { type: "audio/wav" }),
    );
    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/speech/recorded"),
    );
    const clearsBeforeUnmount = clearTimeoutSpy.mock.calls.length;

    view.unmount();
    expect(clearTimeoutSpy.mock.calls.length).toBeGreaterThan(clearsBeforeUnmount);
    expect(call?.[1]?.signal?.aborted).toBe(true);
    await act(async () => {
      request.resolve(
        jsonResponse(transcriptionWith("late-unmounted", "Late text", "owned.wav")),
      );
      await request.promise;
      await Promise.resolve();
    });
    expect(view.container).toBeEmptyDOMElement();
  });

  it("classifies governance client timeout without accepting late completion", async () => {
    renderApp();
    await waitUntilReady();
    const request = deferred<Response>();
    const fetchMock = deferredFetch({ governance: [request] });
    vi.useFakeTimers();
    fireEvent.change(screen.getByRole("textbox", { name: "Operator command" }), {
      target: { value: "Move." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/governance/typed"),
    );
    const signal = call?.[1]?.signal;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(GOVERNANCE_CLIENT_DEADLINE_MS);
    });
    expect(screen.getByText("CLIENT_TIMEOUT")).toBeInTheDocument();
    expect(signal?.aborted).toBe(true);

    await act(async () => {
      request.resolve(jsonResponse(governanceWithTrace("late-timeout-trace")));
      await request.promise;
    });
    expect(screen.queryByText("late-timeout-trace")).not.toBeInTheDocument();
  });

  it("classifies speech client timeout without implying server cancellation", async () => {
    renderApp();
    await waitUntilReady();
    const request = deferred<Response>();
    const fetchMock = deferredFetch({ speech: [request] });
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText("Recorded WAV file"), {
      target: {
        files: [
          new File([new Uint8Array([1])], "timeout.wav", { type: "audio/wav" }),
        ],
      },
    });
    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/speech/recorded"),
    );
    const signal = call?.[1]?.signal;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(SPEECH_CLIENT_DEADLINE_MS);
    });
    expect(screen.getByText("TRANSCRIPTION_TIMEOUT")).toBeInTheDocument();
    expect(screen.queryByText("CLIENT_TIMEOUT")).not.toBeInTheDocument();
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByText("PROVIDER_TIMEOUT")).not.toBeInTheDocument();

    await act(async () => {
      request.resolve(jsonResponse(transcription));
      await request.promise;
      await Promise.resolve();
    });
    expect(screen.getByText("TRANSCRIPTION_TIMEOUT")).toBeInTheDocument();
    expect(screen.queryByText("RAW ASR TRANSCRIPT — UNTRUSTED")).not.toBeInTheDocument();
  });

  it("bounds bootstrap wait time and aborts both bootstrap fetches", async () => {
    vi.useFakeTimers();
    const request = deferred<Response>();
    const fetchMock = vi.fn(
      (_input: RequestInfo | URL, _init?: RequestInit) => request.promise,
    );
    vi.stubGlobal("fetch", fetchMock);
    renderApp();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BOOTSTRAP_CLIENT_DEADLINE_MS);
    });
    const runtimeStatusRegion = screen.getByRole("region", {
      name: "System capability and runtime status",
    });
    const statusUpdate = screen.getByRole("status", {
      name: "System capability and runtime status update",
    });
    expect(statusUpdate).toHaveTextContent("System capability and runtime status unavailable:");
    const visibleStatusError = screen.getByText(
      "Status unavailable: CLIENT_TIMEOUT",
    );
    expect(visibleStatusError).toBeInTheDocument();
    expect(visibleStatusError).toHaveClass("status-error");
    expect(visibleStatusError).not.toHaveAttribute("role", "status");
    expect(
      runtimeStatusRegion.querySelectorAll('[role="status"]'),
    ).toHaveLength(1);
    expect(fetchMock.mock.calls).toHaveLength(2);
    expect(
      fetchMock.mock.calls.every((call) => call[1]?.signal?.aborted),
    ).toBe(true);
  });

  it("prevents a late transcription from overwriting a newer operator edit", async () => {
    const request = deferred<Response>();
    const fetchMock = deferredFetch({ speech: [request] });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "late.wav", { type: "audio/wav" }),
    );
    const speechCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/speech/recorded"),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "New operator text",
    );
    expect(speechCall?.[1]?.signal?.aborted).toBe(true);

    await act(async () => {
      request.resolve(
        jsonResponse(transcriptionWith("late-transcript", "Stale text", "late.wav")),
      );
      await request.promise;
    });
    expect(
      screen.getByRole("textbox", { name: "Operator command" }),
    ).toHaveValue("New operator text");
    expect(screen.queryByText("Nemotron transcript")).not.toBeInTheDocument();
    expect(screen.queryByText("Transcription failed")).not.toBeInTheDocument();
  });

  it("rejects a second transcription while one is active and preserves the active owner", async () => {
    const requestA = deferred<Response>();
    const requestB = deferred<Response>();
    const fetchMock = deferredFetch({ speech: [requestA, requestB] });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    const input = screen.getByLabelText("Recorded WAV file");
    const audioA = new File([new Uint8Array([1])], "a.wav", { type: "audio/wav" });
    const audioB = new File([new Uint8Array([2])], "b.wav", { type: "audio/wav" });
    const speechCalls = () => fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/api/v1/speech/recorded"),
    );

    await user.upload(input, audioA);
    await waitFor(() => expect(speechCalls()).toHaveLength(1));
    const signalA = speechCalls()[0]?.[1]?.signal;
    expect(signalA).toBeInstanceOf(AbortSignal);
    expect(signalA?.aborted).toBe(false);
    expect(screen.getByText("Transcribing recording")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Upload WAV recording" }),
    ).toBeDisabled();

    await user.upload(input, audioB);
    expect(speechCalls()).toHaveLength(1);
    expect(signalA?.aborted).toBe(false);
    expect(screen.getByText("Transcribing recording")).toBeInTheDocument();
    expect(screen.queryByText("b.wav · 860.0 ms")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "Operator review command" }),
    ).not.toBeInTheDocument();

    await act(async () => {
      const activeFailure = new TypeError("active network failure");
      requestA.reject(activeFailure);
      await expect(requestA.promise).rejects.toBe(activeFailure);
    });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("TRANSCRIPTION_NETWORK_FAILURE"),
    );
    expect(screen.getByText("Transcription failed")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Upload WAV recording" }),
    ).toBeEnabled();

    await user.upload(screen.getByLabelText("Recorded WAV file"), audioB);
    await waitFor(() => expect(speechCalls()).toHaveLength(2));
    const signalB = speechCalls()[1]?.[1]?.signal;
    expect(signalB).toBeInstanceOf(AbortSignal);
    expect(signalB?.aborted).toBe(false);
    expect(screen.getByText("Transcribing recording")).toBeInTheDocument();

    await act(async () => {
      requestB.resolve(
        jsonResponse(transcriptionWith("transcript-b", "Transcript B", "b.wav")),
      );
      await requestB.promise;
    });
    const reviewCommand = await screen.findByRole("textbox", {
      name: "Operator review command",
    });
    expect(reviewCommand).toHaveValue("Transcript B");
    expect(screen.queryByText("Transcribing recording")).not.toBeInTheDocument();
  });

  it("clears a READY transcript when the scenario changes", async () => {
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "scenario.wav", { type: "audio/wav" }),
    );
    await screen.findByRole("textbox", { name: "Operator review command" });
    expect(screen.getByText("RAW ASR TRANSCRIPT — UNTRUSTED")).toBeInTheDocument();
    await chooseScenario(user, "Manufacturing scenario 2");

    expect(
      screen.queryByRole("textbox", { name: "Operator review command" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("RAW ASR TRANSCRIPT — UNTRUSTED"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("No command submitted.")).toBeInTheDocument();
  });

  it("discarding a submitted voice identity suppresses its late result", async () => {
    const speechRequest = deferred<Response>();
    const governanceRequest = deferred<Response>();
    const fetchMock = deferredFetch({
      speech: [speechRequest],
      governance: [governanceRequest],
    });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "voice.wav", { type: "audio/wav" }),
    );
    await act(async () => {
      speechRequest.resolve(jsonResponse(transcription));
      await speechRequest.promise;
    });
    const reviewCommand = await screen.findByRole("textbox", {
      name: "Operator review command",
    });
    expect(reviewCommand).toHaveValue("Move the blue component.");
    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    const voiceCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/governance/voice"),
    );
    await user.click(screen.getByRole("button", { name: "Discard transcript" }));
    expect(voiceCall?.[1]?.signal?.aborted).toBe(true);

    await act(async () => {
      governanceRequest.resolve(
        jsonResponse(governanceWithTrace("discarded-voice-trace")),
      );
      await governanceRequest.promise;
    });
    expect(screen.queryByText("discarded-voice-trace")).not.toBeInTheDocument();
    expect(screen.queryByText("Request failed")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  it("prevents older typed and voice operations from cross-committing", async () => {
    const typedRequest = deferred<Response>();
    const speechRequest = deferred<Response>();
    const voiceRequest = deferred<Response>();
    deferredFetch({
      governance: [typedRequest, voiceRequest],
      speech: [speechRequest],
    });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Typed request",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await user.click(screen.getByRole("radio", { name: "Local" }));
    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "newer.wav", { type: "audio/wav" }),
    );
    await act(async () => {
      speechRequest.resolve(
        jsonResponse(transcriptionWith("newer-voice", "Newer voice", "newer.wav")),
      );
      await speechRequest.promise;
    });
    const reviewCommand = await screen.findByRole("textbox", {
      name: "Operator review command",
    });
    expect(reviewCommand).toHaveValue("Newer voice");
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await act(async () => {
      voiceRequest.resolve(jsonResponse(governanceWithTrace("voice-wins")));
      await voiceRequest.promise;
      typedRequest.resolve(jsonResponse(governanceWithTrace("typed-stale")));
      await typedRequest.promise;
    });
    await waitFor(() => expect(screen.getByText("voice-wins")).toBeInTheDocument());
    expect(screen.queryByText("typed-stale")).not.toBeInTheDocument();
    expect(screen.getByText("Reviewed voice transcript")).toBeInTheDocument();
  });

  it("prevents an older voice operation from replacing a newer typed result", async () => {
    const speechRequest = deferred<Response>();
    const voiceRequest = deferred<Response>();
    const typedRequest = deferred<Response>();
    deferredFetch({
      governance: [voiceRequest, typedRequest],
      speech: [speechRequest],
    });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "older.wav", { type: "audio/wav" }),
    );
    await act(async () => {
      speechRequest.resolve(
        jsonResponse(transcriptionWith("older-voice", "Older voice", "older.wav")),
      );
      await speechRequest.promise;
    });
    await screen.findByRole("textbox", { name: "Operator review command" });
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await user.click(screen.getByRole("button", { name: "Discard transcript" }));
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "New typed request",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await act(async () => {
      typedRequest.resolve(jsonResponse(governanceWithTrace("typed-wins")));
      await typedRequest.promise;
      voiceRequest.resolve(jsonResponse(governanceWithTrace("voice-stale")));
      await voiceRequest.promise;
    });
    await waitFor(() => expect(screen.getByText("typed-wins")).toBeInTheDocument());
    expect(screen.queryByText("voice-stale")).not.toBeInTheDocument();
    expect(screen.getByText("Operator")).toBeInTheDocument();
  });

  it("clears owned deadlines on success, failure, and supersession", async () => {
    const requestA = deferred<Response>();
    const requestB = deferred<Response>();
    const fetchMock = deferredFetch({ governance: [requestA, requestB] });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    const firstCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/governance/typed"),
    );
    await user.click(screen.getByRole("radio", { name: "Local" }));
    expect(firstCall?.[1]?.signal?.aborted).toBe(true);
    expect(clearTimeoutSpy).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Submit" }));
    await act(async () => {
      requestB.resolve(jsonResponse(governanceWithTrace("timer-cleared")));
      await requestB.promise;
    });
    await waitFor(() => expect(screen.getByText("timer-cleared")).toBeInTheDocument());
    const callsAfterSuccess = clearTimeoutSpy.mock.calls.length;
    expect(callsAfterSuccess).toBeGreaterThan(1);

    await act(async () => {
      requestA.reject(new TypeError("stale"));
      try {
        await requestA.promise;
      } catch {
        // The superseded request cannot finalise the current state.
      }
    });
    expect(clearTimeoutSpy.mock.calls.length).toBe(callsAfterSuccess);
  });

  it("never exposes arbitrary native Error messages", () => {
    expect(clientErrorMessage(new Error("sensitive browser detail"))).toBe(
      "UNKNOWN_CLIENT_FAILURE",
    );
    expect(clientErrorMessage(new TypeError("not necessarily transport"))).toBe(
      "UNKNOWN_CLIENT_FAILURE",
    );
  });

  it("renders frozen qualification evidence and starts with scenario identity only", async () => {
    const fetchMock = mockFetch();
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Start" })).toBeEnabled());
    expect(screen.getByText("NOT PHYSICAL EXECUTION")).toBeInTheDocument();
    expect(screen.getByText("DISCRETE SAMPLED STATES — NO DYNAMIC TIMING")).toBeInTheDocument();
    expect(screen.getByText("B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION")).toBeInTheDocument();
    expect(screen.getAllByText("NOT_IMPLEMENTED").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(screen.getByText("Frame 1 of 469")).toBeInTheDocument());
    const startCall = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/replay/start"));
    expect(JSON.parse(String(startCall?.[1]?.body))).toEqual({
      scenario_id: "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    });
    expect(screen.getByRole("button", { name: "Resume" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Pause" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Pause" })).toBeEnabled());
    const controlCall = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/replay/control"));
    expect(JSON.parse(String(controlCall?.[1]?.body))).toEqual({
      scenario_id: "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
      session_id: "opaque-session-s1",
      expected_control_version: 1,
      control: "RESUME",
    });
  });

  it("recovers an unknown START settlement through GET without retrying START", async () => {
    let stateCalls = 0;
    let startCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        if (stateCalls === 1) return jsonResponse(replayState());
        if (stateCalls === 2) {
          return jsonResponse(replayState({
            command_in_flight: true,
            available_controls: [],
          }));
        }
        return jsonResponse(pausedReplayState());
      }
      if (url.includes("/api/v1/replay/start")) {
        startCalls += 1;
        return jsonResponse({ code: "REPLAY_START_TIMEOUT" }, 504);
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Start" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(screen.getByText("Frame 1 of 469")).toBeInTheDocument(), { timeout: 2_000 });
    expect(startCalls).toBe(1);
    expect(stateCalls).toBeGreaterThanOrEqual(3);
  });

  it.each([
    {
      control: "PAUSE",
      label: "Pause",
      initial: playingReplayState(),
    },
    {
      control: "NEXT_SNAPSHOT",
      label: "Next snapshot",
      initial: pausedReplayState(),
    },
    {
      control: "PREVIOUS_SNAPSHOT",
      label: "Previous snapshot",
      initial: pausedReplayState({
        available_controls: ["NEXT_SNAPSHOT", "PREVIOUS_SNAPSHOT", "STOP", "RESET_VIEW"],
      }),
    },
    {
      control: "RESET_VIEW",
      label: "Reset view",
      initial: pausedReplayState(),
    },
  ])("submits authoritative $control CAS ownership", async ({ control, label, initial }) => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) return jsonResponse(initial);
      if (url.includes("/api/v1/replay/control")) {
        return jsonResponse(pausedReplayState({
          control_version: Number(initial.control_version) + 1,
          projection_version: Number(initial.projection_version) + 1,
        }));
      }
      throw new Error("UNEXPECTED_REQUEST");
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: label })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: label }));
    const call = await waitFor(() => {
      const next = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/replay/control"));
      expect(next).toBeDefined();
      return next;
    });
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      scenario_id: "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
      session_id: "opaque-session-s1",
      expected_control_version: initial.control_version,
      control,
    });
  });

  it.each([
    ["REPLAY_FRAME_BOUNDARY", 409],
    ["REPLAY_CONTROL_VERSION_STALE", 409],
    ["REPLAY_SESSION_STALE", 409],
    ["REPLAY_CONTROL_INVALID_STATE", 409],
    ["REPLAY_COMMAND_CHANNEL_FULL", 429],
  ] as const)("reconciles %s through GET without retrying mutation", async (code, statusCode) => {
    let stateCalls = 0;
    let controlCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        return jsonResponse(pausedReplayState({
          control_version: controlCalls === 0 ? 1 : 2,
          projection_version: controlCalls === 0 ? 1 : 2,
        }));
      }
      if (url.includes("/api/v1/replay/control")) {
        controlCalls += 1;
        return jsonResponse({ code }, statusCode);
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Next snapshot" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Next snapshot" }));
    await waitFor(() => expect(stateCalls).toBeGreaterThanOrEqual(2), {
      timeout: REPLAY_POLL_INTERVAL_MS + 1_500,
    });
    expect(controlCalls).toBe(1);
    await waitFor(() => expect(screen.getByRole("button", { name: "Next snapshot" })).toBeEnabled());
  }, 10_000);

  it.each([
    ["REPLAY_RUNTIME_INTEGRITY_FAILED", "FAILED"],
    ["REPLAY_CLEANUP_UNRESOLVED", "CLEANUP_FAILED"],
  ] as const)("reconciles %s to the retained server failure projection", async (code, lifecycle) => {
    let stateCalls = 0;
    let controlCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        if (controlCalls === 0) return jsonResponse(pausedReplayState());
        return jsonResponse(pausedReplayState({
          control_version: 2,
          projection_version: 2,
          lifecycle_state: lifecycle,
          current_frame: null,
          available_controls: ["STOP"],
          last_error_code: code,
        }));
      }
      if (url.includes("/api/v1/replay/control")) {
        controlCalls += 1;
        return jsonResponse({ code }, 503);
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Next snapshot" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Next snapshot" }));
    await waitFor(() => expect(screen.getByText(code)).toBeInTheDocument(), {
      timeout: REPLAY_POLL_INTERVAL_MS + 1_500,
    });
    expect(controlCalls).toBe(1);
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop" })).toBeEnabled(), {
      timeout: REPLAY_POLL_INTERVAL_MS + 1_500,
    });
    expect(screen.getAllByText(lifecycle).length).toBeGreaterThan(0);
  }, 10_000);

  it("latches fatal version exhaustion without further replay I/O", async () => {
    let replayCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/")) {
        replayCalls += 1;
        return jsonResponse({ code: "REPLAY_VERSION_EXHAUSTED" }, 503);
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    renderApp();
    await waitUntilReady();
    fireEvent.click(screen.getByRole("combobox", { name: "Scenario" }));
    fireEvent.click(screen.getByRole("option", {
      name: "Frozen B2 pick/place evidence replay",
    }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("REPLAY_VERSION_EXHAUSTED"));
    ["Start", "Pause", "Resume", "Next snapshot", "Previous snapshot", "Stop", "Reset view"].forEach((label) => {
      expect(screen.getByRole("button", { name: label })).toBeDisabled();
    });
    expect(replayCalls).toBe(1);
    vi.useFakeTimers();
    expect(screen.getByRole("alert")).toHaveTextContent("REPLAY_VERSION_EXHAUSTED");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(REPLAY_POLL_INTERVAL_MS * 2);
    });
    expect(replayCalls).toBe(1);
  });

  it("ignores stale replay mutation version exhaustion after scenario switch", async () => {
    const firstReplayRead = deferred<Awaited<ReturnType<typeof replayApi.getReplayState>>>();
    const secondReplayRead = deferred<Awaited<ReturnType<typeof replayApi.getReplayState>>>();
    const staleStart = deferred<Awaited<ReturnType<typeof replayApi.startReplay>>>();
    let stateCalls = 0;
    let controlSignal: AbortSignal | undefined;
    const replayRaceManifest = {
      ...manifest,
      scenarios: manifest.scenarios.filter((scenario) =>
        scenario.scenario_id === "MANUFACTURING_UNSAFE_REJECT" ||
        scenario.scenario_id === "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY"
      ),
    };
    const idleProjection = decodeReplayState(
      replayState(),
      "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    );
    const getReplayStateSpy = vi.spyOn(replayApi, "getReplayState")
      .mockImplementation(() => {
        stateCalls += 1;
        if (stateCalls === 1) return firstReplayRead.promise;
        if (stateCalls === 2) return secondReplayRead.promise;
        throw new Error("UNEXPECTED_REPLAY_STATE_REQUEST");
      });
    const startReplaySpy = vi.spyOn(replayApi, "startReplay")
      .mockImplementation((_payload, signal) => {
        controlSignal = signal;
        return staleStart.promise;
      });
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) {
        return Promise.resolve(jsonResponse(replayRaceManifest));
      }
      if (url.includes("/api/v1/status")) return Promise.resolve(jsonResponse(status));
      if (url.includes("/api/v1/replay/")) throw new Error("UNEXPECTED_REPLAY_FETCH");
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const selectScenario = async (name: string): Promise<void> => {
      fireEvent.click(
        screen.getByRole("combobox", { name: "Scenario" }),
      );
      fireEvent.click(
        await screen.findByRole("option", { name }),
      );
    };
    renderApp();
    await waitUntilReady();
    await selectScenario("Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(getReplayStateSpy).toHaveBeenCalledTimes(1));
    await act(async () => {
      firstReplayRead.resolve(idleProjection);
      await firstReplayRead.promise;
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
    });
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(startReplaySpy).toHaveBeenCalledTimes(1));
    expect(controlSignal).toBeDefined();
    expect(controlSignal?.aborted).toBe(false);
    await selectScenario("Manufacturing scenario 2");
    expect(controlSignal?.aborted).toBe(true);

    const staleFatal = new replayApi.ReplayApiRequestError(
      503,
      "REPLAY_VERSION_EXHAUSTED",
    );
    await act(async () => {
      staleStart.reject(staleFatal);
      await expect(staleStart.promise).rejects.toBe(staleFatal);
    });
    expect(screen.queryByText("Replay restart required")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Scenario" })).toHaveTextContent(
      "Manufacturing scenario 2",
    );

    await selectScenario("Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(getReplayStateSpy).toHaveBeenCalledTimes(2));
    await act(async () => {
      secondReplayRead.resolve(idleProjection);
      await secondReplayRead.promise;
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
    });
    expect(screen.queryByText("Replay restart required")).not.toBeInTheDocument();
  }, 10_000);

  it("ignores stale replay read version exhaustion after ownership revocation", async () => {
    const staleRead = deferred<Response>();
    let stateCalls = 0;
    let staleReadSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return Promise.resolve(jsonResponse(manifest));
      if (url.includes("/api/v1/status")) return Promise.resolve(jsonResponse(status));
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        if (stateCalls === 1) {
          staleReadSignal = init?.signal ?? undefined;
          return staleRead.promise;
        }
        return Promise.resolve(jsonResponse(replayState()));
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    renderApp();
    await waitUntilReady();
    fireEvent.click(screen.getByRole("combobox", { name: "Scenario" }));
    fireEvent.click(screen.getByRole("option", {
      name: "Frozen B2 pick/place evidence replay",
    }));
    await waitFor(() => expect(stateCalls).toBe(1));

    fireEvent.click(screen.getByRole("combobox", { name: "Scenario" }));
    fireEvent.click(screen.getByRole("option", { name: "Manufacturing scenario 2" }));
    expect(staleReadSignal?.aborted).toBe(true);
    await act(async () => {
      staleRead.resolve(jsonResponse({ code: "REPLAY_VERSION_EXHAUSTED" }, 503));
      await staleRead.promise;
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.queryByText("Replay restart required")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("combobox", { name: "Scenario" }));
    fireEvent.click(screen.getByRole("option", {
      name: "Frozen B2 pick/place evidence replay",
    }));
    await waitFor(() => expect(stateCalls).toBe(2));
    expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
    expect(screen.queryByText("Replay restart required")).not.toBeInTheDocument();
  }, 10_000);

  it("latches fatal for current owned replay mutation version exhaustion", async () => {
    let replayCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        replayCalls += 1;
        return jsonResponse(replayState());
      }
      if (url.includes("/api/v1/replay/start")) {
        replayCalls += 1;
        return jsonResponse({ code: "REPLAY_VERSION_EXHAUSTED" }, 503);
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Start" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Start" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Replay restart required");
      expect(screen.getByRole("alert")).toHaveTextContent("REPLAY_VERSION_EXHAUSTED");
    });
    ["Start", "Pause", "Resume", "Next snapshot", "Previous snapshot", "Stop", "Reset view"]
      .forEach((label) => expect(screen.getByRole("button", { name: label })).toBeDisabled());
    const callsAtFatalSettlement = replayCalls;
    vi.useFakeTimers();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(REPLAY_POLL_INTERVAL_MS * 2);
    });
    expect(replayCalls).toBe(callsAtFatalSettlement);
  }, 10_000);

  it("keeps replay polling single-flight and aborts the poll on unmount", async () => {
    const pendingPoll = deferred<Response>();
    let stateCalls = 0;
    let pollSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return Promise.resolve(jsonResponse(manifest));
      if (url.includes("/api/v1/status")) return Promise.resolve(jsonResponse(status));
      if (url.includes("/api/v1/replay/start")) return Promise.resolve(jsonResponse(pausedReplayState()));
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        if (stateCalls === 1) return Promise.resolve(jsonResponse(replayState()));
        pollSignal = init?.signal ?? undefined;
        return pendingPoll.promise;
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    const view = renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Start" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(stateCalls).toBe(2), { timeout: REPLAY_POLL_INTERVAL_MS + 1_500 });
    await new Promise((resolve) => setTimeout(resolve, REPLAY_POLL_INTERVAL_MS + 100));
    expect(stateCalls).toBe(2);
    view.unmount();
    expect(pollSignal?.aborted).toBe(true);
  });

  it("revokes an active replay read before mutation and ignores its late projection", async () => {
    const initialRead = deferred<Awaited<ReturnType<typeof replayApi.getReplayState>>>();
    const pendingPoll = deferred<Awaited<ReturnType<typeof replayApi.getReplayState>>>();
    const mutation = deferred<Response>();
    const initialProjection = decodeReplayState(
      pausedReplayState(),
      "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    );
    let readCalls = 0;
    let initialSignal: AbortSignal | undefined;
    let pollSignal: AbortSignal | undefined;
    let readWasAbortedBeforeMutation = false;
    const getReplayStateSpy = vi.spyOn(replayApi, "getReplayState")
      .mockImplementation((_scenarioId, signal) => {
        readCalls += 1;
        if (readCalls === 1) {
          initialSignal = signal;
          return initialRead.promise;
        }
        if (readCalls === 2) {
          pollSignal = signal;
          return pendingPoll.promise;
        }
        throw new Error("UNEXPECTED_REPLAY_STATE_REQUEST");
      });
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return Promise.resolve(jsonResponse(manifest));
      if (url.includes("/api/v1/status")) return Promise.resolve(jsonResponse(status));
      if (url.includes("/api/v1/replay/state")) throw new Error("UNEXPECTED_REPLAY_FETCH");
      if (url.includes("/api/v1/replay/control")) {
        readWasAbortedBeforeMutation = pollSignal?.aborted ?? false;
        return mutation.promise;
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    renderApp();
    await waitUntilReady();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("combobox", { name: "Scenario" }));

    const replayScenarioOption = screen.getByRole("option", {
      name: "Frozen B2 pick/place evidence replay",
    });

    fireEvent.click(replayScenarioOption);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(getReplayStateSpy).toHaveBeenCalledTimes(1);
    expect(readCalls).toBe(1);
    expect(initialSignal).toBeInstanceOf(AbortSignal);
    expect(initialSignal?.aborted).toBe(false);

    await act(async () => {
      initialRead.resolve(initialProjection);
      await initialRead.promise;
    });
    expect(screen.getByRole("button", { name: "Next snapshot" })).toBeEnabled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(REPLAY_POLL_INTERVAL_MS);
    });
    expect(getReplayStateSpy).toHaveBeenCalledTimes(2);
    expect(readCalls).toBe(2);
    expect(pollSignal).toBeInstanceOf(AbortSignal);
    expect(pollSignal?.aborted).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Next snapshot" }));
    expect(readWasAbortedBeforeMutation).toBe(true);
    expect(pollSignal?.aborted).toBe(true);
    const mutationProjection = pausedReplayState({
      control_version: 2,
      projection_version: 20,
      current_frame: {
        frame_index: 20,
        semantic_snapshot_index: 20,
        route_configuration_index: 20,
        route_state: "INTERPOLATED",
        phase: "CARRIED",
        boundary_snapshot: "NONE",
        is_key_snapshot: false,
      },
    });
    await act(async () => {
      mutation.resolve(jsonResponse(mutationProjection));
      await mutation.promise;
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Frame 21 of 469")).toBeInTheDocument();

    const staleProjection = decodeReplayState(
      pausedReplayState({
        control_version: 400,
        projection_version: 400,
        current_frame: {
          frame_index: 99,
          semantic_snapshot_index: 99,
          route_configuration_index: 99,
          route_state: "INTERPOLATED",
          phase: "CARRIED",
          boundary_snapshot: "NONE",
          is_key_snapshot: false,
        },
      }),
      "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    );
    await act(async () => {
      pendingPoll.resolve(staleProjection);
      await pendingPoll.promise;
    });
    expect(screen.getByText("Frame 21 of 469")).toBeInTheDocument();
    expect(screen.queryByText("Frame 100 of 469")).not.toBeInTheDocument();
    expect(getReplayStateSpy).toHaveBeenCalledTimes(2);
    expect(readCalls).toBe(2);
  });

  it("does not announce same-lifecycle frame polls but announces completion once", async () => {
    let stateCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        if (stateCalls === 1) return jsonResponse(playingReplayState());
        if (stateCalls === 2) {
          return jsonResponse(playingReplayState({
            projection_version: 3,
            current_frame: {
              frame_index: 20,
              semantic_snapshot_index: 20,
              route_configuration_index: 20,
              route_state: "INTERPOLATED",
              phase: "CARRIED",
              boundary_snapshot: "NONE",
              is_key_snapshot: false,
            },
          }));
        }
        return jsonResponse(pausedReplayState({
          control_version: 3,
          projection_version: 4,
          lifecycle_state: "COMPLETED",
          current_frame: {
            frame_index: 468,
            semantic_snapshot_index: 468,
            route_configuration_index: 466,
            route_state: "HOME",
            phase: "DESTINATION_SUPPORTED",
            boundary_snapshot: "NONE",
            is_key_snapshot: true,
          },
          available_controls: ["PREVIOUS_SNAPSHOT", "STOP", "RESET_VIEW"],
        }));
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    const view = renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    const liveRegion = view.container.querySelector(".replay-live-region");
    await waitFor(() => expect(liveRegion).toHaveTextContent("Evidence replay playing, frame 11 of 469"));
    const initialAnnouncement = liveRegion?.textContent;
    await waitFor(() => expect(screen.getByText("Frame 21 of 469")).toBeInTheDocument(), {
      timeout: REPLAY_POLL_INTERVAL_MS + 1_500,
    });
    expect(liveRegion?.textContent).toBe(initialAnnouncement);
    await waitFor(() => expect(screen.getByText("Frame 469 of 469")).toBeInTheDocument(), {
      timeout: REPLAY_POLL_INTERVAL_MS + 1_500,
    });
    expect(liveRegion).toHaveTextContent("Evidence replay completed, frame 469 of 469");
    view.unmount();
  });

  it("rejects a mutation response from another session without scheduling from it", async () => {
    let stateCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        return jsonResponse(pausedReplayState());
      }
      if (url.includes("/api/v1/replay/control")) {
        return jsonResponse(pausedReplayState({
          session_id: "opaque-session-s2",
          control_version: 400,
          projection_version: 400,
        }));
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Next snapshot" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Next snapshot" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("CONTRACT_FAILURE"));
    const callsAfterRejection = stateCalls;
    await new Promise((resolve) => setTimeout(resolve, REPLAY_POLL_INTERVAL_MS + 100));
    expect(stateCalls).toBe(callsAfterRejection);
  });

  it("rejects a lower same-session poll without regressing the accepted projection", async () => {
    let stateCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        stateCalls += 1;
        if (stateCalls === 1) {
          return jsonResponse(playingReplayState({
            session_id: "opaque-session-s2",
            control_version: 10,
            projection_version: 10,
          }));
        }
        return jsonResponse(playingReplayState({
          session_id: "opaque-session-s2",
          control_version: 9,
          projection_version: 9,
          current_frame: {
            frame_index: 0,
            semantic_snapshot_index: 0,
            route_configuration_index: 0,
            route_state: "HOME",
            phase: "SOURCE_SUPPORTED",
            boundary_snapshot: "NONE",
            is_key_snapshot: true,
          },
        }));
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    const view = renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByText("Frame 11 of 469")).toBeInTheDocument());
    await waitFor(() => expect(stateCalls).toBe(2), {
      timeout: REPLAY_POLL_INTERVAL_MS + 1_500,
    });
    expect(screen.getByText("Frame 11 of 469")).toBeInTheDocument();
    view.unmount();
  });

  it("renders COMPLETED as the final frozen frame rather than execution success", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        return jsonResponse(pausedReplayState({
          control_version: 9,
          projection_version: 469,
          lifecycle_state: "COMPLETED",
          current_frame: {
            frame_index: 468,
            semantic_snapshot_index: 468,
            route_configuration_index: 466,
            route_state: "HOME",
            phase: "DESTINATION_SUPPORTED",
            boundary_snapshot: "NONE",
            is_key_snapshot: true,
          },
          available_controls: ["PREVIOUS_SNAPSHOT", "STOP", "RESET_VIEW"],
        }));
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByText("Frame 469 of 469")).toBeInTheDocument());
    expect(screen.getByText(/COMPLETED means only/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous snapshot" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
  });

  it("propagates STOP CAS ownership and accepts canonical IDLE", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) return jsonResponse(pausedReplayState());
      if (url.includes("/api/v1/replay/control")) return jsonResponse(replayState());
      throw new Error("UNEXPECTED_REQUEST");
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Start" })).toBeEnabled());
    const call = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/replay/control"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      scenario_id: "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
      session_id: "opaque-session-s1",
      expected_control_version: 1,
      control: "STOP",
    });
  }, 10_000);

  it.each([
    ["FAILED", "REPLAY_RUNTIME_INTEGRITY_FAILED"],
    ["CLEANUP_FAILED", "REPLAY_CLEANUP_UNRESOLVED"],
  ] as const)("renders retained %s recovery using server-projected STOP only", async (lifecycle, lastError) => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/demo/manifest")) return jsonResponse(manifest);
      if (url.includes("/api/v1/status")) return jsonResponse(status);
      if (url.includes("/api/v1/replay/state")) {
        return jsonResponse(pausedReplayState({
          lifecycle_state: lifecycle,
          current_frame: null,
          available_controls: ["STOP"],
          last_error_code: lastError,
        }));
      }
      throw new Error("UNEXPECTED_REQUEST");
    }));
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await chooseScenario(user, "Frozen B2 pick/place evidence replay");
    await waitFor(() => expect(screen.getByText(lastError)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Stop" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
  });

});
