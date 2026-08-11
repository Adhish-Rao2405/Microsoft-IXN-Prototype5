import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  ContractValidationError,
  decodeDemoManifest,
  decodeDemoStatus,
  decodeGovernanceResult,
  decodeRecordedTranscription,
} from "../src/runtimeContracts";
import { ApiRequestError, getDemoStatus } from "../src/api";

const authority = [
  "UNTRUSTED_PROPOSAL",
  "GOVERNANCE_DECISION",
  "EXECUTION_ELIGIBILITY",
  "QUALIFICATION_REPLAY_ACCESS",
  "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
  "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
];

const RAW_MOVE_RESPONSE =
  '{"actions":[{"action":"MOVE","object_id":"blue_component","source_id":"input_tray_a","destination_id":"assembly_fixture_b","duration_ms":null}]}';
const RAW_MOVE_RESPONSE_SHA256 =
  "7cfabaee94153f7cbc5176cc888666da70968290fe7f240cc5ff5b1597df501a";

function scenario(index: number) {
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
  const replay = index === 9;
  const live = index < 5;
  return {
    scenario_id: identifiers[index],
    display_name: `Scenario ${index}`,
    presentation_classification: replay
      ? "FROZEN_EVIDENCE_REPLAY"
      : live
        ? "SYNTHETIC_LIVE_DEMO"
        : "FROZEN_RESEARCH_EVIDENCE",
    model_input_enabled: live,
    allowed_inference_modes: live ? ["LOCAL", "CLOUD", "AUTO"] : [],
    registered_command: `Command ${index}`,
    demonstration_purpose: `Purpose ${index}`,
    evidence_classification: replay
      ? "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION"
      : live
        ? "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE"
        : "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT",
    replay_capability_classification: replay
      ? "FROZEN_B2_REPLAY_COMPATIBLE"
      : "GOVERNANCE_ONLY",
    qualification_replay_access: replay ? "SERVER_REGISTERED_ONLY" : "PROHIBITED",
    downstream_geometric_qualification: replay ? "FAIL" : "NOT_APPLICABLE",
    claim_boundary_note: "No physical execution authority.",
  };
}

function manifest() {
  return {
    contract_id: "PROTOTYPE5_FINAL_DEMONSTRATOR_D0",
    contract_version: "1.0.0",
    authority_taxonomy: [...authority],
    physical_execution_authority_state: "NOT_IMPLEMENTED",
    healthcare_scope: "OUT_OF_SCOPE_FOR_FINAL_DEMO",
    d2_replay_enabled: false,
    scenarios: Array.from({ length: 10 }, (_, index) => scenario(index)),
  };
}

function health() {
  return {
    circuit_state: "CLOSED",
    local_available: true,
    local_model_ready: true,
    consecutive_failures: 0,
    rolling_sample_count: 1,
    rolling_structured_success_rate: 1,
    rolling_p50_latency_ms: 15,
    rolling_p95_latency_ms: 15,
    last_failure_reason: "NONE",
    last_circuit_transition: null,
  };
}

function status() {
  return {
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
    local_health: health(),
  };
}

