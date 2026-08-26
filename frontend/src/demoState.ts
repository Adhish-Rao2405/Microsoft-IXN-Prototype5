import type {
  DemoManifest,
  DemoStatus,
  HybridGovernanceResult,
  InferenceMode,
  RecordedTranscription,
  ReplayControl,
  ReplayErrorCode,
  ReplayStateProjection,
} from "./types";

export type ClientFailureCode =
  | "CLIENT_TIMEOUT"
  | "NETWORK_FAILURE"
  | "HTTP_ERROR"
  | "CONTRACT_FAILURE"
  | "TRANSCRIPTION_FAILURE"
  | "UNKNOWN_CLIENT_FAILURE";

export interface ClientFailure {
  code: ClientFailureCode;
  detail: string | null;
}

export type BootstrapState =
  | { kind: "BOOTSTRAPPING"; operationId: number }
  | { kind: "READY"; manifest: DemoManifest; status: DemoStatus }
  | { kind: "FAILED"; operationId: number; failure: ClientFailure };

export interface GovernanceContext {
  readonly operationId: number;
  readonly scenarioId: string;
  readonly inferenceMode: InferenceMode;
  readonly inputMode: "TYPED" | "VOICE";
  readonly command: string;
  readonly transcriptionId: string | null;
}

export type GovernanceState =
  | { kind: "IDLE" }
  | { kind: "SUBMITTING"; context: GovernanceContext }
  | { kind: "SUCCEEDED"; context: GovernanceContext; result: HybridGovernanceResult }
  | { kind: "FAILED"; context: GovernanceContext; failure: ClientFailure };

export interface TranscriptionContext {
  readonly operationId: number;
  readonly scenarioId: string;
  readonly commandRevision: number;
  readonly source: "WAV_UPLOAD" | "MICROPHONE";
}

export type TranscriptionFailureReason =
  | "PERMISSION_DENIED"
  | "DEVICE_UNAVAILABLE"
  | "CAPTURE_SAMPLE_RATE_UNSUPPORTED"
  | "DEVICE_LOST"
  | "CAPTURE_EMPTY"
  | "CAPTURE_TOO_LONG"
  | "CAPTURE_FAILED"
  | "ENCODING_FAILED"
  | "TRANSCRIPTION_PARTIAL"
  | "TRANSCRIPTION_EMPTY"
  | "SPEECH_BACKEND_UNAVAILABLE"
  | "SPEECH_BUSY"
  | "TRANSCRIPTION_INVALID_RESPONSE"
  | "TRANSCRIPTION_TIMEOUT"
  | "TRANSCRIPTION_NETWORK_FAILURE"
  | "TRANSCRIPTION_FAILED"
  | "CANCELLED";

export interface TranscriptionFailure {
  readonly reason: TranscriptionFailureReason;
  readonly serverCode: string | null;
}

export type TranscriptionState =
  | { kind: "NONE" }
  | { kind: "REQUESTING_PERMISSION"; context: TranscriptionContext }
  | { kind: "CAPTURING"; context: TranscriptionContext }
  | { kind: "FINALISING"; context: TranscriptionContext }
  | { kind: "TRANSCRIBING"; context: TranscriptionContext }
  | {
      kind: "READY";
      context: TranscriptionContext;
      transcription: RecordedTranscription;
      consumed: boolean;
    }
  | {
      kind: "FAILED";
      context: TranscriptionContext;
      failure: TranscriptionFailure;
    };

export type ReplayClientFailureCode =
  | ReplayErrorCode
  | "CLIENT_TIMEOUT"
  | "NETWORK_FAILURE"
  | "CONTRACT_FAILURE"
  | "UNKNOWN_CLIENT_FAILURE";

export interface ReplayClientFailure {
  readonly code: ReplayClientFailureCode;
  readonly detail: null;
}

export interface ReplayReadContext {
  readonly operationId: number;
  readonly scenarioId: string;
  readonly purpose: "INITIAL" | "POLL" | "RECONCILE";
}

export interface ReplayMutationContext {
  readonly operationId: number;
  readonly scenarioId: string;
  readonly control: ReplayControl;
  readonly sessionId: string | null;
  readonly controlVersion: number;
}

