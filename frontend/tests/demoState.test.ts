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
  ReplayLifecycle,
  ReplayStateProjection,
} from "../src/types";

const failure = { code: "NETWORK_FAILURE", detail: null } as const;
const transcriptionFailure = {
  reason: "TRANSCRIPTION_NETWORK_FAILURE",
  serverCode: null,
} as const;

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

function transcriptionContext(
  operationId: number,
  source: TranscriptionContext["source"] = "WAV_UPLOAD",
): TranscriptionContext {
  return {
    operationId,
    scenarioId: "scenario-a",
    commandRevision: 4,
    source,
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
  it.each(["AVAILABLE", "UNAVAILABLE"] as const)(
    "does not import process-level %s speech status into the client session",
    (speechStatus) => {
      const bootstrapping = demoReducer(initialDemoState, {
        type: "BOOTSTRAP_STARTED",
        operationId: 1,
      });
      const ready = demoReducer(bootstrapping, {
        type: "BOOTSTRAP_SUCCEEDED",
        operationId: 1,
        manifest: {} as DemoManifest,
        status: { speech_status: speechStatus } as DemoStatus,
        initialScenarioId: "scenario-a",
        initialMode: "AUTO",
      });

      expect(ready.speechSessionState).toBe("NOT_CHECKED");
    },
  );

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

    expect(active.speechSessionState).toBe("NOT_CHECKED");

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
        failure: transcriptionFailure,
      }),
    ).toBe(active);
    expect(active.speechSessionState).toBe("NOT_CHECKED");
  });

  it("updates speech presentation only from the owned completed operation", () => {
    const active = demoReducer(stateForScenario(), {
      type: "TRANSCRIPTION_STARTED",
      context: transcriptionContext(4),
    });
    const succeeded = demoReducer(active, {
      type: "TRANSCRIPTION_SUCCEEDED",
      operationId: 4,
      transcription,
    });

    expect(succeeded.speechSessionState).toBe("COMPLETED");

    const discarded = demoReducer(succeeded, { type: "DISCARD_TRANSCRIPT" });
    const nextActive = demoReducer(discarded, {
      type: "TRANSCRIPTION_STARTED",
      context: {
        ...transcriptionContext(5),
        commandRevision: discarded.controls.commandRevision,
      },
    });
    const failed = demoReducer(nextActive, {
      type: "TRANSCRIPTION_FAILED",
      operationId: 5,
      failure: {
        reason: "TRANSCRIPTION_PARTIAL",
        serverCode: "TRANSCRIPTION_PARTIAL",
      },
    });

    expect(failed.speechSessionState).toBe("INCOMPLETE");
    const newerActive = demoReducer(failed, {
      type: "TRANSCRIPTION_STARTED",
      context: {
        ...transcriptionContext(6),
        commandRevision: failed.controls.commandRevision,
      },
    });
    expect(
      demoReducer(newerActive, {
        type: "TRANSCRIPTION_SUCCEEDED",
        operationId: 5,
        transcription,
      }),
    ).toBe(newerActive);
    expect(
      demoReducer(newerActive, {
        type: "TRANSCRIPTION_FAILED",
        operationId: 5,
        failure: {
          reason: "TRANSCRIPTION_TIMEOUT",
          serverCode: "TRANSCRIPTION_TIMEOUT",
        },
      }),
    ).toBe(newerActive);
  });

  it.each([
    ["TRANSCRIPTION_EMPTY", "COMPLETED"],
    ["TRANSCRIPTION_PARTIAL", "INCOMPLETE"],
    ["SPEECH_BACKEND_UNAVAILABLE", "UNAVAILABLE"],
    ["TRANSCRIPTION_TIMEOUT", "TIMED_OUT"],
    ["TRANSCRIPTION_FAILED", "FAILED"],
  ] as const)("maps owned %s settlement to %s", (reason, expected) => {
    const active = demoReducer(stateForScenario(), {
      type: "TRANSCRIPTION_STARTED",
      context: transcriptionContext(4),
    });
    const settled = demoReducer(active, {
      type: "TRANSCRIPTION_FAILED",
      operationId: 4,
      failure: { reason, serverCode: reason },
    });

    expect(settled.speechSessionState).toBe(expected);
  });

  it.each([
    "PERMISSION_DENIED",
    "DEVICE_UNAVAILABLE",
    "CAPTURE_SAMPLE_RATE_UNSUPPORTED",
    "DEVICE_LOST",
    "CAPTURE_EMPTY",
    "CAPTURE_TOO_LONG",
    "CAPTURE_FAILED",
    "ENCODING_FAILED",
    "SPEECH_BUSY",
    "TRANSCRIPTION_INVALID_RESPONSE",
    "TRANSCRIPTION_NETWORK_FAILURE",
  ] as const)("does not fabricate backend state for %s", (reason) => {
    const active = demoReducer(stateForScenario(), {
      type: "TRANSCRIPTION_STARTED",
      context: transcriptionContext(4),
    });
    const settled = demoReducer(active, {
      type: "TRANSCRIPTION_FAILED",
      operationId: 4,
      failure: { reason, serverCode: null },
    });

    expect(settled.speechSessionState).toBe("NOT_CHECKED");
  });

  it("does not create a backend-health claim when client capture is cancelled", () => {
    const active = demoReducer(stateForScenario(), {
      type: "TRANSCRIPTION_STARTED",
      context: transcriptionContext(4),
    });
    const cancelled = demoReducer(active, {
      type: "TRANSCRIPTION_CANCELLED",
      operationId: 4,
    });

    expect(cancelled.speechSessionState).toBe("NOT_CHECKED");
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
    if (edited.transcription.kind === "READY") {
      expect(edited.transcription.transcription.transcript_text).toBe(
        "Move the blue component.",
      );
    }
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

function replayProjection(
  sessionId: string | null,
  projectionVersion: number,
  lifecycle: ReplayLifecycle = sessionId === null ? "IDLE" : "PAUSED",
): ReplayStateProjection {
  const idle = sessionId === null;
  return {
    contract_id: "PROTOTYPE5_D3_REPLAY_STATE_V1",
    contract_version: "1.0.0",
    scenario_id: "scenario-a",
    binding_id: "FROZEN_B2_B3_2_EVIDENCE_V1",
    session_id: sessionId,
    control_version: idle ? 0 : projectionVersion,
    projection_version: idle ? 0 : projectionVersion,
    lifecycle_state: lifecycle,
    command_in_flight: false,
    current_frame: idle ? null : {
      frame_index: lifecycle === "COMPLETED" ? 468 : 0,
      semantic_snapshot_index: lifecycle === "COMPLETED" ? 468 : 0,
      route_configuration_index: lifecycle === "COMPLETED" ? 466 : 0,
      route_state: "HOME",
      phase: lifecycle === "COMPLETED" ? "DESTINATION_SUPPORTED" : "SOURCE_SUPPORTED",
      boundary_snapshot: "NONE",
      is_key_snapshot: true,
    },
    frame_count: 469,
    key_snapshot_indices: [0, 78, 118, 119, 157, 311, 351, 352, 390, 468],
    allowed_controls: ["START", "PAUSE", "RESUME", "NEXT_SNAPSHOT", "PREVIOUS_SNAPSHOT", "STOP", "RESET_VIEW"],
    available_controls: idle ? ["START"] : ["RESUME", "NEXT_SNAPSHOT", "STOP", "RESET_VIEW"],
    presentation_cadence_ms: 50,
    b2_sha256: "a".repeat(64),
    b3_2_sha256: "b".repeat(64),
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
    last_error_code: lifecycle === "FAILED" ? "REPLAY_SCENE_FAILED" : null,
    updated_at_utc: "2026-08-14T10:00:00Z",
  };
}

function replayReadyState(): DemoState {
  const base = stateForScenario();
  const started = demoReducer(base, {
    type: "REPLAY_READ_STARTED",
    context: { operationId: 101, scenarioId: "scenario-a", purpose: "INITIAL" },
  });
  return demoReducer(started, {
    type: "REPLAY_PROJECTION_RECEIVED",
    operationId: 101,
    source: "READ",
    projection: replayProjection(null, 0),
  });
}

describe("replay reducer ownership", () => {
  it("establishes START ownership and accepts only its new session", () => {
    const ready = replayReadyState();
    const started = demoReducer(ready, {
      type: "REPLAY_MUTATION_STARTED",
      context: {
        operationId: 102,
        scenarioId: "scenario-a",
        control: "START",
        sessionId: null,
        controlVersion: 0,
      },
    });
    expect(started.replay.kind).toBe("MUTATING");
    const settled = demoReducer(started, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 102,
      source: "MUTATION",
      projection: replayProjection("S1", 1),
    });
    expect(settled.replay.projection?.session_id).toBe("S1");
    expect(settled.replay.kind).toBe("READY");
  });

  it("rejects double mutation and stale operation settlement", () => {
    const ready = replayReadyState();
    const started = demoReducer(ready, {
      type: "REPLAY_MUTATION_STARTED",
      context: { operationId: 102, scenarioId: "scenario-a", control: "START", sessionId: null, controlVersion: 0 },
    });
    const duplicate = demoReducer(started, {
      type: "REPLAY_MUTATION_STARTED",
      context: { operationId: 103, scenarioId: "scenario-a", control: "START", sessionId: null, controlVersion: 0 },
    });
    expect(duplicate).toBe(started);
    const stale = demoReducer(started, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 999,
      source: "MUTATION",
      projection: replayProjection("stale", 1),
    });
    expect(stale).toBe(started);
  });

  it.each([
    {
      mismatch: "session identity",
      sessionId: "S2",
      controlVersion: 2,
    },
    {
      mismatch: "control version",
      sessionId: "S1",
      controlVersion: 1,
    },
  ])("rejects replay mutation start with stale $mismatch", ({ sessionId, controlVersion }) => {
    const ready = replayReadyState();
    const current = {
      ...ready,
      replay: {
        ...ready.replay,
        projection: replayProjection("S1", 2),
      },
    };

    const rejected = demoReducer(current, {
      type: "REPLAY_MUTATION_STARTED",
      context: {
        operationId: 116,
        scenarioId: "scenario-a",
        control: "NEXT_SNAPSHOT",
        sessionId,
        controlVersion,
      },
    });

    expect(rejected).toBe(current);
    expect(rejected.replay.kind).toBe("READY");
    expect(rejected.replay.mutation).toBeNull();
  });

  it("orders session identity before projection magnitude", () => {
    const base = { ...replayReadyState(), replay: { ...replayReadyState().replay, projection: replayProjection("S2", 2) } };
    const polling = demoReducer(base, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 104, scenarioId: "scenario-a", purpose: "POLL" },
    });
    const staleSession = demoReducer(polling, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 104,
      source: "READ",
      projection: replayProjection("S1", 400),
    });
    expect(staleSession.replay.projection?.session_id).toBe("S2");
    expect(staleSession.replay.read).toBeNull();
    const reconciliating = demoReducer(base, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 105, scenarioId: "scenario-a", purpose: "POLL" },
    });
    const sameSessionHigher = demoReducer(reconciliating, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 105,
      source: "READ",
      projection: replayProjection("S2", 3),
    });
    expect(sameSessionHigher.replay.projection?.projection_version).toBe(3);
    const nextPoll = demoReducer(sameSessionHigher, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 106, scenarioId: "scenario-a", purpose: "POLL" },
    });
    const lowerSameSession = demoReducer(nextPoll, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 106,
      source: "READ",
      projection: replayProjection("S2", 2),
    });
    expect(lowerSameSession.replay.projection?.projection_version).toBe(3);
    expect(lowerSameSession.replay.read).toBeNull();
  });

  it("accepts authoritative STOP to canonical IDLE", () => {
    const base = { ...replayReadyState(), replay: { ...replayReadyState().replay, projection: replayProjection("S1", 2) } };
    const stopping = demoReducer(base, {
      type: "REPLAY_MUTATION_STARTED",
      context: { operationId: 106, scenarioId: "scenario-a", control: "STOP", sessionId: "S1", controlVersion: 2 },
    });
    const stopped = demoReducer(stopping, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 106,
      source: "MUTATION",
      projection: replayProjection(null, 0),
    });
    expect(stopped.replay.projection?.session_id).toBeNull();
    expect(stopped.replay.projection?.available_controls).toEqual(["START"]);
  });

  it("permits explicit reconciliation to recover a server-issued session", () => {
    const ready = replayReadyState();
    const reconciling = demoReducer(ready, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 107, scenarioId: "scenario-a", purpose: "RECONCILE" },
    });
    const recovered = demoReducer(reconciling, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 107,
      source: "READ",
      projection: replayProjection("S1", 1),
    });
    expect(recovered.replay.projection?.session_id).toBe("S1");
    expect(recovered.replay.projection?.projection_version).toBe(1);
  });

  it("accepts authoritative active-to-IDLE read settlement", () => {
    const base = {
      ...replayReadyState(),
      replay: {
        ...replayReadyState().replay,
        projection: replayProjection("S1", 2),
      },
    };
    const reading = demoReducer(base, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 113, scenarioId: "scenario-a", purpose: "POLL" },
    });
    const settled = demoReducer(reading, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 113,
      source: "READ",
      projection: replayProjection(null, 0),
    });
    expect(settled.replay.projection?.session_id).toBeNull();
    expect(settled.replay.projection?.projection_version).toBe(0);
  });

  it.each(["INITIAL", "RECONCILE"] as const)(
    "rejects cross-session active replacement during %s read",
    (purpose) => {
      const base = {
        ...replayReadyState(),
        replay: {
          ...replayReadyState().replay,
          projection: replayProjection("S2", 2),
        },
      };
      const reading = demoReducer(base, {
        type: "REPLAY_READ_STARTED",
        context: { operationId: 114, scenarioId: "scenario-a", purpose },
      });
      const rejected = demoReducer(reading, {
        type: "REPLAY_PROJECTION_RECEIVED",
        operationId: 114,
        source: "READ",
        projection: replayProjection("S1", 400),
      });
      expect(rejected.replay.projection?.session_id).toBe("S2");
      expect(rejected.replay.projection?.projection_version).toBe(2);
      expect(rejected.replay.read).toBeNull();
    },
  );

  it("accepts an equal projection from the same active session", () => {
    const current = replayProjection("S2", 2);
    const base = {
      ...replayReadyState(),
      replay: { ...replayReadyState().replay, projection: current },
    };
    const reading = demoReducer(base, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 115, scenarioId: "scenario-a", purpose: "POLL" },
    });
    const candidate = { ...current, updated_at_utc: "2026-08-14T10:00:01Z" };
    const accepted = demoReducer(reading, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 115,
      source: "READ",
      projection: candidate,
    });
    expect(accepted.replay.projection).toBe(candidate);
    expect(accepted.replay.read).toBeNull();
  });

  it("latches fatal exhaustion across deactivation and scenario changes", () => {
    const fatal = demoReducer(replayReadyState(), {
      type: "REPLAY_FATAL",
      originScenarioId: "scenario-a",
    });
    expect(fatal.replay.kind).toBe("FATAL");
    expect(demoReducer(fatal, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 108, scenarioId: "scenario-a", purpose: "RECONCILE" },
    })).toBe(fatal);
    expect(demoReducer(fatal, { type: "REPLAY_DEACTIVATED" })).toBe(fatal);
    const switched = demoReducer(fatal, {
      type: "SCENARIO_SELECTED",
      scenarioId: "scenario-b",
      command: "",
      inferenceMode: "AUTO",
    });
    expect(switched.replay.kind).toBe("FATAL");
    expect(switched.replay.failure?.code).toBe("REPLAY_VERSION_EXHAUSTED");
    expect(demoReducer(switched, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 109, scenarioId: "scenario-b", purpose: "INITIAL" },
    })).toBe(switched);
    expect(demoReducer(switched, {
      type: "REPLAY_MUTATION_STARTED",
      context: {
        operationId: 110,
        scenarioId: "scenario-b",
        control: "START",
        sessionId: null,
        controlVersion: 0,
      },
    })).toBe(switched);
  });

  it("publishes an owned fatal event after the selected scenario changes", () => {
    const switched = demoReducer(replayReadyState(), {
      type: "SCENARIO_SELECTED",
      scenarioId: "scenario-b",
      command: "",
      inferenceMode: "AUTO",
    });
    const fatal = demoReducer(switched, {
      type: "REPLAY_FATAL",
      originScenarioId: "scenario-a",
    });
    expect(fatal.controls.scenarioId).toBe("scenario-b");
    expect(fatal.replay.kind).toBe("FATAL");
    expect(fatal.replay.scenarioId).toBe("scenario-a");
    expect(fatal.replay.failure?.code).toBe("REPLAY_VERSION_EXHAUSTED");
  });

  it("rejects a mutation projection that changes session identity", () => {
    const base = {
      ...replayReadyState(),
      replay: {
        ...replayReadyState().replay,
        projection: replayProjection("S1", 2),
      },
    };
    const mutating = demoReducer(base, {
      type: "REPLAY_MUTATION_STARTED",
      context: {
        operationId: 111,
        scenarioId: "scenario-a",
        control: "NEXT_SNAPSHOT",
        sessionId: "S1",
        controlVersion: 2,
      },
    });
    const rejected = demoReducer(mutating, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 111,
      source: "MUTATION",
      projection: replayProjection("S2", 400),
    });
    expect(rejected.replay.kind).toBe("ERROR");
    expect(rejected.replay.failure?.code).toBe("CONTRACT_FAILURE");
    expect(rejected.replay.projection?.session_id).toBe("S1");
  });

  it("does not announce same-lifecycle poll frame progression", () => {
    const playing = replayProjection("S1", 2, "PLAYING");
    const base = {
      ...replayReadyState(),
      replay: {
        ...replayReadyState().replay,
        projection: playing,
        announcement: "Evidence replay playing.",
      },
    };
    const polling = demoReducer(base, {
      type: "REPLAY_READ_STARTED",
      context: { operationId: 112, scenarioId: "scenario-a", purpose: "POLL" },
    });
    const progressed = demoReducer(polling, {
      type: "REPLAY_PROJECTION_RECEIVED",
      operationId: 112,
      source: "READ",
      projection: {
        ...playing,
        projection_version: 3,
        current_frame: playing.current_frame === null
          ? null
          : {
              ...playing.current_frame,
              frame_index: 1,
              semantic_snapshot_index: 1,
              is_key_snapshot: false,
            },
      },
    });
    expect(progressed.replay.projection?.current_frame?.frame_index).toBe(1);
    expect(progressed.replay.announcement).toBe("Evidence replay playing.");
  });
});
