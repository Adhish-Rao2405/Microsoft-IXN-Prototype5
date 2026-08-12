import {
  ContractValidationError,
  decodeDemoManifest,
  decodeDemoStatus,
  decodeGovernanceResult,
  decodeRecordedTranscription,
} from "./runtimeContracts";
import type {
  DemoManifest,
  DemoStatus,
  HybridGovernanceResult,
  RecordedTranscription,
  TypedCommandPayload,
  VoiceCommandPayload,
} from "./types";

export class ApiRequestError extends Error {
  readonly code = "HTTP_ERROR";
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export class ApiTransportError extends Error {
  readonly code = "NETWORK_FAILURE";

  constructor() {
    super("NETWORK_FAILURE");
    this.name = "ApiTransportError";
  }
}

async function request(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiTransportError();
  }
}

async function responseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    if (response.ok) {
      throw new ContractValidationError("response: invalid JSON");
    }
    return null;
  }
}

function boundedHttpDetail(value: unknown, status: number): string {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const body = value as Record<string, unknown>;
    if (body.detail !== null && typeof body.detail === "object" && !Array.isArray(body.detail)) {
      const code = (body.detail as Record<string, unknown>).code;
      if (typeof code === "string" && /^[A-Z0-9_]{1,100}$/.test(code)) {
        return code;
      }
    }
    if (typeof body.detail === "string" && /^[A-Z0-9_]{1,100}$/.test(body.detail)) {
      return body.detail;
    }
  }
  return `HTTP_${status}`;
}

async function validatedResponse<T>(
  response: Response,
  decode: (value: unknown) => T,
): Promise<T> {
  const body = await responseJson(response);
  if (!response.ok) {
    throw new ApiRequestError(response.status, boundedHttpDetail(body, response.status));
  }
  return decode(body);
}

export async function getDemoManifest(
  signal?: AbortSignal,
): Promise<DemoManifest> {
  const response = await request("/api/v1/demo/manifest", { signal });
  return validatedResponse(response, decodeDemoManifest);
}

export async function getDemoStatus(
  signal?: AbortSignal,
): Promise<DemoStatus> {
  const response = await request("/api/v1/status", { signal });
  return validatedResponse(response, decodeDemoStatus);
}

export async function submitTypedCommand(
  payload: TypedCommandPayload,
  signal?: AbortSignal,
): Promise<HybridGovernanceResult> {
  const response = await request("/api/v1/governance/typed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  return validatedResponse(response, decodeGovernanceResult);
}

export async function transcribeRecordedAudio(
  audio: File,
  signal?: AbortSignal,
): Promise<RecordedTranscription> {
  const response = await request("/api/v1/speech/recorded", {
    method: "POST",
    headers: {
      "Content-Type": audio.type || "application/octet-stream",
      "X-Audio-Filename": audio.name,
    },
    body: audio,
    signal,
  });
  return validatedResponse(response, decodeRecordedTranscription);
}

export async function submitVoiceCommand(
  payload: VoiceCommandPayload,
  signal?: AbortSignal,
): Promise<HybridGovernanceResult> {
  const response = await request("/api/v1/governance/voice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  return validatedResponse(response, decodeGovernanceResult);
}
