# Prototype 5 canonical governance runner

## Milestone

`A2.2 - Canonical governance runner`

## Scope

The runner provides one provider-neutral path from a reviewed typed command or
reviewed voice transcript to `GovernanceRecordV2`. It does not implement
hybrid routing, speech recognition, simulation, healthcare policy, or evidence
generation.

Historical Prototype 3-5 evidence is unchanged. The runner does not call the
legacy `score_semantics` function and does not convert legacy
`semantic_valid` or `semantic_score` values.

## Processing boundary

```text
Typed text or reviewed READY transcript
        |
        v
PlannerBackend raw response
        |
        v
Strict JSON and StructuredTaskProposalV2 validation
        |
        v
ManufacturingPolicyV2
  - command ambiguity
  - proposed-plan semantic alignment
  - scene and destination safety
  - requester authority
        |
        v
ACCEPT / REJECT / CLARIFY / ERROR
```

The output is not an actuator command. A later simulation milestone may issue
a short-lived execution permit only when `execution_eligible` is true.

## Proposal contract

The bounded action vocabulary is:

```text
MOVE
PICK
PLACE
WAIT
STOP
INSPECT
```

Unknown fields are rejected. Action-specific object, source, destination, and
duration requirements are enforced. A `MOVE` proposal may be represented as a
single `MOVE` step or as the equivalent ordered `PICK` then `PLACE` sequence.

## Decision contract

`ACCEPT` requires all of these independent conditions:

```text
parse PASSED
JSON PASSED
schema PASSED
plan semantics VALID
ambiguity PASSED
safety PASSED
authority PASSED
```

Structural provider failures produce `ERROR`. A semantically wrong but
schema-valid proposal produces `REJECT`. An underspecified command produces
`CLARIFY`. A safety or authority failure produces `REJECT`.

A structurally invalid proposal is not semantically valid. It is explicitly
not assessable. Correct rejection is represented only by evaluation-mode
`decision_correctness_status`.

## Live and evaluation modes

Live mode applies deterministic gates but does not invent oracle correctness.

Evaluation mode additionally requires a benchmark identifier and hash, an
oracle version and hash, and an expected decision. It can then classify the
final decision as correct or incorrect without changing the plan-semantic
result.

## Manufacturing policy

`configs/prototype5/manufacturing_policy_v2.json` is a versioned synthetic
demonstration policy. It contains bounded vocabulary, entity aliases, restricted
locations, explicit safety phrases, and role permissions. It contains no
benchmark gold labels or expected decisions.

This policy is not a certified industrial robot safety function and does not
establish real-world robot safety.

## Integration contract

Direct `LOCAL` and `CLOUD` requests may call the runner directly. `AUTO` is
reserved for the later `HybridInferenceRouter`, which will select a final
provider response and then call the same `evaluate_response` method. Policy
rejection is downstream of routing and therefore cannot trigger provider
shopping.
