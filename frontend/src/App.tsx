import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react";
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
  ArrowUpload24Regular,
  Bot24Regular,
  Cloud24Regular,
  Desktop24Regular,
  Dismiss24Regular,
  Mic24Regular,
  Send24Regular,
  ShieldCheckmark24Regular,
  Stop24Regular,
} from "@fluentui/react-icons";
import {
  getDemoManifest,
  getDemoStatus,
  submitTypedCommand,
  submitVoiceCommand,
  transcribeRecordedAudio,
} from "./api";
import type {
  AvailabilityStatus,
  DemoManifest,
  DemoStatus,
  HybridGovernanceResult,
  InferenceMode,
  RecordedTranscription,
} from "./types";

const gateDefinitions = [
  ["Parse", "parse_status"],
  ["JSON", "json_status"],
  ["Schema", "schema_status"],
  ["Plan semantics", "plan_semantic_status"],
  ["Ambiguity", "ambiguity_status"],
  ["Safety", "safety_status"],
  ["Role / action authority", "authority_status"],
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

function formatStatus(status: string): string {
  return status.replaceAll("_", " ").toLowerCase().replace(/^\w/, (value) => value.toUpperCase());
}

function formatLatency(value: number | null | undefined): string {
  return value == null ? "Not recorded" : `${value.toFixed(1)} ms`;
}

export function clientErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message.slice(0, 200);
  }
  return "UNKNOWN_CLIENT_FAILURE";
}

export function isInferenceMode(value: unknown): value is InferenceMode {
  return value === "LOCAL" || value === "CLOUD" || value === "AUTO";
}

export function selectInferenceMode(
  current: InferenceMode,
  candidate: unknown,
): InferenceMode {
  return isInferenceMode(candidate) ? candidate : current;
}

