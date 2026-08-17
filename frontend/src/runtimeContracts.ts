import type {
  ActionStep,
  AuthorityState,
  AvailabilityStatus,
  DemoManifest,
  DemoScenario,
  DemoStatus,
  FinalDecision,
  GateDisplayStatus,
  HybridGovernanceResult,
  InferenceMode,
  LocalHealth,
  RecordedAudioMetadata,
  RecordedTranscription,
  ReplayBoundarySnapshot,
  ReplayControl,
  ReplayErrorCode,
  ReplayFrameProjection,
  ReplayLastErrorCode,
  ReplayLifecycle,
  ReplayPhase,
  ReplayQualificationProjection,
  ReplayRouteState,
  ReplayStateProjection,
  TranscriptStatus,
} from "./types";

export class ContractValidationError extends Error {
  readonly code = "CONTRACT_FAILURE";

  constructor(message: string) {
    super(message);
    this.name = "ContractValidationError";
  }
}

const AVAILABILITY = ["AVAILABLE", "UNAVAILABLE", "NOT_ASSESSED"] as const;
const INFERENCE_MODES = ["LOCAL", "CLOUD", "AUTO"] as const;
const DECISIONS = ["ACCEPT", "REJECT", "CLARIFY", "ERROR"] as const;
const GATE_STATUSES = [
  "PASSED",
  "FAILED",
  "NOT_ASSESSABLE",
  "NOT_EVALUATED",
  "ERROR",
] as const;
const SEMANTIC_STATUSES = [
  "VALID",
  "INVALID",
  "NOT_ASSESSABLE_NO_PROPOSAL",
  "NOT_ASSESSABLE_PARSE_FAILED",
  "NOT_ASSESSABLE_SCHEMA_INVALID",
  "NOT_ASSESSABLE_MISSING_ORACLE",
  "NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT",
  "NOT_EVALUATED",
  "ERROR",
] as const;
const TRANSCRIPT_STATUSES = [
  "READY",
  "PARTIAL",
  "EMPTY",
  "BACKEND_UNAVAILABLE",
  "FAILED",
  "CANCELLED",
] as const;
const FALLBACK_REASONS = [
  "NONE", "LOCAL_UNAVAILABLE", "LOCAL_MODEL_NOT_READY", "LOCAL_TIMEOUT",
  "LOCAL_TRANSPORT_ERROR", "LOCAL_EMPTY_RESPONSE", "LOCAL_PARSE_FAILURE",
  "LOCAL_JSON_FAILURE", "LOCAL_SCHEMA_FAILURE", "LOCAL_CIRCUIT_OPEN",
  "LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD",
  "LOCAL_LATENCY_THRESHOLD_EXCEEDED",
] as const;
const AUTHORITY_TAXONOMY = [
  "UNTRUSTED_PROPOSAL",
  "GOVERNANCE_DECISION",
  "EXECUTION_ELIGIBILITY",
  "QUALIFICATION_REPLAY_ACCESS",
  "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
  "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
] as const satisfies readonly AuthorityState[];
const SHA256 = /^[0-9a-f]{64}$/i;
const SCENARIO_ID = /^[A-Z][A-Z0-9_]{0,127}$/;
const ENTITY_IDENTIFIER = /^[a-z][a-z0-9_]*$/;
const REASON_CODE = /^[A-Z][A-Z0-9_]*$/;
const QUALIFIED_TRANSCRIPT_BACKEND = "foundry_nemotron";
const QUALIFIED_SPEECH_ALIAS = "nemotron-speech-streaming-en-0.6b";
const QUALIFIED_SPEECH_MODEL =
  "nemotron-speech-streaming-en-0.6b-generic-cpu:3";
const MAX_SAFE_INTEGER = 9_007_199_254_740_991;
const REPLAY_CONTROLS = [
  "START", "PAUSE", "RESUME", "NEXT_SNAPSHOT", "PREVIOUS_SNAPSHOT", "STOP", "RESET_VIEW",
] as const satisfies readonly ReplayControl[];
const REPLAY_LIFECYCLES = [
  "IDLE", "PAUSED", "PLAYING", "COMPLETED", "FAILED", "CLEANUP_FAILED",
] as const satisfies readonly ReplayLifecycle[];
const REPLAY_LAST_ERRORS = [
  "REPLAY_RUNTIME_INTEGRITY_FAILED", "REPLAY_SCENE_FAILED", "REPLAY_GUI_CLOSED",
  "REPLAY_CLEANUP_UNRESOLVED",
] as const satisfies readonly ReplayLastErrorCode[];
const REPLAY_ERRORS = [
  "REPLAY_SCENARIO_NOT_FOUND", "REPLAY_SCENARIO_NOT_REPLAYABLE", "REPLAY_SESSION_ACTIVE",
  "REPLAY_SESSION_STALE", "REPLAY_CONTROL_VERSION_STALE", "REPLAY_CONTROL_INVALID_STATE",
  "REPLAY_FRAME_BOUNDARY", "REPLAY_REQUEST_INVALID", "REPLAY_COMMAND_CHANNEL_FULL",
  "REPLAY_CLEANUP_UNRESOLVED", "REPLAY_SERVER_SHUTTING_DOWN",
  "REPLAY_RUNTIME_INTEGRITY_FAILED", "REPLAY_VERSION_EXHAUSTED", "REPLAY_SCENE_FAILED",
  "REPLAY_COMMAND_EXPIRED", "REPLAY_START_TIMEOUT", "REPLAY_CONTROL_SETTLEMENT_UNKNOWN",
] as const satisfies readonly ReplayErrorCode[];
const REPLAY_ROUTE_STATES = [
  "HOME", "SOURCE_HIGH", "SOURCE_PICK", "SOURCE_HIGH_RETURN", "DESTINATION_HIGH",
  "DESTINATION_PLACE", "DESTINATION_HIGH_RETURN", "INTERPOLATED",
] as const satisfies readonly ReplayRouteState[];
const REPLAY_PHASES = [
  "SOURCE_SUPPORTED", "ATTACHMENT_BOUNDARY", "CARRIED", "RELEASE_BOUNDARY",
  "DESTINATION_SUPPORTED",
] as const satisfies readonly ReplayPhase[];
const REPLAY_BOUNDARIES = ["NONE", "PRE", "POST"] as const satisfies readonly ReplayBoundarySnapshot[];
const REPLAY_KEY_INDICES = [0, 78, 118, 119, 157, 311, 351, 352, 390, 468] as const;
const REPLAY_KEY_INDEX_SET = new Set<number>(REPLAY_KEY_INDICES);
const REPLAY_LABELS = [
  "EVIDENCE REPLAY",
  "NOT PHYSICAL EXECUTION",
  "DISCRETE SAMPLED STATES — NO DYNAMIC TIMING",
] as const;
const B2_SHA256 = "a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554";
const B3_2_SHA256 = "11c8b83f8c4d0545c9a8df604046a335acb00121a51bf6e1d5b39504991c1798";

type JsonObject = Record<string, unknown>;

function fail(path: string, message: string): never {
  throw new ContractValidationError(`${path}: ${message}`);
}

function objectValue(
  value: unknown,
  path: string,
  allowedKeys?: readonly string[],
): JsonObject {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return fail(path, "expected object");
  }
  const result = value as JsonObject;
  if (allowedKeys) {
    const allowed = new Set(allowedKeys);
    const unexpected = Object.keys(result).find((key) => !allowed.has(key));
    if (unexpected) fail(path, `unexpected property ${unexpected}`);
  }
  return result;
}

function arrayValue(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) return fail(path, "expected array");
  return value;
}

function stringValue(value: unknown, path: string, nonempty = true): string {
  if (typeof value !== "string" || (nonempty && value.length === 0)) {
    return fail(path, "expected string");
  }
  return value;
}

function nonBlankString(value: unknown, path: string): string {
  const text = stringValue(value, path);
  if (!text.trim()) return fail(path, "expected non-blank string");
  return text;
}

function nullableString(value: unknown, path: string): string | null {
  return value === null ? null : stringValue(value, path, false);
}

function boundedString(
  value: unknown,
  path: string,
  maximum: number,
  nonempty = true,
): string {
  const text = stringValue(value, path, nonempty);
  if (text.length > maximum) {
    return fail(path, `must contain at most ${maximum} characters`);
  }
  return text;
}

function boundedNullableString(
  value: unknown,
  path: string,
  maximum: number,
): string | null {
  return value === null ? null : boundedString(value, path, maximum, false);
}

function booleanValue(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") return fail(path, "expected boolean");
  return value;
}

function finiteNumber(value: unknown, path: string, minimum = 0): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum) {
    return fail(path, `expected finite number >= ${minimum}`);
  }
  return value;
}

function integerValue(value: unknown, path: string, minimum = 0): number {
  const number = finiteNumber(value, path, minimum);
  if (!Number.isInteger(number)) return fail(path, "expected integer");
  return number;
}

function entityIdentifier(value: unknown, path: string): string {
  const identifier = stringValue(value, path);
  if (!ENTITY_IDENTIFIER.test(identifier)) {
    return fail(path, "expected lower_snake_case identifier");
  }
  return identifier;
}

