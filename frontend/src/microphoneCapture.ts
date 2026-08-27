import processorModuleUrl from "./microphoneCaptureProcessor.ts?worker&url";
import {
  MAX_CAPTURE_FRAMES,
  MAX_CAPTURE_SECONDS,
  MAX_RETAINED_FLOAT32_BYTES,
  MICROPHONE_PROCESSOR_NAME,
  TARGET_SAMPLE_RATE_HZ,
  type ProcessorFailureReason,
} from "./microphoneCaptureProcessor";

export {
  MAX_CAPTURE_FRAMES,
  MAX_CAPTURE_SECONDS,
  MAX_RETAINED_FLOAT32_BYTES,
  TARGET_SAMPLE_RATE_HZ,
};

export const MAX_PCM16_BYTES = MAX_CAPTURE_FRAMES * Int16Array.BYTES_PER_ELEMENT;
export const MAX_WAV_BYTES = 44 + MAX_PCM16_BYTES;
const SETUP_DEADLINE_MS = 30_000;
const RECORDING_DEADLINE_MS = 16_000;
export const FINALISE_ACK_TIMEOUT_MS = 2_000;
export const CONTEXT_CLOSE_TIMEOUT_MS = 2_000;

export type MicrophoneCaptureFailureReason =
  | "PERMISSION_DENIED"
  | "DEVICE_UNAVAILABLE"
  | "CAPTURE_SAMPLE_RATE_UNSUPPORTED"
  | "DEVICE_LOST"
  | "CAPTURE_EMPTY"
  | "CAPTURE_TOO_LONG"
  | "CAPTURE_FAILED"
  | "ENCODING_FAILED";

export type MicrophoneCaptureOutcome =
  | { kind: "CAPTURED"; file: File; frameCount: number }
  | { kind: "FAILED"; reason: MicrophoneCaptureFailureReason }
  | { kind: "CANCELLED" };

type WorkletCaptureMessage =
  | {
      type: "CAPTURE_COMPLETE";
      buffer: ArrayBuffer;
      frameCount: number;
      reachedLimit: boolean;
    }
  | { type: "CAPTURE_FAILED"; reason: ProcessorFailureReason };

type SetupOperationResult<T> =
  | { kind: "VALUE"; value: T }
  | { kind: "ERROR"; error: unknown }
  | { kind: "TERMINAL" };

interface TerminalState {
  terminal: boolean;
}

function stopMediaStreamTracks(stream: MediaStream): void {
  let tracks: MediaStreamTrack[];
  try {
    tracks = [...new Set(stream.getTracks())];
  } catch {
    return;
  }
  for (const track of tracks) {
    try {
      track.stop();
    } catch {
      // Terminal late-result disposal cannot recover capture authority.
    }
  }
}

export interface MicrophoneCaptureDependencies {
  readonly getUserMedia: () => Promise<MediaStream>;
  readonly createAudioContext: () => AudioContext;
  readonly createWorkletNode: (context: AudioContext) => AudioWorkletNode;
  readonly workletModuleUrl: string;
  readonly setTimer: (callback: () => void, delayMs: number) => ReturnType<typeof setTimeout>;
  readonly clearTimer: (handle: ReturnType<typeof setTimeout>) => void;
}

export class MicrophoneCaptureError extends Error {
  constructor(readonly reason: MicrophoneCaptureFailureReason) {
    super(reason);
    this.name = "MicrophoneCaptureError";
  }
}

function defaultDependencies(): MicrophoneCaptureDependencies {
  return {
    getUserMedia: async () => {
      if (!globalThis.navigator?.mediaDevices?.getUserMedia) {
        throw new MicrophoneCaptureError("DEVICE_UNAVAILABLE");
      }
      return globalThis.navigator.mediaDevices.getUserMedia({
        audio: { channelCount: { ideal: 1 }, sampleRate: { ideal: 16_000 } },
        video: false,
      });
    },
    createAudioContext: () => {
      if (!globalThis.AudioContext) {
        throw new MicrophoneCaptureError("DEVICE_UNAVAILABLE");
      }
      return new AudioContext({ sampleRate: TARGET_SAMPLE_RATE_HZ });
    },
    createWorkletNode: (context) => new AudioWorkletNode(
      context,
      MICROPHONE_PROCESSOR_NAME,
      {
        numberOfInputs: 1,
        numberOfOutputs: 0,
        channelCount: 2,
        channelCountMode: "max",
      },
    ),
    workletModuleUrl: processorModuleUrl,
    setTimer: (callback, delayMs) => setTimeout(callback, delayMs),
    clearTimer: (handle) => clearTimeout(handle),
  };
}

