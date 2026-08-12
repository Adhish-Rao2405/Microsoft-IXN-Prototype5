import type {
  DemoManifest,
  DemoStatus,
  HybridGovernanceResult,
  InferenceMode,
  RecordedTranscription,
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
}

export type TranscriptionState =
  | { kind: "NONE" }
  | { kind: "TRANSCRIBING"; context: TranscriptionContext }
  | {
      kind: "READY";
      context: TranscriptionContext;
      transcription: RecordedTranscription;
      consumed: boolean;
    }
  | { kind: "FAILED"; context: TranscriptionContext; failure: ClientFailure };

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
  | { type: "TRANSCRIPTION_STARTED"; context: TranscriptionContext }
  | {
      type: "TRANSCRIPTION_SUCCEEDED";
      operationId: number;
      transcription: RecordedTranscription;
    }
  | { type: "TRANSCRIPTION_FAILED"; operationId: number; failure: ClientFailure }
  | { type: "DISCARD_TRANSCRIPT" };

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
};

function isPositiveSafeOperationId(operationId: number): boolean {
  return Number.isSafeInteger(operationId) && operationId > 0;
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
          state.transcription.kind === "TRANSCRIBING"
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

    case "TRANSCRIPTION_STARTED":
      if (
        state.bootstrap.kind !== "READY" ||
        !isPositiveSafeOperationId(action.context.operationId) ||
        action.context.scenarioId !== state.controls.scenarioId ||
        action.context.commandRevision !== state.controls.commandRevision
      ) {
        return state;
      }
      return {
        ...state,
        governance: { kind: "IDLE" },
        transcription: { kind: "TRANSCRIBING", context: action.context },
      };

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
        state.transcription.kind !== "TRANSCRIBING" ||
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
  }
}
