export type AvailabilityStatus = "AVAILABLE" | "UNAVAILABLE" | "NOT_ASSESSED";
export type InferenceMode = "LOCAL" | "CLOUD" | "AUTO";
export type DomainId = "MANUFACTURING";
export type FinalDecision = "ACCEPT" | "REJECT" | "CLARIFY" | "ERROR";
export type TranscriptStatus =
  | "READY"
  | "PARTIAL"
  | "EMPTY"
  | "BACKEND_UNAVAILABLE"
  | "FAILED"
  | "CANCELLED";
export type GateDisplayStatus =
  | "PASSED"
  | "FAILED"
  | "NOT_ASSESSABLE"
  | "NOT_EVALUATED"
  | "ERROR"
  | "VALID"
  | "INVALID"
  | "NOT_ASSESSABLE_NO_PROPOSAL"
  | "NOT_ASSESSABLE_PARSE_FAILED"
  | "NOT_ASSESSABLE_SCHEMA_INVALID"
  | "NOT_ASSESSABLE_MISSING_ORACLE"
  | "NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT";

export type AuthorityState =
  | "UNTRUSTED_PROPOSAL"
  | "GOVERNANCE_DECISION"
  | "EXECUTION_ELIGIBILITY"
  | "QUALIFICATION_REPLAY_ACCESS"
  | "DOWNSTREAM_GEOMETRIC_QUALIFICATION"
  | "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED";

export interface DemoScenario {
  scenario_id: string;
  display_name: string;
  presentation_classification:
    | "SYNTHETIC_LIVE_DEMO"
    | "FROZEN_RESEARCH_EVIDENCE"
    | "FROZEN_EVIDENCE_REPLAY";
  model_input_enabled: boolean;
  allowed_inference_modes: InferenceMode[];
  registered_command: string;
  demonstration_purpose: string;
  evidence_classification:
    | "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE"
    | "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT"
    | "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION";
  replay_capability_classification:
    | "GOVERNANCE_ONLY"
    | "FROZEN_B2_REPLAY_COMPATIBLE";
  qualification_replay_access: "PROHIBITED" | "SERVER_REGISTERED_ONLY";
  downstream_geometric_qualification: "FAIL" | "NOT_APPLICABLE";
  claim_boundary_note: string;
}

export interface DemoManifest {
  contract_id: "PROTOTYPE5_FINAL_DEMONSTRATOR_D0";
  contract_version: "1.0.0";
  authority_taxonomy: AuthorityState[];
  physical_execution_authority_state: "NOT_IMPLEMENTED";
  healthcare_scope: "OUT_OF_SCOPE_FOR_FINAL_DEMO";
  d2_replay_enabled: false;
  scenarios: DemoScenario[];
}

export interface LocalHealth {
  circuit_state: "CLOSED" | "OPEN" | "HALF_OPEN";
  local_available: boolean;
  local_model_ready: boolean;
  consecutive_failures: number;
  rolling_sample_count: number;
  rolling_structured_success_rate: number | null;
  rolling_p50_latency_ms: number | null;
  rolling_p95_latency_ms: number | null;
  last_failure_reason: string;
  last_circuit_transition: string | null;
}

export interface DemoStatus {
  service_status: string;
  frozen_baseline_tag: string;
  frozen_baseline_commit: string;
  software_commit: string;
  evidence_schema_version: string;
  supported_domains: DomainId[];
  supported_inference_modes: InferenceMode[];
  local_status: AvailabilityStatus;
  cloud_status: AvailabilityStatus;
  speech_status: AvailabilityStatus;
  simulator_status: AvailabilityStatus;
  local_health: LocalHealth;
}

export interface ActionStep {
  action: "MOVE" | "PICK" | "PLACE" | "WAIT" | "STOP" | "INSPECT";
  object_id: string | null;
  source_id: string | null;
  destination_id: string | null;
  duration_ms: number | null;
}

export interface GovernanceRecord {
  trace_id: string;
  timestamp_utc: string;
  normalised_command: string | null;
  input_mode: "TYPED" | "VOICE";
  transcription_id: string | null;
  original_transcript_text: string | null;
  transcript_text: string | null;
  transcript_status: TranscriptStatus | "NOT_APPLICABLE";
  transcript_backend: string | null;
  transcript_confidence: number | null;
  audio_sha256: string | null;
  policy_id: string;
  evidence_schema_version: "2.0.0";
  parse_status: GateDisplayStatus;
  json_status: GateDisplayStatus;
  schema_status: GateDisplayStatus;
  plan_semantic_status: GateDisplayStatus;
  ambiguity_status: GateDisplayStatus;
  safety_status: GateDisplayStatus;
  authority_status: GateDisplayStatus;
  final_decision: FinalDecision;
  execution_eligible: boolean;
  decision_reason_codes: string[];
  provider_latency_ms: number | null;
  validation_latency_ms: number;
  total_pipeline_latency_ms: number;
  execution_permit_id: string | null;
  simulation_status:
    | "NOT_REQUESTED"
    | "NOT_STARTED"
    | "QUEUED"
    | "RUNNING"
    | "COMPLETED"
    | "STOPPED_BY_OPERATOR"
    | "FAILED";
  routing: {
    requested_mode: InferenceMode;
    selected_provider: "FOUNDRY_LOCAL" | "CLOUD" | "NONE";
    selected_model: string | null;
    local_attempted: boolean;
    cloud_attempted: boolean;
    fallback_triggered: boolean;
    fallback_reason: string;
    local_latency_ms: number | null;
    cloud_latency_ms: number | null;
  };
}

export interface HybridGovernanceResult {
  routing_policy_id: string;
  routing_policy_version: string;
  routing_policy_sha256: string;
  local_health: LocalHealth;
  canonical_result: {
    raw_response_text: string | null;
    proposal: { actions: ActionStep[] } | null;
    governance_record: GovernanceRecord;
  };
}

export interface TypedCommandPayload {
  scenario_id: string;
  command: string;
  inference_mode: InferenceMode;
}

export interface VoiceCommandPayload {
  scenario_id: string;
  transcription_id: string;
  reviewed_transcript_text: string;
  inference_mode: InferenceMode;
}

export interface RecordedAudioMetadata {
  original_filename: string;
  audio_sha256: string;
  audio_bytes: number;
  sample_rate_hz: number;
  channels: number;
  bits_per_sample: number;
  frame_count: number;
  duration_ms: number;
}

export interface RecordedTranscription {
  result_schema_version: "1.0.0";
  transcription_id: string;
  timestamp_utc: string;
  transcript_status: TranscriptStatus;
  transcript_text: string | null;
  transcript_backend: string;
  transcript_confidence: number | null;
  audio: RecordedAudioMetadata;
  requested_model_alias: string;
  resolved_model_id: string | null;
  execution_provider: string | null;
  sdk_distribution: string;
  sdk_version: string | null;
  core_distribution: string;
  core_version: string | null;
  model_cached_before: boolean | null;
  model_loaded_before: boolean | null;
  model_downloaded_for_request: boolean;
  model_loaded_for_request: boolean;
  model_unloaded_after_request: boolean;
  segment_count: number;
  transcription_latency_ms: number | null;
  error_code: string | null;
  error_detail: string | null;
}
