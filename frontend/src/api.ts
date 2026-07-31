import type {
  DemoStatus,
  HybridGovernanceResult,
  TypedCommandPayload,
} from "./types";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      body?.detail?.code ?? body?.detail ?? `HTTP_${response.status}`;
    throw new Error(String(detail));
  }
  return (await response.json()) as T;
}

export async function getDemoStatus(
  signal?: AbortSignal,
): Promise<DemoStatus> {
  const response = await fetch("/api/v1/status", { signal });
  return readJson<DemoStatus>(response);
}

export async function submitTypedCommand(
  payload: TypedCommandPayload,
): Promise<HybridGovernanceResult> {
  const response = await fetch("/api/v1/governance/typed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<HybridGovernanceResult>(response);
}
