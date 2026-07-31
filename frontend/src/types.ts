export type AvailabilityStatus = "AVAILABLE" | "UNAVAILABLE" | "NOT_ASSESSED";
export type InferenceMode = "LOCAL" | "CLOUD" | "AUTO";
export type DomainId = "MANUFACTURING" | "HEALTHCARE_SYNTHETIC";
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
  | string;

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
  action: string;
  object_id?: string | null;
  source_id?: string | null;
  destination_id?: string | null;
  duration_ms?: number | null;
}

export interface GovernanceRecord {
  trace_id: string;
  timestamp_utc: string;
  normalised_command: string;
  input_mode: "TYPED" | "VOICE";
  transcription_id: string | null;
  original_transcript_text: string | null;
  transcript_text: string | null;
  transcript_status: TranscriptStatus | "NOT_APPLICABLE";
  transcript_backend: string | null;
  transcript_confidence: number | null;
  audio_sha256: string | null;
  policy_id: string;
  evidence_schema_version: string;
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
  simulation_status: string;
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
  command: string;
  inference_mode: InferenceMode;
  domain_id: DomainId;
  requester_role: "operator" | "observer" | "supervisor";
}

export interface VoiceCommandPayload {
  transcription_id: string;
  reviewed_transcript_text: string;
  inference_mode: InferenceMode;
  domain_id: DomainId;
  requester_role: "operator" | "observer" | "supervisor";
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
  result_schema_version: string;
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
