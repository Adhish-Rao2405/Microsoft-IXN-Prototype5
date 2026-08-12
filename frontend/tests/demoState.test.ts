import { describe, expect, it } from "vitest";
import {
  demoReducer,
  initialDemoState,
  type DemoState,
  type GovernanceContext,
  type TranscriptionContext,
} from "../src/demoState";
import type {
  DemoManifest,
  DemoStatus,
  HybridGovernanceResult,
  RecordedTranscription,
} from "../src/types";

const failure = { code: "NETWORK_FAILURE", detail: null } as const;

const result = {
  routing_policy_id: "test-policy",
} as HybridGovernanceResult;

const transcription: RecordedTranscription = {
  result_schema_version: "1.0.0",
  transcription_id: "transcription-state-1",
  timestamp_utc: "2026-08-12T10:00:00Z",
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
  transcription_latency_ms: 800,
  error_code: null,
  error_detail: null,
};

function stateForScenario(): DemoState {
  return {
    ...initialDemoState,
    bootstrap: {
      kind: "READY",
      manifest: {} as DemoManifest,
      status: {} as DemoStatus,
    },
    controls: {
      scenarioId: "scenario-a",
      inferenceMode: "AUTO",
      command: "Move the blue component.",
      commandRevision: 4,
    },
  };
}

function governanceContext(
  operationId: number,
  inputMode: "TYPED" | "VOICE" = "TYPED",
): GovernanceContext {
  return {
    operationId,
    scenarioId: "scenario-a",
    inferenceMode: "AUTO",
    inputMode,
    command: "Move the blue component.",
    transcriptionId: inputMode === "VOICE" ? transcription.transcription_id : null,
  };
}

function transcriptionContext(operationId: number): TranscriptionContext {
  return {
    operationId,
    scenarioId: "scenario-a",
    commandRevision: 4,
  };
}

function readyTranscriptionState(): DemoState {
  const started = demoReducer(stateForScenario(), {
    type: "TRANSCRIPTION_STARTED",
    context: transcriptionContext(11),
  });
  return demoReducer(started, {
    type: "TRANSCRIPTION_SUCCEEDED",
    operationId: 11,
    transcription,
  });
}

