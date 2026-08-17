import type {
  AuthorityState,
  DemoScenario,
  GateDisplayStatus,
  GovernanceRecord,
  ReplayLifecycle,
} from "./types";

export const SYSTEM_STATUS_EVIDENCE_LABEL =
  "SYSTEM CAPABILITY / STATUS — NOT EXPERIMENTAL EVIDENCE";

export interface AuthorityPresentationRow {
  readonly taxonomyState: AuthorityState;
  readonly label: string;
  readonly state: string;
  readonly detail: readonly string[];
}

interface AuthorityPresentationInput {
  readonly taxonomy: readonly AuthorityState[];
  readonly scenario: DemoScenario;
  readonly record: GovernanceRecord | null;
  readonly proposalPresent: boolean;
  readonly physicalExecutionAuthorityState: "NOT_IMPLEMENTED";
  readonly replayLifecycle: ReplayLifecycle | null;
}

function authorityLabel(state: AuthorityState): string {
  switch (state) {
    case "UNTRUSTED_PROPOSAL":
      return "Untrusted proposal";
    case "GOVERNANCE_DECISION":
      return "Governance decision";
    case "EXECUTION_ELIGIBILITY":
      return "Execution eligibility";
    case "QUALIFICATION_REPLAY_ACCESS":
      return "Qualification replay access";
    case "DOWNSTREAM_GEOMETRIC_QUALIFICATION":
      return "Downstream geometric qualification";
    case "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED":
      return "Physical execution authority";
  }
}

function authorityState(
  state: AuthorityState,
  input: AuthorityPresentationInput,
): Pick<AuthorityPresentationRow, "state" | "detail"> {
  const { scenario, record } = input;
  switch (state) {
    case "UNTRUSTED_PROPOSAL":
      return {
        state: record
          ? input.proposalPresent
            ? "PRESENT — NO AUTHORITY"
            : "NOT AVAILABLE"
          : "NOT REQUESTED",
        detail: [],
      };
    case "GOVERNANCE_DECISION":
      return { state: record?.final_decision ?? "NOT REQUESTED", detail: [] };
    case "EXECUTION_ELIGIBILITY":
      return {
        state: record
          ? record.execution_eligible
            ? "ELIGIBLE"
            : "NOT ELIGIBLE"
          : "NOT REQUESTED",
        detail: [],
      };
    case "QUALIFICATION_REPLAY_ACCESS":
      return {
        state: scenario.qualification_replay_access === "SERVER_REGISTERED_ONLY"
          ? input.replayLifecycle === null
            ? "SERVER_REGISTERED_ONLY — RECONCILING"
            : `SERVER_REGISTERED_ONLY — ${input.replayLifecycle}`
          : "PROHIBITED",
        detail: [
          `Policy: ${scenario.qualification_replay_access}`,
          `Capability class: ${scenario.replay_capability_classification}`,
        ],
      };
    case "DOWNSTREAM_GEOMETRIC_QUALIFICATION":
      return {
        state: scenario.downstream_geometric_qualification,
        detail:
          scenario.downstream_geometric_qualification === "FAIL"
            ? ["Independent of the governance decision"]
            : [],
      };
    case "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED":
      return { state: input.physicalExecutionAuthorityState, detail: [] };
  }
}

export function deriveAuthorityProgression(
  input: AuthorityPresentationInput,
): readonly AuthorityPresentationRow[] {
  return input.taxonomy.map((taxonomyState) => ({
    taxonomyState,
    label: authorityLabel(taxonomyState),
    ...authorityState(taxonomyState, input),
  }));
}

export function evidenceClassificationLabel(scenario: DemoScenario): string {
  switch (scenario.evidence_classification) {
    case "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE":
      return "LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE";
    case "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT":
    case "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION":
      return "FROZEN RESEARCH EVIDENCE — EXACT REGISTERED ARTIFACT";
  }
}

export function secondaryEvidenceClassificationLabel(
  scenario: DemoScenario,
): string | null {
  return scenario.evidence_classification ===
    "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION"
    ? "EVIDENCE REPLAY — NOT PHYSICAL EXECUTION"
    : null;
}

export function presentationClassificationLabel(
  scenario: DemoScenario,
): string {
  switch (scenario.presentation_classification) {
    case "SYNTHETIC_LIVE_DEMO":
      return "SYNTHETIC LIVE DEMO";
    case "FROZEN_RESEARCH_EVIDENCE":
      return "FROZEN RESEARCH EVIDENCE";
    case "FROZEN_EVIDENCE_REPLAY":
      return "FROZEN EVIDENCE REPLAY";
  }
}

export function gateStatusLabel(status: GateDisplayStatus): string {
  switch (status) {
    case "PASSED":
    case "FAILED":
    case "ERROR":
    case "VALID":
    case "INVALID":
      return status;
    case "NOT_ASSESSABLE":
      return "NOT ASSESSABLE";
    case "NOT_EVALUATED":
      return "NOT EVALUATED";
    case "NOT_ASSESSABLE_NO_PROPOSAL":
      return "NOT ASSESSABLE — NO PROPOSAL";
    case "NOT_ASSESSABLE_PARSE_FAILED":
      return "NOT ASSESSABLE — PARSE FAILED";
    case "NOT_ASSESSABLE_SCHEMA_INVALID":
      return "NOT ASSESSABLE — SCHEMA INVALID";
    case "NOT_ASSESSABLE_MISSING_ORACLE":
      return "NOT ASSESSABLE — MISSING ORACLE";
    case "NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT":
      return "NOT ASSESSABLE — MISSING REQUIRED CONTEXT";
  }
}

export function providerLabel(
  provider: GovernanceRecord["routing"]["selected_provider"],
): string {
  switch (provider) {
    case "FOUNDRY_LOCAL":
      return "Foundry Local";
    case "CLOUD":
      return "Cloud";
    case "NONE":
      return "None";
  }
}
