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
  App,
  BOOTSTRAP_CLIENT_DEADLINE_MS,
  GOVERNANCE_CLIENT_DEADLINE_MS,
  SPEECH_CLIENT_DEADLINE_MS,
  clientErrorMessage,
  selectInferenceMode,
} from "../src/App";

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
      screen.getByRole("button", { name: "Microphone available in V2" }),
    ).toBeDisabled();
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
    expect(rows[3]).toHaveTextContent("NOT REQUESTED — NOT ENABLED IN D2");
    expect(rows[3]).toHaveTextContent("Policy: PROHIBITED");
    expect(rows[5]).toHaveTextContent("NOT_IMPLEMENTED");
    expect(
      screen.getByText("Passing layer N does not establish layer N+1."),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Available")).toBeInTheDocument());
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
    expect(rows[3]).toHaveTextContent("NOT REQUESTED — NOT ENABLED IN D2");
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
    expect(rows[3]).toHaveTextContent("NOT REQUESTED — NOT ENABLED IN D2");
    expect(rows[3]).toHaveTextContent("Policy: SERVER_REGISTERED_ONLY");
    expect(rows[3]).toHaveTextContent("Capability class: FROZEN_B2_REPLAY_COMPATIBLE");
    expect(rows[3]).not.toHaveTextContent("GRANTED");
    expect(rows[4]).toHaveTextContent("FAIL");
    expect(rows[4]).toHaveTextContent("Independent of the governance decision");
    expect(rows[5]).toHaveTextContent("NOT_IMPLEMENTED");
    expect(screen.queryByRole("button", { name: /replay/i })).not.toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
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

  it("keeps AbortError silent when governance is intentionally superseded", async () => {
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
    expect(screen.getByText("CLIENT_TIMEOUT")).toBeInTheDocument();
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByText("PROVIDER_TIMEOUT")).not.toBeInTheDocument();
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
    expect(
      screen.getByText("Status unavailable: CLIENT_TIMEOUT"),
    ).toBeInTheDocument();
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

  it("keeps transcription B when A settles late with an error", async () => {
    const requestA = deferred<Response>();
    const requestB = deferred<Response>();
    const fetchMock = deferredFetch({ speech: [requestA, requestB] });
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    const input = screen.getByLabelText("Recorded WAV file");
    await user.upload(
      input,
      new File([new Uint8Array([1])], "a.wav", { type: "audio/wav" }),
    );
    await user.upload(
      input,
      new File([new Uint8Array([2])], "b.wav", { type: "audio/wav" }),
    );
    const speechCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/api/v1/speech/recorded"),
    );
    expect(speechCalls[0]?.[1]?.signal?.aborted).toBe(true);
    expect(speechCalls[1]?.[1]?.signal?.aborted).toBe(false);

    await act(async () => {
      requestB.resolve(
        jsonResponse(transcriptionWith("transcript-b", "Transcript B", "b.wav")),
      );
      await requestB.promise;
    });
    await waitFor(() => expect(screen.getByText("b.wav · 860.0 ms")).toBeInTheDocument());
    await act(async () => {
      requestA.reject(new TypeError("stale network failure"));
      try {
        await requestA.promise;
      } catch {
        // The stale rejection is expected and must not own UI state.
      }
    });
    expect(
      screen.getByRole("textbox", { name: "Operator command" }),
    ).toHaveValue("Transcript B");
    expect(screen.queryByText("Transcription failed")).not.toBeInTheDocument();
  });

  it("clears a READY transcript when the scenario changes", async () => {
    const user = userEvent.setup();
    renderApp();
    await waitUntilReady();
    await user.upload(
      screen.getByLabelText("Recorded WAV file"),
      new File([new Uint8Array([1])], "scenario.wav", { type: "audio/wav" }),
    );
    await screen.findByText("Nemotron transcript");
    await chooseScenario(user, "Manufacturing scenario 2");

    expect(screen.queryByText("Nemotron transcript")).not.toBeInTheDocument();
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
    await screen.findByText("Nemotron transcript");
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
    await screen.findByText("Nemotron transcript");
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
    await screen.findByText("Nemotron transcript");
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

});