export function quantizePcm16(sample: number): number {
  if (!Number.isFinite(sample)) throw new MicrophoneCaptureError("ENCODING_FAILED");
  const clamped = Math.max(-1, Math.min(1, sample));
  const scaled = clamped < 0 ? clamped * 32_768 : clamped * 32_767;
  const rounded = scaled < 0
    ? -Math.floor(Math.abs(scaled) + 0.5)
    : Math.floor(scaled + 0.5);
  return Math.max(-32_768, Math.min(32_767, rounded));
}

export function encodePcm16Wav(
  samples: Float32Array,
): Uint8Array<ArrayBuffer> {
  if (samples.length === 0) throw new MicrophoneCaptureError("CAPTURE_EMPTY");
  if (samples.length > MAX_CAPTURE_FRAMES) {
    throw new MicrophoneCaptureError("CAPTURE_TOO_LONG");
  }
  const dataBytes = samples.length * Int16Array.BYTES_PER_ELEMENT;
  const output = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(output);
  const writeAscii = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };
  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, TARGET_SAMPLE_RATE_HZ, true);
  view.setUint32(28, TARGET_SAMPLE_RATE_HZ * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, dataBytes, true);
  for (let index = 0; index < samples.length; index += 1) {
    view.setInt16(44 + index * 2, quantizePcm16(samples[index] as number), true);
  }
  return new Uint8Array(output);
}

function permissionFailure(error: unknown): MicrophoneCaptureFailureReason {
  if (error instanceof MicrophoneCaptureError) return error.reason;
  if (
    error instanceof DOMException &&
    (error.name === "NotAllowedError" || error.name === "SecurityError")
  ) return "PERMISSION_DENIED";
  if (
    error instanceof DOMException &&
    (error.name === "NotFoundError" || error.name === "OverconstrainedError")
  ) return "DEVICE_UNAVAILABLE";
  return "CAPTURE_FAILED";
}

function isProcessorFailureReason(
  value: unknown,
): value is ProcessorFailureReason {
  return value === "CAPTURE_SAMPLE_RATE_UNSUPPORTED" ||
    value === "CAPTURE_TOO_LONG" ||
    value === "CAPTURE_FAILED";
}

export function parseWorkletCaptureMessage(
  value: unknown,
): WorkletCaptureMessage | null {
  if (value === null || typeof value !== "object") return null;
  const message = value as {
    type?: unknown;
    reason?: unknown;
    buffer?: unknown;
    frameCount?: unknown;
    reachedLimit?: unknown;
  };
  if (message.type === "CAPTURE_FAILED") {
    return isProcessorFailureReason(message.reason)
      ? { type: "CAPTURE_FAILED", reason: message.reason }
      : null;
  }
  if (
    message.type !== "CAPTURE_COMPLETE" ||
    !(message.buffer instanceof ArrayBuffer) ||
    message.buffer.byteLength !== MAX_RETAINED_FLOAT32_BYTES ||
    !Number.isSafeInteger(message.frameCount) ||
    typeof message.reachedLimit !== "boolean"
  ) return null;

  const frameCount = message.frameCount as number;
  if (frameCount < 0 || frameCount > MAX_CAPTURE_FRAMES) return null;
  if (message.reachedLimit !== (frameCount === MAX_CAPTURE_FRAMES)) return null;
  return {
    type: "CAPTURE_COMPLETE",
    buffer: message.buffer,
    frameCount,
    reachedLimit: message.reachedLimit,
  };
}

export class MicrophoneCaptureController {
  readonly outcome: Promise<MicrophoneCaptureOutcome>;
  private readonly terminalSignal: Promise<void>;
  private readonly terminalState: TerminalState = { terminal: false };
  private readonly dependencies: MicrophoneCaptureDependencies;
  private resolveOutcome!: (outcome: MicrophoneCaptureOutcome) => void;
  private resolveTerminalSignal!: () => void;
  private stream: MediaStream | null = null;
  private track: MediaStreamTrack | null = null;
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private worklet: AudioWorkletNode | null = null;
  private lifecycleTimer: ReturnType<typeof setTimeout> | null = null;
  private lifecycleDeadlineGeneration = 0;
  private finaliseTimer: ReturnType<typeof setTimeout> | null = null;
  private started = false;
  private finalising = false;
  private terminal = false;