export interface ReplayClientState {
  readonly kind: "INACTIVE" | "RECONCILING" | "READY" | "MUTATING" | "ERROR" | "FATAL";
  readonly scenarioId: string | null;
  readonly projection: ReplayStateProjection | null;
  readonly read: ReplayReadContext | null;
  readonly mutation: ReplayMutationContext | null;
  readonly failure: ReplayClientFailure | null;
  readonly announcement: string | null;
}

export interface DemoState {
  readonly bootstrap: BootstrapState;
  readonly controls: {
    readonly scenarioId: string;
    readonly inferenceMode: InferenceMode;
    readonly command: string;
    readonly commandRevision: number;
  };
  readonly governance: GovernanceState;
  readonly transcription: TranscriptionState;
  readonly replay: ReplayClientState;
}

export type DemoAction =
  | { type: "BOOTSTRAP_STARTED"; operationId: number }
  | {
      type: "BOOTSTRAP_SUCCEEDED";
      operationId: number;
      manifest: DemoManifest;
      status: DemoStatus;
      initialScenarioId: string;
      initialMode: InferenceMode;
    }
  | { type: "BOOTSTRAP_FAILED"; operationId: number; failure: ClientFailure }
  | {
      type: "SCENARIO_SELECTED";
      scenarioId: string;
      command: string;
      inferenceMode: InferenceMode;
    }
  | { type: "MODE_SELECTED"; inferenceMode: InferenceMode }
  | { type: "COMMAND_EDITED"; command: string }
  | { type: "GOVERNANCE_STARTED"; context: GovernanceContext }
  | { type: "GOVERNANCE_SUCCEEDED"; operationId: number; result: HybridGovernanceResult }
  | { type: "GOVERNANCE_FAILED"; operationId: number; failure: ClientFailure }
  | { type: "MICROPHONE_REQUESTED"; context: TranscriptionContext }
  | { type: "MICROPHONE_CAPTURE_STARTED"; operationId: number }
  | { type: "MICROPHONE_FINALISING"; operationId: number }
  | { type: "TRANSCRIPTION_STARTED"; context: TranscriptionContext }
  | {
      type: "TRANSCRIPTION_SUCCEEDED";
      operationId: number;
      transcription: RecordedTranscription;
    }
  | {
      type: "TRANSCRIPTION_FAILED";
      operationId: number;
      failure: TranscriptionFailure;
    }
  | { type: "TRANSCRIPTION_CANCELLED"; operationId: number }
  | { type: "DISCARD_TRANSCRIPT" }
  | { type: "REPLAY_DEACTIVATED" }
  | { type: "REPLAY_READ_STARTED"; context: ReplayReadContext }
  | { type: "REPLAY_READ_CANCELLED"; operationId: number }
  | { type: "REPLAY_MUTATION_STARTED"; context: ReplayMutationContext }
  | {
      type: "REPLAY_PROJECTION_RECEIVED";
      operationId: number;
      source: "READ" | "MUTATION";
      projection: ReplayStateProjection;
    }
  | {
      type: "REPLAY_OPERATION_FAILED";
      operationId: number;
      source: "READ" | "MUTATION";
      failure: ReplayClientFailure;
    }
  | { type: "REPLAY_FATAL"; originScenarioId: string };

export const initialDemoState: DemoState = {
  bootstrap: { kind: "BOOTSTRAPPING", operationId: 0 },
  controls: {
    scenarioId: "",
    inferenceMode: "AUTO",
    command: "",
    commandRevision: 0,
  },
  governance: { kind: "IDLE" },
  transcription: { kind: "NONE" },
  replay: {
    kind: "INACTIVE",
    scenarioId: null,
    projection: null,
    read: null,
    mutation: null,
    failure: null,
    announcement: null,
  },
};

function isPositiveSafeOperationId(operationId: number): boolean {
  return Number.isSafeInteger(operationId) && operationId > 0;
}

function isActiveTranscription(
  transcription: TranscriptionState,
): transcription is Extract<
  TranscriptionState,
  { kind: "REQUESTING_PERMISSION" | "CAPTURING" | "FINALISING" | "TRANSCRIBING" }
> {
  return transcription.kind === "REQUESTING_PERMISSION" ||
    transcription.kind === "CAPTURING" ||
    transcription.kind === "FINALISING" ||
    transcription.kind === "TRANSCRIBING";
}

function replayAnnouncement(projection: ReplayStateProjection): string {
  const frame = projection.current_frame;
  return frame === null
    ? `Evidence replay ${projection.lifecycle_state.toLowerCase()}.`
    : `Evidence replay ${projection.lifecycle_state.toLowerCase()}, frame ${frame.frame_index + 1} of ${projection.frame_count}.`;
}