function nullableEntityIdentifier(value: unknown, path: string): string | null {
  return value === null ? null : entityIdentifier(value, path);
}

function nullableDuration(value: unknown, path: string): number | null {
  if (value === null) return null;
  const duration = integerValue(value, path, 1);
  if (duration > 60_000) return fail(path, "duration must be <= 60000 ms");
  return duration;
}

function nullableNumber(value: unknown, path: string): number | null {
  return value === null ? null : finiteNumber(value, path);
}

function enumValue<const T extends readonly string[]>(
  value: unknown,
  values: T,
  path: string,
): T[number] {
  if (typeof value !== "string" || !values.includes(value)) {
    return fail(path, "unknown enum value");
  }
  return value as T[number];
}

function exactString(value: unknown, expected: string, path: string): string {
  if (value !== expected) return fail(path, `expected ${expected}`);
  return expected;
}

function requiredProperty(source: JsonObject, key: string, path: string): unknown {
  if (!Object.prototype.hasOwnProperty.call(source, key)) {
    return fail(`${path}.${key}`, "required property missing");
  }
  return source[key];
}

function scenarioIdentifier(value: unknown, path: string): string {
  const identifier = stringValue(value, path);
  if (!SCENARIO_ID.test(identifier)) {
    return fail(path, "expected bounded scenario identifier");
  }
  return identifier;
}

function sha256(value: unknown, path: string): string {
  const text = stringValue(value, path);
  if (!SHA256.test(text)) return fail(path, "expected SHA-256");
  return text;
}

function uniqueStrings(value: unknown, path: string, nonempty = false): string[] {
  const result = arrayValue(value, path).map((item, index) =>
    stringValue(item, `${path}[${index}]`),
  );
  if (nonempty && result.length === 0) return fail(path, "must not be empty");
  if (new Set(result).size !== result.length) return fail(path, "duplicates forbidden");
  return result;
}

function stableReasonCode(value: unknown, path: string): string {
  const code = stringValue(value, path);
  if (!REASON_CODE.test(code)) return fail(path, "invalid stable reason code");
  return code;
}

function uniqueReasonCodes(
  value: unknown,
  path: string,
  nonempty: boolean,
): string[] {
  const result = arrayValue(value, path).map((item, index) =>
    stableReasonCode(item, `${path}[${index}]`),
  );
  if (nonempty && result.length === 0) {
    return fail(path, "reason-code collection must not be empty");
  }
  if (new Set(result).size !== result.length) {
    return fail(path, "duplicate reason code");
  }
  return result;
}

function utcTimestamp(value: unknown, path: string): string {
  const timestamp = stringValue(value, path);
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]00:00)$/.exec(timestamp);
  const parsed = new Date(timestamp);
  const year = match === null ? 0 : Number(match[1]);
  if (
    match === null ||
    year < 1 ||
    year > 9999 ||
    Number.isNaN(parsed.getTime()) ||
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() + 1 !== Number(match[2]) ||
    parsed.getUTCDate() !== Number(match[3]) ||
    parsed.getUTCHours() !== Number(match[4]) ||
    parsed.getUTCMinutes() !== Number(match[5]) ||
    parsed.getUTCSeconds() !== Number(match[6])
  ) {
    return fail(path, "expected ISO-8601 UTC timestamp");
  }
  return timestamp;
}

function decodeLocalHealth(value: unknown, path: string): LocalHealth {
  const source = objectValue(value, path, [
    "circuit_state", "local_available", "local_model_ready",
    "consecutive_failures", "rolling_sample_count",
    "rolling_structured_success_rate", "rolling_p50_latency_ms",
    "rolling_p95_latency_ms", "last_failure_reason",
    "last_circuit_transition",
  ]);
  const successRate = nullableNumber(
    source.rolling_structured_success_rate,
    `${path}.rolling_structured_success_rate`,
  );
  if (successRate !== null && successRate > 1) {
    return fail(`${path}.rolling_structured_success_rate`, "must be <= 1");
  }
  return {
    circuit_state: enumValue(
      source.circuit_state,
      ["CLOSED", "OPEN", "HALF_OPEN"] as const,
      `${path}.circuit_state`,
    ),
    local_available: booleanValue(source.local_available, `${path}.local_available`),
    local_model_ready: booleanValue(source.local_model_ready, `${path}.local_model_ready`),
    consecutive_failures: integerValue(source.consecutive_failures, `${path}.consecutive_failures`),
    rolling_sample_count: integerValue(source.rolling_sample_count, `${path}.rolling_sample_count`),
    rolling_structured_success_rate: successRate,
    rolling_p50_latency_ms: nullableNumber(source.rolling_p50_latency_ms, `${path}.rolling_p50_latency_ms`),
    rolling_p95_latency_ms: nullableNumber(source.rolling_p95_latency_ms, `${path}.rolling_p95_latency_ms`),
    last_failure_reason: enumValue(source.last_failure_reason, FALLBACK_REASONS, `${path}.last_failure_reason`),
    last_circuit_transition: nullableString(source.last_circuit_transition, `${path}.last_circuit_transition`),
  };
}

export function decodeDemoStatus(value: unknown): DemoStatus {
  const source = objectValue(value, "status", [
    "service_status", "frozen_baseline_tag", "frozen_baseline_commit",
    "software_commit", "evidence_schema_version", "supported_domains",
    "supported_inference_modes", "local_status", "cloud_status",
    "speech_status", "simulator_status", "local_health",
  ]);
  const domains = arrayValue(source.supported_domains, "status.supported_domains").map(
    (item, index) => exactString(item, "MANUFACTURING", `status.supported_domains[${index}]`) as "MANUFACTURING",
  );
  if (domains.length !== 1) fail("status.supported_domains", "expected one canonical domain");
  const modes = arrayValue(source.supported_inference_modes, "status.supported_inference_modes").map(
    (item, index) => enumValue(item, INFERENCE_MODES, `status.supported_inference_modes[${index}]`),
  );
  if (new Set(modes).size !== modes.length || modes.length === 0) {
    fail("status.supported_inference_modes", "invalid cardinality");
  }
  return {
    service_status: exactString(source.service_status, "READY", "status.service_status"),
    frozen_baseline_tag: stringValue(source.frozen_baseline_tag, "status.frozen_baseline_tag"),
    frozen_baseline_commit: exactCommit(source.frozen_baseline_commit, "status.frozen_baseline_commit"),
    software_commit: exactCommit(source.software_commit, "status.software_commit"),
    evidence_schema_version: exactString(source.evidence_schema_version, "2.0.0", "status.evidence_schema_version"),
    supported_domains: domains,
    supported_inference_modes: modes,
    local_status: enumValue(source.local_status, AVAILABILITY, "status.local_status") as AvailabilityStatus,
    cloud_status: enumValue(source.cloud_status, AVAILABILITY, "status.cloud_status") as AvailabilityStatus,
    speech_status: enumValue(source.speech_status, AVAILABILITY, "status.speech_status") as AvailabilityStatus,
    simulator_status: enumValue(source.simulator_status, AVAILABILITY, "status.simulator_status") as AvailabilityStatus,
    local_health: decodeLocalHealth(source.local_health, "status.local_health"),
  };
}

function exactCommit(value: unknown, path: string): string {
  const text = stringValue(value, path);
  if (!/^[0-9a-f]{40}$/i.test(text)) return fail(path, "expected Git commit SHA");
  return text;
}