function governance() {
  return {
    routing_policy_id: "policy",
    routing_policy_version: "1.0.0",
    routing_policy_sha256: "d".repeat(64),
    local_health: health(),
    canonical_result: {
      request: {
        input_mode: "TYPED", typed_text: "Move.", transcription_id: null,
        original_transcript_text: null, transcript_text: null,
        transcript_status: "NOT_APPLICABLE", transcript_backend: null,
        transcript_confidence: null, audio_sha256: null,
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
        actions: [{
          action: "MOVE",
          object_id: "blue_component",
          source_id: "input_tray_a",
          destination_id: "assembly_fixture_b",
          duration_ms: null,
        }],
      },
      governance_record: {
        record_id: "record-1",
        trace_id: "trace-1",
        timestamp_utc: "2026-07-30T12:00:00+00:00",
        evaluation_mode: "LIVE",
        input_mode: "TYPED",
        normalised_command: "Move.",
        typed_text: "Move.",
        transcription_id: null,
        original_transcript_text: null,
        transcript_text: null,
        transcript_status: "NOT_APPLICABLE",
        transcript_backend: null,
        transcript_confidence: null,
        audio_sha256: null,
        domain_id: "MANUFACTURING",
        benchmark_id: null,
        policy_id: "policy",
        oracle_version: null,
        evidence_schema_version: "2.0.0",
        routing: {
          requested_mode: "AUTO",
          selected_provider: "FOUNDRY_LOCAL",
          selected_model: "local-model",
          local_attempted: true,
          cloud_attempted: false,
          fallback_triggered: false,
          fallback_reason: "NONE",
          local_latency_ms: 15,
          cloud_latency_ms: null,
        },
        raw_response_sha256: RAW_MOVE_RESPONSE_SHA256,
        raw_response_present: true,
        provider_latency_ms: 15,
        parse_status: "PASSED",
        json_status: "PASSED",
        schema_status: "PASSED",
        plan_semantic_status: "VALID",
        ambiguity_status: "PASSED",
        safety_status: "PASSED",
        authority_status: "PASSED",
        gate_reasons: [{ gate: "PARSE", reason_codes: ["PARSE_OK"] }],
        gate_latencies: [{ gate: "PARSE", latency_ms: 1 }],
        expected_decision: null,
        decision_correctness_status: "NOT_EVALUATED",
        final_decision: "ACCEPT",
        execution_eligible: true,
        decision_reason_codes: ["ALL_REQUIRED_GATES_PASSED"],
        validation_latency_ms: 2,
        total_pipeline_latency_ms: 17,
        execution_permit_id: null,
        simulation_status: "NOT_REQUESTED",
        provenance: {
          source_repository: "repository", software_commit: "a".repeat(40),
          prompt_id: "prompt", prompt_version: "2.0.0",
          model_provider: "FOUNDRY_LOCAL", model_id: "local-model",
          benchmark_sha256: null, oracle_sha256: null,
          policy_sha256: "f".repeat(64),
        },
      },
    },
  };
}

