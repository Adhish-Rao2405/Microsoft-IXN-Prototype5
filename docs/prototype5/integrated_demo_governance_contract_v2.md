# Integrated Demonstrator Governance Contract v2

## Status

This contract is the canonical evidence and decision record for the integrated
Prototype 5 demonstrator.

```text
Evidence schema: 2.0.0
Primary domain: MANUFACTURING
Secondary domain: HEALTHCARE_SYNTHETIC
Historical evidence: immutable
```

It defines data meaning and fail-closed invariants. It does not call a model,
evaluate a policy, issue an execution permit, or move a simulator.

The machine-readable interface is committed at:

```text
schemas/prototype5/governance_record_v2.schema.json
```

A regression test requires that file to remain byte-semantically equivalent to
the Pydantic-generated schema.

## Scientific correction

Historical `semantic_score` and `semantic_valid` values are not migrated into
v2 plan-semantic validity. Prototype 3's score combines plan matching with
correct-rejection behaviour. Prototype 5 Mode E2 uses policy-category agreement
under the same label.

The v2 contract separates:

* plan-semantic validity;
* ambiguity outcome;
* safety outcome;
* authority outcome;
* final governance decision;
* benchmark decision correctness;
* execution eligibility.

A correct rejection belongs to decision correctness. It does not make an
unparseable or schema-invalid proposal semantically valid.

## Live and evaluation modes

### Live mode

Live mode may determine:

* parse validity;
* JSON validity;
* schema validity;
* plan-semantic status where the bounded domain contract supplies sufficient
  deterministic context;
* ambiguity, safety, and authority gate outcomes;
* final decision and execution eligibility.

Live mode has no independent benchmark label. Therefore:

```text
expected_decision = null
decision_correctness_status = NOT_EVALUATED
```

### Evaluation mode

Evaluation mode requires:

* benchmark ID;
* oracle version;
* expected decision;
* decision-correctness result.

This prevents arbitrary live prompts from being counted as correct benchmark
decisions.

## Mandatory fail-closed invariants

```text
parse FAILED or ERROR
    -> JSON/schema cannot PASS
    -> plan semantics cannot be VALID

JSON FAILED or ERROR
    -> schema cannot PASS
    -> plan semantics cannot be VALID

schema FAILED or ERROR
    -> plan semantics cannot be VALID

execution_eligible
    = parse PASSED
    AND JSON PASSED
    AND schema PASSED
    AND plan semantics VALID
    AND ambiguity PASSED
    AND safety PASSED
    AND authority PASSED

final decision ACCEPT
    <-> execution_eligible
```

`NOT_ASSESSABLE` is not equivalent to `FAILED`. In particular, an inherited
legacy `safety_valid=false` value is not converted into a v2 safety failure.

## Routing boundary

The routing record supports:

```text
LOCAL
CLOUD
AUTO
```

AUTO fallback accepts only enumerated operational or structured-output failure
reasons. Safety, ambiguity, authority, and domain-policy rejection are not
fallback reasons and therefore cannot be represented as such.

LOCAL mode cannot call cloud. CLOUD mode cannot call local. AUTO must attempt
local before cloud.

## Voice boundary

Voice records require explicit transcript state and provenance.

```text
READY
PARTIAL
EMPTY
BACKEND_UNAVAILABLE
FAILED
CANCELLED
```

Only a `READY` transcript can enter provider routing. Partial, empty, failed,
cancelled, or unavailable transcripts cannot select a model provider or become
execution eligible.

The contract records a non-predictable transcription identifier, the original
ASR text, the operator-reviewed text, the transcript backend, and optional
audio SHA-256. The reviewed text is the command evaluated by the canonical
runner; the original text remains available for edit-trace analysis. The
contract does not permit a fabricated transcript fallback.

## Simulation boundary

Simulation states beyond `NOT_REQUESTED` or `NOT_STARTED` require:

* `execution_eligible=true`;
* a non-empty execution permit ID.

Permit issuance, expiry, one-time consumption, and plan-hash verification belong
to the later simulator milestone.

## Provenance

Each record includes:

* source repository;
* full software commit SHA;
* prompt ID and version;
* selected provider and model;
* policy SHA-256;
* optional benchmark and oracle SHA-256 values.

Routing provider/model values must match provenance provider/model values.

## Legacy reference

`LegacyMetricReference` preserves selected historical fields and their source
identity while assigning:

```text
semantic_metric_classification =
    LEGACY_HYBRID_DECISION_SCORE

v2_plan_semantic_status =
    NOT_ASSESSABLE_MISSING_ORACLE

v2_safety_status =
    NOT_ASSESSABLE
```

This is a non-converting adapter. It cannot be used to create new v2 accuracy
claims from historical Boolean fields.

## Claim boundary

Contract validity proves that a record is internally coherent. It does not
prove:

* model quality;
* benchmark correctness;
* policy completeness;
* production readiness;
* real-world robot safety;
* clinical safety;
* simulator or physical execution.
