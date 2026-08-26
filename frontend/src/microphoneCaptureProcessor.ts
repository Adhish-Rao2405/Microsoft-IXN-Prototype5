export const MICROPHONE_PROCESSOR_NAME = "prototype5-bounded-microphone-capture";
export const TARGET_SAMPLE_RATE_HZ = 16_000;
export const MAX_CAPTURE_SECONDS = 15;
export const MAX_CAPTURE_FRAMES = TARGET_SAMPLE_RATE_HZ * MAX_CAPTURE_SECONDS;
export const MAX_RETAINED_FLOAT32_BYTES = MAX_CAPTURE_FRAMES * Float32Array.BYTES_PER_ELEMENT;

export type ProcessorFailureReason =
  | "CAPTURE_SAMPLE_RATE_UNSUPPORTED"
  | "CAPTURE_TOO_LONG"
  | "CAPTURE_FAILED";

export type AppendFramesResult =
  | { kind: "APPENDED"; nextFrame: number; reachedLimit: boolean }
  | { kind: "FAILED"; reason: ProcessorFailureReason };

export function appendInputFrames(
  target: Float32Array,
  currentFrame: number,
  channels: readonly Float32Array[],
): AppendFramesResult {
  if (
    target.length !== MAX_CAPTURE_FRAMES ||
    !Number.isSafeInteger(currentFrame) ||
    currentFrame < 0 ||
    currentFrame > MAX_CAPTURE_FRAMES
  ) {
    return { kind: "FAILED", reason: "CAPTURE_FAILED" };
  }
  if (channels.length < 1 || channels.length > 2) {
    return { kind: "FAILED", reason: "CAPTURE_FAILED" };
  }
  const first = channels[0];
  const second = channels[1];
  if (!first || (second !== undefined && second.length !== first.length)) {
    return { kind: "FAILED", reason: "CAPTURE_FAILED" };
  }
  if (currentFrame === MAX_CAPTURE_FRAMES && first.length > 0) {
    return { kind: "FAILED", reason: "CAPTURE_TOO_LONG" };
  }

  const accepted = Math.min(first.length, MAX_CAPTURE_FRAMES - currentFrame);
  for (let index = 0; index < accepted; index += 1) {
    const left = first[index];
    const right = second?.[index];
    if (
      left === undefined ||
      !Number.isFinite(left) ||
      (second !== undefined && (right === undefined || !Number.isFinite(right)))
    ) {
      return { kind: "FAILED", reason: "CAPTURE_FAILED" };
    }
    target[currentFrame + index] = second === undefined
      ? left
      : (left + (right as number)) / 2;
  }
  const nextFrame = currentFrame + accepted;
  return {
    kind: "APPENDED",
    nextFrame,
    reachedLimit: nextFrame === MAX_CAPTURE_FRAMES,
  };
}

export type CaptureProcessorMessage =
  | { type: "FINALISE" }
  | { type: "CANCEL" };

export function parseCaptureProcessorMessage(
  value: unknown,
): CaptureProcessorMessage | null {
  if (value === null || typeof value !== "object") return null;
  const type = (value as { type?: unknown }).type;
  if (type === "FINALISE") return { type: "FINALISE" };
  if (type === "CANCEL") return { type: "CANCEL" };
  return null;
}

interface AudioWorkletProcessorInstance {
  readonly port: MessagePort;
}

interface AudioWorkletRuntime {
  readonly AudioWorkletProcessor?: new () => AudioWorkletProcessorInstance;
  readonly registerProcessor?: (
    name: string,
    processor: new () => AudioWorkletProcessorInstance,
  ) => void;
  readonly sampleRate?: number;
}

const runtime = globalThis as unknown as AudioWorkletRuntime;

if (runtime.AudioWorkletProcessor && runtime.registerProcessor) {
  const ProcessorBase = runtime.AudioWorkletProcessor;

  class Prototype5MicrophoneCaptureProcessor extends ProcessorBase {
    private buffer = new Float32Array(MAX_CAPTURE_FRAMES);
    private frameCount = 0;
    private terminal = false;

    constructor() {
      super();
      this.port.onmessage = (event: MessageEvent<unknown>) => {
        if (this.terminal) return;
        const message = parseCaptureProcessorMessage(event.data);
        if (message === null) {
          this.fail("CAPTURE_FAILED");
          return;
        }
        if (message.type === "FINALISE") {
          this.complete(false);
          return;
        }
        this.cancel();
      };
      if (runtime.sampleRate !== TARGET_SAMPLE_RATE_HZ) {
        this.fail("CAPTURE_SAMPLE_RATE_UNSUPPORTED");
      }
    }

    process(inputs: Float32Array[][]): boolean {
      if (this.terminal) return false;
      const result = appendInputFrames(
        this.buffer,
        this.frameCount,
        inputs[0] ?? [],
      );
      if (result.kind === "FAILED") {
        this.fail(result.reason);
        return false;
      }
      this.frameCount = result.nextFrame;
      if (result.reachedLimit) {
        this.complete(true);
        return false;
      }
      return true;
    }

    private complete(reachedLimit: boolean): void {
      if (this.terminal) return;
      if (reachedLimit !== (this.frameCount === MAX_CAPTURE_FRAMES)) {
        this.fail("CAPTURE_FAILED");
        return;
      }
      this.terminal = true;
      const buffer = this.buffer.buffer;
      this.buffer = new Float32Array(0);
      this.port.postMessage(
        {
          type: "CAPTURE_COMPLETE",
          buffer,
          frameCount: this.frameCount,
          reachedLimit,
        },
        [buffer],
      );
    }

    private fail(reason: ProcessorFailureReason): void {
      if (this.terminal) return;
      this.terminal = true;
      this.buffer = new Float32Array(0);
      this.port.postMessage({ type: "CAPTURE_FAILED", reason });
    }

    private cancel(): void {
      if (this.terminal) return;
      this.terminal = true;
      this.buffer = new Float32Array(0);
      this.port.close();
    }
  }

  runtime.registerProcessor(
    MICROPHONE_PROCESSOR_NAME,
    Prototype5MicrophoneCaptureProcessor,
  );
}