function transcription() {
  return {
    result_schema_version: "1.0.0",
    transcription_id: "transcription-1",
    timestamp_utc: "2026-07-31T12:00:00Z",
    transcript_status: "READY",
    transcript_text: "Move.",
    transcript_backend: "foundry_nemotron",
    transcript_confidence: null,
    audio: {
      original_filename: "operator.wav",
      audio_sha256: "b".repeat(64),
      audio_bytes: 10,
      sample_rate_hz: 16000,
      channels: 1,
      bits_per_sample: 16,
      frame_count: 10,
      duration_ms: 1,
    },
    requested_model_alias: "nemotron-speech-streaming-en-0.6b",
    resolved_model_id: "nemotron-speech-streaming-en-0.6b-generic-cpu:3",
    execution_provider: "CPUExecutionProvider",
    sdk_distribution: "sdk",
    sdk_version: "1",
    core_distribution: "core",
    core_version: "1",
    model_cached_before: true,
    model_loaded_before: false,
    model_downloaded_for_request: false,
    model_loaded_for_request: true,
    model_unloaded_after_request: true,
    segment_count: 1,
    transcription_latency_ms: 10,
    error_code: null,
    error_detail: null,
  };
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

describe("runtime network contracts", () => {
  it("accepts the canonical manifest, status, governance and transcription shapes", () => {
    expect(decodeDemoManifest(manifest()).scenarios).toHaveLength(10);
    expect(decodeDemoStatus(status()).service_status).toBe("READY");
    expect(decodeGovernanceResult(governance()).canonical_result.governance_record.execution_eligible).toBe(true);
    expect(decodeRecordedTranscription(transcription()).transcript_status).toBe("READY");
  });

  it("uses a mechanically coherent raw-response fixture", () => {
    const value = governance();
    expect(JSON.parse(RAW_MOVE_RESPONSE)).toEqual(value.canonical_result.proposal);
    expect(createHash("sha256").update(RAW_MOVE_RESPONSE).digest("hex")).toBe(
      RAW_MOVE_RESPONSE_SHA256,
    );
  });

  it.each([null, true, 1, "manifest", []])("rejects non-object manifest root %j", (value) => {
    expect(() => decodeDemoManifest(value)).toThrow(ContractValidationError);
  });

  it("rejects an empty object and missing physical-authority state", () => {
    expect(() => decodeDemoManifest({})).toThrow(ContractValidationError);
    const value = manifest();
    delete (value as Partial<typeof value>).physical_execution_authority_state;
    expect(() => decodeDemoManifest(value)).toThrow(ContractValidationError);
  });

  it("rejects unexpected critical manifest keys and malformed scenarios", () => {
    expect(() => decodeDemoManifest({ ...manifest(), artifact_path: "secret" })).toThrow(ContractValidationError);
    const value = manifest();
    value.scenarios[0].model_input_enabled = false;
    expect(() => decodeDemoManifest(value)).toThrow(ContractValidationError);
  });

  it("rejects missing, unknown and duplicate authority or scenario identities", () => {
    const wrongAuthority = manifest();
    wrongAuthority.authority_taxonomy[0] = "GOVERNANCE_DECISION";
    expect(() => decodeDemoManifest(wrongAuthority)).toThrow(ContractValidationError);
    const duplicate = manifest();
    duplicate.scenarios[1].scenario_id = duplicate.scenarios[0].scenario_id;
    expect(() => decodeDemoManifest(duplicate)).toThrow(ContractValidationError);
  });

  it("rejects unknown availability, inference mode and wrong status primitives", () => {
    const unknownStatus = status();
    unknownStatus.local_status = "READY";
    expect(() => decodeDemoStatus(unknownStatus)).toThrow(ContractValidationError);
    const unknownMode = status();
    unknownMode.supported_inference_modes[0] = "EDGE";
    expect(() => decodeDemoStatus(unknownMode)).toThrow(ContractValidationError);
    const wrongBoolean = status();
    (wrongBoolean.local_health as { local_available: unknown }).local_available = "true";
    expect(() => decodeDemoStatus(wrongBoolean)).toThrow(ContractValidationError);
  });

  it("rejects malformed SHA and unexpected status fields", () => {
    expect(() => decodeDemoStatus({ ...status(), software_commit: "bad" })).toThrow(ContractValidationError);
    expect(() => decodeDemoStatus({ ...status(), physical_authority: "IMPLEMENTED" })).toThrow(ContractValidationError);
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, -1])("rejects invalid governance latency %s", (latency) => {
    const value = governance();
    value.canonical_result.governance_record.provider_latency_ms = latency;
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("rejects unknown provider, inference mode, decision and gate status", () => {
    for (const [field, invalid] of [["selected_provider", "EDGE"], ["requested_mode", "EDGE"]] as const) {
      const value = governance();
      value.canonical_result.governance_record.routing[field] = invalid;
      expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
    }
    const decision = governance();
    decision.canonical_result.governance_record.final_decision = "APPROVED";
    expect(() => decodeGovernanceResult(decision)).toThrow(ContractValidationError);
    const gate = governance();
    gate.canonical_result.governance_record.safety_status = "SAFE";
    expect(() => decodeGovernanceResult(gate)).toThrow(ContractValidationError);
  });

  it("rejects duplicate reason codes and duplicate gate rows", () => {
    const reasons = governance();
    reasons.canonical_result.governance_record.decision_reason_codes.push("ALL_REQUIRED_GATES_PASSED");
    expect(() => decodeGovernanceResult(reasons)).toThrow(ContractValidationError);
    const gates = governance();
    gates.canonical_result.governance_record.gate_reasons.push({ gate: "PARSE", reason_codes: ["AGAIN"] });
    expect(() => decodeGovernanceResult(gates)).toThrow(ContractValidationError);
  });

  it("rejects contradictory decision eligibility and failed mandatory gates", () => {
    const rejected = governance();
    rejected.canonical_result.governance_record.final_decision = "REJECT";
    expect(() => decodeGovernanceResult(rejected)).toThrow(ContractValidationError);
    const acceptedButIneligible = governance();
    acceptedButIneligible.canonical_result.governance_record.execution_eligible = false;
    expect(() => decodeGovernanceResult(acceptedButIneligible)).toThrow(ContractValidationError);
    const failed = governance();
    failed.canonical_result.governance_record.safety_status = "FAILED";
    expect(() => decodeGovernanceResult(failed)).toThrow(ContractValidationError);
  });

  it("rejects unknown fallback reason", () => {
    const value = governance();
    value.canonical_result.governance_record.routing.fallback_reason = "UNKNOWN";
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("rejects malformed governance roots, missing keys and critical extras", () => {
    expect(() => decodeGovernanceResult(null)).toThrow(ContractValidationError);
    const missing = governance();
    delete (missing.canonical_result as Partial<typeof missing.canonical_result>).governance_record;
    expect(() => decodeGovernanceResult(missing)).toThrow(ContractValidationError);
    expect(() => decodeGovernanceResult({ ...governance(), physical_execution_authority: true })).toThrow(ContractValidationError);
  });

  it("rejects non-finite and wrong transcription primitives", () => {
    const nonfinite = transcription();
    nonfinite.transcription_latency_ms = Number.POSITIVE_INFINITY;
    expect(() => decodeRecordedTranscription(nonfinite)).toThrow(ContractValidationError);
    const wrong = transcription();
    (wrong as { model_loaded_for_request: unknown }).model_loaded_for_request = 1;
    expect(() => decodeRecordedTranscription(wrong)).toThrow(ContractValidationError);
  });

  it("classifies malformed successful JSON as a contract failure", async () => {
    const fetchMock = () => Promise.resolve(new Response("not-json", { status: 200 }));
    const original = globalThis.fetch;
    globalThis.fetch = fetchMock;
    try {
      await expect(getDemoStatus()).rejects.toBeInstanceOf(ContractValidationError);
    } finally {
      globalThis.fetch = original;
    }
  });

  it("classifies malformed 2xx payloads as contract failures", async () => {
    const fetchMock = () => Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    const original = globalThis.fetch;
    globalThis.fetch = fetchMock;
    try {
      await expect(getDemoStatus()).rejects.toBeInstanceOf(ContractValidationError);
    } finally {
      globalThis.fetch = original;
    }
  });

  it("bounds non-JSON HTTP errors without exposing response text", async () => {
    const fetchMock = () => Promise.resolve(new Response("<h1>secret</h1>", { status: 500 }));
    const original = globalThis.fetch;
    globalThis.fetch = fetchMock;
    try {
      await expect(getDemoStatus()).rejects.toMatchObject({
        name: "ApiRequestError",
        code: "HTTP_ERROR",
        message: "HTTP_500",
      } satisfies Partial<ApiRequestError>);
    } finally {
      globalThis.fetch = original;
    }
  });
  it("does not encode the canonical D0 scenario registry in production TypeScript", () => {
    const source = readFileSync(
      resolve(process.cwd(), "src/runtimeContracts.ts"),
      "utf8",
    );
    expect(source).not.toContain("const SCENARIO_IDS");
    expect(source).not.toContain("MANUFACTURING_TYPED_ACCEPT");
    expect(source).not.toContain("FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY");
  });

  it("derives unique structurally valid scenario identities from the manifest", () => {
    const value = manifest();
    value.scenarios.forEach((item, index) => {
      item.scenario_id = `SERVER_SCENARIO_${index}`;
    });
    expect(decodeDemoManifest(value).scenarios.map((item) => item.scenario_id)).toEqual(
      value.scenarios.map((item) => item.scenario_id),
    );

    const empty = manifest();
    empty.scenarios = [];
    expect(() => decodeDemoManifest(empty)).toThrow(ContractValidationError);
  });

  it.each(["REJECT", "CLARIFY", "ERROR"])(
    "rejects all-pass %s records that claim ineligibility",
    (decision) => {
      const value = governance();
      value.canonical_result.governance_record.final_decision = decision;
      value.canonical_result.governance_record.execution_eligible = false;
      expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
    },
  );

  it("rejects structural gate-propagation contradictions", () => {
    const value = governance();
    value.canonical_result.governance_record.parse_status = "FAILED";
    value.canonical_result.governance_record.final_decision = "REJECT";
    value.canonical_result.governance_record.execution_eligible = false;
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("rejects permit, simulation and latency relationships forbidden by the backend contract", () => {
    const permit = governance();
    permit.canonical_result.governance_record.safety_status = "FAILED";
    permit.canonical_result.governance_record.final_decision = "REJECT";
    permit.canonical_result.governance_record.execution_eligible = false;
    (permit.canonical_result.governance_record as {
      execution_permit_id: string | null;
    }).execution_permit_id = "permit-1";
    expect(() => decodeGovernanceResult(permit)).toThrow(ContractValidationError);

    const simulation = governance();
    simulation.canonical_result.governance_record.simulation_status = "RUNNING";
    expect(() => decodeGovernanceResult(simulation)).toThrow(ContractValidationError);

    const latency = governance();
    latency.canonical_result.governance_record.total_pipeline_latency_ms = 1;
    expect(() => decodeGovernanceResult(latency)).toThrow(ContractValidationError);
  });

  it("accepts explicit nullable action fields and rejects their omission", () => {
    expect(decodeGovernanceResult(governance()).canonical_result.proposal?.actions[0].duration_ms).toBeNull();
    const value = governance();
    delete (value.canonical_result.proposal.actions[0] as Partial<{
      duration_ms: number | null;
    }>).duration_ms;
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it.each([
    ["MOVE missing an entity", { action: "MOVE", object_id: null, source_id: "input_tray_a", destination_id: "assembly_fixture_b", duration_ms: null }],
    ["fractional WAIT", { action: "WAIT", object_id: null, source_id: null, destination_id: null, duration_ms: 1.5 }],
    ["zero WAIT", { action: "WAIT", object_id: null, source_id: null, destination_id: null, duration_ms: 0 }],
    ["overlong WAIT", { action: "WAIT", object_id: null, source_id: null, destination_id: null, duration_ms: 60_001 }],
    ["STOP carrying an entity", { action: "STOP", object_id: "blue_component", source_id: null, destination_id: null, duration_ms: null }],
    ["invalid entity identifier", { action: "MOVE", object_id: "Blue-Component", source_id: "input_tray_a", destination_id: "assembly_fixture_b", duration_ms: null }],
  ])("rejects ActionStepV2-invalid %s", (_label, action) => {
    const value = governance();
    (value.canonical_result.proposal as { actions: unknown[] }).actions = [action];
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it.each([
    ["multiple STOP actions", [
      { action: "STOP", object_id: null, source_id: null, destination_id: null, duration_ms: null },
      { action: "STOP", object_id: null, source_id: null, destination_id: null, duration_ms: null },
    ]],
    ["non-terminal STOP", [
      { action: "STOP", object_id: null, source_id: null, destination_id: null, duration_ms: null },
      { action: "MOVE", object_id: "blue_component", source_id: "input_tray_a", destination_id: "assembly_fixture_b", duration_ms: null },
    ]],
  ])("rejects %s", (_label, actions) => {
    const value = governance();
    (value.canonical_result.proposal as { actions: unknown[] }).actions = actions;
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("binds proposal presence to the structural gate conjunction", () => {
    const missing = governance();
    (missing.canonical_result as { proposal: unknown }).proposal = null;
    expect(() => decodeGovernanceResult(missing)).toThrow(ContractValidationError);

    const impossible = governance();
    impossible.canonical_result.governance_record.schema_status = "FAILED";
    impossible.canonical_result.governance_record.plan_semantic_status = "NOT_ASSESSABLE_SCHEMA_INVALID";
    impossible.canonical_result.governance_record.final_decision = "REJECT";
    impossible.canonical_result.governance_record.execution_eligible = false;
    expect(() => decodeGovernanceResult(impossible)).toThrow(ContractValidationError);
  });

  it("rejects typed canonical requests containing voice provenance", () => {
    const value = governance();
    (value.canonical_result.request as unknown as Record<string, unknown>).transcription_id = "transcription-1";
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("rejects canonical voice requests that are not reviewed READY input", () => {
    const value = governance();
    Object.assign(value.canonical_result.request, {
      input_mode: "VOICE",
      typed_text: null,
      transcription_id: "transcription-1",
      original_transcript_text: "Move.",
      transcript_text: "Move.",
      transcript_status: "PARTIAL",
      transcript_backend: "foundry_nemotron",
      transcript_confidence: null,
      audio_sha256: "b".repeat(64),
    });
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("binds canonical LIVE and EVALUATION requests to oracle metadata", () => {
    const live = governance();
    (live.canonical_result.request as unknown as Record<string, unknown>).benchmark_id = "benchmark";
    expect(() => decodeGovernanceResult(live)).toThrow(ContractValidationError);

    const evaluation = governance();
    (evaluation.canonical_result.request as unknown as Record<string, unknown>).evaluation_mode = "EVALUATION";
    expect(() => decodeGovernanceResult(evaluation)).toThrow(ContractValidationError);
  });

  it("rejects non-UTC governance timestamps and blank selected models", () => {
    const timestamp = governance();
    timestamp.canonical_result.governance_record.timestamp_utc = "2026-07-30T12:00:00";
    expect(() => decodeGovernanceResult(timestamp)).toThrow(ContractValidationError);

    const model = governance();
    model.canonical_result.governance_record.routing.selected_model = "   ";
    model.canonical_result.governance_record.provenance.model_id = "   ";
    expect(() => decodeGovernanceResult(model)).toThrow(ContractValidationError);
  });

  it("requires nonempty stable gate and decision reason codes", () => {
    const empty = governance();
    empty.canonical_result.governance_record.gate_reasons[0].reason_codes = [];
    expect(() => decodeGovernanceResult(empty)).toThrow(ContractValidationError);

    const gate = governance();
    gate.canonical_result.governance_record.gate_reasons[0].reason_codes = ["bad-code"];
    expect(() => decodeGovernanceResult(gate)).toThrow(ContractValidationError);

    const decision = governance();
    decision.canonical_result.governance_record.decision_reason_codes = ["bad-code"];
    expect(() => decodeGovernanceResult(decision)).toThrow(ContractValidationError);
  });

  it.each([
    ["confidence above one", { transcript_confidence: 1.1 }],
    ["wrong backend", { transcript_backend: "attacker_backend" }],
    ["wrong alias", { requested_model_alias: "arbitrary-model" }],
    ["wrong resolved model", { resolved_model_id: "arbitrary-model" }],
  ])("rejects transcription with %s", (_label, mutation) => {
    const value = transcription();
    Object.assign(value, mutation);
    expect(() => decodeRecordedTranscription(value)).toThrow(ContractValidationError);
  });

  it("requires completed transcription to observe a loaded model", () => {
    const value = transcription();
    value.model_loaded_before = false;
    value.model_loaded_for_request = false;
    expect(() => decodeRecordedTranscription(value)).toThrow(ContractValidationError);
  });

  it("rejects READY transcription carrying an error code", () => {
    const value = transcription();
    (value as unknown as Record<string, unknown>).error_code = "UNEXPECTED_ERROR";
    expect(() => decodeRecordedTranscription(value)).toThrow(ContractValidationError);
  });

  it.each(["FAILED", "BACKEND_UNAVAILABLE"])(
    "requires %s transcription to carry an error code",
    (statusValue) => {
      const value = transcription();
      Object.assign(value, {
        transcript_status: statusValue,
        transcript_text: null,
        error_code: null,
      });
      expect(() => decodeRecordedTranscription(value)).toThrow(ContractValidationError);
    },
  );

  it("requires EMPTY transcription to carry TRANSCRIPT_EMPTY", () => {
    const value = transcription();
    Object.assign(value, {
      transcript_status: "EMPTY",
      transcript_text: null,
      error_code: null,
    });
    expect(() => decodeRecordedTranscription(value)).toThrow(ContractValidationError);
  });

  it("rejects unsafe transcription bounds and filename paths", () => {
    const identifier = transcription();
    identifier.transcription_id = "x".repeat(201);
    expect(() => decodeRecordedTranscription(identifier)).toThrow(ContractValidationError);

    const timestamp = transcription();
    timestamp.timestamp_utc = "2026-07-31T12:00:00+01:00";
    expect(() => decodeRecordedTranscription(timestamp)).toThrow(ContractValidationError);

    const impossibleDate = transcription();
    impossibleDate.timestamp_utc = "2026-02-30T12:00:00Z";
    expect(() => decodeRecordedTranscription(impossibleDate)).toThrow(ContractValidationError);

    const segments = transcription();
    segments.segment_count = 1001;
    expect(() => decodeRecordedTranscription(segments)).toThrow(ContractValidationError);

    const detail = transcription();
    (detail as unknown as Record<string, unknown>).error_detail = "x".repeat(501);
    expect(() => decodeRecordedTranscription(detail)).toThrow(ContractValidationError);

    const filename = transcription();
    filename.audio.original_filename = "directory/operator.wav";
    expect(() => decodeRecordedTranscription(filename)).toThrow(ContractValidationError);

    const driveRelativeFilename = transcription();
    driveRelativeFilename.audio.original_filename = "C:operator.wav";
    expect(() => decodeRecordedTranscription(driveRelativeFilename)).toThrow(ContractValidationError);
  });

  it.each([
    [0, "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT"],
    [5, "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE"],
    [9, "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT"],
  ])("rejects contradictory evidence classification for scenario %i", (index, classification) => {
    const value = manifest();
    value.scenarios[index].evidence_classification = classification;
    expect(() => decodeDemoManifest(value)).toThrow(ContractValidationError);
  });

  it("requires live scenarios to expose the exact ordered inference-mode tuple", () => {
    const value = manifest();
    value.scenarios[0].allowed_inference_modes = ["LOCAL"];
    expect(() => decodeDemoManifest(value)).toThrow(ContractValidationError);
  });

  it("rejects PARTIAL governance records that invoked a provider", () => {
    const value = governance();
    Object.assign(value.canonical_result.governance_record, {
      input_mode: "VOICE",
      typed_text: null,
      transcription_id: "transcription-1",
      original_transcript_text: "Move.",
      transcript_text: "Move.",
      transcript_status: "PARTIAL",
      transcript_backend: "foundry_nemotron",
      transcript_confidence: null,
      audio_sha256: "b".repeat(64),
      normalised_command: "Move.",
    });
    expect(() => decodeGovernanceResult(value)).toThrow(
      /non-READY voice input invoked inference provider/,
    );
  });

  it.each([
    ["object_id", "Blue-Component"],
    ["location_id", "input tray"],
  ] as const)("rejects malformed canonical scene %s", (field, malformed) => {
    const value = governance();
    value.canonical_result.request.scene.objects[0][field] = malformed;
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("rejects duplicate canonical scene object identifiers", () => {
    const value = governance();
    value.canonical_result.request.scene.objects.push({
      object_id: "blue_component",
      location_id: "assembly_fixture_b",
    });
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it("rejects malformed canonical requester identifiers", () => {
    const value = governance();
    value.canonical_result.request.requester.requester_id = "Synthetic Operator";
    expect(() => decodeGovernanceResult(value)).toThrow(ContractValidationError);
  });

  it.each([
    "display_name",
    "registered_command",
    "demonstration_purpose",
    "claim_boundary_note",
  ] as const)("rejects whitespace-only manifest %s", (field) => {
    const value = manifest();
    value.scenarios[0][field] = "   ";
    expect(() => decodeDemoManifest(value)).toThrow(ContractValidationError);
  });

  it("rejects year zero in UTC timestamps", () => {
    const governanceValue = governance();
    governanceValue.canonical_result.governance_record.timestamp_utc =
      "0000-01-01T00:00:00Z";
    expect(() => decodeGovernanceResult(governanceValue)).toThrow(
      ContractValidationError,
    );

    const transcriptionValue = transcription();
    transcriptionValue.timestamp_utc = "0000-01-01T00:00:00Z";
    expect(() => decodeRecordedTranscription(transcriptionValue)).toThrow(
      ContractValidationError,
    );
  });

  it("rejects canonical-request and routing inference-mode drift", () => {
    const value = governance();
    value.canonical_result.request.requested_inference_mode = "LOCAL";
    expect(() => decodeGovernanceResult(value)).toThrow(
      /canonical request and routing requested modes differ/,
    );
  });

  it("rejects canonical-request and record input-mode drift", () => {
    const value = governance();
    Object.assign(value.canonical_result.request, {
      input_mode: "VOICE",
      typed_text: null,
      transcription_id: "transcription-1",
      original_transcript_text: "Move.",
      transcript_text: "Move.",
      transcript_status: "READY",
      transcript_backend: "foundry_nemotron",
      transcript_confidence: null,
      audio_sha256: "b".repeat(64),
    });
    expect(() => decodeGovernanceResult(value)).toThrow(
      /canonical request and governance record input modes differ/,
    );
  });

  it("cross-binds remaining canonical request and record identity fields", () => {
    const evaluation = governance();
    Object.assign(evaluation.canonical_result.request, {
      evaluation_mode: "EVALUATION",
      benchmark_id: "benchmark",
      benchmark_sha256: "1".repeat(64),
      oracle_version: "1.0.0",
      oracle_sha256: "2".repeat(64),
      expected_decision: "ACCEPT",
    });
    expect(() => decodeGovernanceResult(evaluation)).toThrow(
      /evaluation modes differ/,
    );

    const transcript = governance();
    Object.assign(transcript.canonical_result.request, {
      input_mode: "VOICE",
      typed_text: null,
      transcription_id: "request-transcription",
      original_transcript_text: "Move.",
      transcript_text: "Move.",
      transcript_status: "READY",
      transcript_backend: "foundry_nemotron",
      transcript_confidence: null,
      audio_sha256: "b".repeat(64),
    });
    Object.assign(transcript.canonical_result.governance_record, {
      input_mode: "VOICE",
      typed_text: null,
      transcription_id: "record-transcription",
      original_transcript_text: "Move.",
      transcript_text: "Move.",
      transcript_status: "READY",
      transcript_backend: "foundry_nemotron",
      transcript_confidence: null,
      audio_sha256: "b".repeat(64),
      normalised_command: "Move.",
    });
    expect(() => decodeGovernanceResult(transcript)).toThrow(
      /transcription IDs differ/,
    );
  });

  it("rejects canonical raw-response presence drift", () => {
    const value = governance();
    Object.assign(value.canonical_result, { raw_response_text: null });

    expect(() => decodeGovernanceResult(value)).toThrow(
      /canonical raw response presence contradicts governance record/,
    );
  });

  it("rejects canonical-request and record typed-text drift", () => {
    const value = governance();
    value.canonical_result.request.typed_text = "Different command.";

    expect(() => decodeGovernanceResult(value)).toThrow(
      /canonical request and governance record typed texts differ/,
    );
  });

  it("rejects reviewed voice transcript drift across canonical request and record", () => {
    const value = governance();

    Object.assign(value.canonical_result.request, {
      input_mode: "VOICE",
      typed_text: null,
      transcription_id: "transcription-1",
      original_transcript_text: "Move.",
      transcript_text: "Reviewed request transcript.",
      transcript_status: "READY",
      transcript_backend: "foundry_nemotron",
      transcript_confidence: 0.9,
      audio_sha256: "b".repeat(64),
    });

    Object.assign(value.canonical_result.governance_record, {
      input_mode: "VOICE",
      typed_text: null,
      transcription_id: "transcription-1",
      original_transcript_text: "Move.",
      transcript_text: "Different reviewed transcript.",
      transcript_status: "READY",
      transcript_backend: "foundry_nemotron",
      transcript_confidence: 0.9,
      audio_sha256: "b".repeat(64),
      normalised_command: "Different reviewed transcript.",
    });

    expect(() => decodeGovernanceResult(value)).toThrow(
      /canonical request and governance record reviewed transcripts differ/,
    );
  });

  it("rejects coherent EVALUATION output on the live final-demo governance boundary", () => {
    const value = governance();

    Object.assign(value.canonical_result.request, {
      evaluation_mode: "EVALUATION",
      benchmark_id: "benchmark-1",
      benchmark_sha256: "1".repeat(64),
      oracle_version: "1.0.0",
      oracle_sha256: "2".repeat(64),
      expected_decision: "ACCEPT",
    });

    Object.assign(value.canonical_result.governance_record, {
      evaluation_mode: "EVALUATION",
      benchmark_id: "benchmark-1",
      oracle_version: "1.0.0",
      expected_decision: "ACCEPT",
      decision_correctness_status: "CORRECT",
    });

    Object.assign(
      value.canonical_result.governance_record.provenance,
      {
        benchmark_sha256: "1".repeat(64),
        oracle_sha256: "2".repeat(64),
      },
    );

    expect(() => decodeGovernanceResult(value)).toThrow(
      /final-demo governance responses must use LIVE evaluation mode/,
    );
  });

  it("rejects benchmark provenance on a LIVE final-demo trace", () => {
    const value = governance();

    Object.assign(
      value.canonical_result.governance_record.provenance,
      {
        benchmark_sha256: "1".repeat(64),
      },
    );

    expect(() => decodeGovernanceResult(value)).toThrow(
      /LIVE final-demo trace contains evaluation evidence metadata/,
    );
  });

});
