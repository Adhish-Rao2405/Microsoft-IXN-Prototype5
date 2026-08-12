import { describe, expect, it } from "vitest";
import {
  deriveAuthorityProgression,
  evidenceClassificationLabel,
  gateStatusLabel,
  secondaryEvidenceClassificationLabel,
} from "../src/authorityPresentation";
import type {
  AuthorityState,
  DemoScenario,
  GovernanceRecord,
} from "../src/types";

const taxonomy: AuthorityState[] = [
  "UNTRUSTED_PROPOSAL",
  "GOVERNANCE_DECISION",
  "EXECUTION_ELIGIBILITY",
  "QUALIFICATION_REPLAY_ACCESS",
  "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
  "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
];

const liveScenario: DemoScenario = {
  scenario_id: "live-scenario",
  display_name: "Live scenario",
  presentation_classification: "SYNTHETIC_LIVE_DEMO",
  model_input_enabled: true,
  allowed_inference_modes: ["LOCAL", "CLOUD", "AUTO"],
  registered_command: "Move the blue component.",
  demonstration_purpose: "Demonstrate live governance.",
  evidence_classification:
    "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE",
  replay_capability_classification: "GOVERNANCE_ONLY",
  qualification_replay_access: "PROHIBITED",
  downstream_geometric_qualification: "NOT_APPLICABLE",
  claim_boundary_note: "No physical execution authority.",
};

const frozenReplayScenario: DemoScenario = {
  ...liveScenario,
  scenario_id: "frozen-replay",
  display_name: "Frozen replay evidence",
  presentation_classification: "FROZEN_EVIDENCE_REPLAY",
  model_input_enabled: false,
  allowed_inference_modes: [],
  evidence_classification: "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION",
  replay_capability_classification: "FROZEN_B2_REPLAY_COMPATIBLE",
  qualification_replay_access: "SERVER_REGISTERED_ONLY",
  downstream_geometric_qualification: "FAIL",
};

function record(
  decision: GovernanceRecord["final_decision"],
  eligible: boolean,
): GovernanceRecord {
  return { final_decision: decision, execution_eligible: eligible } as GovernanceRecord;
}

function progression(
  scenario: DemoScenario,
  governanceRecord: GovernanceRecord | null,
  proposalPresent = false,
) {
  return deriveAuthorityProgression({
    taxonomy,
    scenario,
    record: governanceRecord,
    proposalPresent,
    physicalExecutionAuthorityState: "NOT_IMPLEMENTED",
    d2ReplayEnabled: false,
  });
}

describe("authority presentation", () => {
  it("preserves the exact six-layer manifest order", () => {
    expect(progression(liveScenario, null).map((row) => row.taxonomyState)).toEqual(
      taxonomy,
    );
  });

  it("uses fail-closed initial authority states", () => {
    const rows = progression(liveScenario, null);
    expect(rows.map((row) => row.state)).toEqual([
      "NOT REQUESTED",
      "NOT REQUESTED",
      "NOT REQUESTED",
      "NOT REQUESTED — NOT ENABLED IN D2",
      "NOT_APPLICABLE",
      "NOT_IMPLEMENTED",
    ]);
    expect(rows.map((row) => row.state).join(" ")).not.toMatch(/GRANTED/);
  });

  it.each([
    ["ACCEPT", true, "ELIGIBLE"],
    ["REJECT", false, "NOT ELIGIBLE"],
    ["CLARIFY", false, "NOT ELIGIBLE"],
  ] as const)("maps %s without granting later authority", (decision, eligible, state) => {
    const rows = progression(liveScenario, record(decision, eligible), true);
    expect(rows[0]?.state).toBe("PRESENT — NO AUTHORITY");
    expect(rows[1]?.state).toBe(decision);
    expect(rows[2]?.state).toBe(state);
    expect(rows[3]?.state).toBe("NOT REQUESTED — NOT ENABLED IN D2");
    expect(rows[5]?.state).toBe("NOT_IMPLEMENTED");
  });

  it("presents registered replay policy without converting it into permission", () => {
    const rows = progression(frozenReplayScenario, null);
    expect(rows[3]?.state).toBe("NOT REQUESTED — NOT ENABLED IN D2");
    expect(rows[3]?.detail).toContain("Policy: SERVER_REGISTERED_ONLY");
    expect(rows[3]?.detail).toContain(
      "Capability class: FROZEN_B2_REPLAY_COMPATIBLE",
    );
    expect(rows[3]?.state).not.toContain("GRANTED");
  });

  it("keeps downstream FAIL independent from governance decision", () => {
    const rows = progression(frozenReplayScenario, record("ACCEPT", true), true);
    expect(rows[1]?.state).toBe("ACCEPT");
    expect(rows[2]?.state).toBe("ELIGIBLE");
    expect(rows[4]?.state).toBe("FAIL");
    expect(rows[4]?.detail).toContain("Independent of the governance decision");
  });

  it("uses exact live and frozen evidence classifications", () => {
    expect(evidenceClassificationLabel(liveScenario)).toBe(
      "LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE",
    );
    expect(evidenceClassificationLabel(frozenReplayScenario)).toBe(
      "FROZEN RESEARCH EVIDENCE — EXACT REGISTERED ARTIFACT",
    );
    expect(secondaryEvidenceClassificationLabel(frozenReplayScenario)).toBe(
      "EVIDENCE REPLAY — NOT PHYSICAL EXECUTION",
    );
  });

  it("does not collapse structural gate states", () => {
    expect(gateStatusLabel("FAILED")).toBe("FAILED");
    expect(gateStatusLabel("INVALID")).toBe("INVALID");
    expect(gateStatusLabel("NOT_EVALUATED")).toBe("NOT EVALUATED");
    expect(gateStatusLabel("NOT_ASSESSABLE_SCHEMA_INVALID")).toBe(
      "NOT ASSESSABLE — SCHEMA INVALID",
    );
  });
});