function decodeScenario(value: unknown, path: string): DemoScenario {
  const source = objectValue(value, path, [
    "scenario_id", "display_name", "presentation_classification",
    "model_input_enabled", "allowed_inference_modes", "registered_command",
    "demonstration_purpose", "evidence_classification",
    "replay_capability_classification", "qualification_replay_access",
    "downstream_geometric_qualification", "claim_boundary_note",
  ]);
  const modelInput = booleanValue(source.model_input_enabled, `${path}.model_input_enabled`);
  const modes = arrayValue(source.allowed_inference_modes, `${path}.allowed_inference_modes`).map(
    (item, index) => enumValue(item, INFERENCE_MODES, `${path}.allowed_inference_modes[${index}]`),
  );
  if (new Set(modes).size !== modes.length) {
    fail(`${path}.allowed_inference_modes`, "duplicates forbidden");
  }
  const presentation = enumValue(
    source.presentation_classification,
    ["SYNTHETIC_LIVE_DEMO", "FROZEN_RESEARCH_EVIDENCE", "FROZEN_EVIDENCE_REPLAY"] as const,
    `${path}.presentation_classification`,
  );
  const evidence = enumValue(
    source.evidence_classification,
    ["LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE", "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT", "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION"] as const,
    `${path}.evidence_classification`,
  );
  const replay = enumValue(
    source.replay_capability_classification,
    ["GOVERNANCE_ONLY", "FROZEN_B2_REPLAY_COMPATIBLE"] as const,
    `${path}.replay_capability_classification`,
  );
  const access = enumValue(
    source.qualification_replay_access,
    ["PROHIBITED", "SERVER_REGISTERED_ONLY"] as const,
    `${path}.qualification_replay_access`,
  );
  if ((replay === "FROZEN_B2_REPLAY_COMPATIBLE") !== (access === "SERVER_REGISTERED_ONLY")) {
    fail(path, "replay capability and access contradict");
  }
  const downstream = enumValue(
    source.downstream_geometric_qualification,
    ["FAIL", "NOT_APPLICABLE"] as const,
    `${path}.downstream_geometric_qualification`,
  );
  if (presentation === "SYNTHETIC_LIVE_DEMO") {
    if (
      !modelInput ||
      modes.length !== INFERENCE_MODES.length ||
      modes.some((mode, index) => mode !== INFERENCE_MODES[index]) ||
      evidence !== "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE" ||
      replay !== "GOVERNANCE_ONLY" ||
      access !== "PROHIBITED" ||
      downstream !== "NOT_APPLICABLE"
    ) {
      fail(path, "live scenario presentation contract is contradictory");
    }
  } else if (presentation === "FROZEN_RESEARCH_EVIDENCE") {
    if (
      modelInput ||
      modes.length !== 0 ||
      evidence !== "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT" ||
      replay !== "GOVERNANCE_ONLY" ||
      access !== "PROHIBITED" ||
      downstream !== "NOT_APPLICABLE"
    ) {
      fail(path, "frozen research-evidence contract is contradictory");
    }
  } else if (
    modelInput ||
    modes.length !== 0 ||
    evidence !== "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION" ||
    replay !== "FROZEN_B2_REPLAY_COMPATIBLE" ||
    access !== "SERVER_REGISTERED_ONLY" ||
    downstream !== "FAIL"
  ) {
    fail(path, "frozen evidence-replay contract is contradictory");
  }
  return {
    scenario_id: scenarioIdentifier(source.scenario_id, `${path}.scenario_id`),
    display_name: nonBlankString(source.display_name, `${path}.display_name`),
    presentation_classification: presentation,
    model_input_enabled: modelInput,
    allowed_inference_modes: modes,
    registered_command: nonBlankString(source.registered_command, `${path}.registered_command`),
    demonstration_purpose: nonBlankString(source.demonstration_purpose, `${path}.demonstration_purpose`),
    evidence_classification: evidence,
    replay_capability_classification: replay,
    qualification_replay_access: access,
    downstream_geometric_qualification: downstream,
    claim_boundary_note: nonBlankString(source.claim_boundary_note, `${path}.claim_boundary_note`),
  };
}

export function decodeDemoManifest(value: unknown): DemoManifest {
  const source = objectValue(value, "manifest", [
    "contract_id", "contract_version", "authority_taxonomy",
    "physical_execution_authority_state", "healthcare_scope",
    "d2_replay_enabled", "scenarios",
  ]);
  const authority = arrayValue(source.authority_taxonomy, "manifest.authority_taxonomy").map(
    (item, index) => enumValue(item, AUTHORITY_TAXONOMY, `manifest.authority_taxonomy[${index}]`),
  );
  if (authority.length !== AUTHORITY_TAXONOMY.length || authority.some((item, index) => item !== AUTHORITY_TAXONOMY[index])) {
    fail("manifest.authority_taxonomy", "canonical order changed");
  }
  const scenarios = arrayValue(source.scenarios, "manifest.scenarios").map(
    (scenario, index) => decodeScenario(scenario, `manifest.scenarios[${index}]`),
  );
  const identifiers = scenarios.map((scenario) => scenario.scenario_id);
  if (scenarios.length === 0) {
    fail("manifest.scenarios", "must not be empty");
  }
  if (new Set(identifiers).size !== identifiers.length) {
    fail("manifest.scenarios", "duplicate scenario identifier");
  }
  if (scenarios.filter((scenario) => scenario.replay_capability_classification === "FROZEN_B2_REPLAY_COMPATIBLE").length !== 1) {
    fail("manifest.scenarios", "expected exactly one replay-compatible scenario");
  }
  if (source.d2_replay_enabled !== false) fail("manifest.d2_replay_enabled", "must be false");
  return {
    contract_id: exactString(source.contract_id, "PROTOTYPE5_FINAL_DEMONSTRATOR_D0", "manifest.contract_id") as DemoManifest["contract_id"],
    contract_version: exactString(source.contract_version, "1.0.0", "manifest.contract_version") as "1.0.0",
    authority_taxonomy: authority,
    physical_execution_authority_state: exactString(source.physical_execution_authority_state, "NOT_IMPLEMENTED", "manifest.physical_execution_authority_state") as "NOT_IMPLEMENTED",
    healthcare_scope: exactString(source.healthcare_scope, "OUT_OF_SCOPE_FOR_FINAL_DEMO", "manifest.healthcare_scope") as "OUT_OF_SCOPE_FOR_FINAL_DEMO",
    d2_replay_enabled: false,
    scenarios,
  };
}

function decodeAction(value: unknown, path: string): ActionStep {
  const source = objectValue(value, path, ["action", "object_id", "source_id", "destination_id", "duration_ms"]);
  const action = enumValue(
    source.action,
    ["MOVE", "PICK", "PLACE", "WAIT", "STOP", "INSPECT"] as const,
    `${path}.action`,
  );
  const objectId = nullableEntityIdentifier(
    requiredProperty(source, "object_id", path),
    `${path}.object_id`,
  );
  const sourceId = nullableEntityIdentifier(
    requiredProperty(source, "source_id", path),
    `${path}.source_id`,
  );
  const destinationId = nullableEntityIdentifier(
    requiredProperty(source, "destination_id", path),
    `${path}.destination_id`,
  );
  const durationMs = nullableDuration(
    requiredProperty(source, "duration_ms", path),
    `${path}.duration_ms`,
  );

  if (action === "MOVE") {
    if (objectId === null || sourceId === null || destinationId === null || durationMs !== null) {
      fail(path, "MOVE field combination violates ActionStepV2");
    }
  } else if (action === "PICK") {
    if (objectId === null || sourceId === null || destinationId !== null || durationMs !== null) {
      fail(path, "PICK field combination violates ActionStepV2");
    }
  } else if (action === "PLACE") {
    if (objectId === null || sourceId !== null || destinationId === null || durationMs !== null) {
      fail(path, "PLACE field combination violates ActionStepV2");
    }
  } else if (action === "WAIT") {
    if (objectId !== null || sourceId !== null || destinationId !== null || durationMs === null) {
      fail(path, "WAIT field combination violates ActionStepV2");
    }
  } else if (action === "STOP") {
    if (objectId !== null || sourceId !== null || destinationId !== null || durationMs !== null) {
      fail(path, "STOP field combination violates ActionStepV2");
    }
  } else if (objectId === null || destinationId !== null || durationMs !== null) {
    fail(path, "INSPECT field combination violates ActionStepV2");
  }

  return {
    action,
    object_id: objectId,
    source_id: sourceId,
    destination_id: destinationId,
    duration_ms: durationMs,
  };
}

function nullableSha256(value: unknown, path: string): string | null {
  return value === null ? null : sha256(value, path);
}

interface CanonicalRequestSummary {
  inputMode: "TYPED" | "VOICE";
  evaluationMode: "LIVE" | "EVALUATION";
  requestedInferenceMode: InferenceMode;
  typedText: string | null;
  transcriptionId: string | null;
  originalTranscriptText: string | null;
  transcriptText: string | null;
  transcriptStatus: "NOT_APPLICABLE" | TranscriptStatus;
  transcriptBackend: string | null;
  transcriptConfidence: number | null;
  audioSha256: string | null;
  expectedDecision: FinalDecision | null;
}

