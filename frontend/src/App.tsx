import {
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ChangeEvent,
  type MutableRefObject,
  type ReactNode,
} from "react";
import {
  Badge,
  Button,
  Dropdown,
  Field,
  Option,
  Radio,
  RadioGroup,
  Spinner,
  Textarea,
  Tooltip,
} from "@fluentui/react-components";
import {
  ArrowDownload24Regular,
  ArrowUpload24Regular,
  Bot24Regular,
  Cloud24Regular,
  Desktop24Regular,
  Dismiss24Regular,
  Mic24Regular,
  Send24Regular,
  ShieldCheckmark24Regular,
} from "@fluentui/react-icons";
import {
  ApiRequestError,
  ApiTransportError,
  ReplayApiRequestError,
  controlReplay,
  getDemoManifest,
  getReplayState,
  getDemoStatus,
  startReplay,
  submitTypedCommand,
  submitVoiceCommand,
  transcribeRecordedAudio,
} from "./api";
import {
  acceptsReplayProjection,
  demoReducer,
  initialDemoState,
  type ClientFailure,
  type GovernanceContext,
  type ReplayClientFailure,
  type ReplayMutationContext,
  type ReplayReadContext,
} from "./demoState";
import { ContractValidationError } from "./runtimeContracts";
import {
  deriveAuthorityProgression,
  evidenceClassificationLabel,
  gateStatusLabel,
  presentationClassificationLabel,
  providerLabel,
  secondaryEvidenceClassificationLabel,
  SYSTEM_STATUS_EVIDENCE_LABEL,
} from "./authorityPresentation";
import type {
  AvailabilityStatus,
  DemoScenario,
  InferenceMode,
  ReplayControl,
  ReplayStateProjection,
} from "./types";

const gateDefinitions = [
  ["Parse", "parse_status"],
  ["JSON", "json_status"],
  ["Schema", "schema_status"],
  ["Plan semantics", "plan_semantic_status"],
  ["Ambiguity", "ambiguity_status"],
  ["Safety", "safety_status"],
  ["Role / action authority", "authority_status"],
] as const;

function availabilityLabel(status: AvailabilityStatus | undefined): string {
  if (status === "AVAILABLE") return "Available";
  if (status === "UNAVAILABLE") return "Unavailable";
  return "Not assessed";
}

function statusTone(status: string): "success" | "danger" | "warning" | "informative" | "subtle" {
  if (status === "PASSED" || status === "VALID" || status === "ACCEPT" || status === "AVAILABLE" || status === "ELIGIBLE") {
    return "success";
  }
  if (status === "FAILED" || status === "FAIL" || status === "INVALID" || status === "REJECT" || status === "ERROR" || status === "UNAVAILABLE") {
    return "danger";
  }
  if (status === "CLARIFY" || status === "HALF_OPEN") return "warning";
  if (status === "NOT_ASSESSABLE" || status.startsWith("NOT_ASSESSABLE")) {
    return "warning";
  }
  return "subtle";
}

function formatStatus(status: string): string {
  return status.replaceAll("_", " ").toLowerCase().replace(/^\w/, (value) => value.toUpperCase());
}

function formatLatency(value: number | null | undefined): string {
  return value == null ? "Not recorded" : `${value.toFixed(1)} ms`;
}

export const BOOTSTRAP_CLIENT_DEADLINE_MS = 30_000;
export const GOVERNANCE_CLIENT_DEADLINE_MS = 60_000;
export const SPEECH_CLIENT_DEADLINE_MS = 130_000;
export const REPLAY_START_CLIENT_DEADLINE_MS = 20_000;
export const REPLAY_CONTROL_CLIENT_DEADLINE_MS = 10_000;
export const REPLAY_GET_CLIENT_DEADLINE_MS = 5_000;
export const REPLAY_POLL_INTERVAL_MS = 500;

const replayControls = [
  ["START", "Start"],
  ["PAUSE", "Pause"],
  ["RESUME", "Resume"],
  ["NEXT_SNAPSHOT", "Next snapshot"],
  ["PREVIOUS_SNAPSHOT", "Previous snapshot"],
  ["STOP", "Stop"],
  ["RESET_VIEW", "Reset view"],
] as const satisfies readonly (readonly [ReplayControl, string])[];

const reconciliationErrors = new Set<ReplayClientFailure["code"]>([
  "CLIENT_TIMEOUT",
  "NETWORK_FAILURE",
  "REPLAY_START_TIMEOUT",
  "REPLAY_CONTROL_SETTLEMENT_UNKNOWN",
  "REPLAY_COMMAND_EXPIRED",
  "REPLAY_SESSION_ACTIVE",
  "REPLAY_SESSION_STALE",
  "REPLAY_CONTROL_VERSION_STALE",
  "REPLAY_CONTROL_INVALID_STATE",
  "REPLAY_FRAME_BOUNDARY",
  "REPLAY_COMMAND_CHANNEL_FULL",
  "REPLAY_CLEANUP_UNRESOLVED",
  "REPLAY_RUNTIME_INTEGRITY_FAILED",
  "REPLAY_SCENE_FAILED",
]);

interface OperationOwner {
  readonly operationId: number;
  readonly controller: AbortController;
  deadlineHandle: ReturnType<typeof setTimeout> | null;
}

type OperationOwnerRef = MutableRefObject<OperationOwner | null>;

function failureMessage(failure: ClientFailure): string {
  return failure.detail ?? failure.code;
}

function classifyClientFailure(error: unknown): ClientFailure {
  if (error instanceof ApiRequestError) {
    return { code: "HTTP_ERROR", detail: error.message };
  }
  if (error instanceof ContractValidationError) {
    return { code: "CONTRACT_FAILURE", detail: null };
  }
  if (error instanceof ApiTransportError) {
    return { code: "NETWORK_FAILURE", detail: null };
  }
  return { code: "UNKNOWN_CLIENT_FAILURE", detail: null };
}

function classifyReplayFailure(error: unknown): ReplayClientFailure {
  if (error instanceof ReplayApiRequestError) {
    return { code: error.code, detail: null };
  }
  if (error instanceof ContractValidationError) {
    return { code: "CONTRACT_FAILURE", detail: null };
  }
  if (error instanceof ApiTransportError) {
    return { code: "NETWORK_FAILURE", detail: null };
  }
  return { code: "UNKNOWN_CLIENT_FAILURE", detail: null };
}

