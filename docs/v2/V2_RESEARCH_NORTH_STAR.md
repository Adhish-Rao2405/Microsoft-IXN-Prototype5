# V2 Research North Star — Authority-Preserving Recovery

## Status

`V2_STATUS=PREREGISTRATION_AND_ARCHITECTURE_ONLY`

This branch is an additive research extension of the frozen Prototype 5 dissertation subject. It does not alter, reinterpret, overwrite, or retroactively improve any frozen Prototype 5 empirical result.

The current dissertation title remains unchanged unless and until a V2 experiment produces qualified evidence strong enough to justify revising the title:

> **Schema Validity Is Not Enough: Zero-Trust Evaluation of Local SLMs for Industrial Robot Task Planning with Microsoft Foundry Local**

No V2 title promotion is authorised at this stage.

## Exact Lineage and Evidence Firewall

V2 begins from the post-core presentation-correction commit:

`32f840314b59c0830f6d6b8d17ff9d5743611277`

The frozen dissertation engineering subject remains bounded by the qualified core release:

`f99d343a7aba57bf34c7a1ceaf26944329915a24`

The existing Prototype 5 research evidence, including P1–P5, Mode E, D4.3, D4.5, B2, B3.1, B3.2, SO-V2 and their derived claims, remains immutable for dissertation provenance.

V2 MUST NOT:

- mutate frozen V1 research records;
- tune a historical failure into a pass;
- represent a V2 output as provenance for frozen B2/B3 evidence;
- reuse historical observations as though they were prospectively generated V2 evidence;
- weaken existing governance tests or claim boundaries;
- infer physical execution authority from governance eligibility or geometric qualification.

All new V2 evidence MUST be versioned separately under a dedicated namespace before any experimental run.

## Research Motivation

Prototype 5 established that schema-valid model output is insufficient for execution eligibility and demonstrated that useful task proposals can coexist with deterministic authority containment under the tested conditions.

The next research problem is not to increase acceptance rate indiscriminately. It is to determine whether useful capability can be recovered after recoverable governance failure **without weakening authority containment**.

The strongest V2 extension therefore focuses on **authority-preserving recovery**: deterministic failure information may guide a bounded regeneration attempt, but every regenerated proposal must return to the untrusted state and undergo complete revalidation.

## Provisional Research Question

> **RQ6. To what extent can bounded deterministic recovery improve proposal utility following recoverable governance failure without increasing unauthorised execution eligibility?**

This RQ is provisional until V2.0 preregistration is frozen.

## Central V2 Claim Under Test

The intended hypothesis is not assumed true in advance.

> A bounded recovery mechanism can increase retained proposal utility while preserving containment only if regenerated proposals inherit no authority, hard-policy rejections remain terminal, retry budgets are finite, and every regenerated proposal is fully revalidated.

A negative result remains valid research evidence.

## Authority-Preserving Recovery Definition

A recovery mechanism is authority-preserving only if all of the following hold:

1. Every model output begins as `UNTRUSTED_PROPOSAL`.
2. Only explicitly recoverable deterministic failure codes may trigger regeneration.
3. Hard-policy, safety, role/action and other terminal rejection classes MUST NOT trigger model repair.
4. A regenerated proposal inherits no prior schema, semantic, ambiguity, policy, eligibility or downstream qualification state.
5. Every regenerated proposal re-enters the complete canonical governance path from the beginning.
6. Provider fallback MUST NOT override semantic, ambiguity, safety, role/action or policy rejection.
7. Retry count is finite and fixed before the experiment.
8. Downstream state or geometric qualification can only restrict authority further; it cannot retroactively validate a rejected proposal.
9. No state in this V2 work grants physical execution authority unless a separately authorised future research phase explicitly implements and qualifies that boundary.

## Provisional Authority State Model

The conceptual state chain is:

```text
UNTRUSTED_PROPOSAL
        ↓
STRUCTURALLY_VALID
        ↓
SEMANTICALLY_VALID
        ↓
CONTEXT_RESOLVED
        ↓
POLICY_ADMISSIBLE
        ↓
GOVERNANCE_ELIGIBLE
        ↓
OPTIONAL_STATE_QUALIFICATION
        ↓
OPTIONAL_GEOMETRIC_QUALIFICATION
```