export function App() {
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [mode, setMode] = useState<InferenceMode>("AUTO");
  const [scenarioId, setScenarioId] = useState("");
  const [result, setResult] = useState<HybridGovernanceResult | null>(null);
  const [submittedCommand, setSubmittedCommand] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [transcription, setTranscription] =
    useState<RecordedTranscription | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [transcriptConsumed, setTranscriptConsumed] = useState(false);
  const [transcriptionError, setTranscriptionError] = useState<string | null>(
    null,
  );
  const [submittedInputMode, setSubmittedInputMode] = useState<"TYPED" | "VOICE">(
    "TYPED",
  );
  const audioInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getDemoManifest(controller.signal),
      getDemoStatus(controller.signal),
    ])
      .then(([nextManifest, nextStatus]) => {
        setManifest(nextManifest);
        setStatus(nextStatus);
        const initial = nextManifest.scenarios.find(
          (scenario) => scenario.model_input_enabled,
        );
        if (!initial) throw new Error("CONTRACT_FAILURE");
        setScenarioId(initial.scenario_id);
      })
      .catch((error: unknown) => {
        if (!(error instanceof Error && error.name === "AbortError")) {
          setStatusError(clientErrorMessage(error));
        }
      });
    return () => controller.abort();
  }, []);

  const record = result?.canonical_result.governance_record ?? null;
  const selectedScenario = manifest?.scenarios.find(
    (scenario) => scenario.scenario_id === scenarioId,
  ) ?? null;
  const proposalText = useMemo(
    () =>
      result?.canonical_result.proposal
        ? JSON.stringify(result.canonical_result.proposal, null, 2)
        : "No schema-valid proposal available.",
    [result],
  );

  async function handleSubmit() {
    const trimmed = command.trim();
    if (
      !trimmed ||
      !selectedScenario?.model_input_enabled ||
      pending ||
      transcribing ||
      transcriptConsumed
    ) return;
    setPending(true);
    setRequestError(null);
    setSubmittedCommand(trimmed);
    const isVoice = transcription?.transcript_status === "READY";
    setSubmittedInputMode(isVoice ? "VOICE" : "TYPED");
    // The server claims a transcript before provider invocation. Treat any
    // voice submission attempt as consumed so the UI cannot suggest replay.
    if (isVoice) setTranscriptConsumed(true);
    try {
      const nextResult = isVoice
        ? await submitVoiceCommand({
            scenario_id: selectedScenario.scenario_id,
            transcription_id: transcription.transcription_id,
            reviewed_transcript_text: trimmed,
            inference_mode: mode,
          })
        : await submitTypedCommand({
            scenario_id: selectedScenario.scenario_id,
            command: trimmed,
            inference_mode: mode,
          });
      setResult(nextResult);
    } catch (error) {
      setResult(null);
      setRequestError(clientErrorMessage(error));
    } finally {
      setPending(false);
    }
  }

  async function handleAudioSelection(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || transcribing || pending) return;
    setTranscribing(true);
    setTranscriptionError(null);
    setRequestError(null);
    setResult(null);
    setTranscriptConsumed(false);
    try {
      const nextTranscription = await transcribeRecordedAudio(file);
      setTranscription(nextTranscription);
      if (
        nextTranscription.transcript_status === "READY" &&
        nextTranscription.transcript_text
      ) {
        setCommand(nextTranscription.transcript_text);
      } else {
        setTranscriptionError(
          nextTranscription.error_code ?? nextTranscription.transcript_status,
        );
      }
    } catch (error) {
      setTranscription(null);
      setTranscriptionError(clientErrorMessage(error));
    } finally {
      setTranscribing(false);
    }
  }

  function discardTranscript() {
    setTranscription(null);
    setTranscriptionError(null);
    setTranscriptConsumed(false);
    setCommand("");
  }

  function downloadTrace() {
    if (!result || !record) return;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            transcription,
            governance: result,
          },
          null,
          2,
        ),
      ],
      {
        type: "application/json",
      },
    );
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
            <Field label="Scenario" size="small">
              <Dropdown
                aria-label="Scenario"
                value={selectedScenario?.display_name ?? "Loading scenarios"}
                selectedOptions={scenarioId ? [scenarioId] : []}
                disabled={!manifest}
                onOptionSelect={(_, data) => {
                  const next = manifest?.scenarios.find(
                    (scenario) => scenario.scenario_id === data.optionValue,
                  );
                  if (!next) return;
                  setScenarioId(next.scenario_id);
                  setResult(null);
                  setRequestError(null);
                  setSubmittedCommand(null);
                  setCommand(next.model_input_enabled ? next.registered_command : "");
                  const nextMode = next.allowed_inference_modes[0];
                  if (nextMode && !next.allowed_inference_modes.includes(mode)) {
                    setMode(nextMode);
                  }
                }}
              >
                {manifest?.scenarios.map((scenario) => (
                  <Option key={scenario.scenario_id} value={scenario.scenario_id}>
                    {scenario.display_name}
                  </Option>
                ))}
              </Dropdown>
            </Field>
            <Field label="Inference" size="small">
              <RadioGroup
                layout="horizontal"
                value={mode}
                onChange={(_, data) => {
                  setMode((current) => selectInferenceMode(current, data.value));
                }}
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
                <span className="message-label">
                  {submittedInputMode === "VOICE"
                    ? "Reviewed voice transcript"
                    : "Operator"}
                </span>
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
            {transcriptionError && (
              <div className="request-error" role="alert">
                <strong>Transcription failed</strong>
                <span>{transcriptionError}</span>
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
            {transcription?.transcript_status === "READY" && (
              <div className="transcript-review" role="status">
                <div className="transcript-identity">
                  <Mic24Regular aria-hidden="true" />
                  <div>
                    <strong>Nemotron transcript</strong>
                    <span>
                      {transcription.audio.original_filename} ·{" "}
                      {formatLatency(transcription.transcription_latency_ms)}
                    </span>
                  </div>
                </div>
                <div className="transcript-actions">
                  <Badge
                    appearance="tint"
                    color={transcriptConsumed ? "subtle" : "success"}
                  >
                    {transcriptConsumed ? "Submitted" : "Ready"}
                  </Badge>
                  <Tooltip content="Discard transcript" relationship="label">
                    <Button
                      appearance="subtle"
                      icon={<Dismiss24Regular />}
                      aria-label="Discard transcript"
                      onClick={discardTranscript}
                    />
                  </Tooltip>
                </div>
              </div>
            )}
            <Field label="Operator command">
              <Textarea
                value={command}
                onChange={(_, data) => setCommand(data.value)}
                placeholder="Enter a bounded manufacturing command"
                resize="vertical"
                disabled={pending || !selectedScenario?.model_input_enabled}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    void handleSubmit();
                  }
                }}
              />
            </Field>
            <div className="composer-actions">
              <input
                ref={audioInputRef}
                className="visually-hidden"
                type="file"
                accept=".wav,audio/wav,audio/x-wav"
                onChange={(event) => void handleAudioSelection(event)}
                aria-label="Recorded WAV file"
              />
              <Tooltip content="Upload WAV recording" relationship="label">
                <Button
                  appearance="subtle"
                  icon={<ArrowUpload24Regular />}
                  aria-label="Upload WAV recording"
                  disabled={pending || transcribing}
                  onClick={() => audioInputRef.current?.click()}
                />
              </Tooltip>
              <Tooltip content="Microphone available in V2" relationship="label">
                <Button
                  appearance="subtle"
                  icon={<Mic24Regular />}
                  aria-label="Microphone available in V2"
                  disabled
                />
              </Tooltip>
              {transcribing && (
                <Spinner size="tiny" label="Transcribing recording" />
              )}
              <Button
                appearance="primary"
                icon={<Send24Regular />}
                disabled={
                  !command.trim() ||
                  !selectedScenario?.model_input_enabled ||
                  pending ||
                  transcribing ||
                  transcriptConsumed
                }
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
                  {record
                    ? record.execution_eligible
                      ? "Eligible"
                      : "Not eligible"
                    : "Not evaluated"}
                </Badge>
              </div>
            </div>
          </InspectorSection>

          <InspectorSection title="Routing">
            <DefinitionRow label="Requested" value={record?.routing.requested_mode ?? "NOT_EVALUATED"} />
            <DefinitionRow
              label="Selected"
              value={record ? record.routing.selected_provider : "Not evaluated"}
            />
            <DefinitionRow
              label="Model"
              value={record ? record.routing.selected_model ?? "Not selected" : "Not evaluated"}
            />
            <DefinitionRow
              label="Fallback"
              value={
                record?.routing.fallback_triggered
                  ? formatStatus(record.routing.fallback_reason)
                  : record
                    ? "Not triggered"
                    : "Not evaluated"
              }
            />
            <DefinitionRow
              label="Local latency"
              value={record ? formatLatency(record.routing.local_latency_ms) : "Not evaluated"}
            />
            <DefinitionRow
              label="Cloud latency"
              value={record ? formatLatency(record.routing.cloud_latency_ms) : "Not evaluated"}
            />
            <DefinitionRow
              label="Circuit"
              value={result?.local_health.circuit_state ?? "NOT_AVAILABLE"}
            />
          </InspectorSection>

          <InspectorSection title="Simulation">
            <DefinitionRow
              label="State"
              value={record ? formatStatus(record.simulation_status) : "Not evaluated"}
            />
            <DefinitionRow
              label="Permit"
              value={record ? record.execution_permit_id ?? "Not issued" : "Not evaluated"}
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
            <DefinitionRow label="Trace ID" value={record?.trace_id ?? "Not evaluated"} mono />
            <DefinitionRow
              label="Policy"
              value={record?.policy_id ?? "NOT_EVALUATED"}
            />
            <DefinitionRow
              label="Schema"
              value={record?.evidence_schema_version ?? "NOT_EVALUATED"}
            />
            <DefinitionRow
              label="Provider"
              value={record ? formatLatency(record.provider_latency_ms) : "Not evaluated"}
            />
            <DefinitionRow
              label="Validation"
              value={record ? formatLatency(record.validation_latency_ms) : "Not evaluated"}
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