function validateCanonicalRequest(
  value: unknown,
  path: string,
): CanonicalRequestSummary {
  const source = objectValue(value, path, [
    "input_mode", "typed_text", "transcription_id", "original_transcript_text",
    "transcript_text", "transcript_status", "transcript_backend",
    "transcript_confidence", "audio_sha256", "domain_id", "scene", "requester",
    "requested_inference_mode", "evaluation_mode", "benchmark_id",
    "benchmark_sha256", "oracle_version", "oracle_sha256", "expected_decision",
  ]);
  const inputMode = enumValue(source.input_mode, ["TYPED", "VOICE"] as const, `${path}.input_mode`);
  const typedText = nullableString(source.typed_text, `${path}.typed_text`);
  const transcriptionId = boundedNullableString(source.transcription_id, `${path}.transcription_id`, 200);
  const originalTranscript = boundedNullableString(source.original_transcript_text, `${path}.original_transcript_text`, 1000);
  const transcriptText = boundedNullableString(source.transcript_text, `${path}.transcript_text`, 1000);
  const transcriptStatus = enumValue(source.transcript_status, ["NOT_APPLICABLE", ...TRANSCRIPT_STATUSES] as const, `${path}.transcript_status`);
  const transcriptBackend = nullableString(source.transcript_backend, `${path}.transcript_backend`);
  const confidence = nullableNumber(source.transcript_confidence, `${path}.transcript_confidence`);
  if (confidence !== null && confidence > 1) fail(`${path}.transcript_confidence`, "must be <= 1");
  const audioSha = nullableSha256(source.audio_sha256, `${path}.audio_sha256`);
  if (inputMode === "TYPED") {
    if (!typedText?.trim() || transcriptStatus !== "NOT_APPLICABLE") {
      fail(path, "typed request input fields contradict canonical contract");
    }
    if ([transcriptionId, originalTranscript, transcriptText, transcriptBackend, confidence, audioSha].some((entry) => entry !== null)) {
      fail(path, "typed request cannot contain voice provenance");
    }
  } else {
    if (typedText !== null || transcriptStatus !== "READY") {
      fail(path, "canonical voice request requires READY voice input");
    }
    if (!transcriptionId?.trim() || !originalTranscript?.trim() || !transcriptText?.trim() || !transcriptBackend?.trim() || audioSha === null) {
      fail(path, "canonical voice request lacks reviewed transcript provenance");
    }
  }
  exactString(source.domain_id, "MANUFACTURING", `${path}.domain_id`);
  const requestedInferenceMode = enumValue(source.requested_inference_mode, INFERENCE_MODES, `${path}.requested_inference_mode`) as InferenceMode;
  const evaluationMode = enumValue(source.evaluation_mode, ["LIVE", "EVALUATION"] as const, `${path}.evaluation_mode`);
  const benchmarkId = nullableString(source.benchmark_id, `${path}.benchmark_id`);
  const benchmarkSha = nullableSha256(source.benchmark_sha256, `${path}.benchmark_sha256`);
  const oracleVersion = nullableString(source.oracle_version, `${path}.oracle_version`);
  const oracleSha = nullableSha256(source.oracle_sha256, `${path}.oracle_sha256`);
  const expectedDecision = source.expected_decision === null
    ? null
    : enumValue(source.expected_decision, DECISIONS, `${path}.expected_decision`);
  const oracleFields = [benchmarkId, benchmarkSha, oracleVersion, oracleSha, expectedDecision];
  if (evaluationMode === "LIVE") {
    if (oracleFields.some((entry) => entry !== null)) {
      fail(path, "LIVE request cannot contain evaluation oracle metadata");
    }
  } else if (oracleFields.some((entry) => entry === null)) {
    fail(path, "EVALUATION request requires complete benchmark and oracle metadata");
  }
  const scene = objectValue(source.scene, `${path}.scene`, ["scene_id", "state_version", "objects", "human_obstruction", "safety_interlock_enabled"]);
  stringValue(scene.scene_id, `${path}.scene.scene_id`);
  stringValue(scene.state_version, `${path}.scene.state_version`);
  booleanValue(scene.human_obstruction, `${path}.scene.human_obstruction`);
  booleanValue(scene.safety_interlock_enabled, `${path}.scene.safety_interlock_enabled`);
  const sceneObjectIds = arrayValue(scene.objects, `${path}.scene.objects`).map((item, index) => {
    const itemPath = `${path}.scene.objects[${index}]`;
    const object = objectValue(item, itemPath, ["object_id", "location_id"]);
    const objectId = entityIdentifier(object.object_id, `${itemPath}.object_id`);
    entityIdentifier(object.location_id, `${itemPath}.location_id`);
    return objectId;
  });
  if (new Set(sceneObjectIds).size !== sceneObjectIds.length) {
    fail(`${path}.scene.objects`, "duplicate scene object identifier");
  }
  const requester = objectValue(source.requester, `${path}.requester`, ["requester_id", "role"]);
  entityIdentifier(requester.requester_id, `${path}.requester.requester_id`);
  enumValue(requester.role, ["operator", "observer", "supervisor"] as const, `${path}.requester.role`);
  return {
    inputMode,
    evaluationMode,
    requestedInferenceMode,
    typedText,
    transcriptionId,
    originalTranscriptText: originalTranscript,
    transcriptText,
    transcriptStatus,
    transcriptBackend,
    transcriptConfidence: confidence,
    audioSha256: audioSha,
    expectedDecision: expectedDecision as FinalDecision | null,
  };
}

interface ProvenanceSummary {
  provider: "FOUNDRY_LOCAL" | "CLOUD" | "NONE";
  model: string | null;
  benchmarkSha256: string | null;
  oracleSha256: string | null;
}

function validateProvenance(value: unknown, path: string): ProvenanceSummary {
  const source = objectValue(value, path, ["source_repository", "software_commit", "prompt_id", "prompt_version", "model_provider", "model_id", "benchmark_sha256", "oracle_sha256", "policy_sha256"]);
  stringValue(source.source_repository, `${path}.source_repository`);
  exactCommit(source.software_commit, `${path}.software_commit`);
  stringValue(source.prompt_id, `${path}.prompt_id`);
  stringValue(source.prompt_version, `${path}.prompt_version`);
  const provider = enumValue(source.model_provider, ["FOUNDRY_LOCAL", "CLOUD", "NONE"] as const, `${path}.model_provider`);
  const model = nullableString(source.model_id, `${path}.model_id`);
  const benchmarkSha256 = nullableSha256(source.benchmark_sha256, `${path}.benchmark_sha256`);
  const oracleSha256 = nullableSha256(source.oracle_sha256, `${path}.oracle_sha256`);
  sha256(source.policy_sha256, `${path}.policy_sha256`);
  if ((provider === "NONE") !== (model === null)) fail(path, "provider and model identity contradict");
  return { provider, model, benchmarkSha256, oracleSha256 };
}

const GOVERNANCE_KEYS = [
  "record_id", "trace_id", "timestamp_utc", "evaluation_mode", "input_mode",
  "normalised_command", "typed_text", "transcription_id",
  "original_transcript_text", "transcript_text", "transcript_status",
  "transcript_backend", "transcript_confidence", "audio_sha256", "domain_id",
  "benchmark_id", "policy_id", "oracle_version", "evidence_schema_version",
  "routing", "raw_response_sha256", "raw_response_present", "provider_latency_ms",
  "parse_status", "json_status", "schema_status", "plan_semantic_status",
  "ambiguity_status", "safety_status", "authority_status", "gate_reasons",
  "gate_latencies", "expected_decision", "decision_correctness_status",
  "final_decision", "execution_eligible", "decision_reason_codes",
  "validation_latency_ms", "total_pipeline_latency_ms", "execution_permit_id",
  "simulation_status", "provenance",
] as const;

function validateGateCollections(source: JsonObject, path: string): number {
  let latencyTotal = 0;
  for (const [key, latency] of [["gate_reasons", false], ["gate_latencies", true]] as const) {
    const entries = arrayValue(source[key], `${path}.${key}`);
    const gates = entries.map((entry, index) => {
      const row = objectValue(entry, `${path}.${key}[${index}]`, latency ? ["gate", "latency_ms"] : ["gate", "reason_codes"]);
      const gate = enumValue(row.gate, ["PARSE", "JSON", "SCHEMA", "SEMANTICS", "AMBIGUITY", "SAFETY", "AUTHORITY"] as const, `${path}.${key}[${index}].gate`);
      if (latency) {
        latencyTotal += finiteNumber(row.latency_ms, `${path}.${key}[${index}].latency_ms`);
      } else {
        uniqueReasonCodes(row.reason_codes, `${path}.${key}[${index}].reason_codes`, true);
      }
      return gate;
    });
    if (new Set(gates).size !== gates.length) fail(`${path}.${key}`, "duplicate gate");
  }
  return latencyTotal;
}

