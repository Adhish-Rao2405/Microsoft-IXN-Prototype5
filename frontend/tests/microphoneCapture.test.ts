import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  CONTEXT_CLOSE_TIMEOUT_MS,
  FINALISE_ACK_TIMEOUT_MS,
  MAX_CAPTURE_FRAMES,
  MAX_CAPTURE_SECONDS,
  MAX_RETAINED_FLOAT32_BYTES,
  MicrophoneCaptureController,
  encodePcm16Wav,
  parseWorkletCaptureMessage,
  quantizePcm16,
  type MicrophoneCaptureDependencies,
} from "../src/microphoneCapture";
import {
  appendInputFrames,
  parseCaptureProcessorMessage,
} from "../src/microphoneCaptureProcessor";

const SETUP_DEADLINE_MS = 30_000;
const RECORDING_DEADLINE_MS = 16_000;

interface Deferred<T> {
  readonly promise: Promise<T>;
  readonly resolve: (value: T) => void;
  readonly reject: (reason?: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

async function flushMicrotasks(): Promise<void> {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
  }
}

class FakeTrack extends EventTarget {
  readyState: MediaStreamTrackState = "live";
  readonly stop = vi.fn(() => {
    this.readyState = "ended";
  });

  end(): void {
    this.readyState = "ended";
    this.dispatchEvent(new Event("ended"));
  }
}

class FakePort extends EventTarget {
  readonly postMessage = vi.fn();
  readonly start = vi.fn();
  readonly close = vi.fn();

  emit(data: unknown): void {
    this.dispatchEvent(new MessageEvent("message", { data }));
  }
}

class FakeWorkletNode extends EventTarget {
  readonly portOwner = new FakePort();
  readonly port = this.portOwner as unknown as MessagePort;
  readonly disconnect = vi.fn();

