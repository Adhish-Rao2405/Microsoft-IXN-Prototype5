import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Badge,
  Button,
  Dropdown,
  Field,
  Option,
  Radio,
  RadioGroup,
  Spinner,
  Textarea,
  Tooltip,
} from "@fluentui/react-components";
import {
  ArrowDownload24Regular,
  Bot24Regular,
  Cloud24Regular,
  Desktop24Regular,
  Mic24Regular,
  Send24Regular,
  ShieldCheckmark24Regular,
  Stop24Regular,
} from "@fluentui/react-icons";
import { getDemoStatus, submitTypedCommand } from "./api";
import type {
  AvailabilityStatus,
  DemoStatus,
  DomainId,
  GateDisplayStatus,
  HybridGovernanceResult,
  InferenceMode,
} from "./types";

const gateDefinitions = [
  ["Parse", "parse_status"],
  ["JSON", "json_status"],
  ["Schema", "schema_status"],
  ["Plan semantics", "plan_semantic_status"],
  ["Ambiguity", "ambiguity_status"],
  ["Safety", "safety_status"],
  ["Authority", "authority_status"],
] as const;

function availabilityLabel(status: AvailabilityStatus | undefined): string {
  if (status === "AVAILABLE") return "Available";
  if (status === "UNAVAILABLE") return "Unavailable";
  return "Not assessed";
}

function statusTone(status: string): "success" | "danger" | "warning" | "informative" | "subtle" {
  if (status === "PASSED" || status === "VALID" || status === "ACCEPT" || status === "AVAILABLE") {
    return "success";
  }
  if (status === "FAILED" || status === "INVALID" || status === "REJECT" || status === "ERROR" || status === "UNAVAILABLE") {
    return "danger";
  }
  if (status === "CLARIFY" || status === "HALF_OPEN") return "warning";
  if (status === "NOT_ASSESSABLE" || status.startsWith("NOT_ASSESSABLE")) {
    return "warning";
  }
  return "subtle";
}

function formatStatus(status: GateDisplayStatus): string {
  return status.replaceAll("_", " ").toLowerCase().replace(/^\w/, (value) => value.toUpperCase());
}

function formatLatency(value: number | null | undefined): string {
  return value == null ? "Not recorded" : `${value.toFixed(1)} ms`;
}