export function decodeGovernanceResult(value: unknown): HybridGovernanceResult {
  const root = objectValue(value, "governance", ["routing_policy_id", "routing_policy_version", "routing_policy_sha256", "local_health", "canonical_result"]);
  const canonical = objectValue(root.canonical_result, "governance.canonical_result", ["request", "raw_response_text", "proposal", "governance_record"]);
  const rawResponseText = nullableString(
    canonical.raw_response_text,
    "governance.canonical_result.raw_response_text",
  );
  const request = validateCanonicalRequest(
    canonical.request,
    "governance.canonical_result.request",
  );
  const record = objectValue(canonical.governance_record, "governance.canonical_result.governance_record", GOVERNANCE_KEYS);
  const path = "governance.canonical_result.governance_record";
  const routing = objectValue(record.routing, `${path}.routing`, ["requested_mode", "selected_provider", "selected_model", "local_attempted", "cloud_attempted", "fallback_triggered", "fallback_reason", "local_latency_ms", "cloud_latency_ms"]);
  const gateLatencyTotal = validateGateCollections(record, path);

  stringValue(record.record_id, `${path}.record_id`);
  stringValue(record.trace_id, `${path}.trace_id`);
  const timestamp = utcTimestamp(record.timestamp_utc, `${path}.timestamp_utc`);
  const evaluationMode = enumValue(record.evaluation_mode, ["LIVE", "EVALUATION"] as const, `${path}.evaluation_mode`);
  const inputMode = enumValue(record.input_mode, ["TYPED", "VOICE"] as const, `${path}.input_mode`);
  const normalisedCommand = nullableString(record.normalised_command, `${path}.normalised_command`);
  const typedText = nullableString(record.typed_text, `${path}.typed_text`);
  const transcriptionId = boundedNullableString(record.transcription_id, `${path}.transcription_id`, 200);
  const originalTranscript = boundedNullableString(record.original_transcript_text, `${path}.original_transcript_text`, 1000);
  const transcriptText = boundedNullableString(record.transcript_text, `${path}.transcript_text`, 1000);
  const transcriptStatus = enumValue(record.transcript_status, ["NOT_APPLICABLE", ...TRANSCRIPT_STATUSES] as const, `${path}.transcript_status`);
  const transcriptBackend = nullableString(record.transcript_backend, `${path}.transcript_backend`);
  const transcriptConfidence = nullableNumber(record.transcript_confidence, `${path}.transcript_confidence`);
  if (transcriptConfidence !== null && transcriptConfidence > 1) {
    fail(`${path}.transcript_confidence`, "must be <= 1");
  }
  const audioSha = nullableSha256(record.audio_sha256, `${path}.audio_sha256`);
  exactString(record.domain_id, "MANUFACTURING", `${path}.domain_id`);
  const benchmarkId = nullableString(record.benchmark_id, `${path}.benchmark_id`);
  const oracleVersion = nullableString(record.oracle_version, `${path}.oracle_version`);
  const rawResponseSha = nullableSha256(record.raw_response_sha256, `${path}.raw_response_sha256`);
  const rawResponsePresent = booleanValue(record.raw_response_present, `${path}.raw_response_present`);
  if (rawResponsePresent !== (rawResponseSha !== null)) fail(path, "raw response provenance contradicts presence");
  const rawTextPresent = rawResponseText !== null && rawResponseText.trim().length > 0;
  if (rawTextPresent !== rawResponsePresent) {
    fail(path, "canonical raw response presence contradicts governance record");
  }
  const expectedDecision = record.expected_decision === null
    ? null
    : enumValue(record.expected_decision, DECISIONS, `${path}.expected_decision`);
  const correctnessStatus = enumValue(record.decision_correctness_status, ["CORRECT", "INCORRECT", "NOT_ASSESSABLE", "NOT_EVALUATED", "ERROR"] as const, `${path}.decision_correctness_status`);
  const provenance = validateProvenance(record.provenance, `${path}.provenance`);

  const decision = enumValue(record.final_decision, DECISIONS, `${path}.final_decision`) as FinalDecision;
  const eligible = booleanValue(record.execution_eligible, `${path}.execution_eligible`);
  const parseStatus = enumValue(record.parse_status, GATE_STATUSES, `${path}.parse_status`) as GateDisplayStatus;
  const jsonStatus = enumValue(record.json_status, GATE_STATUSES, `${path}.json_status`) as GateDisplayStatus;
  const schemaStatus = enumValue(record.schema_status, GATE_STATUSES, `${path}.schema_status`) as GateDisplayStatus;
  const semanticStatus = enumValue(record.plan_semantic_status, SEMANTIC_STATUSES, `${path}.plan_semantic_status`) as GateDisplayStatus;
  const ambiguityStatus = enumValue(record.ambiguity_status, GATE_STATUSES, `${path}.ambiguity_status`) as GateDisplayStatus;
  const safetyStatus = enumValue(record.safety_status, GATE_STATUSES, `${path}.safety_status`) as GateDisplayStatus;
  const authorityStatus = enumValue(record.authority_status, GATE_STATUSES, `${path}.authority_status`) as GateDisplayStatus;

  if (parseStatus !== "PASSED" && (jsonStatus === "PASSED" || schemaStatus === "PASSED" || semanticStatus === "VALID")) {
    fail(path, "gate propagation contradicts parse status");
  }
  if (jsonStatus !== "PASSED" && (schemaStatus === "PASSED" || semanticStatus === "VALID")) {
    fail(path, "gate propagation contradicts JSON status");
  }
  if (schemaStatus !== "PASSED" && semanticStatus === "VALID") {
    fail(path, "gate propagation contradicts schema status");
  }
  const mandatoryPass = parseStatus === "PASSED"
    && jsonStatus === "PASSED"
    && schemaStatus === "PASSED"
    && semanticStatus === "VALID"
    && ambiguityStatus === "PASSED"
    && safetyStatus === "PASSED"
    && authorityStatus === "PASSED";
  if (eligible !== mandatoryPass) {
    fail(path, "execution eligibility differs from mandatory gate conjunction");
  }
  if ((decision === "ACCEPT") !== eligible) {
    fail(path, "decision contradicts execution eligibility");
  }
  const reasons = uniqueReasonCodes(record.decision_reason_codes, `${path}.decision_reason_codes`, true);

  const requestedMode = enumValue(routing.requested_mode, INFERENCE_MODES, `${path}.routing.requested_mode`) as InferenceMode;
  const selectedProvider = enumValue(routing.selected_provider, ["FOUNDRY_LOCAL", "CLOUD", "NONE"] as const, `${path}.routing.selected_provider`);
  const selectedModel = nullableString(routing.selected_model, `${path}.routing.selected_model`);
  if (selectedModel !== null && !selectedModel.trim()) {
    fail(`${path}.routing.selected_model`, "must not be blank");
  }
  const localAttempted = booleanValue(routing.local_attempted, `${path}.routing.local_attempted`);
  const cloudAttempted = booleanValue(routing.cloud_attempted, `${path}.routing.cloud_attempted`);
  const fallbackTriggered = booleanValue(routing.fallback_triggered, `${path}.routing.fallback_triggered`);
  const fallbackReason = enumValue(routing.fallback_reason, FALLBACK_REASONS, `${path}.routing.fallback_reason`);
  const localLatency = nullableNumber(routing.local_latency_ms, `${path}.routing.local_latency_ms`);
  const cloudLatency = nullableNumber(routing.cloud_latency_ms, `${path}.routing.cloud_latency_ms`);
  const providerLatency = nullableNumber(record.provider_latency_ms, `${path}.provider_latency_ms`);

  if ((selectedProvider === "NONE") !== (selectedModel === null)) {
    fail(path, "selected provider and model contradict");
  }
  if (selectedProvider !== provenance.provider || selectedModel !== provenance.model) {
    fail(path, "routing and provenance identities contradict");
  }
  if (fallbackTriggered) {
    if (requestedMode !== "AUTO" || fallbackReason === "NONE" || !cloudAttempted || (selectedProvider !== "CLOUD" && selectedProvider !== "NONE")) {
      fail(path, "fallback routing contradicts route state");
    }
    const skipReasons = new Set(["LOCAL_UNAVAILABLE", "LOCAL_MODEL_NOT_READY", "LOCAL_CIRCUIT_OPEN", "LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD", "LOCAL_LATENCY_THRESHOLD_EXCEEDED"]);
    if (!localAttempted && !skipReasons.has(fallbackReason)) {
      fail(path, "fallback without local attempt lacks pre-attempt reason");
    }
  } else if (fallbackReason !== "NONE") {
    fail(path, "fallback reason requires fallback");
  }
  if (requestedMode === "LOCAL" && (cloudAttempted || (selectedProvider !== "FOUNDRY_LOCAL" && selectedProvider !== "NONE") || (!localAttempted && selectedProvider !== "NONE"))) {
    fail(path, "LOCAL routing contradicts route state");
  }
  if (requestedMode === "CLOUD" && (localAttempted || (selectedProvider !== "CLOUD" && selectedProvider !== "NONE") || (!cloudAttempted && selectedProvider !== "NONE"))) {
    fail(path, "CLOUD routing contradicts route state");
  }
  if (requestedMode === "AUTO" && !localAttempted && !fallbackTriggered && (cloudAttempted || selectedProvider !== "NONE")) {
    fail(path, "AUTO routing skipped local authority");
  }
  if ((localLatency !== null && !localAttempted) || (cloudLatency !== null && !cloudAttempted)) {
    fail(path, "provider latency lacks matching attempt");
  }

  if (rawResponsePresent) {
    if (selectedProvider === "NONE" || rawResponseSha === null) {
      fail(path, "raw response lacks provider provenance");
    }
  } else if (parseStatus === "PASSED" || jsonStatus === "PASSED" || schemaStatus === "PASSED" || semanticStatus === "VALID") {
    fail(path, "missing raw response cannot pass structural gates");
  }
  if (selectedProvider === "NONE") {
    if (providerLatency !== null) fail(path, "provider latency requires selected provider");
  } else if (providerLatency === null) {
    fail(path, "selected provider requires provider latency");
  } else if (selectedProvider === "FOUNDRY_LOCAL" && localLatency !== providerLatency) {
    fail(path, "provider latency differs from selected local latency");
  } else if (selectedProvider === "CLOUD" && cloudLatency !== providerLatency) {
    fail(path, "provider latency differs from selected cloud latency");
  }

  if (inputMode === "TYPED") {
    if (!typedText?.trim() || !normalisedCommand?.trim() || transcriptStatus !== "NOT_APPLICABLE") {
      fail(path, "typed input provenance contradicts input mode");
    }
    if ([transcriptionId, originalTranscript, transcriptText, transcriptBackend, transcriptConfidence, audioSha].some((item) => item !== null)) {
      fail(path, "typed input contains voice provenance");
    }
  } else {
    if (typedText !== null || !transcriptionId?.trim() || transcriptStatus === "NOT_APPLICABLE") {
      fail(path, "voice input provenance contradicts input mode");
    }
    if (transcriptStatus === "READY" || transcriptStatus === "PARTIAL") {
      if (!originalTranscript?.trim() || !transcriptText?.trim() || !transcriptBackend?.trim() || !normalisedCommand?.trim() || audioSha === null) {
        fail(path, "ready voice input lacks transcript provenance");
      }
    } else {
      if (transcriptText !== null || originalTranscript !== null || normalisedCommand !== null) {
        fail(path, "non-ready voice input contains command text");
      }
    }
    if (
      transcriptStatus !== "READY" &&
      (selectedProvider !== "NONE" || localAttempted || cloudAttempted)
    ) {
      fail(path, "non-READY voice input invoked inference provider");
    }
  }

  if (request.inputMode !== inputMode) {
    fail(path, "canonical request and governance record input modes differ");
  }
  if (request.evaluationMode !== evaluationMode) {
    fail(path, "canonical request and governance record evaluation modes differ");
  }
  if (request.evaluationMode !== "LIVE" || evaluationMode !== "LIVE") {
    fail(path, "final-demo governance responses must use LIVE evaluation mode");
  }
  if (request.requestedInferenceMode !== requestedMode) {
    fail(path, "canonical request and routing requested modes differ");
  }
  if (request.transcriptionId !== transcriptionId) {
    fail(path, "canonical request and governance record transcription IDs differ");
  }
  if (request.transcriptStatus !== transcriptStatus) {
    fail(path, "canonical request and governance record transcript states differ");
  }
  if (request.expectedDecision !== expectedDecision) {
    fail(path, "canonical request and governance record expected decisions differ");
  }
  if (request.typedText !== typedText) {
    fail(path, "canonical request and governance record typed texts differ");
  }
  if (request.originalTranscriptText !== originalTranscript) {
    fail(path, "canonical request and governance record original transcripts differ");
  }
  if (request.transcriptText !== transcriptText) {
    fail(path, "canonical request and governance record reviewed transcripts differ");
  }
  if (request.transcriptBackend !== transcriptBackend) {
    fail(path, "canonical request and governance record transcript backends differ");
  }
  if (request.transcriptConfidence !== transcriptConfidence) {
    fail(path, "canonical request and governance record transcript confidences differ");
  }
  const requestAudioSha = request.audioSha256?.toLowerCase() ?? null;
  const recordAudioSha = audioSha?.toLowerCase() ?? null;
  if (requestAudioSha !== recordAudioSha) {
    fail(path, "canonical request and governance record audio identities differ");
  }

  if (
    benchmarkId !== null ||
    oracleVersion !== null ||
    expectedDecision !== null ||
    correctnessStatus !== "NOT_EVALUATED" ||
    provenance.benchmarkSha256 !== null ||
    provenance.oracleSha256 !== null
  ) {
    fail(path, "LIVE final-demo trace contains evaluation evidence metadata");
  }

  const validationLatency = finiteNumber(record.validation_latency_ms, `${path}.validation_latency_ms`);
  const totalPipelineLatency = finiteNumber(record.total_pipeline_latency_ms, `${path}.total_pipeline_latency_ms`);
  if (totalPipelineLatency < validationLatency || gateLatencyTotal > validationLatency + 0.001) {
    fail(path, "latency relationship contradicts governance record");
  }
  const executionPermitId = nullableString(record.execution_permit_id, `${path}.execution_permit_id`);
  const simulationStatus = enumValue(record.simulation_status, ["NOT_REQUESTED", "NOT_STARTED", "QUEUED", "RUNNING", "COMPLETED", "STOPPED_BY_OPERATOR", "FAILED"] as const, `${path}.simulation_status`);
  if (executionPermitId !== null && !eligible) {
    fail(path, "execution permit requires eligibility");
  }
  if (simulationStatus !== "NOT_REQUESTED" && simulationStatus !== "NOT_STARTED" && (!eligible || executionPermitId === null)) {
    fail(path, "active simulation requires eligibility and permit");
  }

  const proposalSource = canonical.proposal;
  const proposal = proposalSource === null ? null : (() => {
    const object = objectValue(proposalSource, "governance.canonical_result.proposal", ["actions"]);
    const actions = arrayValue(object.actions, "governance.canonical_result.proposal.actions").map(
      (action, index) => decodeAction(action, `governance.canonical_result.proposal.actions[${index}]`),
    );
    if (actions.length < 1 || actions.length > 8) fail("governance.canonical_result.proposal.actions", "invalid cardinality");
    return { actions };
  })();
  const structuralPass = parseStatus === "PASSED"
    && jsonStatus === "PASSED"
    && schemaStatus === "PASSED";
  if ((proposal !== null) !== structuralPass) {
    fail(
      "governance.canonical_result.proposal",
      "proposal presence contradicts structural gate conjunction",
    );
  }
  if (proposal !== null) {
    const stopIndexes = proposal.actions
      .map((action, index) => action.action === "STOP" ? index : -1)
      .filter((index) => index >= 0);
    if (stopIndexes.length > 1) {
      fail(
        "governance.canonical_result.proposal.actions",
        "multiple STOP actions are forbidden",
      );
    }
    if (stopIndexes.length === 1 && stopIndexes[0] !== proposal.actions.length - 1) {
      fail(
        "governance.canonical_result.proposal.actions",
        "STOP must be the final action",
      );
    }
  }

  return {
    routing_policy_id: stringValue(root.routing_policy_id, "governance.routing_policy_id"),
    routing_policy_version: stringValue(root.routing_policy_version, "governance.routing_policy_version"),
    routing_policy_sha256: sha256(root.routing_policy_sha256, "governance.routing_policy_sha256"),
    local_health: decodeLocalHealth(root.local_health, "governance.local_health"),
    canonical_result: {
      raw_response_text: rawResponseText,
      proposal,
      governance_record: {
        trace_id: stringValue(record.trace_id, `${path}.trace_id`),
        timestamp_utc: timestamp,
        normalised_command: normalisedCommand,
        input_mode: inputMode,
        transcription_id: transcriptionId,
        original_transcript_text: originalTranscript,
        transcript_text: transcriptText,
        transcript_status: transcriptStatus,
        transcript_backend: transcriptBackend,
        transcript_confidence: transcriptConfidence,
        audio_sha256: audioSha,
        policy_id: stringValue(record.policy_id, `${path}.policy_id`),
        evidence_schema_version: exactString(record.evidence_schema_version, "2.0.0", `${path}.evidence_schema_version`) as "2.0.0",
        parse_status: parseStatus,
        json_status: jsonStatus,
        schema_status: schemaStatus,
        plan_semantic_status: semanticStatus,
        ambiguity_status: ambiguityStatus,
        safety_status: safetyStatus,
        authority_status: authorityStatus,
        final_decision: decision,
        execution_eligible: eligible,
        decision_reason_codes: reasons,
        provider_latency_ms: providerLatency,
        validation_latency_ms: validationLatency,
        total_pipeline_latency_ms: totalPipelineLatency,
        execution_permit_id: executionPermitId,
        simulation_status: simulationStatus,
        routing: {
          requested_mode: requestedMode,
          selected_provider: selectedProvider as "FOUNDRY_LOCAL" | "CLOUD" | "NONE",
          selected_model: selectedModel,
          local_attempted: localAttempted,
          cloud_attempted: cloudAttempted,
          fallback_triggered: fallbackTriggered,
          fallback_reason: fallbackReason,
          local_latency_ms: localLatency,
          cloud_latency_ms: cloudLatency,
        },
      },
    },
  };
}