  constructor(
    dependencies: MicrophoneCaptureDependencies = defaultDependencies(),
    private readonly onAutomaticFinalise: () => void = () => undefined,
  ) {
    this.dependencies = dependencies;
    this.terminalSignal = new Promise((resolve) => {
      this.resolveTerminalSignal = resolve;
    });
    this.outcome = new Promise((resolve) => {
      this.resolveOutcome = resolve;
    });
  }

  async start(): Promise<boolean> {
    if (this.started || this.terminal) return false;
    this.started = true;
    try {
      this.armLifecycleDeadline(SETUP_DEADLINE_MS, () => {
        void this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
      });
    } catch {
      await this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
      return false;
    }
    if (this.terminal) return false;
    const mediaResult = await this.raceSetupOperation(
      () => this.dependencies.getUserMedia(),
      stopMediaStreamTracks,
    );
    if (mediaResult.kind === "TERMINAL" || this.terminal) {
      return false;
    }
    if (mediaResult.kind === "ERROR") {
      await this.settle({
        kind: "FAILED",
        reason: permissionFailure(mediaResult.error),
      });
      return false;
    }
    const stream = mediaResult.value;
    if (this.terminal) {
      stopMediaStreamTracks(stream);
      return false;
    }
    this.stream = stream;
    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length !== 1 || audioTracks[0]?.readyState !== "live") {
      await this.settle({ kind: "FAILED", reason: "DEVICE_UNAVAILABLE" });
      return false;
    }
    this.track = audioTracks[0];
    this.track.addEventListener("ended", this.handleTrackEnded, { once: true });
    if (this.track.readyState !== "live") {
      await this.settle({ kind: "FAILED", reason: "DEVICE_LOST" });
      return false;
    }