export function acceptsReplayProjection(
  current: ReplayStateProjection | null,
  candidate: ReplayStateProjection,
  source: "READ" | "MUTATION",
  control: ReplayControl | null,
  readPurpose: ReplayReadContext["purpose"] | null,
): boolean {
  if (current === null) {
    return source === "READ" &&
      (readPurpose === "INITIAL" || readPurpose === "RECONCILE");
  }
  if (candidate.scenario_id !== current.scenario_id) return false;
  if (candidate.session_id === current.session_id) {
    if (candidate.session_id === null) return candidate.projection_version === 0;
    return candidate.projection_version >= current.projection_version;
  }
  if (source === "READ") {
    if (candidate.session_id === null && current.session_id !== null) return true;
    return current.session_id === null &&
      candidate.session_id !== null &&
      (readPurpose === "INITIAL" || readPurpose === "RECONCILE");
  }
  if (control === "START") return current.session_id === null && candidate.session_id !== null;
  if (control === "STOP") return current.session_id !== null && candidate.session_id === null;
  return false;
}

export function demoReducer(state: DemoState, action: DemoAction): DemoState {
  switch (action.type) {
    case "BOOTSTRAP_STARTED":
      return {
        ...state,
        bootstrap: { kind: "BOOTSTRAPPING", operationId: action.operationId },
      };

    case "BOOTSTRAP_SUCCEEDED":
      if (
        state.bootstrap.kind !== "BOOTSTRAPPING" ||
        state.bootstrap.operationId !== action.operationId
      ) {
        return state;
      }
      return {
        ...state,
        bootstrap: {
          kind: "READY",
          manifest: action.manifest,
          status: action.status,
        },
        controls: {
          ...state.controls,
          scenarioId: action.initialScenarioId,
          inferenceMode: action.initialMode,
        },
      };

    case "BOOTSTRAP_FAILED":
      if (
        state.bootstrap.kind !== "BOOTSTRAPPING" ||
        state.bootstrap.operationId !== action.operationId
      ) {
        return state;
      }
      return {
        ...state,
        bootstrap: {
          kind: "FAILED",
          operationId: action.operationId,
          failure: action.failure,
        },
      };

    case "SCENARIO_SELECTED":
      if (state.controls.scenarioId === action.scenarioId) return state;
      return {
        ...state,
        controls: {
          scenarioId: action.scenarioId,
          inferenceMode: action.inferenceMode,
          command: action.command,
          commandRevision: state.controls.commandRevision + 1,
        },
        governance: { kind: "IDLE" },
        transcription: { kind: "NONE" },
        replay: state.replay.kind === "FATAL"
          ? state.replay
          : initialDemoState.replay,
      };

    case "MODE_SELECTED":
      if (state.controls.inferenceMode === action.inferenceMode) return state;
      return {
        ...state,
        controls: { ...state.controls, inferenceMode: action.inferenceMode },
        governance: { kind: "IDLE" },
      };

    case "COMMAND_EDITED":
      if (state.controls.command === action.command) return state;
      return {
        ...state,
        controls: {
          ...state.controls,
          command: action.command,
          commandRevision: state.controls.commandRevision + 1,
        },
        transcription:
          isActiveTranscription(state.transcription)
            ? { kind: "NONE" }
            : state.transcription,
      };

    case "GOVERNANCE_STARTED": {
      const voice = action.context.inputMode === "VOICE";
      if (
        state.bootstrap.kind !== "READY" ||
        !isPositiveSafeOperationId(action.context.operationId) ||
        action.context.scenarioId !== state.controls.scenarioId ||
        action.context.inferenceMode !== state.controls.inferenceMode ||
        action.context.command !== state.controls.command.trim() ||
        voice &&
        (state.transcription.kind !== "READY" ||
          state.transcription.consumed ||
          state.transcription.transcription.transcription_id !==
            action.context.transcriptionId ||
          state.transcription.context.scenarioId !== action.context.scenarioId)
      ) {
        return state;
      }
      if (!voice && action.context.transcriptionId !== null) return state;
      return {
        ...state,
        governance: { kind: "SUBMITTING", context: action.context },
        transcription:
          voice && state.transcription.kind === "READY"
            ? { ...state.transcription, consumed: true }
            : state.transcription,
      };
    }

    case "GOVERNANCE_SUCCEEDED":
      if (
        state.governance.kind !== "SUBMITTING" ||
        state.governance.context.operationId !== action.operationId
      ) {
        return state;
      }
      return {
        ...state,
        governance: {
          kind: "SUCCEEDED",
          context: state.governance.context,
          result: action.result,
        },
      };

    case "GOVERNANCE_FAILED":
      if (
        state.governance.kind !== "SUBMITTING" ||
        state.governance.context.operationId !== action.operationId
      ) {
        return state;
      }
      return {
        ...state,
        governance: {
          kind: "FAILED",
          context: state.governance.context,
          failure: action.failure,
        },
      };

    case "MICROPHONE_REQUESTED":
      if (
        state.bootstrap.kind !== "READY" ||
        !isPositiveSafeOperationId(action.context.operationId) ||
        action.context.source !== "MICROPHONE" ||
        action.context.scenarioId !== state.controls.scenarioId ||
        action.context.commandRevision !== state.controls.commandRevision ||
        state.transcription.kind !== "NONE" &&
        state.transcription.kind !== "FAILED"
      ) {
        return state;
      }
      return {
        ...state,
        governance: { kind: "IDLE" },
        transcription: { kind: "REQUESTING_PERMISSION", context: action.context },
      };

    case "MICROPHONE_CAPTURE_STARTED":
      if (
        state.transcription.kind !== "REQUESTING_PERMISSION" ||
        state.transcription.context.operationId !== action.operationId
      ) return state;
      return {
        ...state,
        transcription: {
          kind: "CAPTURING",
          context: state.transcription.context,
        },
      };

    case "MICROPHONE_FINALISING":
      if (
        state.transcription.kind !== "CAPTURING" ||
        state.transcription.context.operationId !== action.operationId
      ) return state;
      return {
        ...state,
        transcription: {
          kind: "FINALISING",
          context: state.transcription.context,
        },
      };

    case "TRANSCRIPTION_STARTED": {
      const fromMicrophone = action.context.source === "MICROPHONE";
      const microphoneOwnsFinalisation =
        state.transcription.kind === "FINALISING" &&
        state.transcription.context.operationId === action.context.operationId;
      if (
        state.bootstrap.kind !== "READY" ||
        !isPositiveSafeOperationId(action.context.operationId) ||
        action.context.scenarioId !== state.controls.scenarioId ||
        action.context.commandRevision !== state.controls.commandRevision ||
        (fromMicrophone
          ? !microphoneOwnsFinalisation
          : state.transcription.kind !== "NONE" &&
            state.transcription.kind !== "FAILED")
      ) return state;
      return {
        ...state,
        governance: { kind: "IDLE" },
        transcription: { kind: "TRANSCRIBING", context: action.context },
      };
    }

    case "TRANSCRIPTION_SUCCEEDED":
      if (
        state.transcription.kind !== "TRANSCRIBING" ||
        state.transcription.context.operationId !== action.operationId ||
        state.transcription.context.scenarioId !== state.controls.scenarioId ||
        state.transcription.context.commandRevision !== state.controls.commandRevision
      ) {
        return state;
      }
      return {
        ...state,
        controls: {
          ...state.controls,
          command: action.transcription.transcript_text ?? "",
          commandRevision: state.controls.commandRevision + 1,
        },
        transcription: {
          kind: "READY",
          context: state.transcription.context,
          transcription: action.transcription,
          consumed: false,
        },
      };

    case "TRANSCRIPTION_FAILED":
      if (
        !isActiveTranscription(state.transcription) ||
        state.transcription.context.operationId !== action.operationId
      ) {
        return state;
      }
      return {
        ...state,
        transcription: {
          kind: "FAILED",
          context: state.transcription.context,
          failure: action.failure,
        },
      };

    case "TRANSCRIPTION_CANCELLED":
      if (
        !isActiveTranscription(state.transcription) ||
        state.transcription.context.operationId !== action.operationId
      ) return state;
      return {
        ...state,
        transcription: {
          kind: "FAILED",
          context: state.transcription.context,
          failure: { reason: "CANCELLED", serverCode: null },
        },
      };

    case "DISCARD_TRANSCRIPT":
      return {
        ...state,
        controls: {
          ...state.controls,
          command: "",
          commandRevision: state.controls.commandRevision + 1,
        },
        governance:
          state.governance.kind !== "IDLE" &&
          state.governance.context.inputMode === "VOICE"
            ? { kind: "IDLE" }
            : state.governance,
        transcription: { kind: "NONE" },
      };

    case "REPLAY_DEACTIVATED":
      return state.replay.kind === "INACTIVE" || state.replay.kind === "FATAL"
        ? state
        : { ...state, replay: initialDemoState.replay };

    case "REPLAY_READ_STARTED":
      if (
        !isPositiveSafeOperationId(action.context.operationId) ||
        action.context.scenarioId !== state.controls.scenarioId ||
        state.replay.mutation !== null ||
        state.replay.read !== null ||
        state.replay.kind === "FATAL"
      ) {
        return state;
      }
      return {
        ...state,
        replay: {
          ...state.replay,
          kind: action.context.purpose === "POLL" && state.replay.projection !== null
            ? "READY"
            : "RECONCILING",
          scenarioId: action.context.scenarioId,
          read: action.context,
          failure: null,
        },
      };

    case "REPLAY_READ_CANCELLED":
      if (state.replay.read?.operationId !== action.operationId) return state;
      return {
        ...state,
        replay: {
          ...state.replay,
          kind: state.replay.projection === null ? "INACTIVE" : "READY",
          read: null,
        },
      };

    case "REPLAY_MUTATION_STARTED": {
      const projection = state.replay.projection;
      if (
        !isPositiveSafeOperationId(action.context.operationId) ||
        action.context.scenarioId !== state.controls.scenarioId ||
        state.replay.kind === "FATAL" ||
        state.replay.mutation !== null ||
        state.replay.read !== null ||
        projection === null ||
        !projection.available_controls.includes(action.context.control) ||
        action.context.sessionId !== projection.session_id ||
        action.context.controlVersion !== projection.control_version
      ) {
        return state;
      }
      return {
        ...state,
        replay: {
          ...state.replay,
          kind: "MUTATING",
          mutation: action.context,
          failure: null,
        },
      };
    }

    case "REPLAY_PROJECTION_RECEIVED": {
      const owner = action.source === "READ" ? state.replay.read : state.replay.mutation;
      if (
        owner === null ||
        owner.operationId !== action.operationId ||
        owner.scenarioId !== state.controls.scenarioId ||
        action.projection.scenario_id !== owner.scenarioId
      ) {
        return state;
      }
      if (!acceptsReplayProjection(
          state.replay.projection,
          action.projection,
          action.source,
          action.source === "MUTATION" ? state.replay.mutation?.control ?? null : null,
          action.source === "READ" ? state.replay.read?.purpose ?? null : null,
        )) {
        if (action.source === "READ") {
          return {
            ...state,
            replay: {
              ...state.replay,
              kind: state.replay.projection === null ? "INACTIVE" : "READY",
              read: null,
            },
          };
        }
        return {
          ...state,
          replay: {
            ...state.replay,
            kind: "ERROR",
            mutation: null,
            failure: { code: "CONTRACT_FAILURE", detail: null },
            announcement: "Evidence replay response rejected.",
          },
        };
      }
      const shouldAnnounce = action.source === "MUTATION" ||
        state.replay.read?.purpose !== "POLL" ||
        state.replay.projection?.lifecycle_state !== action.projection.lifecycle_state;
      return {
        ...state,
        replay: {
          kind: "READY",
          scenarioId: owner.scenarioId,
          projection: action.projection,
          read: null,
          mutation: null,
          failure: null,
          announcement: shouldAnnounce
            ? replayAnnouncement(action.projection)
            : state.replay.announcement,
        },
      };
    }

    case "REPLAY_OPERATION_FAILED": {
      const owner = action.source === "READ" ? state.replay.read : state.replay.mutation;
      if (owner === null || owner.operationId !== action.operationId) return state;
      return {
        ...state,
        replay: {
          ...state.replay,
          kind: "ERROR",
          read: null,
          mutation: null,
          failure: action.failure,
          announcement: "Evidence replay request failed.",
        },
      };
    }

    case "REPLAY_FATAL":
      return {
        ...state,
        replay: {
          kind: "FATAL",
          scenarioId: action.originScenarioId,
          projection: state.replay.projection,
          read: null,
          mutation: null,
          failure: { code: "REPLAY_VERSION_EXHAUSTED", detail: null },
          announcement: "Evidence replay unavailable until application restart.",
        },
      };
  }
}