function decodeAudio(value: unknown, path: string): RecordedAudioMetadata {
  const source = objectValue(value, path, ["original_filename", "audio_sha256", "audio_bytes", "sample_rate_hz", "channels", "bits_per_sample", "frame_count", "duration_ms"]);
  const originalFilename = stringValue(source.original_filename, `${path}.original_filename`, false);
  if (
    originalFilename === "." ||
    originalFilename.includes("/") ||
    originalFilename.includes("\\") ||
    /^[A-Za-z]:/.test(originalFilename)
  ) {
    fail(`${path}.original_filename`, "must not contain a path");
  }
  return {
    original_filename: originalFilename,
    audio_sha256: sha256(source.audio_sha256, `${path}.audio_sha256`),
    audio_bytes: integerValue(source.audio_bytes, `${path}.audio_bytes`),
    sample_rate_hz: integerValue(source.sample_rate_hz, `${path}.sample_rate_hz`),
    channels: integerValue(source.channels, `${path}.channels`),
    bits_per_sample: integerValue(source.bits_per_sample, `${path}.bits_per_sample`),
    frame_count: integerValue(source.frame_count, `${path}.frame_count`),
    duration_ms: finiteNumber(source.duration_ms, `${path}.duration_ms`),
  };
}

export function decodeRecordedTranscription(value: unknown): RecordedTranscription {
  const path = "transcription";
  const source = objectValue(value, path, ["result_schema_version", "transcription_id", "timestamp_utc", "transcript_status", "transcript_text", "transcript_backend", "transcript_confidence", "audio", "requested_model_alias", "resolved_model_id", "execution_provider", "sdk_distribution", "sdk_version", "core_distribution", "core_version", "model_cached_before", "model_loaded_before", "model_downloaded_for_request", "model_loaded_for_request", "model_unloaded_after_request", "segment_count", "transcription_latency_ms", "error_code", "error_detail"]);
  const nullableBoolean = (value: unknown, field: string): boolean | null => value === null ? null : booleanValue(value, field);
  const status = enumValue(source.transcript_status, TRANSCRIPT_STATUSES, `${path}.transcript_status`);
  const transcriptText = boundedNullableString(source.transcript_text, `${path}.transcript_text`, 1000);
  const confidence = nullableNumber(source.transcript_confidence, `${path}.transcript_confidence`);
  if (confidence !== null && confidence > 1) {
    fail(`${path}.transcript_confidence`, "must be <= 1");
  }
  const resolvedModel = nullableString(source.resolved_model_id, `${path}.resolved_model_id`);
  const loadedBefore = nullableBoolean(source.model_loaded_before, `${path}.model_loaded_before`);
  const loadedForRequest = booleanValue(source.model_loaded_for_request, `${path}.model_loaded_for_request`);
  const segmentCount = integerValue(source.segment_count, `${path}.segment_count`);
  if (segmentCount > 1000) fail(`${path}.segment_count`, "must be <= 1000");
  const errorCode = source.error_code === null
    ? null
    : stableReasonCode(source.error_code, `${path}.error_code`);

  if (status === "READY" || status === "PARTIAL") {
    if (!transcriptText?.trim()) {
      fail(path, "READY or PARTIAL transcription requires transcript text");
    }
    if (status === "READY" && errorCode !== null) {
      fail(path, "READY transcription cannot contain an error code");
    }
  } else if (transcriptText?.trim()) {
    fail(path, "non-transcript state cannot contain transcript text");
  }
  if ((status === "BACKEND_UNAVAILABLE" || status === "FAILED") && errorCode === null) {
    fail(path, "failed or unavailable transcription requires error code");
  }
  if (status === "EMPTY" && errorCode !== "TRANSCRIPT_EMPTY") {
    fail(path, "EMPTY transcription requires TRANSCRIPT_EMPTY");
  }
  if (status === "READY" || status === "PARTIAL" || status === "EMPTY") {
    if (resolvedModel !== QUALIFIED_SPEECH_MODEL) {
      fail(path, "completed transcription requires qualified model identity");
    }
    if (!(loadedBefore === true || loadedForRequest)) {
      fail(path, "completed transcription requires observed loaded model");
    }
  }
  return {
    result_schema_version: exactString(source.result_schema_version, "1.0.0", `${path}.result_schema_version`) as "1.0.0",
    transcription_id: boundedString(source.transcription_id, `${path}.transcription_id`, 200),
    timestamp_utc: utcTimestamp(source.timestamp_utc, `${path}.timestamp_utc`),
    transcript_status: status as TranscriptStatus,
    transcript_text: transcriptText,
    transcript_backend: exactString(source.transcript_backend, QUALIFIED_TRANSCRIPT_BACKEND, `${path}.transcript_backend`),
    transcript_confidence: confidence,
    audio: decodeAudio(source.audio, `${path}.audio`),
    requested_model_alias: exactString(source.requested_model_alias, QUALIFIED_SPEECH_ALIAS, `${path}.requested_model_alias`),
    resolved_model_id: resolvedModel,
    execution_provider: nullableString(source.execution_provider, `${path}.execution_provider`),
    sdk_distribution: stringValue(source.sdk_distribution, `${path}.sdk_distribution`),
    sdk_version: nullableString(source.sdk_version, `${path}.sdk_version`),
    core_distribution: stringValue(source.core_distribution, `${path}.core_distribution`),
    core_version: nullableString(source.core_version, `${path}.core_version`),
    model_cached_before: nullableBoolean(source.model_cached_before, `${path}.model_cached_before`),
    model_loaded_before: loadedBefore,
    model_downloaded_for_request: booleanValue(source.model_downloaded_for_request, `${path}.model_downloaded_for_request`),
    model_loaded_for_request: loadedForRequest,
    model_unloaded_after_request: booleanValue(source.model_unloaded_after_request, `${path}.model_unloaded_after_request`),
    segment_count: segmentCount,
    transcription_latency_ms: nullableNumber(source.transcription_latency_ms, `${path}.transcription_latency_ms`),
    error_code: errorCode,
    error_detail: boundedNullableString(source.error_detail, `${path}.error_detail`, 500),
  };
}