    try {
      this.context = this.dependencies.createAudioContext();
    } catch (error: unknown) {
      await this.settle({
        kind: "FAILED",
        reason: error instanceof MicrophoneCaptureError
          ? error.reason
          : "CAPTURE_SAMPLE_RATE_UNSUPPORTED",
      });
      return false;
    }
    if (this.context.sampleRate !== TARGET_SAMPLE_RATE_HZ) {
      await this.settle({
        kind: "FAILED",
        reason: "CAPTURE_SAMPLE_RATE_UNSUPPORTED",
      });
      return false;
    }
    try {
      if (this.context.state === "suspended") {
        const resumeResult = await this.raceSetupOperation(
          () => this.context!.resume(),
        );
        if (resumeResult.kind === "TERMINAL" || this.terminal) return false;
        if (resumeResult.kind === "ERROR") throw resumeResult.error;
      }
      if (this.context.state !== "running") throw new Error("CONTEXT_NOT_RUNNING");
      if (this.track.readyState !== "live") {
        await this.settle({ kind: "FAILED", reason: "DEVICE_LOST" });
        return false;
      }
      const moduleResult = await this.raceSetupOperation(
        () => this.context!.audioWorklet.addModule(
          this.dependencies.workletModuleUrl,
        ),
      );
      if (moduleResult.kind === "TERMINAL" || this.terminal) return false;
      if (moduleResult.kind === "ERROR") throw moduleResult.error;
      if (this.track.readyState !== "live") {
        await this.settle({ kind: "FAILED", reason: "DEVICE_LOST" });
        return false;
      }
      this.worklet = this.dependencies.createWorkletNode(this.context);
      this.source = this.context.createMediaStreamSource(stream);
      this.worklet.port.addEventListener("message", this.handleWorkletMessage);
      this.worklet.addEventListener("processorerror", this.handleProcessorError);
      this.worklet.port.start();
      this.source.connect(this.worklet);
      this.armLifecycleDeadline(
        RECORDING_DEADLINE_MS,
        this.handleRecordingDeadline,
      );
      return true;
    } catch {
      await this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
      return false;
    }
  }

  async stop(): Promise<MicrophoneCaptureOutcome> {
    if (this.terminal) return this.outcome;
    if (!this.worklet) {
      await this.settle({ kind: "CANCELLED" });
      return this.outcome;
    }
    if (this.finalising) return this.outcome;
    this.finalising = true;
    this.clearLifecycleDeadline();
    try {
      this.armFinaliseTimeout();
      this.worklet.port.postMessage({ type: "FINALISE" });
    } catch {
      await this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
    }
    return this.outcome;
  }

  async cancel(): Promise<MicrophoneCaptureOutcome> {
    if (!this.terminal) {
      try {
        this.worklet?.port.postMessage({ type: "CANCEL" });
      } catch {
        // Local cancellation authority does not depend on a worklet ACK.
      }
      await this.settle({ kind: "CANCELLED" });
    }
    return this.outcome;
  }

  private readonly handleTrackEnded = () => {
    if (!this.terminal) {
      void this.settle({ kind: "FAILED", reason: "DEVICE_LOST" });
    }
  };

  private readonly handleProcessorError = () => {
    if (!this.terminal) {
      void this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
    }
  };

  private readonly handleRecordingDeadline = () => {
    if (this.terminal || this.finalising || this.worklet === null) return;
    void this.stop();
    if (this.terminal) return;
    try {
      this.onAutomaticFinalise();
    } catch {
      // Presentation failure cannot block controller-owned finalisation.
    }
  };

  private readonly handleWorkletMessage = (event: MessageEvent<unknown>) => {
    if (this.terminal) return;
    const message = parseWorkletCaptureMessage(event.data);
    if (message === null) {
      void this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
      return;
    }
    if (message.type === "CAPTURE_FAILED") {
      void this.settle({ kind: "FAILED", reason: message.reason });
      return;
    }
    const completionAuthorised = message.reachedLimit
      ? message.frameCount === MAX_CAPTURE_FRAMES
      : this.finalising;
    if (!completionAuthorised) {
      void this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
      return;
    }
    if (message.frameCount === 0) {
      void this.settle({ kind: "FAILED", reason: "CAPTURE_EMPTY" });
      return;
    }
    try {
      const samples = new Float32Array(message.buffer, 0, message.frameCount);
      const wav = encodePcm16Wav(samples);
      const file = new File([wav], "microphone.wav", { type: "audio/wav" });
      void this.settle({
        kind: "CAPTURED",
        file,
        frameCount: message.frameCount,
      });
    } catch (error: unknown) {
      void this.settle({
        kind: "FAILED",
        reason: error instanceof MicrophoneCaptureError
          ? error.reason
          : "ENCODING_FAILED",
      });
    }
  };

  private async raceSetupOperation<T>(
    start: () => Promise<T>,
    onTerminalValue?: (value: T) => void,
  ): Promise<SetupOperationResult<T>> {
    const terminalState = this.terminalState;
    const terminalSignal = this.terminalSignal;

    if (terminalState.terminal) return { kind: "TERMINAL" };

    let operation: Promise<T>;
    try {
      operation = Promise.resolve(start());
    } catch (error: unknown) {
      return { kind: "ERROR", error };
    }

    const observed: Promise<SetupOperationResult<T>> = operation.then(
      (value) => {
        if (terminalState.terminal) {
          try {
            onTerminalValue?.(value);
          } catch {
            // Late external results cannot restore application ownership.
          }
          return { kind: "TERMINAL" };
        }
        return { kind: "VALUE", value };
      },
      (error: unknown) => terminalState.terminal
        ? { kind: "TERMINAL" }
        : { kind: "ERROR", error },
    );
    const terminal = terminalSignal.then<SetupOperationResult<T>>(
      () => ({ kind: "TERMINAL" }),
    );
    return Promise.race([observed, terminal]);
  }

  private async settle(outcome: MicrophoneCaptureOutcome): Promise<void> {
    if (this.terminal) return;
    this.terminal = true;
    this.terminalState.terminal = true;
    this.resolveTerminalSignal();
    try {
      await this.cleanup();
    } finally {
      this.resolveOutcome(outcome);
    }
  }

  private armFinaliseTimeout(): void {
    this.clearFinaliseTimer();
    const handle = this.dependencies.setTimer(
      () => {
        void this.settle({ kind: "FAILED", reason: "CAPTURE_FAILED" });
      },
      FINALISE_ACK_TIMEOUT_MS,
    );
    if (this.terminal) {
      try {
        this.dependencies.clearTimer(handle);
      } catch {
        // Terminal ownership no longer depends on timer cleanup.
      }
      return;
    }
    this.finaliseTimer = handle;
  }

  private armLifecycleDeadline(
    delayMs: number,
    onDeadline: () => void,
  ): void {
    this.clearLifecycleDeadline();
    const generation = this.lifecycleDeadlineGeneration;
    const handle = this.dependencies.setTimer(() => {
      if (
        this.terminal ||
        generation !== this.lifecycleDeadlineGeneration
      ) return;
      this.lifecycleTimer = null;
      onDeadline();
    }, delayMs);
    if (
      this.terminal ||
      generation !== this.lifecycleDeadlineGeneration
    ) {
      try {
        this.dependencies.clearTimer(handle);
      } catch {
        // Terminal ownership no longer depends on timer cleanup.
      }
      return;
    }
    this.lifecycleTimer = handle;
  }

  private clearLifecycleDeadline(): void {
    this.lifecycleDeadlineGeneration += 1;
    const handle = this.lifecycleTimer;
    this.lifecycleTimer = null;
    if (handle === null) return;
    try {
      this.dependencies.clearTimer(handle);
    } catch {
      // Terminal ownership no longer depends on timer cleanup.
    }
  }

  private clearFinaliseTimer(): void {
    const handle = this.finaliseTimer;
    this.finaliseTimer = null;
    if (handle === null) return;
    try {
      this.dependencies.clearTimer(handle);
    } catch {
      // Terminal ownership no longer depends on timer cleanup.
    }
  }

  private async cleanup(): Promise<void> {
    this.clearLifecycleDeadline();
    this.clearFinaliseTimer();

    const stream = this.stream;
    const track = this.track;
    const context = this.context;
    const source = this.source;
    const worklet = this.worklet;

    this.stream = null;
    this.track = null;
    this.context = null;
    this.source = null;
    this.worklet = null;

    if (track) {
      try {
        track.removeEventListener("ended", this.handleTrackEnded);
      } catch {
        // Ownership has already been invalidated.
      }
    }

    if (worklet) {
      try {
        worklet.port.removeEventListener("message", this.handleWorkletMessage);
      } catch {
        // Ownership has already been invalidated.
      }
      try {
        worklet.removeEventListener("processorerror", this.handleProcessorError);
      } catch {
        // Ownership has already been invalidated.
      }
      try {
        worklet.port.close();
      } catch {
        // Ownership has already been invalidated.
      }
      try {
        worklet.disconnect();
      } catch {
        // Ownership has already been invalidated.
      }
    }

    if (source) {
      try {
        source.disconnect();
      } catch {
        // Ownership has already been invalidated.
      }
    }

    const ownedTracks = new Set<MediaStreamTrack>();
    if (track) ownedTracks.add(track);
    if (stream) {
      try {
        stream.getTracks().forEach((ownedTrack) => ownedTracks.add(ownedTrack));
      } catch {
        // The accepted audio track is still stopped below.
      }
    }
    ownedTracks.forEach((ownedTrack) => {
      try {
        ownedTrack.stop();
      } catch {
        // Track ownership is terminal regardless of browser error.
      }
    });

    if (context) {
      let isClosed = false;
      try {
        isClosed = context.state === "closed";
      } catch {
        // Attempt bounded close when state observation itself fails.
      }
      if (!isClosed) await this.closeContextBounded(context);
    }
  }

  private async closeContextBounded(context: AudioContext): Promise<void> {
    let closePromise: Promise<void>;
    try {
      closePromise = context.close();
    } catch {
      return;
    }

    await new Promise<void>((resolve) => {
      let complete = false;
      let timeout: ReturnType<typeof setTimeout> | null = null;
      const finish = () => {
        if (complete) return;
        complete = true;
        if (timeout !== null) {
          try {
            this.dependencies.clearTimer(timeout);
          } catch {
            // Terminal settlement is already independent of the timer.
          }
        }
        resolve();
      };

      try {
        const handle = this.dependencies.setTimer(finish, CONTEXT_CLOSE_TIMEOUT_MS);
        timeout = handle;
        if (complete) {
          try {
            this.dependencies.clearTimer(handle);
          } catch {
            // Synchronous timer implementations cannot block settlement.
          }
        }
      } catch {
        finish();
      }

      void Promise.resolve(closePromise).then(finish, finish);
    });
  }
}

export function createMicrophoneCaptureController(
  onAutomaticFinalise: () => void,
): MicrophoneCaptureController {
  return new MicrophoneCaptureController(
    defaultDependencies(),
    onAutomaticFinalise,
  );
}