export function App() {
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [mode, setMode] = useState<InferenceMode>("AUTO");
  const [domain, setDomain] = useState<DomainId>("MANUFACTURING");
  const [requesterRole, setRequesterRole] = useState<
    "operator" | "observer" | "supervisor"
  >("operator");
  const [result, setResult] = useState<HybridGovernanceResult | null>(null);
  const [submittedCommand, setSubmittedCommand] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getDemoStatus(controller.signal)
      .then(setStatus)
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") {
          setStatusError((error as Error).message);
        }
      });
    return () => controller.abort();
  }, []);

  const record = result?.canonical_result.governance_record ?? null;
  const proposalText = useMemo(
    () =>
      result?.canonical_result.proposal
        ? JSON.stringify(result.canonical_result.proposal, null, 2)
        : "No schema-valid proposal available.",
    [result],
  );

  async function handleSubmit() {
    const trimmed = command.trim();
    if (!trimmed || pending) return;
    setPending(true);
    setRequestError(null);
    setSubmittedCommand(trimmed);
    try {
      const nextResult = await submitTypedCommand({
        command: trimmed,
        inference_mode: mode,
        domain_id: domain,
        requester_role: requesterRole,
      });
      setResult(nextResult);
    } catch (error) {
      setResult(null);
      setRequestError((error as Error).message);
    } finally {
      setPending(false);
    }
  }

  function downloadTrace() {
    if (!result || !record) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${record.trace_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <ShieldCheckmark24Regular aria-hidden="true" />
          <div>
            <div className="product-name">Prototype 5</div>
            <div className="product-subtitle">Zero-Trust Robotics</div>
          </div>
        </div>
        <div className="baseline">
          <span>Baseline</span>
          <code
            className="baseline-tag"
            title={status?.frozen_baseline_tag ?? "Loading"}
          >
            {status?.frozen_baseline_tag ?? "Loading"}
          </code>
          <code
            className="baseline-commit"
            title={status?.frozen_baseline_commit ?? "Loading"}
          >
            {status?.frozen_baseline_commit?.slice(0, 8) ?? "Loading"}
          </code>
        </div>
      </header>

      <section className="status-strip" aria-label="Runtime status">
        <RuntimeStatus
          icon={<Desktop24Regular aria-hidden="true" />}
          label="Local"
          status={status?.local_status}
        />
        <RuntimeStatus
          icon={<Cloud24Regular aria-hidden="true" />}
          label="Cloud"
          status={status?.cloud_status}
        />
        <RuntimeStatus
          icon={<Mic24Regular aria-hidden="true" />}
          label="Speech"
          status={status?.speech_status}
        />
        <RuntimeStatus
          icon={<Bot24Regular aria-hidden="true" />}
          label="Simulator"
          status={status?.simulator_status}
        />
        {statusError && (
          <div className="status-error" role="status">
            Status unavailable
          </div>
        )}
      </section>

      <main className="app-layout">
        <section className="command-workspace" aria-label="Command workspace">
          <div className="workspace-toolbar">
            <Field label="Domain" size="small">
              <Dropdown
                aria-label="Domain"
                value={
                  domain === "MANUFACTURING"
                    ? "Manufacturing"
                    : "Healthcare (synthetic)"
                }
                selectedOptions={[domain]}
                onOptionSelect={(_, data) => setDomain(data.optionValue as DomainId)}
              >
                <Option value="MANUFACTURING">Manufacturing</Option>
                <Option value="HEALTHCARE_SYNTHETIC" disabled>
                  Healthcare (synthetic)
                </Option>
              </Dropdown>
            </Field>
            <Field label="Requester role" size="small">
              <Dropdown
                aria-label="Requester role"
                value={requesterRole[0].toUpperCase() + requesterRole.slice(1)}
                selectedOptions={[requesterRole]}
                onOptionSelect={(_, data) =>
                  setRequesterRole(
                    data.optionValue as "operator" | "observer" | "supervisor",
                  )
                }
              >
                <Option value="operator">Operator</Option>
                <Option value="observer">Observer</Option>
                <Option value="supervisor">Supervisor</Option>
              </Dropdown>
            </Field>
            <Field label="Inference" size="small">
              <RadioGroup
                layout="horizontal"
                value={mode}
                onChange={(_, data) => setMode(data.value as InferenceMode)}
                aria-label="Inference mode"
              >
                <Radio value="LOCAL" label="Local" />
                <Radio value="CLOUD" label="Cloud" />
                <Radio value="AUTO" label="Auto" />
              </RadioGroup>
            </Field>
          </div>

          <div className="conversation" aria-live="polite">
            {!submittedCommand && !pending && (
              <div className="empty-state">
                <Bot24Regular aria-hidden="true" />
                <span>No command submitted.</span>
              </div>
            )}
            {submittedCommand && (
              <div className="message-row operator-message">
                <span className="message-label">Operator</span>
                <p>{submittedCommand}</p>
              </div>
            )}
            {pending && (
              <div className="processing-row" role="status">
                <Spinner size="small" label="Evaluating proposal" />
              </div>
            )}
            {requestError && (
              <div className="request-error" role="alert">
                <strong>Request failed</strong>
                <span>{requestError}</span>
              </div>
            )}
            {record && (
              <div className="message-row system-message">
                <div className="decision-line">
                  <span className="message-label">Governance decision</span>
                  <Badge
                    appearance="tint"
                    color={statusTone(record.final_decision)}
                  >
                    {formatStatus(record.final_decision)}
                  </Badge>
                </div>
                <p>{record.decision_reason_codes.map(formatStatus).join(" · ")}</p>
              </div>
            )}
            {result && (
              <section className="proposal-output" aria-labelledby="proposal-heading">
                <div className="section-heading-row">
                  <h2 id="proposal-heading">Structured proposal</h2>
                  <Badge appearance="outline">
                    {record?.schema_status === "PASSED"
                      ? "Schema valid"
                      : "Unavailable"}
                  </Badge>
                </div>
                <pre>{proposalText}</pre>
              </section>
            )}
          </div>

          <div className="composer">
            <Field label="Operator command">
              <Textarea
                value={command}
                onChange={(_, data) => setCommand(data.value)}
                placeholder="Enter a bounded manufacturing command"
                resize="vertical"
                disabled={pending}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    void handleSubmit();
                  }
                }}
              />
            </Field>
            <div className="composer-actions">
              <Tooltip content="Microphone unavailable" relationship="label">
                <Button
                  appearance="subtle"
                  icon={<Mic24Regular />}
                  aria-label="Microphone unavailable"
                  disabled
                />
              </Tooltip>
              <Button
                appearance="primary"
                icon={<Send24Regular />}
                disabled={!command.trim() || pending}
                onClick={() => void handleSubmit()}
              >
                Submit
              </Button>
            </div>
          </div>
        </section>

        <aside className="inspector" aria-label="Governance inspector">
          <InspectorSection title="Governance gates">
            <div className="gate-list">
              {gateDefinitions.map(([label, field]) => {
                const gateStatus = record?.[field] ?? "NOT_EVALUATED";
                return (
                  <div className="gate-row" key={field}>
                    <span>{label}</span>
                    <Badge appearance="tint" color={statusTone(gateStatus)}>
                      {formatStatus(gateStatus)}
                    </Badge>
                  </div>
                );
              })}
              <div className="gate-row execution-row">
                <span>Execution eligibility</span>
                <Badge
                  appearance="filled"
                  color={record?.execution_eligible ? "success" : "subtle"}
                >
                  {record?.execution_eligible ? "Eligible" : "Not eligible"}
                </Badge>
              </div>
            </div>
          </InspectorSection>

          <InspectorSection title="Routing">
            <DefinitionRow label="Requested" value={record?.routing.requested_mode ?? mode} />
            <DefinitionRow
              label="Selected"
              value={record?.routing.selected_provider ?? "Not selected"}
            />
            <DefinitionRow
              label="Model"
              value={record?.routing.selected_model ?? "Not selected"}
            />
            <DefinitionRow
              label="Fallback"
              value={
                record?.routing.fallback_triggered
                  ? formatStatus(record.routing.fallback_reason)
                  : "Not triggered"
              }
            />
            <DefinitionRow
              label="Local latency"
              value={formatLatency(record?.routing.local_latency_ms)}
            />
            <DefinitionRow
              label="Cloud latency"
              value={formatLatency(record?.routing.cloud_latency_ms)}
            />
            <DefinitionRow
              label="Circuit"
              value={result?.local_health.circuit_state ?? "CLOSED"}
            />
          </InspectorSection>

          <InspectorSection title="Simulation">
            <DefinitionRow
              label="State"
              value={formatStatus(record?.simulation_status ?? "NOT_REQUESTED")}
            />
            <DefinitionRow
              label="Permit"
              value={record?.execution_permit_id ?? "Not issued"}
            />
            <Button
              appearance="secondary"
              icon={<Stop24Regular />}
              disabled
              className="stop-button"
            >
              Stop simulation
            </Button>
          </InspectorSection>

          <InspectorSection title="Audit">
            <DefinitionRow label="Trace ID" value={record?.trace_id ?? "Not assigned"} mono />
            <DefinitionRow
              label="Policy"
              value={record?.policy_id ?? "Not evaluated"}
            />
            <DefinitionRow
              label="Schema"
              value={record?.evidence_schema_version ?? "2.0.0"}
            />
            <DefinitionRow
              label="Provider"
              value={formatLatency(record?.provider_latency_ms)}
            />
            <DefinitionRow
              label="Validation"
              value={formatLatency(record?.validation_latency_ms)}
            />
            <DefinitionRow
              label="Total"
              value={formatLatency(record?.total_pipeline_latency_ms)}
            />
            <Button
              appearance="secondary"
              icon={<ArrowDownload24Regular />}
              onClick={downloadTrace}
              disabled={!result}
            >
              Download trace
            </Button>
          </InspectorSection>
        </aside>
      </main>
    </div>
  );
}

function RuntimeStatus({
  icon,
  label,
  status,
}: {
  icon: ReactNode;
  label: string;
  status?: AvailabilityStatus;
}) {
  return (
    <div className="runtime-status">
      {icon}
      <span>{label}</span>
      <Badge appearance="tint" color={statusTone(status ?? "NOT_ASSESSED")}>
        {availabilityLabel(status)}
      </Badge>
    </div>
  );
}

function InspectorSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="inspector-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function DefinitionRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="definition-row">
      <span>{label}</span>
      <strong className={mono ? "mono-value" : undefined} title={value}>
        {value}
      </strong>
    </div>
  );
}