function safeInteger(value: unknown, path: string, maximum: number): number {
  const result = integerValue(value, path);
  if (!Number.isSafeInteger(result) || result > maximum) {
    return fail(path, `expected safe integer <= ${maximum}`);
  }
  return result;
}

function exactInteger(value: unknown, expected: number, path: string): number {
  const result = safeInteger(value, path, MAX_SAFE_INTEGER);
  if (result !== expected) return fail(path, `expected ${expected}`);
  return expected;
}

function exactStringTuple<const T extends readonly string[]>(
  value: unknown,
  expected: T,
  path: string,
): T {
  const source = arrayValue(value, path);
  if (source.length !== expected.length) return fail(path, "unexpected tuple length");
  expected.forEach((item, index) => exactString(source[index], item, `${path}[${index}]`));
  return expected;
}

function exactIntegerTuple<const T extends readonly number[]>(
  value: unknown,
  expected: T,
  path: string,
): T {
  const source = arrayValue(value, path);
  if (source.length !== expected.length) return fail(path, "unexpected tuple length");
  expected.forEach((item, index) => exactInteger(source[index], item, `${path}[${index}]`));
  return expected;
}

function decodeReplayFrame(value: unknown, path: string): ReplayFrameProjection {
  const source = objectValue(value, path, [
    "frame_index",
    "semantic_snapshot_index",
    "route_configuration_index",
    "route_state",
    "phase",
    "boundary_snapshot",
    "is_key_snapshot",
  ]);
  const frameIndex = safeInteger(requiredProperty(source, "frame_index", path), `${path}.frame_index`, 468);
  const semanticIndex = safeInteger(
    requiredProperty(source, "semantic_snapshot_index", path),
    `${path}.semantic_snapshot_index`,
    468,
  );
  if (semanticIndex !== frameIndex) fail(path, "frame and semantic indices diverge");
  const routeConfigurationIndex = safeInteger(
    requiredProperty(source, "route_configuration_index", path),
    `${path}.route_configuration_index`,
    466,
  );
  const routeState = enumValue(
    requiredProperty(source, "route_state", path),
    REPLAY_ROUTE_STATES,
    `${path}.route_state`,
  );
  const phase = enumValue(
    requiredProperty(source, "phase", path),
    REPLAY_PHASES,
    `${path}.phase`,
  );
  const boundary = enumValue(
    requiredProperty(source, "boundary_snapshot", path),
    REPLAY_BOUNDARIES,
    `${path}.boundary_snapshot`,
  );
  const keySnapshot = booleanValue(
    requiredProperty(source, "is_key_snapshot", path),
    `${path}.is_key_snapshot`,
  );
  if (keySnapshot !== REPLAY_KEY_INDEX_SET.has(semanticIndex)) {
    fail(path, "key-snapshot flag contradicts semantic index");
  }
  return {
    frame_index: frameIndex,
    semantic_snapshot_index: semanticIndex,
    route_configuration_index: routeConfigurationIndex,
    route_state: routeState,
    phase,
    boundary_snapshot: boundary,
    is_key_snapshot: keySnapshot,
  };
}

function decodeReplayQualification(
  value: unknown,
  path: string,
): ReplayQualificationProjection {
  const source = objectValue(value, path, [
    "overall_result",
    "scientific_failure_count",
    "forbidden_contact_failure_count",
    "support_material_penetration_failure_count",
    "required_support_missing_failure_count",
    "failure_codes_present",
    "recorded_failure_example",
  ]);
  const recordedPath = `${path}.recorded_failure_example`;
  const recorded = objectValue(
    requiredProperty(source, "recorded_failure_example", path),
    recordedPath,
    [
      "semantic_snapshot_index",
      "route_state",
      "phase",
      "boundary_snapshot",
      "pair_index",
      "signed_distance_m",
      "decision",
    ],
  );
  const signedDistance = finiteNumber(
    requiredProperty(recorded, "signed_distance_m", recordedPath),
    `${recordedPath}.signed_distance_m`,
    -Number.MAX_VALUE,
  );
  if (signedDistance !== -9.290505685985613e-7) {
    fail(`${recordedPath}.signed_distance_m`, "unexpected frozen distance");
  }
  return {
    overall_result: exactString(
      requiredProperty(source, "overall_result", path),
      "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION",
      `${path}.overall_result`,
    ) as "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION",
    scientific_failure_count: exactInteger(
      requiredProperty(source, "scientific_failure_count", path),
      118,
      `${path}.scientific_failure_count`,
    ) as 118,
    forbidden_contact_failure_count: exactInteger(
      requiredProperty(source, "forbidden_contact_failure_count", path),
      0,
      `${path}.forbidden_contact_failure_count`,
    ) as 0,
    support_material_penetration_failure_count: exactInteger(
      requiredProperty(source, "support_material_penetration_failure_count", path),
      118,
      `${path}.support_material_penetration_failure_count`,
    ) as 118,
    required_support_missing_failure_count: exactInteger(
      requiredProperty(source, "required_support_missing_failure_count", path),
      0,
      `${path}.required_support_missing_failure_count`,
    ) as 0,
    failure_codes_present: exactStringTuple(
      requiredProperty(source, "failure_codes_present", path),
      ["B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"] as const,
      `${path}.failure_codes_present`,
    ),
    recorded_failure_example: {
      semantic_snapshot_index: exactInteger(
        requiredProperty(recorded, "semantic_snapshot_index", recordedPath),
        352,
        `${recordedPath}.semantic_snapshot_index`,
      ) as 352,
      route_state: exactString(
        requiredProperty(recorded, "route_state", recordedPath),
        "DESTINATION_PLACE",
        `${recordedPath}.route_state`,
      ) as "DESTINATION_PLACE",
      phase: exactString(
        requiredProperty(recorded, "phase", recordedPath),
        "RELEASE_BOUNDARY",
        `${recordedPath}.phase`,
      ) as "RELEASE_BOUNDARY",
      boundary_snapshot: exactString(
        requiredProperty(recorded, "boundary_snapshot", recordedPath),
        "POST",
        `${recordedPath}.boundary_snapshot`,
      ) as "POST",
      pair_index: exactInteger(
        requiredProperty(recorded, "pair_index", recordedPath),
        78,
        `${recordedPath}.pair_index`,
      ) as 78,
      signed_distance_m: signedDistance,
      decision: exactString(
        requiredProperty(recorded, "decision", recordedPath),
        "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION",
        `${recordedPath}.decision`,
      ) as "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION",
    },
  };
}