Alternative or terminal states include:

```text
CLARIFY
REJECT
REPAIR_EXHAUSTED
STATE_QUALIFICATION_FAIL
GEOMETRIC_QUALIFICATION_FAIL
```

Core invariants to specify and test include:

```text
REJECT => NOT execution_eligible
CLARIFY => NOT execution_eligible
REPAIR(new_proposal) => authority(new_proposal) = UNTRUSTED_PROPOSAL
POLICY_REJECT => provider_fallback NOT_ALLOWED
GOVERNANCE_ELIGIBLE != PHYSICAL_EXECUTION_AUTHORITY
GEOMETRIC_QUALIFICATION_PASS != PHYSICAL_EXECUTION_AUTHORITY
```

Passing layer N MUST NOT establish layer N+1.

## Highest-Value Incremental Research Plan

V2 is deliberately staged so that each completed phase can stand as a defensible research increment. Later phases are optional and MUST NOT be allowed to contaminate earlier qualified evidence.

### V2.0 — Preregistration and Experimental Contract — P0

Before production-code mutation:

- freeze RQ6 wording;
- define recoverable versus terminal failure classes;
- define primary and secondary endpoints;
- define benchmark composition;
- fix retry budget;
- fix model/runtime/configuration subjects;
- fix statistical analysis;
- define exclusions and missing-data handling;
- define evidence paths and manifest format;
- define stop/go criteria for every later phase.

Gate:

`V2_0_PREREGISTRATION=PASS`

### V2.1 — Formal / Executable Authority Invariants — P0

Build the smallest explicit authority-transition model before repair logic.

Target outputs:

- typed authority-state representation;
- explicit allowed transition table;
- forbidden-transition tests;
- property-based transition tests;
- optional TLA+/PlusCal or Alloy model if this can be introduced without weakening delivery confidence.

Primary question:

> Can any transition sequence produce execution eligibility after a terminal rejection or allow repaired output to inherit prior authority?

Gate requires zero known invariant violations.

### V2.2 — Governance Specification V&V Benchmark — P0

Use the discovered C10 ambiguity over-rejection as the seed for a systematic benchmark of deterministic-governor specification quality.

Case families should include:

- pronoun/coreference variants;
- object aliases and synonyms;
- nested references;
- implicit source/destination references;
- unknown objects;
- unsupported operations;
- conflicting role permissions;
- policy precedence conflicts;
- restricted-zone boundary cases;
- tool-state conflicts;
- human-proximity state cases.

Measure separately:

- false accepts;
- false rejects;
- clarification correctness;
- specification-conflict frequency;
- ambiguity-gate precision/recall where a gold label is available.

Gate requires an immutable labelled benchmark and reproducible evaluator before repair is enabled.

### V2.3 — Structured/Constrained Generation Contract — P1

Resolve the client/service contract that blocked the earlier SO-V2 attempt before evaluating constrained generation.

The experimental comparison MUST be version-bound across:

- Foundry Local/runtime version;
- client/SDK/API representation;
- model identifier;
- schema;
- generation settings.

The central hypothesis to test is:

> Constrained generation may improve structural validity without necessarily improving semantic correctness or execution eligibility.

No result may be reported unless the wire contract itself is proven operational before the treatment run.

### V2.4 — Bounded Deterministic Repair — P0

Implement repair only after V2.0–V2.2 are qualified.

Candidate recoverable violation codes may include:

```text
MISSING_REQUIRED_ARGUMENT
AMBIGUOUS_REFERENCE
UNKNOWN_ALIAS
RECOVERABLE_DESTINATION_REFERENCE
```

Candidate terminal classes include:

```text
ROLE_NOT_AUTHORISED
POLICY_PROHIBITED_ACTION
SAFETY_REJECT
UNSUPPORTED_OPERATION
```

Exact classification remains preregistered, not decided after seeing outcomes.

Every repaired result MUST re-enter as `UNTRUSTED_PROPOSAL` and undergo complete revalidation.

### V2.5 — Prospective Main Experiment — P0

Preferred design, if V2.3 is qualified, is a paired 2 x 2 treatment matrix:

| | No recovery | Bounded recovery |
| --- | --- | --- |
| Prompt-only generation | A | C |
| Constrained generation | B | D |