describe("demoReducer operation ownership", () => {
  it("rejects governance start before bootstrap readiness", () => {
    const base = {
      ...stateForScenario(),
      bootstrap: initialDemoState.bootstrap,
    };

    expect(
      demoReducer(base, {
        type: "GOVERNANCE_STARTED",
        context: governanceContext(1),
      }),
    ).toBe(base);
  });

  it.each([0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1])(
    "rejects governance start with unsafe operation ID %s",
    (operationId) => {
      const base = stateForScenario();
      expect(
        demoReducer(base, {
          type: "GOVERNANCE_STARTED",
          context: governanceContext(operationId),
        }),
      ).toBe(base);
    },
  );

  it("rejects governance start when scenario, mode, or command drifted", () => {
    for (const context of [
      { ...governanceContext(1), scenarioId: "scenario-b" },
      { ...governanceContext(1), inferenceMode: "LOCAL" as const },
      { ...governanceContext(1), command: "Different command" },
    ]) {
      const base = stateForScenario();
      expect(
        demoReducer(base, { type: "GOVERNANCE_STARTED", context }),
      ).toBe(base);
    }
  });

  it("binds governance command to the trimmed current control text", () => {
    const base = {
      ...stateForScenario(),
      controls: {
        ...stateForScenario().controls,
        command: "  Move the blue component.  ",
      },
    };
    const next = demoReducer(base, {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(1),
    });

    expect(next.governance.kind).toBe("SUBMITTING");
  });

  it("rejects transcription start before bootstrap readiness", () => {
    const base = {
      ...stateForScenario(),
      bootstrap: initialDemoState.bootstrap,
    };
    expect(
      demoReducer(base, {
        type: "TRANSCRIPTION_STARTED",
        context: transcriptionContext(1),
      }),
    ).toBe(base);
  });

  it.each([0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1])(
    "rejects transcription start with unsafe operation ID %s",
    (operationId) => {
      const base = stateForScenario();
      expect(
        demoReducer(base, {
          type: "TRANSCRIPTION_STARTED",
          context: transcriptionContext(operationId),
        }),
      ).toBe(base);
    },
  );

  it("rejects transcription start when scenario or command revision drifted", () => {
    for (const context of [
      { ...transcriptionContext(1), scenarioId: "scenario-b" },
      { ...transcriptionContext(1), commandRevision: 5 },
    ]) {
      const base = stateForScenario();
      expect(
        demoReducer(base, { type: "TRANSCRIPTION_STARTED", context }),
      ).toBe(base);
    }
  });

  it("ignores stale governance success and failure by exact identity", () => {
    const submitting = demoReducer(stateForScenario(), {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(2),
    });

    expect(
      demoReducer(submitting, {
        type: "GOVERNANCE_SUCCEEDED",
        operationId: 1,
        result,
      }),
    ).toBe(submitting);
    expect(
      demoReducer(submitting, {
        type: "GOVERNANCE_FAILED",
        operationId: 1,
        failure,
      }),
    ).toBe(submitting);
  });

  it("commits only the active governance operation", () => {
    const submitting = demoReducer(stateForScenario(), {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(2),
    });
    const succeeded = demoReducer(submitting, {
      type: "GOVERNANCE_SUCCEEDED",
      operationId: 2,
      result,
    });

    expect(succeeded.governance.kind).toBe("SUCCEEDED");
  });

  it("scenario selection invalidates governance and READY transcription", () => {
    const ready = readyTranscriptionState();
    const submitting = demoReducer(ready, {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(12, "VOICE"),
    });
    const next = demoReducer(submitting, {
      type: "SCENARIO_SELECTED",
      scenarioId: "scenario-b",
      command: "Registered scenario B command.",
      inferenceMode: "LOCAL",
    });

    expect(next.governance).toEqual({ kind: "IDLE" });
    expect(next.transcription).toEqual({ kind: "NONE" });
    expect(next.controls).toMatchObject({
      scenarioId: "scenario-b",
      inferenceMode: "LOCAL",
      command: "Registered scenario B command.",
      commandRevision: 6,
    });
  });

  it("mode selection invalidates governance but retains a READY transcript", () => {
    const ready = readyTranscriptionState();
    const withResult = demoReducer(
      demoReducer(ready, {
        type: "GOVERNANCE_STARTED",
        context: governanceContext(12, "VOICE"),
      }),
      { type: "GOVERNANCE_SUCCEEDED", operationId: 12, result },
    );
    const next = demoReducer(withResult, {
      type: "MODE_SELECTED",
      inferenceMode: "LOCAL",
    });

    expect(next.governance).toEqual({ kind: "IDLE" });
    expect(next.transcription.kind).toBe("READY");
    if (next.transcription.kind === "READY") {
      expect(next.transcription.consumed).toBe(true);
    }
  });

  it("governance start atomically clears the previous result", () => {
    const first = demoReducer(stateForScenario(), {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(1),
    });
    const succeeded = demoReducer(first, {
      type: "GOVERNANCE_SUCCEEDED",
      operationId: 1,
      result,
    });
    const second = demoReducer(succeeded, {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(2),
    });

    expect(second.governance).toEqual({
      kind: "SUBMITTING",
      context: governanceContext(2),
    });
  });

  it("consumes a READY voice identity exactly once", () => {
    const ready = readyTranscriptionState();
    const submitting = demoReducer(ready, {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(12, "VOICE"),
    });
    expect(submitting.transcription.kind).toBe("READY");
    if (submitting.transcription.kind === "READY") {
      expect(submitting.transcription.consumed).toBe(true);
    }
    const failed = demoReducer(submitting, {
      type: "GOVERNANCE_FAILED",
      operationId: 12,
      failure,
    });
    const replayAttempt = demoReducer(failed, {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(13, "VOICE"),
    });

    expect(replayAttempt).toBe(failed);
  });

  it("discard removes a consumed identity without restoring it", () => {
    const submitting = demoReducer(readyTranscriptionState(), {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(12, "VOICE"),
    });
    const discarded = demoReducer(submitting, { type: "DISCARD_TRANSCRIPT" });

    expect(discarded.transcription).toEqual({ kind: "NONE" });
    expect(discarded.governance).toEqual({ kind: "IDLE" });
    expect(discarded.controls.command).toBe("");
  });

  it("ignores stale transcription success and failure", () => {
    const active = demoReducer(stateForScenario(), {
      type: "TRANSCRIPTION_STARTED",
      context: transcriptionContext(4),
    });

    expect(
      demoReducer(active, {
        type: "TRANSCRIPTION_SUCCEEDED",
        operationId: 3,
        transcription,
      }),
    ).toBe(active);
    expect(
      demoReducer(active, {
        type: "TRANSCRIPTION_FAILED",
        operationId: 3,
        failure,
      }),
    ).toBe(active);
  });

  it("command editing invalidates active transcription and preserves the edit", () => {
    const active = demoReducer(stateForScenario(), {
      type: "TRANSCRIPTION_STARTED",
      context: transcriptionContext(4),
    });
    const edited = demoReducer(active, {
      type: "COMMAND_EDITED",
      command: "New operator text",
    });

    expect(edited.transcription).toEqual({ kind: "NONE" });
    expect(edited.controls.command).toBe("New operator text");
    expect(
      demoReducer(edited, {
        type: "TRANSCRIPTION_SUCCEEDED",
        operationId: 4,
        transcription,
      }),
    ).toBe(edited);
  });

  it("retains READY transcription while the operator reviews its text", () => {
    const ready = readyTranscriptionState();
    const edited = demoReducer(ready, {
      type: "COMMAND_EDITED",
      command: "Reviewed voice text",
    });

    expect(edited.transcription.kind).toBe("READY");
    expect(edited.controls.command).toBe("Reviewed voice text");
  });

  it("rejects typed and voice ownership with invalid transcript identity", () => {
    const typedBase = stateForScenario();
    const typedWithTranscript = demoReducer(typedBase, {
      type: "GOVERNANCE_STARTED",
      context: { ...governanceContext(1), transcriptionId: "unexpected" },
    });
    expect(typedWithTranscript).toBe(typedBase);

    const voiceBase = stateForScenario();
    const voiceWithoutReadyTranscript = demoReducer(voiceBase, {
      type: "GOVERNANCE_STARTED",
      context: governanceContext(2, "VOICE"),
    });
    expect(voiceWithoutReadyTranscript).toBe(voiceBase);
  });
});