export function decodeReplayState(
  value: unknown,
  expectedScenarioId: string,
): ReplayStateProjection {
  const path = "replay";
  const source = objectValue(value, path, [
    "contract_id",
    "contract_version",
    "scenario_id",
    "binding_id",
    "session_id",
    "control_version",
    "projection_version",
    "lifecycle_state",
    "command_in_flight",
    "current_frame",
    "frame_count",
    "key_snapshot_indices",
    "allowed_controls",
    "available_controls",
    "presentation_cadence_ms",
    "b2_sha256",
    "b3_2_sha256",
    "qualification",
    "presentation_labels",
    "physical_execution_authority",
    "last_error_code",
    "updated_at_utc",
  ]);
  const expectedScenario = scenarioIdentifier(expectedScenarioId, "expectedScenarioId");
  const scenarioId = scenarioIdentifier(
    requiredProperty(source, "scenario_id", path),
    `${path}.scenario_id`,
  );
  if (scenarioId !== expectedScenario) fail(`${path}.scenario_id`, "unexpected scenario identity");
  const lifecycle = enumValue(
    requiredProperty(source, "lifecycle_state", path),
    REPLAY_LIFECYCLES,
    `${path}.lifecycle_state`,
  );
  const sessionValue = requiredProperty(source, "session_id", path);
  const sessionId = sessionValue === null
    ? null
    : boundedString(sessionValue, `${path}.session_id`, 200);
  if (sessionId !== null && !sessionId.trim()) fail(`${path}.session_id`, "must be non-blank");
  const controlVersion = safeInteger(
    requiredProperty(source, "control_version", path),
    `${path}.control_version`,
    MAX_SAFE_INTEGER,
  );
  const projectionVersion = safeInteger(
    requiredProperty(source, "projection_version", path),
    `${path}.projection_version`,
    MAX_SAFE_INTEGER,
  );
  const commandInFlight = booleanValue(
    requiredProperty(source, "command_in_flight", path),
    `${path}.command_in_flight`,
  );
  const frameValue = requiredProperty(source, "current_frame", path);
  const frame = frameValue === null ? null : decodeReplayFrame(frameValue, `${path}.current_frame`);
  const availableSource = arrayValue(
    requiredProperty(source, "available_controls", path),
    `${path}.available_controls`,
  );
  const available = availableSource.map((item, index) =>
    enumValue(item, REPLAY_CONTROLS, `${path}.available_controls[${index}]`),
  );
  if (new Set(available).size !== available.length) fail(`${path}.available_controls`, "duplicates forbidden");
  const availableOrder = available.map((control) => REPLAY_CONTROLS.indexOf(control));
  if (availableOrder.some((value, index) => index > 0 && value <= availableOrder[index - 1]!)) {
    fail(`${path}.available_controls`, "control order is not canonical");
  }
  const lastErrorValue = requiredProperty(source, "last_error_code", path);
  const lastError = lastErrorValue === null
    ? null
    : enumValue(lastErrorValue, REPLAY_LAST_ERRORS, `${path}.last_error_code`);

  if (lifecycle === "IDLE") {
    if (sessionId !== null || controlVersion !== 0 || projectionVersion !== 0 || frame !== null || lastError !== null) {
      fail(path, "canonical IDLE projection is contradictory");
    }
    const expectedAvailable = commandInFlight ? [] : ["START"];
    if (available.join("|") !== expectedAvailable.join("|")) {
      fail(`${path}.available_controls`, "canonical IDLE availability is contradictory");
    }
  } else {
    if (sessionId === null || controlVersion < 1 || projectionVersion < 1) {
      fail(path, "retained session identity/version is missing");
    }
    if (["PAUSED", "PLAYING", "COMPLETED"].includes(lifecycle) && frame === null) {
      fail(path, "healthy active projection requires a current frame");
    }
    if (["PAUSED", "PLAYING", "COMPLETED"].includes(lifecycle) && lastError !== null) {
      fail(path, "healthy projection cannot carry a replay error");
    }
    if (lifecycle === "FAILED" && lastError === null) fail(path, "FAILED requires a replay error");
    if (lifecycle === "CLEANUP_FAILED" && lastError !== "REPLAY_CLEANUP_UNRESOLVED") {
      fail(path, "CLEANUP_FAILED requires cleanup-unresolved error");
    }
    if (lifecycle === "COMPLETED" && frame?.frame_index !== 468) {
      fail(path, "COMPLETED requires final frame");
    }
    if (available.includes("START")) fail(`${path}.available_controls`, "active session cannot START");
  }
  if (commandInFlight && available.length !== 0) {
    fail(`${path}.available_controls`, "unsettled command requires empty availability");
  }

  return {
    contract_id: exactString(
      requiredProperty(source, "contract_id", path),
      "PROTOTYPE5_D3_REPLAY_STATE_V1",
      `${path}.contract_id`,
    ) as "PROTOTYPE5_D3_REPLAY_STATE_V1",
    contract_version: exactString(
      requiredProperty(source, "contract_version", path),
      "1.0.0",
      `${path}.contract_version`,
    ) as "1.0.0",
    scenario_id: scenarioId,
    binding_id: exactString(
      requiredProperty(source, "binding_id", path),
      "FROZEN_B2_B3_2_EVIDENCE_V1",
      `${path}.binding_id`,
    ) as "FROZEN_B2_B3_2_EVIDENCE_V1",
    session_id: sessionId,
    control_version: controlVersion,
    projection_version: projectionVersion,
    lifecycle_state: lifecycle,
    command_in_flight: commandInFlight,
    current_frame: frame,
    frame_count: exactInteger(requiredProperty(source, "frame_count", path), 469, `${path}.frame_count`) as 469,
    key_snapshot_indices: exactIntegerTuple(
      requiredProperty(source, "key_snapshot_indices", path),
      REPLAY_KEY_INDICES,
      `${path}.key_snapshot_indices`,
    ),
    allowed_controls: exactStringTuple(
      requiredProperty(source, "allowed_controls", path),
      REPLAY_CONTROLS,
      `${path}.allowed_controls`,
    ),
    available_controls: available,
    presentation_cadence_ms: exactInteger(
      requiredProperty(source, "presentation_cadence_ms", path),
      50,
      `${path}.presentation_cadence_ms`,
    ) as 50,
    b2_sha256: exactString(requiredProperty(source, "b2_sha256", path), B2_SHA256, `${path}.b2_sha256`),
    b3_2_sha256: exactString(requiredProperty(source, "b3_2_sha256", path), B3_2_SHA256, `${path}.b3_2_sha256`),
    qualification: decodeReplayQualification(requiredProperty(source, "qualification", path), `${path}.qualification`),
    presentation_labels: exactStringTuple(
      requiredProperty(source, "presentation_labels", path),
      REPLAY_LABELS,
      `${path}.presentation_labels`,
    ),
    physical_execution_authority: exactString(
      requiredProperty(source, "physical_execution_authority", path),
      "NOT_IMPLEMENTED",
      `${path}.physical_execution_authority`,
    ) as "NOT_IMPLEMENTED",
    last_error_code: lastError,
    updated_at_utc: utcTimestamp(requiredProperty(source, "updated_at_utc", path), `${path}.updated_at_utc`),
  };
}

export function decodeReplayError(value: unknown): ReplayErrorCode {
  const path = "replayError";
  const source = objectValue(value, path, ["code"]);
  return enumValue(requiredProperty(source, "code", path), REPLAY_ERRORS, `${path}.code`);
}
