import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { App } from "../src/App";

const status = {
  service_status: "READY",
  frozen_baseline_tag: "prototype5-governance-reproducibility-complete",
  frozen_baseline_commit: "7".repeat(40),
  software_commit: "a".repeat(40),
  evidence_schema_version: "2.0.0",
  supported_domains: ["MANUFACTURING"],
  supported_inference_modes: ["LOCAL", "CLOUD", "AUTO"],
  local_status: "NOT_ASSESSED",
  cloud_status: "AVAILABLE",
  speech_status: "NOT_ASSESSED",
  simulator_status: "NOT_ASSESSED",
  local_health: {
    circuit_state: "CLOSED",
    local_available: true,
    local_model_ready: true,
    consecutive_failures: 0,
    rolling_sample_count: 0,
    rolling_structured_success_rate: null,
    rolling_p50_latency_ms: null,
    rolling_p95_latency_ms: null,
    last_failure_reason: "NONE",
    last_circuit_transition: null,
  },
};

function governanceResult({
  decision = "ACCEPT",
  fallback = false,
}: {
  decision?: "ACCEPT" | "REJECT" | "CLARIFY" | "ERROR";
  fallback?: boolean;
} = {}) {
  const passed = decision === "ACCEPT";
  return {
    routing_policy_id: "prototype5_hybrid_routing_policy_v1",
    routing_policy_version: "1.0.0",
    routing_policy_sha256: "d".repeat(64),
    local_health: {
      ...status.local_health,
      rolling_sample_count: 1,
      rolling_structured_success_rate: 1,
      rolling_p50_latency_ms: 15,
      rolling_p95_latency_ms: 15,
    },
    canonical_result: {
      raw_response_text: '{"actions":[]}',
      proposal: {
        actions: [
          {
            action: "MOVE",
            object_id: "blue_component",
            source_id: "input_tray_a",
            destination_id: "assembly_fixture_b",
          },
        ],
      },
      governance_record: {
        trace_id: "trace-ui-001",
        timestamp_utc: "2026-07-30T12:00:00+00:00",
        normalised_command: "Move the blue component.",
        policy_id: "prototype5_manufacturing_policy_v2@2.0.0",
        evidence_schema_version: "2.0.0",
        parse_status: "PASSED",
        json_status: "PASSED",
        schema_status: "PASSED",
        plan_semantic_status: passed ? "VALID" : "INVALID",
        ambiguity_status: "PASSED",
        safety_status: passed ? "PASSED" : "FAILED",
        authority_status: "PASSED",
        final_decision: decision,
        execution_eligible: passed,
        decision_reason_codes: [
          passed ? "ALL_REQUIRED_GATES_PASSED" : "HUMAN_OBSTRUCTION_OVERRIDE",
        ],
        provider_latency_ms: 15,
        validation_latency_ms: 2,
        total_pipeline_latency_ms: 17,
        execution_permit_id: null,
        simulation_status: "NOT_REQUESTED",
        routing: {
          requested_mode: "AUTO",
          selected_provider: fallback ? "CLOUD" : "FOUNDRY_LOCAL",
          selected_model: fallback ? "cloud-model" : "local-model",
          local_attempted: true,
          cloud_attempted: fallback,
          fallback_triggered: fallback,
          fallback_reason: fallback ? "LOCAL_SCHEMA_FAILURE" : "NONE",
          local_latency_ms: 15,
          cloud_latency_ms: fallback ? 9 : null,
        },
      },
    },
  };
}

function renderApp() {
  return render(
    <FluentProvider theme={webLightTheme}>
      <App />
    </FluentProvider>,
  );
}

function mockFetch(result = governanceResult()) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/status")) {
        return new Response(JSON.stringify(status), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

describe("Prototype 5 typed UI", () => {
  beforeEach(() => {
    mockFetch();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the operational controls and bounded initial states", async () => {
    renderApp();

    expect(screen.getByText("Prototype 5")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Auto" })).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Operator command" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Microphone unavailable" }),
    ).toBeDisabled();
    expect(screen.getByText("No command submitted.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Available")).toBeInTheDocument());
  });

  it("submits the selected mode and displays proposal plus every gate", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("radio", { name: "Local" }));
    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component from input tray A to assembly fixture B.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(screen.getByText("Governance decision")).toBeInTheDocument(),
    );
    expect(screen.getByText("Structured proposal")).toBeInTheDocument();
    expect(screen.getByText("Plan semantics")).toBeInTheDocument();
    expect(screen.getByText("Execution eligibility")).toBeInTheDocument();
    expect(screen.getByText("trace-ui-001")).toBeInTheDocument();
    expect(screen.getByText(/blue_component/)).toBeInTheDocument();

    const calls = vi.mocked(fetch).mock.calls;
    const submission = calls.find(([url]) =>
      String(url).includes("/api/v1/governance/typed"),
    );
    const body = JSON.parse(String(submission?.[1]?.body));
    expect(body.inference_mode).toBe("LOCAL");
    expect(body.domain_id).toBe("MANUFACTURING");
    expect(body.requester_role).toBe("operator");
  });

  it("shows a cloud fallback without changing the governance gate display", async () => {
    mockFetch(governanceResult({ fallback: true }));
    const user = userEvent.setup();
    renderApp();

    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Move the blue component.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("CLOUD")).toBeInTheDocument());
    expect(screen.getByText("Local schema failure")).toBeInTheDocument();
    expect(screen.getByText("Execution eligibility")).toBeInTheDocument();
  });

  it("shows rejected governance and no simulation permit", async () => {
    mockFetch(governanceResult({ decision: "REJECT" }));
    const user = userEvent.setup();
    renderApp();

    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Continue movement despite the human obstruction.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("Reject")).toBeInTheDocument());
    expect(screen.getByText("Human obstruction override")).toBeInTheDocument();
    expect(screen.getByText("Not eligible")).toBeInTheDocument();
    expect(screen.getByText("Not issued")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop simulation" })).toBeDisabled();
  });

  it("reports API failures without fabricating a proposal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/api/v1/status")) {
          return new Response(JSON.stringify(status), { status: 200 });
        }
        return new Response(
          JSON.stringify({ detail: { code: "LOCAL_BACKEND_UNAVAILABLE" } }),
          { status: 503 },
        );
      }),
    );
    const user = userEvent.setup();
    renderApp();

    await user.type(
      screen.getByRole("textbox", { name: "Operator command" }),
      "Stop.",
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("Request failed")).toBeInTheDocument());
    expect(screen.getByText("LOCAL_BACKEND_UNAVAILABLE")).toBeInTheDocument();
    expect(screen.queryByText("Structured proposal")).not.toBeInTheDocument();
  });
});