  processorError(): void {
    this.dispatchEvent(new Event("processorerror"));
  }
}

class FakeSourceNode {
  readonly connect = vi.fn();
  readonly disconnect = vi.fn();
}

interface HarnessOptions {
  readonly tracks?: FakeTrack[];
  readonly getUserMedia?: (stream: MediaStream) => Promise<MediaStream>;
  readonly contextState?: AudioContextState;
  readonly sampleRate?: number;
  readonly resume?: () => Promise<void>;
  readonly addModule?: () => Promise<void>;
  readonly close?: () => Promise<void>;
  readonly automaticFinalise?: () => void;
}

function makeHarness(options: HarnessOptions = {}) {
  const tracks = options.tracks ?? [new FakeTrack()];
  const stream = {
    getAudioTracks: vi.fn(() => tracks as unknown as MediaStreamTrack[]),
    getTracks: vi.fn(() => tracks as unknown as MediaStreamTrack[]),
  } as unknown as MediaStream;
  const source = new FakeSourceNode();
  const worklet = new FakeWorkletNode();
  const context = {
    sampleRate: options.sampleRate ?? 16_000,
    state: options.contextState ?? "running",
    resume: vi.fn(async function (this: { state: AudioContextState }) {
      await (options.resume?.() ?? Promise.resolve());
      if (this.state !== "closed") this.state = "running";
    }),
    audioWorklet: {
      addModule: vi.fn(() => options.addModule?.() ?? Promise.resolve()),
    },
    createMediaStreamSource: vi.fn(() => source as unknown as MediaStreamAudioSourceNode),
    close: vi.fn(async function (this: { state: AudioContextState }) {
      await (options.close?.() ?? Promise.resolve());
      this.state = "closed";
    }),
  } as unknown as AudioContext;
  const getUserMedia = vi.fn(
    () => options.getUserMedia?.(stream) ?? Promise.resolve(stream),
  );
  const createAudioContext = vi.fn(() => context);
  const createWorkletNode = vi.fn(
    () => worklet as unknown as AudioWorkletNode,
  );
  const setTimer = vi.fn(
    (callback: () => void, delayMs: number) => setTimeout(callback, delayMs),
  );
  const clearTimer = vi.fn(
    (handle: ReturnType<typeof setTimeout>) => clearTimeout(handle),
  );
  const dependencies: MicrophoneCaptureDependencies = {
    getUserMedia,
    createAudioContext,
    createWorkletNode,
    workletModuleUrl: "bounded-capture-worklet.js",
    setTimer,
    clearTimer,
  };
  const controller = new MicrophoneCaptureController(
    dependencies,
    options.automaticFinalise,
  );
  return {
    context,
    controller,
    createAudioContext,
    createWorkletNode,
    clearTimer,
    getUserMedia,
    setTimer,
    source,
    stream,
    tracks,
    worklet,
  };
}

function completeMessage(frameCount: number, reachedLimit: boolean) {
  const samples = new Float32Array(MAX_CAPTURE_FRAMES);
  return {
    type: "CAPTURE_COMPLETE",
    buffer: samples.buffer,
    frameCount,
    reachedLimit,
  };
}

describe("MicrophoneCaptureController bounded lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("settles CANCELLED when stopped during pending getUserMedia", async () => {
    const permission = deferred<MediaStream>();
    const lateTracks = [new FakeTrack(), new FakeTrack()];
    const harness = makeHarness({
      tracks: lateTracks,
      getUserMedia: () => permission.promise,
    });
    const starting = harness.controller.start();
    await flushMicrotasks();

    await expect(harness.controller.stop()).resolves.toEqual({ kind: "CANCELLED" });
    await expect(starting).resolves.toBe(false);

    permission.resolve(harness.stream);
    await flushMicrotasks();
    lateTracks.forEach((track) => {
      expect(track.stop).toHaveBeenCalledOnce();
    });
  });

  it("releases start when cancelled during pending getUserMedia", async () => {
    const permission = deferred<MediaStream>();
    const harness = makeHarness({ getUserMedia: () => permission.promise });
    const starting = harness.controller.start();
    await flushMicrotasks();

    await expect(harness.controller.cancel()).resolves.toEqual({
      kind: "CANCELLED",
    });
    await expect(starting).resolves.toBe(false);

    permission.resolve(harness.stream);
    await flushMicrotasks();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
  });

  it("consumes a late getUserMedia rejection after cancellation", async () => {
    const permission = deferred<MediaStream>();
    const harness = makeHarness({ getUserMedia: () => permission.promise });
    const unhandled = vi.fn();
    window.addEventListener("unhandledrejection", unhandled);
    const starting = harness.controller.start();
    await flushMicrotasks();

    await expect(harness.controller.cancel()).resolves.toEqual({
      kind: "CANCELLED",
    });
    await expect(starting).resolves.toBe(false);

    permission.reject(new DOMException("late denial", "NotAllowedError"));
    await flushMicrotasks();
    expect(unhandled).not.toHaveBeenCalled();
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "CANCELLED",
    });
    window.removeEventListener("unhandledrejection", unhandled);
  });

  it("settles CANCELLED when stopped during pending AudioContext resume", async () => {
    const resume = deferred<void>();
    const harness = makeHarness({
      contextState: "suspended",
      resume: () => resume.promise,
    });
    const starting = harness.controller.start();
    await flushMicrotasks();

    expect(harness.context.resume).toHaveBeenCalledOnce();
    await expect(harness.controller.stop()).resolves.toEqual({ kind: "CANCELLED" });
    await expect(starting).resolves.toBe(false);

    resume.resolve();
    await flushMicrotasks();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
  });

  it("settles CANCELLED when stopped during pending addModule", async () => {
    const moduleLoad = deferred<void>();
    const harness = makeHarness({ addModule: () => moduleLoad.promise });
    const starting = harness.controller.start();
    await flushMicrotasks();

    expect(harness.context.audioWorklet.addModule).toHaveBeenCalledOnce();
    await expect(harness.controller.stop()).resolves.toEqual({ kind: "CANCELLED" });
    await expect(starting).resolves.toBe(false);

    moduleLoad.resolve();
    await flushMicrotasks();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
  });

  it("terminates pending getUserMedia at the setup deadline and disposes a late stream", async () => {
    const permission = deferred<MediaStream>();
    const harness = makeHarness({ getUserMedia: () => permission.promise });
    const settlement = vi.fn();
    void harness.controller.outcome.then(settlement);
    const starting = harness.controller.start();
    await flushMicrotasks();

    await vi.advanceTimersByTimeAsync(SETUP_DEADLINE_MS);

    await expect(starting).resolves.toBe(false);
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(settlement).toHaveBeenCalledOnce();
    expect(harness.createAudioContext).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);

    permission.resolve(harness.stream);
    await flushMicrotasks();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.createAudioContext).not.toHaveBeenCalled();
    expect(settlement).toHaveBeenCalledOnce();
  });

  it("cleans partially acquired resources when AudioContext resume exceeds setup deadline", async () => {
    const resume = deferred<void>();
    const harness = makeHarness({
      contextState: "suspended",
      resume: () => resume.promise,
    });
    const starting = harness.controller.start();
    await flushMicrotasks();
    expect(harness.context.resume).toHaveBeenCalledOnce();

    await vi.advanceTimersByTimeAsync(SETUP_DEADLINE_MS);

    await expect(starting).resolves.toBe(false);
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();
    expect(harness.createWorkletNode).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);

    resume.resolve();
    await flushMicrotasks();
    expect(harness.createWorkletNode).not.toHaveBeenCalled();
    expect(harness.source.connect).not.toHaveBeenCalled();
  });

  it("cannot resurrect capture when addModule resolves after setup deadline", async () => {
    const moduleLoad = deferred<void>();
    const harness = makeHarness({ addModule: () => moduleLoad.promise });
    const starting = harness.controller.start();
    await flushMicrotasks();
    expect(harness.context.audioWorklet.addModule).toHaveBeenCalledOnce();

    await vi.advanceTimersByTimeAsync(SETUP_DEADLINE_MS);

    await expect(starting).resolves.toBe(false);
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();
    expect(harness.createWorkletNode).not.toHaveBeenCalled();

    moduleLoad.resolve();
    await flushMicrotasks();
    expect(harness.createWorkletNode).not.toHaveBeenCalled();
    expect(harness.source.connect).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("lets cancellation win immediately before the setup deadline", async () => {
    const permission = deferred<MediaStream>();
    const harness = makeHarness({ getUserMedia: () => permission.promise });
    const starting = harness.controller.start();
    await flushMicrotasks();
    await vi.advanceTimersByTimeAsync(SETUP_DEADLINE_MS - 1);

    await expect(harness.controller.cancel()).resolves.toEqual({
      kind: "CANCELLED",
    });
    await vi.advanceTimersByTimeAsync(1);
    await expect(starting).resolves.toBe(false);
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "CANCELLED",
    });
    expect(vi.getTimerCount()).toBe(0);

    permission.resolve(harness.stream);
    await flushMicrotasks();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.createAudioContext).not.toHaveBeenCalled();
  });

  it("fails and cleans up when FINALISE acknowledgement is lost", async () => {
    const harness = makeHarness();
    await expect(harness.controller.start()).resolves.toBe(true);

    const stopping = harness.controller.stop();
    await vi.advanceTimersByTimeAsync(FINALISE_ACK_TIMEOUT_MS);

    await expect(stopping).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.close).toHaveBeenCalledOnce();
  });

  it("observes processorerror and releases capture resources", async () => {
    const harness = makeHarness();
    await harness.controller.start();

    harness.worklet.processorError();

    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(harness.worklet.disconnect).toHaveBeenCalledOnce();
    expect(harness.source.disconnect).toHaveBeenCalledOnce();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
  });

  it("observes a track ending while addModule is pending", async () => {
    const moduleLoad = deferred<void>();
    const harness = makeHarness({ addModule: () => moduleLoad.promise });
    const starting = harness.controller.start();
    await flushMicrotasks();

    harness.tracks[0]?.end();
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "DEVICE_LOST",
    });
    moduleLoad.resolve();

    await expect(starting).resolves.toBe(false);
    expect(harness.context.close).toHaveBeenCalledOnce();
  });

  it.each([null, 7, "bad", {}, { type: "UNKNOWN" }])(
    "fails closed for malformed worklet IPC %#",
    async (payload) => {
      const harness = makeHarness();
      await harness.controller.start();

      harness.worklet.portOwner.emit(payload);

      await expect(harness.controller.outcome).resolves.toEqual({
        kind: "FAILED",
        reason: "CAPTURE_FAILED",
      });
    },
  );

  it("rejects contradictory reachedLimit evidence", () => {
    expect(parseWorkletCaptureMessage(
      completeMessage(MAX_CAPTURE_FRAMES - 1, true),
    )).toBeNull();
    expect(parseWorkletCaptureMessage(
      completeMessage(MAX_CAPTURE_FRAMES, false),
    )).toBeNull();
  });

  it("rejects malformed CAPTURE_COMPLETE evidence", () => {
    const validBuffer = new ArrayBuffer(MAX_RETAINED_FLOAT32_BYTES);
    const message = (overrides: Record<string, unknown>) => ({
      type: "CAPTURE_COMPLETE",
      buffer: validBuffer,
      frameCount: 1,
      reachedLimit: false,
      ...overrides,
    });

    expect(parseWorkletCaptureMessage(message({
      buffer: new ArrayBuffer(MAX_RETAINED_FLOAT32_BYTES - 4),
    }))).toBeNull();
    expect(parseWorkletCaptureMessage(message({ frameCount: -1 }))).toBeNull();
    expect(parseWorkletCaptureMessage(message({
      frameCount: MAX_CAPTURE_FRAMES + 1,
    }))).toBeNull();
    expect(parseWorkletCaptureMessage(message({ frameCount: 1.5 }))).toBeNull();
    expect(parseWorkletCaptureMessage(message({ reachedLimit: "false" }))).toBeNull();
  });

  it("rejects unsolicited partial completion", async () => {
    const harness = makeHarness();
    await harness.controller.start();

    harness.worklet.portOwner.emit(completeMessage(1, false));

    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
  });

  it("accepts partial completion authorised by explicit stop", async () => {
    const harness = makeHarness();
    await harness.controller.start();

    const stopping = harness.controller.stop();
    harness.worklet.portOwner.emit(completeMessage(1, false));

    await expect(stopping).resolves.toMatchObject({
      kind: "CAPTURED",
      frameCount: 1,
    });
  });

  it("autonomously accepts exact-limit worklet completion", async () => {
    const harness = makeHarness();
    await harness.controller.start();

    harness.worklet.portOwner.emit(
      completeMessage(MAX_CAPTURE_FRAMES, true),
    );

    await expect(harness.controller.outcome).resolves.toMatchObject({
      kind: "CAPTURED",
      frameCount: MAX_CAPTURE_FRAMES,
    });
  });

  it("settles after the bounded close deadline when close never resolves", async () => {
    const close = deferred<void>();
    const harness = makeHarness({ close: () => close.promise });
    await harness.controller.start();

    const cancelling = harness.controller.cancel();
    await vi.advanceTimersByTimeAsync(CONTEXT_CLOSE_TIMEOUT_MS - 1);
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(1);

    await expect(cancelling).resolves.toEqual({ kind: "CANCELLED" });
  });

  it("makes the recording deadline own finalisation and bounded cleanup", async () => {
    const automaticFinalise = vi.fn();
    const harness = makeHarness({ automaticFinalise });
    await harness.controller.start();
    let settled = false;
    void harness.controller.outcome.then(() => {
      settled = true;
    });

    expect(RECORDING_DEADLINE_MS).toBe(MAX_CAPTURE_SECONDS * 1000 + 1_000);
    await vi.advanceTimersByTimeAsync(RECORDING_DEADLINE_MS);

    expect(automaticFinalise).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledWith({
      type: "FINALISE",
    });
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(FINALISE_ACK_TIMEOUT_MS - 1);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);

    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.source.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.close).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("contains a throwing presentation callback after controller finalisation starts", async () => {
    const automaticFinalise = vi.fn(() => {
      throw new Error("UI callback failed");
    });
    const harness = makeHarness({ automaticFinalise });
    await harness.controller.start();

    await vi.advanceTimersByTimeAsync(RECORDING_DEADLINE_MS);

    expect(automaticFinalise).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledWith({
      type: "FINALISE",
    });
    harness.worklet.portOwner.emit(completeMessage(1, false));
    await expect(harness.controller.outcome).resolves.toMatchObject({
      kind: "CAPTURED",
      frameCount: 1,
    });
  });

  it("suppresses automatic finalising projection after synchronous FINALISE failure", async () => {
    const automaticFinalise = vi.fn();
    const harness = makeHarness({ automaticFinalise });
    const unhandled = vi.fn();
    window.addEventListener("unhandledrejection", unhandled);
    await harness.controller.start();
    const recordingDeadline = harness.setTimer.mock.calls.find(
      ([, delayMs]) => delayMs === RECORDING_DEADLINE_MS,
    );
    if (!recordingDeadline) throw new Error("recording deadline was not armed");
    const staleDeadlineCallback = recordingDeadline[0];
    const settlement = vi.fn();
    void harness.controller.outcome.then(settlement);
    harness.worklet.portOwner.postMessage.mockImplementationOnce(() => {
      throw new Error("FINALISE transport failed");
    });

    await vi.advanceTimersByTimeAsync(RECORDING_DEADLINE_MS);

    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledWith({
      type: "FINALISE",
    });
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(automaticFinalise).not.toHaveBeenCalled();
    expect(settlement).toHaveBeenCalledOnce();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.source.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.close).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();

    staleDeadlineCallback();
    await flushMicrotasks();
    expect(automaticFinalise).not.toHaveBeenCalled();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledOnce();
    expect(settlement).toHaveBeenCalledOnce();
    expect(unhandled).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    window.removeEventListener("unhandledrejection", unhandled);
  });

  it("encodes only frames owned at the recording deadline without padding", async () => {
    const harness = makeHarness();
    await harness.controller.start();
    const settlement = vi.fn();
    void harness.controller.outcome.then(settlement);

    await vi.advanceTimersByTimeAsync(RECORDING_DEADLINE_MS);
    harness.worklet.portOwner.emit(completeMessage(3, false));

    const outcome = await harness.controller.outcome;
    expect(outcome).toMatchObject({ kind: "CAPTURED", frameCount: 3 });
    if (outcome.kind !== "CAPTURED") throw new Error("expected captured audio");
    expect(outcome.file.size).toBe(44 + 3 * Int16Array.BYTES_PER_ELEMENT);
    expect(outcome.file.size).toBeLessThanOrEqual(44 + MAX_CAPTURE_FRAMES * 2);
    expect(settlement).toHaveBeenCalledOnce();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.source.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.close).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();

    harness.worklet.portOwner.emit(completeMessage(4, false));
    harness.tracks[0]?.end();
    await flushMicrotasks();
    expect(settlement).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("lets manual stop clear the recording deadline without duplicate finalisation", async () => {
    const automaticFinalise = vi.fn();
    const harness = makeHarness({ automaticFinalise });
    await harness.controller.start();
    const settlement = vi.fn();
    void harness.controller.outcome.then(settlement);

    const stopping = harness.controller.stop();
    harness.worklet.portOwner.emit(completeMessage(2, false));
    await expect(stopping).resolves.toMatchObject({
      kind: "CAPTURED",
      frameCount: 2,
    });
    await vi.advanceTimersByTimeAsync(RECORDING_DEADLINE_MS);

    expect(automaticFinalise).not.toHaveBeenCalled();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledTimes(1);
    expect(settlement).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("ignores a captured recording deadline callback after manual stop", async () => {
    const automaticFinalise = vi.fn();
    const harness = makeHarness({ automaticFinalise });
    await harness.controller.start();
    const recordingDeadline = harness.setTimer.mock.calls.find(
      ([, delayMs]) => delayMs === RECORDING_DEADLINE_MS,
    );
    if (!recordingDeadline) throw new Error("recording deadline was not armed");
    const staleDeadlineCallback = recordingDeadline[0];
    const settlement = vi.fn();
    void harness.controller.outcome.then(settlement);

    const stopping = harness.controller.stop();
    harness.worklet.portOwner.emit(completeMessage(2, false));
    await expect(stopping).resolves.toMatchObject({
      kind: "CAPTURED",
      frameCount: 2,
    });

    staleDeadlineCallback();
    await flushMicrotasks();
    expect(automaticFinalise).not.toHaveBeenCalled();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledTimes(1);
    expect(settlement).toHaveBeenCalledOnce();
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.source.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.disconnect).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.close).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("lets exact-frame completion win once after the recording deadline", async () => {
    const automaticFinalise = vi.fn();
    const harness = makeHarness({ automaticFinalise });
    await harness.controller.start();
    const settlement = vi.fn();
    void harness.controller.outcome.then(settlement);

    await vi.advanceTimersByTimeAsync(RECORDING_DEADLINE_MS);
    harness.worklet.portOwner.emit(
      completeMessage(MAX_CAPTURE_FRAMES, true),
    );

    const outcome = await harness.controller.outcome;
    expect(outcome).toMatchObject({
      kind: "CAPTURED",
      frameCount: MAX_CAPTURE_FRAMES,
    });
    if (outcome.kind !== "CAPTURED") throw new Error("expected captured audio");
    expect(outcome.file.size).toBe(44 + MAX_CAPTURE_FRAMES * 2);
    await vi.advanceTimersByTimeAsync(FINALISE_ACK_TIMEOUT_MS);
    expect(automaticFinalise).toHaveBeenCalledOnce();
    expect(harness.worklet.portOwner.postMessage).toHaveBeenCalledTimes(1);
    expect(settlement).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("makes repeated stop and cancel calls idempotent", async () => {
    const harness = makeHarness();
    await harness.controller.start();

    const firstStop = harness.controller.stop();
    const secondStop = harness.controller.stop();
    const firstCancel = harness.controller.cancel();
    const secondCancel = harness.controller.cancel();

    await expect(firstStop).resolves.toEqual({ kind: "CANCELLED" });
    await expect(secondStop).resolves.toEqual({ kind: "CANCELLED" });
    await expect(firstCancel).resolves.toEqual({ kind: "CANCELLED" });
    await expect(secondCancel).resolves.toEqual({ kind: "CANCELLED" });
    expect(harness.tracks[0]?.stop).toHaveBeenCalledOnce();
    expect(harness.context.close).toHaveBeenCalledOnce();
  });

  it("lets device loss win deterministically before finalise acknowledgement", async () => {
    const harness = makeHarness();
    await harness.controller.start();
    const stopping = harness.controller.stop();

    harness.tracks[0]?.end();
    harness.worklet.portOwner.emit(completeMessage(1, false));

    await expect(stopping).resolves.toEqual({
      kind: "FAILED",
      reason: "DEVICE_LOST",
    });
  });

  it("rejects zero, multiple, and already-ended audio tracks", async () => {
    for (const tracks of [[], [new FakeTrack(), new FakeTrack()]]) {
      const harness = makeHarness({ tracks });
      await expect(harness.controller.start()).resolves.toBe(false);
      await expect(harness.controller.outcome).resolves.toEqual({
        kind: "FAILED",
        reason: "DEVICE_UNAVAILABLE",
      });
    }

    const ended = new FakeTrack();
    ended.readyState = "ended";
    const harness = makeHarness({ tracks: [ended] });
    await expect(harness.controller.start()).resolves.toBe(false);
    await expect(harness.controller.outcome).resolves.toEqual({
      kind: "FAILED",
      reason: "DEVICE_UNAVAILABLE",
    });
  });

});

describe("microphone processor IPC and bounded PCM", () => {
  it.each([null, 0, "FINALISE", {}, { type: "UNKNOWN" }])(
    "rejects malformed processor control payload %#",
    (payload) => {
      expect(parseCaptureProcessorMessage(payload)).toBeNull();
    },
  );

  it("accepts only FINALISE and CANCEL processor controls", () => {
    expect(parseCaptureProcessorMessage({ type: "FINALISE" })).toEqual({
      type: "FINALISE",
    });
    expect(parseCaptureProcessorMessage({ type: "CANCEL" })).toEqual({
      type: "CANCEL",
    });
  });

  it("keeps a zero-length channel quantum non-terminal", () => {
    const result = appendInputFrames(
      new Float32Array(MAX_CAPTURE_FRAMES),
      0,
      [new Float32Array(0)],
    );

    expect(result).toEqual({
      kind: "APPENDED",
      nextFrame: 0,
      reachedLimit: false,
    });
  });

  it("copies mono and deterministically averages stereo", () => {
    const mono = new Float32Array(MAX_CAPTURE_FRAMES);
    const monoResult = appendInputFrames(mono, 0, [
      new Float32Array([0.25, -0.5]),
    ]);
    expect(monoResult).toMatchObject({ kind: "APPENDED", nextFrame: 2 });
    expect(Array.from(mono.slice(0, 2))).toEqual([0.25, -0.5]);

    const stereo = new Float32Array(MAX_CAPTURE_FRAMES);
    const stereoResult = appendInputFrames(stereo, 0, [
      new Float32Array([1, -1]),
      new Float32Array([-1, 0.5]),
    ]);
    expect(stereoResult).toMatchObject({ kind: "APPENDED", nextFrame: 2 });
    expect(Array.from(stereo.slice(0, 2))).toEqual([0, -0.25]);
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])(
    "rejects non-finite PCM %s",
    (sample) => {
      const result = appendInputFrames(
        new Float32Array(MAX_CAPTURE_FRAMES),
        0,
        [new Float32Array([sample])],
      );
      expect(result).toEqual({ kind: "FAILED", reason: "CAPTURE_FAILED" });
    },
  );

  it("rejects zero and more than two channels", () => {
    const target = new Float32Array(MAX_CAPTURE_FRAMES);
    expect(appendInputFrames(target, 0, [])).toEqual({
      kind: "FAILED",
      reason: "CAPTURE_FAILED",
    });
    expect(appendInputFrames(target, 0, [
      new Float32Array(1),
      new Float32Array(1),
      new Float32Array(1),
    ])).toEqual({ kind: "FAILED", reason: "CAPTURE_FAILED" });
  });

  it("rejects mismatched stereo channel lengths", () => {
    expect(appendInputFrames(
      new Float32Array(MAX_CAPTURE_FRAMES),
      0,
      [new Float32Array(2), new Float32Array(1)],
    )).toEqual({ kind: "FAILED", reason: "CAPTURE_FAILED" });
  });

  it.each([
    -1,
    MAX_CAPTURE_FRAMES + 1,
    0.5,
    Number.MAX_SAFE_INTEGER + 1,
  ])("rejects invalid currentFrame %s", (currentFrame) => {
    expect(appendInputFrames(
      new Float32Array(MAX_CAPTURE_FRAMES),
      currentFrame,
      [new Float32Array(1)],
    )).toEqual({ kind: "FAILED", reason: "CAPTURE_FAILED" });
  });

  it("rejects a target buffer with the wrong fixed capacity", () => {
    expect(appendInputFrames(
      new Float32Array(MAX_CAPTURE_FRAMES - 1),
      0,
      [new Float32Array(1)],
    )).toEqual({ kind: "FAILED", reason: "CAPTURE_FAILED" });
  });

  it("finalises exactly at 240000 frames and rejects later PCM", () => {
    const target = new Float32Array(MAX_CAPTURE_FRAMES);
    const boundary = appendInputFrames(
      target,
      MAX_CAPTURE_FRAMES - 1,
      new Array<Float32Array>(1).fill(new Float32Array([0.5, 0.75])),
    );
    expect(boundary).toEqual({
      kind: "APPENDED",
      nextFrame: MAX_CAPTURE_FRAMES,
      reachedLimit: true,
    });
    expect(target[MAX_CAPTURE_FRAMES - 1]).toBe(0.5);

    expect(appendInputFrames(
      target,
      MAX_CAPTURE_FRAMES,
      [new Float32Array([0.25])],
    )).toEqual({ kind: "FAILED", reason: "CAPTURE_TOO_LONG" });
  });
});

describe("deterministic PCM16 WAV encoding", () => {
  it("uses the frozen exact and half-step quantisation rules", () => {
    expect(quantizePcm16(-1)).toBe(-32_768);
    expect(quantizePcm16(0)).toBe(0);
    expect(quantizePcm16(1)).toBe(32_767);
    expect(quantizePcm16(-0.5 / 32_768)).toBe(-1);
    expect(quantizePcm16(0.5 / 32_767)).toBe(1);
  });

  it("writes deterministic canonical mono 16 kHz PCM WAV bytes", () => {
    const input = new Float32Array([-1, 0, 1]);
    const first = encodePcm16Wav(input);
    const second = encodePcm16Wav(input);
    const view = new DataView(first.buffer, first.byteOffset, first.byteLength);

    expect(Array.from(first)).toEqual(Array.from(second));
    expect(first.byteLength).toBe(50);
    expect(new TextDecoder().decode(first.slice(0, 4))).toBe("RIFF");
    expect(new TextDecoder().decode(first.slice(8, 12))).toBe("WAVE");
    expect(view.getUint16(20, true)).toBe(1);
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(16_000);
    expect(view.getUint32(28, true)).toBe(32_000);
    expect(view.getUint16(32, true)).toBe(2);
    expect(view.getUint16(34, true)).toBe(16);
    expect(view.getUint32(40, true)).toBe(6);
    expect(view.getInt16(44, true)).toBe(-32_768);
    expect(view.getInt16(46, true)).toBe(0);
    expect(view.getInt16(48, true)).toBe(32_767);
  });

  it("rejects empty, oversized, and non-finite encoding input", () => {
    expect(() => encodePcm16Wav(new Float32Array(0))).toThrow("CAPTURE_EMPTY");
    expect(() => encodePcm16Wav(
      new Float32Array(MAX_CAPTURE_FRAMES + 1),
    )).toThrow("CAPTURE_TOO_LONG");
    expect(() => encodePcm16Wav(new Float32Array([Number.NaN]))).toThrow(
      "ENCODING_FAILED",
    );
  });

  it("retains the exact fixed cross-thread buffer size", () => {
    expect(MAX_RETAINED_FLOAT32_BYTES).toBe(960_000);
  });
});