If constrained generation remains unassessed, the minimum viable main experiment becomes paired baseline versus bounded recovery with all other variables fixed.

Primary endpoint — Utility:

- proportion of recoverable, initially non-eligible requests that yield a correct eligible proposal after the permitted recovery attempt.

Primary endpoint — Containment:

- proportion of inadmissible requests that become execution-eligible after recovery;
- count of unauthorised authority transitions;
- false-accept classifications under the preregistered gold standard.

Secondary endpoints may include:

- clarification resolution;
- false-reject rate;
- semantic-valid rate;
- execution-eligible rate;
- end-to-end decision latency;
- retry count.

### V2.6 — Server-Owned Workcell-State Qualification — P1

Only after the core V2 experiment is stable, add a new prospective downstream qualification path with fresh evidence.

Potential state checks:

- object existence;
- authoritative object location;
- tool compatibility;
- safety-interlock/workcell state;
- reachability;
- inverse-kinematics feasibility;
- collision qualification.

Frozen B2/B3 evidence may be used as engineering reference material but MUST NOT be presented as V2 prospective output.

### V2.7 — External Validity — P1/P2

Potential extensions:

- independently authored benchmark cases;
- two independent annotators plus adjudication;
- larger scenario set;
- additional local model families;
- second hardware profile.

This phase is desirable for publication-strength evidence but must not block a clean V2-core result.

### V2.8 — Adversarial Authority-Boundary Evaluation — P1/P2

Evaluate whether adversarial inputs can induce an authority transition that the deterministic architecture should forbid.

Examples include:

- prompt injection;
- role impersonation;
- policy laundering through paraphrase;
- malformed structured output;
- repeated repair pressure;
- provider-fallback manipulation;
- injection-like strings in object labels or command text.

The primary metric is authority-boundary violation, not model refusal style.

### V2.9 — Voice Human-Factors Study — Later

Measure WER/CER, noise/accent sensitivity, operator correction burden, review time, unnoticed transcription error and decision confidence only as a separate study. Existing reviewed-input semantics remain unchanged.

### V2.10 — Physical Robot Integration — Last / Separately Authorised

Physical actuation is not required for the V2-core contribution and MUST remain out of scope until a separately specified hazard-analysis, safety-system and qualification programme exists.

## Containment–Utility Frontier

V2 should avoid optimising acceptance rate in isolation.

Each treatment should be evaluated on two independent dimensions.

Utility indicators may include:

- correct eligible proposals;
- useful clarification outcomes;
- successfully recovered proposals;
- false-reject reduction.

Containment indicators may include:

- false accepts;
- terminal-policy bypasses;
- authority-transition violations;
- downstream inadmissible cases admitted.

The target is an improved utility point with no evidenced degradation in containment under the preregistered test conditions.

## Dissertation Integration Rule

The current dissertation remains the submission-safe baseline.

V2 evidence may be integrated into the dissertation only when ALL of the following hold:

1. the relevant V2 protocol was preregistered before execution;
2. implementation and tests passed the phase gate;
3. raw results and derivations are reproducible;
4. claim boundaries are explicit;
5. no frozen V1 evidence was modified;
6. the result materially strengthens the central thesis rather than adding implementation volume;
7. integration does not destabilise the already-qualified dissertation structure.

Until then, V2 remains future/research-extension work.

## Title Promotion Rule

Current dissertation title remains:

> **Schema Validity Is Not Enough: Zero-Trust Evaluation of Local SLMs for Industrial Robot Task Planning with Microsoft Foundry Local**

Only after a qualified bounded-recovery experiment may a stronger title be considered, for example:

> **Schema Validity Is Not Enough: Zero-Trust Governance and Authority-Preserving Recovery for Local SLM Robot Task Planning with Microsoft Foundry Local**

A title change MUST follow evidence. It MUST NOT precede it.

## Immediate Next Gate

No V2 production implementation is authorised yet.

The next task is V2.0 only:

1. inspect the current governance implementation and test boundaries;
2. enumerate current deterministic outcome/failure codes;
3. identify the smallest recoverable-vs-terminal taxonomy consistent with existing semantics;
4. design the preregistered benchmark and treatment matrix;
5. review the design adversarially;
6. freeze `V2_0_PREREGISTRATION` before any recovery code is written.

This is the active V2 north star.