export function clientErrorMessage(error: unknown): string {
  return failureMessage(classifyClientFailure(error));
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function nextOperationId(counter: MutableRefObject<number>): number {
  const next = counter.current + 1;
  if (!Number.isSafeInteger(next)) {
    throw new Error("CLIENT_OPERATION_ID_EXHAUSTED");
  }
  counter.current = next;
  return next;
}

function cancelOwner(ownerRef: OperationOwnerRef): void {
  const owner = ownerRef.current;
  if (owner === null) return;
  ownerRef.current = null;
  if (owner.deadlineHandle !== null) clearTimeout(owner.deadlineHandle);
  owner.controller.abort();
}

function releaseOwner(
  ownerRef: OperationOwnerRef,
  operationId: number,
): boolean {
  const owner = ownerRef.current;
  if (owner?.operationId !== operationId) return false;
  ownerRef.current = null;
  if (owner.deadlineHandle !== null) clearTimeout(owner.deadlineHandle);
  return true;
}

function startOwner(
  ownerRef: OperationOwnerRef,
  operationId: number,
  clientDeadlineMs: number,
  onTimeout: () => void,
): OperationOwner {
  cancelOwner(ownerRef);
  const owner: OperationOwner = {
    operationId,
    controller: new AbortController(),
    deadlineHandle: null,
  };
  ownerRef.current = owner;
  owner.deadlineHandle = setTimeout(() => {
    if (ownerRef.current !== owner) return;
    ownerRef.current = null;
    if (owner.deadlineHandle !== null) clearTimeout(owner.deadlineHandle);
    owner.controller.abort();
    onTimeout();
  }, clientDeadlineMs);
  return owner;
}

export function isInferenceMode(value: unknown): value is InferenceMode {
  return value === "LOCAL" || value === "CLOUD" || value === "AUTO";
}

export function selectInferenceMode(
  current: InferenceMode,
  candidate: unknown,
): InferenceMode {
  return isInferenceMode(candidate) ? candidate : current;
}

function isReplayScenario(scenario: DemoScenario | null): boolean {
  return scenario?.replay_capability_classification === "FROZEN_B2_REPLAY_COMPATIBLE" &&
    scenario.qualification_replay_access === "SERVER_REGISTERED_ONLY";
}

interface ReplayPanelProps {
  readonly projection: ReplayStateProjection | null;
  readonly clientKind: "INACTIVE" | "RECONCILING" | "READY" | "MUTATING" | "ERROR" | "FATAL";
  readonly failure: ReplayClientFailure | null;
  readonly announcement: string | null;
  readonly physicalAuthority: "NOT_IMPLEMENTED";
  readonly onControl: (control: ReplayControl) => void;
}

function ReplayPanel({
  projection,
  clientKind,
  failure,
  announcement,
  physicalAuthority,
  onControl,
}: ReplayPanelProps) {
  const available = new Set(projection?.available_controls ?? []);
  const controlsLocked = clientKind !== "READY";
  const frame = projection?.current_frame ?? null;
  const qualification = projection?.qualification ?? null;
  const recorded = qualification?.recorded_failure_example ?? null;
  return (
    <section className="replay-panel" aria-labelledby="replay-heading" aria-busy={clientKind === "RECONCILING" || clientKind === "MUTATING"}>
      <div className="replay-heading-row">
        <div>
          <h2 id="replay-heading">EVIDENCE REPLAY</h2>
          <strong>NOT PHYSICAL EXECUTION</strong>
        </div>
        <Badge appearance="outline" color={projection?.lifecycle_state === "FAILED" || projection?.lifecycle_state === "CLEANUP_FAILED" ? "danger" : "informative"}>
          {projection?.lifecycle_state ?? "STATE NOT LOADED"}
        </Badge>
      </div>
      <p className="replay-timing-label">DISCRETE SAMPLED STATES — NO DYNAMIC TIMING</p>
      <p className="replay-boundary-note">
        SCHEMA VALIDITY ≠ EXECUTION ELIGIBILITY ≠ DOWNSTREAM GEOMETRIC VALIDITY ≠ PHYSICAL SAFETY
      </p>
      <div className="replay-live-region" role="status" aria-live="polite" aria-atomic="true">
        {announcement ?? "Awaiting authoritative replay state."}
      </div>
      {(clientKind === "RECONCILING" || clientKind === "MUTATING") && (
        <Spinner size="small" label={clientKind === "MUTATING" ? "Replay control unsettled" : "Reconciling replay state"} />
      )}
      {failure !== null && (
        <div className="request-error" role="alert">
          <strong>{clientKind === "FATAL" ? "Replay restart required" : "Replay request failed"}</strong>
          <span>{failure.code}</span>
        </div>
      )}
      <div className="replay-controls" aria-label="Evidence replay controls">
        {replayControls.map(([control, label]) => (
          <Button
            key={control}
            disabled={controlsLocked || !available.has(control)}
            onClick={() => onControl(control)}
          >
            {label}
          </Button>
        ))}
      </div>
      <div className="replay-state-grid">
        <div><span>Lifecycle</span><strong>{projection?.lifecycle_state ?? "NOT LOADED"}</strong></div>
        <div><span>Frame</span><strong>{frame === null ? "NO ACTIVE FRAME" : `Frame ${frame.frame_index + 1} of ${projection?.frame_count ?? 469}`}</strong></div>
        <div><span>Semantic snapshot</span><strong>{frame?.semantic_snapshot_index ?? "N/A"}</strong></div>
        <div><span>Route configuration</span><strong>{frame?.route_configuration_index ?? "N/A"}</strong></div>
        <div><span>Route state</span><strong>{frame?.route_state ?? "N/A"}</strong></div>
        <div><span>Phase</span><strong>{frame?.phase ?? "N/A"}</strong></div>
        <div><span>Boundary snapshot</span><strong>{frame?.boundary_snapshot ?? "N/A"}</strong></div>
        <div><span>Key snapshot</span><strong>{frame === null ? "N/A" : frame.is_key_snapshot ? "YES" : "NO"}</strong></div>
      </div>
      <section className="replay-evidence" aria-labelledby="replay-evidence-heading">
        <h3 id="replay-evidence-heading">Frozen downstream qualification</h3>
        <div className="replay-evidence-grid">
          <span>Overall result</span><strong>{qualification?.overall_result ?? "AUTHORITATIVE STATE NOT LOADED"}</strong>
          <span>Scientific failures</span><strong>{qualification?.scientific_failure_count ?? "N/A"}</strong>
          <span>Support-material penetrations</span><strong>{qualification?.support_material_penetration_failure_count ?? "N/A"}</strong>
          <span>Forbidden-contact failures</span><strong>{qualification?.forbidden_contact_failure_count ?? "N/A"}</strong>
          <span>Required-support-missing failures</span><strong>{qualification?.required_support_missing_failure_count ?? "N/A"}</strong>
          <span>Last replay error</span><strong>{projection?.last_error_code ?? "NONE"}</strong>
          <span>Physical execution authority</span><strong>{projection?.physical_execution_authority ?? physicalAuthority}</strong>
        </div>
        {recorded !== null && (
          <p className="recorded-failure">
            <strong>Recorded frozen failure example:</strong>{" "}
            snapshot {recorded.semantic_snapshot_index}, pair {recorded.pair_index},{" "}
            {recorded.decision}, signed distance {recorded.signed_distance_m} m.
          </p>
        )}
        <dl className="replay-digests">
          <div><dt>B2 SHA-256</dt><dd>{projection?.b2_sha256 ?? "NOT LOADED"}</dd></div>
          <div><dt>B3.2 SHA-256</dt><dd>{projection?.b3_2_sha256 ?? "NOT LOADED"}</dd></div>
        </dl>
      </section>
      <p className="replay-completion-note">
        COMPLETED means only that the frozen replay reached its final registered discrete state.
      </p>
    </section>
  );
}

export function App() {
  const [state, dispatch] = useReducer(demoReducer, initialDemoState);
  const audioInputRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(false);
  const nextOperationIdRef = useRef(0);
  const bootstrapOwnerRef = useRef<OperationOwner | null>(null);
  const governanceOwnerRef = useRef<OperationOwner | null>(null);
  const transcriptionOwnerRef = useRef<OperationOwner | null>(null);
  const replayMutationOwnerRef = useRef<OperationOwner | null>(null);
  const replayReadOwnerRef = useRef<OperationOwner | null>(null);
  const replayPollHandleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectedScenarioIdRef = useRef("");
  const replayProjectionRef = useRef<ReplayStateProjection | null>(null);
  const replayFatalRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    const operationId = nextOperationId(nextOperationIdRef);
    dispatch({ type: "BOOTSTRAP_STARTED", operationId });
    const owner = startOwner(
      bootstrapOwnerRef,
      operationId,
      BOOTSTRAP_CLIENT_DEADLINE_MS,
      () => {
        if (!mountedRef.current) return;
        dispatch({
          type: "BOOTSTRAP_FAILED",
          operationId,
          failure: { code: "CLIENT_TIMEOUT", detail: null },
        });
      },
    );
    // Browser wait deadlines do not prove server or provider cancellation.
    Promise.all([
      getDemoManifest(owner.controller.signal),
      getDemoStatus(owner.controller.signal),
    ])
      .then(([nextManifest, nextStatus]) => {
        if (!mountedRef.current || bootstrapOwnerRef.current !== owner) return;
        const initial = nextManifest.scenarios.find(
          (scenario) => scenario.model_input_enabled,
        );
        const initialMode = initial?.allowed_inference_modes.includes("AUTO")
          ? "AUTO"
          : initial?.allowed_inference_modes[0];
        if (!initial || !initialMode) {
          throw new ContractValidationError(
            "manifest: no live scenario with an inference mode",
          );
        }
        if (!releaseOwner(bootstrapOwnerRef, operationId)) return;
        selectedScenarioIdRef.current = initial.scenario_id;
        dispatch({
          type: "BOOTSTRAP_SUCCEEDED",
          operationId,
          manifest: nextManifest,
          status: nextStatus,
          initialScenarioId: initial.scenario_id,
          initialMode,
        });
      })
      .catch((error: unknown) => {
        if (!mountedRef.current || bootstrapOwnerRef.current !== owner) return;
        if (!releaseOwner(bootstrapOwnerRef, operationId)) return;
        // Promise.all has a sibling request; stop it after this operation loses
        // ownership, without claiming any server-side cancellation.
        owner.controller.abort();
        if (isAbortError(error)) return;
        dispatch({
          type: "BOOTSTRAP_FAILED",
          operationId,
          failure: classifyClientFailure(error),
        });
      });
    return () => {
      mountedRef.current = false;
      cancelOwner(bootstrapOwnerRef);
      cancelOwner(governanceOwnerRef);
      cancelOwner(transcriptionOwnerRef);
      cancelOwner(replayMutationOwnerRef);
      cancelOwner(replayReadOwnerRef);
      if (replayPollHandleRef.current !== null) {
        clearTimeout(replayPollHandleRef.current);
        replayPollHandleRef.current = null;
      }
    };
  }, []);

  const manifest = state.bootstrap.kind === "READY"
    ? state.bootstrap.manifest
    : null;
  const status = state.bootstrap.kind === "READY" ? state.bootstrap.status : null;
  const statusError = state.bootstrap.kind === "FAILED"
    ? failureMessage(state.bootstrap.failure)
    : null;
  const { command, scenarioId } = state.controls;
  const mode = state.controls.inferenceMode;
  const pending = state.governance.kind === "SUBMITTING";
  const transcribing = state.transcription.kind === "TRANSCRIBING";
  const result = state.governance.kind === "SUCCEEDED"
    ? state.governance.result
    : null;
  const governanceContext = state.governance.kind === "IDLE"
    ? null
    : state.governance.context;
  const submittedCommand = governanceContext?.command ?? null;
  const submittedInputMode = governanceContext?.inputMode ?? "TYPED";
  const requestError = state.governance.kind === "FAILED"
    ? failureMessage(state.governance.failure)
    : null;
  const transcription = state.transcription.kind === "READY"
    ? state.transcription.transcription
    : null;
  const transcriptConsumed = state.transcription.kind === "READY"
    ? state.transcription.consumed
    : false;
  const transcriptionError = state.transcription.kind === "FAILED"
    ? failureMessage(state.transcription.failure)
    : null;
  const record = result?.canonical_result.governance_record ?? null;
  const selectedScenario = manifest?.scenarios.find(
    (scenario) => scenario.scenario_id === scenarioId,
  ) ?? null;

  useEffect(() => {
    selectedScenarioIdRef.current = scenarioId;
    replayProjectionRef.current = state.replay.projection;
    if (state.replay.kind === "FATAL") replayFatalRef.current = true;
  }, [scenarioId, state.replay.kind, state.replay.projection]);
  const authorityRows = useMemo(
    () =>
      manifest && selectedScenario
        ? deriveAuthorityProgression({
            taxonomy: manifest.authority_taxonomy,
            scenario: selectedScenario,
            record,
            proposalPresent: result?.canonical_result.proposal != null,
            physicalExecutionAuthorityState:
              manifest.physical_execution_authority_state,
            replayLifecycle:
              state.replay.projection?.scenario_id === selectedScenario.scenario_id
                ? state.replay.projection.lifecycle_state
                : null,
          })
        : [],
    [manifest, record, result, selectedScenario, state.replay.projection],
  );
  const proposalText = useMemo(
    () =>
      result?.canonical_result.proposal
        ? JSON.stringify(result.canonical_result.proposal, null, 2)
        : "No schema-valid proposal available.",
    [result],
  );

  function clearReplayPoll(): void {
    if (replayPollHandleRef.current === null) return;
    clearTimeout(replayPollHandleRef.current);
    replayPollHandleRef.current = null;
  }

  function publishReplayFatal(originScenarioId: string): void {
    replayFatalRef.current = true;
    clearReplayPoll();
    cancelOwner(replayReadOwnerRef);
    cancelOwner(replayMutationOwnerRef);
    dispatch({ type: "REPLAY_FATAL", originScenarioId });
  }

  function cancelReplayRead(): void {
    clearReplayPoll();
    const owner = replayReadOwnerRef.current;
    if (owner === null) return;
    dispatch({ type: "REPLAY_READ_CANCELLED", operationId: owner.operationId });
    cancelOwner(replayReadOwnerRef);
  }

  function shouldMonitorReplay(projection: ReplayStateProjection): boolean {
    return projection.command_in_flight ||
      projection.lifecycle_state === "PAUSED" ||
      projection.lifecycle_state === "PLAYING" ||
      projection.lifecycle_state === "COMPLETED";
  }

  function scheduleReplayPoll(projection: ReplayStateProjection): void {
    clearReplayPoll();
    if (
      replayFatalRef.current ||
      !shouldMonitorReplay(projection) ||
      !mountedRef.current
    ) return;
    const expectedScenarioId = projection.scenario_id;
    const purpose: ReplayReadContext["purpose"] = projection.command_in_flight
      ? "RECONCILE"
      : "POLL";
    replayPollHandleRef.current = setTimeout(() => {
      replayPollHandleRef.current = null;
      if (selectedScenarioIdRef.current !== expectedScenarioId) return;
      void beginReplayRead(expectedScenarioId, purpose);
    }, REPLAY_POLL_INTERVAL_MS);
  }

  function beginReplayRead(
    expectedScenarioId: string,
    purpose: ReplayReadContext["purpose"],
  ): void {
    if (
      !mountedRef.current ||
      replayFatalRef.current ||
      selectedScenarioIdRef.current !== expectedScenarioId ||
      replayReadOwnerRef.current !== null ||
      replayMutationOwnerRef.current !== null
    ) {
      return;
    }
    clearReplayPoll();
    const operationId = nextOperationId(nextOperationIdRef);
    const context: ReplayReadContext = {
      operationId,
      scenarioId: expectedScenarioId,
      purpose,
    };
    dispatch({ type: "REPLAY_READ_STARTED", context });
    const owner = startOwner(
      replayReadOwnerRef,
      operationId,
      REPLAY_GET_CLIENT_DEADLINE_MS,
      () => {
        if (!mountedRef.current || selectedScenarioIdRef.current !== expectedScenarioId) return;
        dispatch({
          type: "REPLAY_OPERATION_FAILED",
          operationId,
          source: "READ",
          failure: { code: "CLIENT_TIMEOUT", detail: null },
        });
      },
    );
    void getReplayState(expectedScenarioId, owner.controller.signal)
      .then((projection) => {
        if (
          !mountedRef.current ||
          replayReadOwnerRef.current !== owner ||
          selectedScenarioIdRef.current !== expectedScenarioId ||
          !releaseOwner(replayReadOwnerRef, operationId)
        ) {
          return;
        }
        const currentProjection = replayProjectionRef.current;
        const accepted = acceptsReplayProjection(
          currentProjection,
          projection,
          "READ",
          null,
          purpose,
        );
        dispatch({
          type: "REPLAY_PROJECTION_RECEIVED",
          operationId,
          source: "READ",
          projection,
        });
        if (accepted) {
          replayProjectionRef.current = projection;
          scheduleReplayPoll(projection);
        } else if (currentProjection !== null) {
          scheduleReplayPoll(currentProjection);
        }
      })
      .catch((error: unknown) => {
        if (!mountedRef.current) return;
        if (isAbortError(error)) return;
        const failure = classifyReplayFailure(error);
        if (failure.code === "REPLAY_VERSION_EXHAUSTED") {
          publishReplayFatal(expectedScenarioId);
          return;
        }
        if (replayReadOwnerRef.current !== owner) return;
        if (!releaseOwner(replayReadOwnerRef, operationId)) return;
        dispatch({
          type: "REPLAY_OPERATION_FAILED",
          operationId,
          source: "READ",
          failure,
        });
      });
  }

  function handleReplayControl(control: ReplayControl): void {
    if (
      replayFatalRef.current ||
      selectedScenario === null ||
      !isReplayScenario(selectedScenario)
    ) return;
    const projection = state.replay.projection;
    if (
      state.replay.kind !== "READY" ||
      projection === null ||
      state.replay.mutation !== null ||
      replayMutationOwnerRef.current !== null ||
      !projection.available_controls.includes(control)
    ) {
      return;
    }
    if (control !== "START" && projection.session_id === null) return;
    cancelReplayRead();
    const operationId = nextOperationId(nextOperationIdRef);
    const context: ReplayMutationContext = {
      operationId,
      scenarioId: selectedScenario.scenario_id,
      control,
      sessionId: projection.session_id,
      controlVersion: projection.control_version,
    };
    dispatch({ type: "REPLAY_MUTATION_STARTED", context });
    const owner = startOwner(
      replayMutationOwnerRef,
      operationId,
      control === "START"
        ? REPLAY_START_CLIENT_DEADLINE_MS
        : REPLAY_CONTROL_CLIENT_DEADLINE_MS,
      () => {
        if (!mountedRef.current || selectedScenarioIdRef.current !== context.scenarioId) return;
        dispatch({
          type: "REPLAY_OPERATION_FAILED",
          operationId,
          source: "MUTATION",
          failure: { code: "CLIENT_TIMEOUT", detail: null },
        });
      },
    );
    const mutationSessionId = context.sessionId;
    const request = control === "START"
      ? startReplay({ scenario_id: context.scenarioId }, owner.controller.signal)
      : mutationSessionId === null
        ? Promise.reject(new ContractValidationError("replay: active control has no session"))
        : controlReplay({
            scenario_id: context.scenarioId,
            session_id: mutationSessionId,
            expected_control_version: context.controlVersion,
            control,
          }, owner.controller.signal);
    void request
      .then((nextProjection) => {
        if (
          !mountedRef.current ||
          replayMutationOwnerRef.current !== owner ||
          selectedScenarioIdRef.current !== context.scenarioId ||
          !releaseOwner(replayMutationOwnerRef, operationId)
        ) {
          return;
        }
        const accepted = acceptsReplayProjection(
          replayProjectionRef.current,
          nextProjection,
          "MUTATION",
          context.control,
          null,
        );
        dispatch({
          type: "REPLAY_PROJECTION_RECEIVED",
          operationId,
          source: "MUTATION",
          projection: nextProjection,
        });
        if (accepted) {
          replayProjectionRef.current = nextProjection;
          scheduleReplayPoll(nextProjection);
        }
      })
      .catch((error: unknown) => {
        if (!mountedRef.current) return;
        if (isAbortError(error)) return;
        const failure = classifyReplayFailure(error);
        if (failure.code === "REPLAY_VERSION_EXHAUSTED") {
          publishReplayFatal(context.scenarioId);
          return;
        }
        if (replayMutationOwnerRef.current !== owner) return;
        if (!releaseOwner(replayMutationOwnerRef, operationId)) return;
        dispatch({
          type: "REPLAY_OPERATION_FAILED",
          operationId,
          source: "MUTATION",
          failure,
        });
      });
  }

  useEffect(() => {
    cancelOwner(replayMutationOwnerRef);
    cancelReplayRead();
    dispatch({ type: "REPLAY_DEACTIVATED" });
    if (replayFatalRef.current) return;
    if (selectedScenario === null || !isReplayScenario(selectedScenario)) return;
    const expectedScenarioId = selectedScenario.scenario_id;
    const handle = setTimeout(() => beginReplayRead(expectedScenarioId, "INITIAL"), 0);
    return () => clearTimeout(handle);
  }, [selectedScenario?.scenario_id]);

  useEffect(() => {
    if (
      state.replay.kind !== "ERROR" ||
      state.replay.failure === null ||
      state.replay.scenarioId === null ||
      replayFatalRef.current ||
      !reconciliationErrors.has(state.replay.failure.code)
    ) {
      return;
    }
    const expectedScenarioId = state.replay.scenarioId;
    const handle = setTimeout(
      () => beginReplayRead(expectedScenarioId, "RECONCILE"),
      REPLAY_POLL_INTERVAL_MS,
    );
    return () => clearTimeout(handle);
  }, [state.replay.kind, state.replay.failure?.code, state.replay.scenarioId]);

  async function handleSubmit() {
    const trimmed = command.trim();
    if (
      !trimmed ||
      !selectedScenario?.model_input_enabled ||
      pending ||
      transcribing ||
      transcriptConsumed
    ) return;
    const readyTranscription = state.transcription.kind === "READY"
      ? state.transcription
      : null;
    const isVoice =
      readyTranscription !== null &&
      !readyTranscription.consumed &&
      readyTranscription.context.scenarioId === selectedScenario.scenario_id;
    const operationId = nextOperationId(nextOperationIdRef);
    const context: GovernanceContext = {
      operationId,
      scenarioId: selectedScenario.scenario_id,
      inferenceMode: mode,
      inputMode: isVoice ? "VOICE" : "TYPED",
      command: trimmed,
      transcriptionId: isVoice
        ? readyTranscription.transcription.transcription_id
        : null,
    };
    dispatch({ type: "GOVERNANCE_STARTED", context });
    const owner = startOwner(
      governanceOwnerRef,
      operationId,
      GOVERNANCE_CLIENT_DEADLINE_MS,
      () => {
        if (!mountedRef.current) return;
        dispatch({
          type: "GOVERNANCE_FAILED",
          operationId,
          failure: { code: "CLIENT_TIMEOUT", detail: null },
        });
      },
    );
    // A voice identity is consumed at start. Client abort/timeout cannot prove
    // that the server rolled back transcript claiming or provider work.
    try {
      const nextResult = isVoice
        ? await submitVoiceCommand({
            scenario_id: selectedScenario.scenario_id,
            transcription_id: readyTranscription.transcription.transcription_id,
            reviewed_transcript_text: trimmed,
            inference_mode: mode,
          }, owner.controller.signal)
        : await submitTypedCommand({
            scenario_id: selectedScenario.scenario_id,
            command: trimmed,
            inference_mode: mode,
          }, owner.controller.signal);
      if (
        !mountedRef.current ||
        !releaseOwner(governanceOwnerRef, operationId)
      ) return;
      dispatch({ type: "GOVERNANCE_SUCCEEDED", operationId, result: nextResult });
    } catch (error: unknown) {
      if (
        !mountedRef.current ||
        !releaseOwner(governanceOwnerRef, operationId) ||
        isAbortError(error)
      ) return;
      dispatch({
        type: "GOVERNANCE_FAILED",
        operationId,
        failure: classifyClientFailure(error),
      });
    }
  }

  async function handleAudioSelection(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (
      !file ||
      pending ||
      state.bootstrap.kind !== "READY" ||
      !selectedScenario?.model_input_enabled
    ) return;
    const operationId = nextOperationId(nextOperationIdRef);
    const context = {
      operationId,
      scenarioId: selectedScenario.scenario_id,
      commandRevision: state.controls.commandRevision,
    };
    dispatch({ type: "TRANSCRIPTION_STARTED", context });
    const owner = startOwner(
      transcriptionOwnerRef,
      operationId,
      SPEECH_CLIENT_DEADLINE_MS,
      () => {
        if (!mountedRef.current) return;
        dispatch({
          type: "TRANSCRIPTION_FAILED",
          operationId,
          failure: { code: "CLIENT_TIMEOUT", detail: null },
        });
      },
    );
    try {
      const nextTranscription = await transcribeRecordedAudio(
        file,
        owner.controller.signal,
      );
      if (
        !mountedRef.current ||
        !releaseOwner(transcriptionOwnerRef, operationId)
      ) return;
      if (
        nextTranscription.transcript_status === "READY" &&
        nextTranscription.transcript_text
      ) {
        dispatch({
          type: "TRANSCRIPTION_SUCCEEDED",
          operationId,
          transcription: nextTranscription,
        });
      } else {
        dispatch({
          type: "TRANSCRIPTION_FAILED",
          operationId,
          failure: {
            code: "TRANSCRIPTION_FAILURE",
            detail:
              nextTranscription.error_code ?? nextTranscription.transcript_status,
          },
        });
      }
    } catch (error: unknown) {
      if (
        !mountedRef.current ||
        !releaseOwner(transcriptionOwnerRef, operationId) ||
        isAbortError(error)
      ) return;
      dispatch({
        type: "TRANSCRIPTION_FAILED",
        operationId,
        failure: classifyClientFailure(error),
      });
    }
  }

  function discardTranscript() {
    cancelOwner(transcriptionOwnerRef);
    if (governanceContext?.inputMode === "VOICE") {
      cancelOwner(governanceOwnerRef);
    }
    dispatch({ type: "DISCARD_TRANSCRIPT" });
  }

  function downloadTrace() {
    if (!result || !record) return;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            transcription,
            governance: result,
          },
          null,
          2,
        ),
      ],
      {
        type: "application/json",
      },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${record.trace_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <ShieldCheckmark24Regular aria-hidden="true" />
          <div>
            <h1 className="product-name">Zero-Trust Governance Demonstrator</h1>
            <div className="product-subtitle">Prototype 5 · Zero-Trust Robotics</div>
          </div>
        </div>
        <div className="baseline">
          <span>Baseline</span>
          <code
            className="baseline-tag"
            title={status?.frozen_baseline_tag ?? "Loading"}
          >
            {status?.frozen_baseline_tag ?? "Loading"}
          </code>
          <code
            className="baseline-commit"
            title={status?.frozen_baseline_commit ?? "Loading"}
          >
            {status?.frozen_baseline_commit?.slice(0, 8) ?? "Loading"}
          </code>
        </div>
      </header>

      <section className="status-strip" aria-label="Runtime status">
        <div
          className="visually-hidden"
          role="status"
          aria-live="polite"
          aria-atomic="true"
          aria-label="Runtime status update"
        >
          {statusError ? (
            `Runtime status unavailable: ${statusError}`
          ) : (
            <>
              Runtime status: Local {availabilityLabel(status?.local_status)}; Cloud{" "}
              {availabilityLabel(status?.cloud_status)}; Speech{" "}
              {availabilityLabel(status?.speech_status)}; Simulator{" "}
              {availabilityLabel(status?.simulator_status)}.
            </>
          )}
        </div>
        <strong className="status-classification">
          {SYSTEM_STATUS_EVIDENCE_LABEL}
        </strong>
        <RuntimeStatus
          icon={<Desktop24Regular aria-hidden="true" />}
          label="Local"
          status={status?.local_status}
        />
        <RuntimeStatus
          icon={<Cloud24Regular aria-hidden="true" />}
          label="Cloud"
          status={status?.cloud_status}
        />
        <RuntimeStatus
          icon={<Mic24Regular aria-hidden="true" />}
          label="Speech"
          status={status?.speech_status}
        />
        <RuntimeStatus
          icon={<Bot24Regular aria-hidden="true" />}
          label="Simulator"
          status={status?.simulator_status}
        />
        {statusError && (
          <div className="status-error">
            Status unavailable: {statusError}
          </div>
        )}
      </section>

      <main className="app-layout">
        <section className="command-workspace" aria-label="Command workspace">
          <div className="workspace-toolbar">
            <Field label="Scenario" size="small">
              <Dropdown
                aria-label="Scenario"
                value={selectedScenario?.display_name ?? "Loading scenarios"}
                selectedOptions={scenarioId ? [scenarioId] : []}
                disabled={!manifest}
                onOptionSelect={(_, data) => {
                  const next = manifest?.scenarios.find(
                    (scenario) => scenario.scenario_id === data.optionValue,
                  );
                  if (!next || next.scenario_id === scenarioId) return;
                  cancelOwner(governanceOwnerRef);
                  cancelOwner(transcriptionOwnerRef);
                  selectedScenarioIdRef.current = next.scenario_id;
                  if (!replayFatalRef.current) replayProjectionRef.current = null;
                  const nextMode = next.allowed_inference_modes[0];
                  dispatch({
                    type: "SCENARIO_SELECTED",
                    scenarioId: next.scenario_id,
                    command: next.model_input_enabled ? next.registered_command : "",
                    inferenceMode:
                      nextMode && !next.allowed_inference_modes.includes(mode)
                        ? nextMode
                        : mode,
                  });
                }}
              >
                {manifest?.scenarios.map((scenario) => (
                  <Option key={scenario.scenario_id} value={scenario.scenario_id}>
                    {scenario.display_name}
                  </Option>
                ))}
              </Dropdown>
            </Field>
            <Field label="Inference" size="small">
              {!selectedScenario ? (
                <div className="inference-not-applicable" role="status">
                  NOT AVAILABLE — SCENARIO MANIFEST NOT LOADED
                </div>
              ) : selectedScenario.model_input_enabled ? (
                <RadioGroup
                  layout="horizontal"
                  value={mode}
                  onChange={(_, data) => {
                    const nextMode = selectInferenceMode(mode, data.value);
                    if (nextMode === mode) return;
                    cancelOwner(governanceOwnerRef);
                    dispatch({ type: "MODE_SELECTED", inferenceMode: nextMode });
                  }}
                  aria-label="Inference mode"
                >
                  <Radio value="LOCAL" label="Local" />
                  <Radio value="CLOUD" label="Cloud" />
                  <Radio value="AUTO" label="Auto" />
                </RadioGroup>
              ) : (
                <div className="inference-not-applicable" role="status">
                  NOT APPLICABLE — FROZEN REGISTERED EVIDENCE
                </div>
              )}
            </Field>
            {selectedScenario && (
              <section
                className="scenario-context"
                aria-labelledby="scenario-context-heading"
              >
                <div className="scenario-context-heading-row">
                  <h2 id="scenario-context-heading">Scenario context</h2>
                  <Badge appearance="outline">
                    {presentationClassificationLabel(selectedScenario)}
                  </Badge>
                </div>
                <strong className="evidence-classification">
                  {evidenceClassificationLabel(selectedScenario)}
                </strong>
                {secondaryEvidenceClassificationLabel(selectedScenario) && (
                  <span className="secondary-classification">
                    {secondaryEvidenceClassificationLabel(selectedScenario)}
                  </span>
                )}
                <p>{selectedScenario.demonstration_purpose}</p>
                <p className="claim-boundary-note">
                  {selectedScenario.claim_boundary_note}
                </p>
              </section>
            )}
          </div>

          {isReplayScenario(selectedScenario) ? (
            <ReplayPanel
              projection={state.replay.projection}
              clientKind={state.replay.kind}
              failure={state.replay.failure}
              announcement={state.replay.announcement}
              physicalAuthority={manifest?.physical_execution_authority_state ?? "NOT_IMPLEMENTED"}
              onControl={handleReplayControl}
            />
          ) : (
            <>
          <div className="conversation" aria-live="polite">
            {!submittedCommand && !pending && (
              <div className="empty-state">
                <Bot24Regular aria-hidden="true" />
                <span>No command submitted.</span>
              </div>
            )}
            {submittedCommand && (
              <div className="message-row operator-message">
                <span className="message-label">
                  {submittedInputMode === "VOICE"
                    ? "Reviewed voice transcript"
                    : "Operator"}
                </span>
                <p>{submittedCommand}</p>
              </div>
            )}
            {pending && (
              <div className="processing-row" role="status">
                <Spinner size="small" label="Evaluating proposal" />
              </div>
            )}
            {requestError && (
              <div className="request-error" role="alert">
                <strong>Request failed</strong>
                <span>{requestError}</span>
              </div>
            )}
            {transcriptionError && (
              <div className="request-error" role="alert">
                <strong>Transcription failed</strong>
                <span>{transcriptionError}</span>
              </div>
            )}
            {record && (
              <div className="message-row system-message">
                <div className="decision-line">
                  <span className="message-label">Governance decision</span>
                  <Badge
                    appearance="tint"
                    color={statusTone(record.final_decision)}
                  >
                    {formatStatus(record.final_decision)}
                  </Badge>
                </div>
                <p>{record.decision_reason_codes.map(formatStatus).join(" · ")}</p>
              </div>
            )}
            {result && (
              <section className="proposal-output" aria-labelledby="proposal-heading">
                <div className="section-heading-row">
                  <div>
                    <h2 id="proposal-heading">Untrusted model proposal</h2>
                    <strong className="proposal-authority-classification">
                      UNTRUSTED PROPOSAL — NO AUTHORITY
                    </strong>
                  </div>
                  <Badge
                    appearance="outline"
                    color={statusTone(record?.schema_status ?? "NOT_EVALUATED")}
                  >
                    Schema:{" "}
                    {record
                      ? gateStatusLabel(record.schema_status)
                      : "NOT EVALUATED"}
                  </Badge>
                </div>
                <pre>{proposalText}</pre>
              </section>
            )}
          </div>

          <div className="composer">
            {transcription?.transcript_status === "READY" && (
              <div className="transcript-review" role="status">
                <div className="transcript-identity">
                  <Mic24Regular aria-hidden="true" />
                  <div>
                    <strong>Nemotron transcript</strong>
                    <span>
                      {transcription.audio.original_filename} ·{" "}
                      {formatLatency(transcription.transcription_latency_ms)}
                    </span>
                  </div>
                </div>
                <div className="transcript-actions">
                  <Badge
                    appearance="tint"
                    color={transcriptConsumed ? "subtle" : "success"}
                  >
                    {transcriptConsumed ? "Submitted" : "Ready"}
                  </Badge>
                  <Tooltip content="Discard transcript" relationship="label">
                    <Button
                      appearance="subtle"
                      icon={<Dismiss24Regular />}
                      aria-label="Discard transcript"
                      onClick={discardTranscript}
                    />
                  </Tooltip>
                </div>
              </div>
            )}
            <Field label="Operator command">
              <Textarea
                value={command}
                onChange={(_, data) => {
                  if (transcribing) cancelOwner(transcriptionOwnerRef);
                  dispatch({ type: "COMMAND_EDITED", command: data.value });
                }}
                placeholder="Enter a bounded manufacturing command"
                resize="vertical"
                disabled={pending || !selectedScenario?.model_input_enabled}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    void handleSubmit();
                  }
                }}
              />
            </Field>
            <div className="composer-actions">
              <input
                ref={audioInputRef}
                className="visually-hidden"
                type="file"
                accept=".wav,audio/wav,audio/x-wav"
                tabIndex={-1}
                onChange={(event) => void handleAudioSelection(event)}
                aria-label="Recorded WAV file"
              />
              <Tooltip content="Upload WAV recording" relationship="label">
                <Button
                  appearance="subtle"
                  icon={<ArrowUpload24Regular />}
                  aria-label="Upload WAV recording"
                  disabled={
                    pending ||
                    !selectedScenario?.model_input_enabled
                  }
                  onClick={() => audioInputRef.current?.click()}
                />
              </Tooltip>
              <Tooltip content="Microphone available in V2" relationship="label">
                <Button
                  appearance="subtle"
                  icon={<Mic24Regular />}
                  aria-label="Microphone available in V2"
                  disabled
                />
              </Tooltip>
              {transcribing && (
                <Spinner size="tiny" label="Transcribing recording" />
              )}
              <Button
                appearance="primary"
                icon={<Send24Regular />}
                disabled={
                  !command.trim() ||
                  !selectedScenario?.model_input_enabled ||
                  pending ||
                  transcribing ||
                  transcriptConsumed
                }
                onClick={() => void handleSubmit()}
              >
                Submit
              </Button>
            </div>
          </div>
            </>
          )}
        </section>

        <aside className="inspector" aria-label="Governance inspector">
          <InspectorSection title="Authority progression" dominant>
            <ol
              className="authority-progression"
              aria-label="Six-layer authority progression"
            >
              {authorityRows.map((row, index) => (
                <li
                  className="authority-row"
                  data-authority-state={row.taxonomyState}
                  key={row.taxonomyState}
                >
                  <span className="authority-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div className="authority-content">
                    <span className="authority-label">{row.label}</span>
                    <strong className="authority-state">{row.state}</strong>
                    {row.detail.map((detail) => (
                      <span className="authority-detail" key={detail}>
                        {detail}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ol>
            <p className="authority-boundary-statement">
              Passing layer N does not establish layer N+1.
            </p>
          </InspectorSection>

          <InspectorSection title="Governance gate diagnostics">
            <div className="gate-list">
              {gateDefinitions.map(([label, field]) => {
                const gateStatus = record?.[field] ?? "NOT_EVALUATED";
                return (
                  <div className="gate-row" key={field}>
                    <span>{label}</span>
                    <Badge appearance="tint" color={statusTone(gateStatus)}>
                      {record ? gateStatusLabel(record[field]) : "NOT EVALUATED"}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </InspectorSection>

          {selectedScenario?.model_input_enabled && (
          <InspectorSection title="Routing">
            <DefinitionRow label="Requested" value={record?.routing.requested_mode ?? "NOT_EVALUATED"} />
            <DefinitionRow
              label="Selected"
              value={record ? providerLabel(record.routing.selected_provider) : "Not evaluated"}
            />
            <DefinitionRow
              label="Model"
              value={record ? record.routing.selected_model ?? "Not selected" : "Not evaluated"}
            />
            <DefinitionRow
              label="Fallback"
              value={
                record?.routing.fallback_triggered
                  ? formatStatus(record.routing.fallback_reason)
                  : record
                    ? "Not triggered"
                    : "Not evaluated"
              }
            />
            <DefinitionRow
              label="Local latency"
              value={record ? formatLatency(record.routing.local_latency_ms) : "Not evaluated"}
            />
            <DefinitionRow
              label="Cloud latency"
              value={record ? formatLatency(record.routing.cloud_latency_ms) : "Not evaluated"}
            />
            <DefinitionRow
              label="Circuit"
              value={result?.local_health.circuit_state ?? "NOT_AVAILABLE"}
            />
          </InspectorSection>
          )}

          {selectedScenario?.model_input_enabled && (
          <InspectorSection title="Live trace provenance">
            <strong className="trace-classification">
              LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE
            </strong>
            <DefinitionRow label="Trace ID" value={record?.trace_id ?? "Not evaluated"} mono />
            <DefinitionRow label="Timestamp UTC" value={record?.timestamp_utc ?? "Not evaluated"} mono />
            <DefinitionRow
              label="Requested routing mode"
              value={record?.routing.requested_mode ?? "Not evaluated"}
            />
            <DefinitionRow
              label="Selected provider"
              value={record ? providerLabel(record.routing.selected_provider) : "Not evaluated"}
            />
            <DefinitionRow
              label="Resolved model"
              value={record?.routing.selected_model ?? "Not evaluated"}
            />
            <DefinitionRow
              label="Software commit"
              value={status?.software_commit ?? "Not available"}
              mono
            />
            <DefinitionRow
              label="Policy"
              value={record?.policy_id ?? "NOT_EVALUATED"}
            />
            <DefinitionRow
              label="Schema"
              value={record?.evidence_schema_version ?? "NOT_EVALUATED"}
            />
            <DefinitionRow
              label="Provider latency"
              value={record ? formatLatency(record.provider_latency_ms) : "Not evaluated"}
            />
            <DefinitionRow
              label="Validation"
              value={record ? formatLatency(record.validation_latency_ms) : "Not evaluated"}
            />
            <DefinitionRow
              label="Total"
              value={formatLatency(record?.total_pipeline_latency_ms)}
            />
            <Button
              appearance="secondary"
              icon={<ArrowDownload24Regular />}
              onClick={downloadTrace}
              disabled={!result}
            >
              Download live demo trace
            </Button>
          </InspectorSection>
          )}
        </aside>
      </main>
    </div>
  );
}

function RuntimeStatus({
  icon,
  label,
  status,
}: {
  icon: ReactNode;
  label: string;
  status?: AvailabilityStatus;
}) {
  return (
    <div className="runtime-status">
      {icon}
      <span>{label}</span>
      <Badge appearance="tint" color={statusTone(status ?? "NOT_ASSESSED")}>
        {availabilityLabel(status)}
      </Badge>
    </div>
  );
}

function InspectorSection({
  title,
  children,
  dominant = false,
}: {
  title: string;
  children: ReactNode;
  dominant?: boolean;
}) {
  return (
    <section
      className={dominant ? "inspector-section authority-section" : "inspector-section"}
    >
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function DefinitionRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="definition-row">
      <span>{label}</span>
      <strong className={mono ? "mono-value" : undefined} title={value}>
        {value}
      </strong>
    </div>
  );
}
