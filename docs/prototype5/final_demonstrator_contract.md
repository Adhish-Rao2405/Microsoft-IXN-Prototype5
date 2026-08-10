# Prototype 5 final demonstrator contract

## Status and authority

This document and
`configs/prototype5/final_demo_scenarios_v1.json` define the D0 contract for
the Prototype 5 final demonstrator. They are specification and
machine-checkable configuration only. They do not implement a replay runtime,
change an API, grant a permit, or authorise D1.

The qualified integration baseline is commit
`c20a184bc40b5dfa7f4c4f1c7937b89e3d06c3df`, tree
`bcc73a639ca2f06f0acc6042327c490665b9dfdf`.

The words **MUST**, **MUST NOT**, **MAY**, and **ONLY** are normative.

## Research boundary

Research expansion is closed. B1, B1.1, B1.2, B2, B3.1, B3.2 and Mode E
inputs, methods, evidence and claims remain immutable. In particular, no final
demonstrator milestone may change the route, inverse kinematics, scene,
waypoints, numerical contact epsilon, closest-point horizon, interpolation,
collision-pair policy, scientific observations, or evidence artifacts.

The frozen B3.2 result remains
`B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION`, with 118 recorded
`B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION` failures. This is valid scientific
evidence. It MUST NOT be tuned into a pass.

## Authority taxonomy

The final demonstrator MUST use the following terms. The generic label
“execution authority” MUST NOT be used for governance eligibility or evidence
replay access.

| Layer | Exact term | Meaning | Does not establish |
| --- | --- | --- | --- |
| Model output | `UNTRUSTED PROPOSAL` | Provider output before deterministic governance | Any authority |
| Governance | `GOVERNANCE DECISION: ACCEPT / CLARIFY / REJECT` | Result of parse, JSON, schema, policy-scoped semantic, ambiguity, safety and role/action-policy evaluation | Geometry, dynamics or physical safety |
| Eligibility | `EXECUTION ELIGIBILITY` | An accepted proposal may proceed to a separately bounded downstream qualification step | Geometric validity, collision freedom, dynamic executability, robot authority or physical safety |
| Demo capability | `QUALIFICATION_REPLAY_ACCESS` | A server-resolved registered operation may consume exact frozen B2/B3.2 evidence | Simulated or physical execution authority |
| Geometry | `DOWNSTREAM GEOMETRIC QUALIFICATION: PASS / FAIL / NOT_APPLICABLE / NOT_REQUESTED` | Independent downstream result under the frozen protocol | Continuous collision freedom or physical safety |
| Physical execution | `PHYSICAL EXECUTION AUTHORITY: NOT_IMPLEMENTED` | No physical execution authority exists | Nothing downstream; this is terminally unavailable |

No dynamic PyBullet execution authority exists. PyBullet use in the final
demonstrator is limited to read-only visual evidence reconstruction.

### Required state chain

```text
MODEL / PROVIDER
↓
UNTRUSTED PROPOSAL
↓
PARSE
↓
JSON VALIDITY
↓
SCHEMA VALIDITY
↓
POLICY-SCOPED SEMANTIC VALIDITY
↓
AMBIGUITY / CLARIFICATION
↓
SAFETY / ROLE-ACTION POLICY
↓
EXECUTION ELIGIBILITY
↓
OPTIONAL QUALIFICATION_REPLAY_ACCESS
↓
FROZEN B2 KINEMATIC PLAN
↓
FROZEN B3.2 GEOMETRIC QUALIFICATION
↓
PHYSICAL EXECUTION AUTHORITY: NOT_IMPLEMENTED
```

**PASSING LAYER N DOES NOT ESTABLISH LAYER N+1.**

## Trust boundary

The browser is untrusted. It MAY submit only a bounded scenario identifier,
an inference mode, an approved synthetic persona identifier, typed text, or a
reviewed transcript. A future server implementation MUST validate those
values against the registry and resolve authoritative context itself.

The browser MUST NOT authoritatively supply:

- requester role;
- human-obstruction or safety-interlock state, including the current
  `safety_interlock_enabled` field;
- scene geometry;
- joint states, waypoints, or trajectory coordinates;
- URDF paths;
- collision exclusions or tolerances;
- B2 or B3.2 artifact identities;
- capability/permit binding fields.

Scenario context is server-owned. A synthetic persona selector is a bounded
demonstration input, not authentication and not an operator credential. The
server maps the selected persona ID to an immutable synthetic role.

## Scenario registry

The JSON registry is the normative machine-readable scenario source. It
defines two capability classifications:

- `GOVERNANCE_ONLY`: no PyBullet replay operation may be created, even after
  governance ACCEPT.
- `FROZEN_B2_REPLAY_COMPATIBLE`: the one dedicated registered operation may
  request bounded replay access to the exact frozen evidence binding.

Natural-language similarity MUST NOT establish replay compatibility. Mode E
cases remain `GOVERNANCE_ONLY`. The Mode E pick-and-place case E001 is not
implicitly the frozen B2 replay operation.

| Scenario ID | Source | Classification | Intended demonstration |
| --- | --- | --- | --- |
| `MANUFACTURING_TYPED_ACCEPT` | Mode E E001 command, evaluated through the live canonical path | `GOVERNANCE_ONLY` | Clear typed governance flow |
| `MANUFACTURING_UNSAFE_REJECT` | Existing canonical-runner regression | `GOVERNANCE_ONLY` | Safety rejection |
| `MANUFACTURING_AMBIGUOUS_CLARIFY` | Existing canonical-runner regression | `GOVERNANCE_ONLY` | Clarification and non-eligibility |
| `MANUFACTURING_SCHEMA_VALID_INELIGIBLE` | Existing restricted-destination regression | `GOVERNANCE_ONLY` | Schema validity is insufficient |
| `MANUFACTURING_OBSERVER_ROLE_REJECT` | Existing observer-role regression | `GOVERNANCE_ONLY` | Role/action-policy rejection |
| `MODE_E_CONVEYOR_GOVERNANCE` | Mode E E006 | `GOVERNANCE_ONLY` | Frozen conveyor governance breadth; no simulated conveyor |
| `MODE_E_WAREHOUSE_GOVERNANCE` | Mode E E016 | `GOVERNANCE_ONLY` | Frozen warehouse governance breadth; no simulated warehouse |
| `MODE_E_HUMAN_PROXIMITY_GOVERNANCE` | Mode E E024 | `GOVERNANCE_ONLY` | Frozen human-proximity rejection; no simulated human model |
| `MODE_E_RESTRICTED_ZONE_GOVERNANCE` | Mode E E029 | `GOVERNANCE_ONLY` | Frozen restricted-zone rejection; no simulated restricted-zone geometry |
| `FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY` | Direct immutable evidence binding | `FROZEN_B2_REPLAY_COMPATIBLE` | Frozen B2 state replay and B3.2 failure presentation |

The dedicated replay operation does not send its display command to a model.
Its capability comes only from its registered operation ID and exact evidence
binding.

### Live-versus-frozen provenance invariant

`LIVE_MODEL_PROPOSAL != FROZEN_B2_PLAN`

A live inference result is always an `UNTRUSTED PROPOSAL`. A live governance
`ACCEPT` MAY demonstrate that the proposal passed the evaluated governance
layer, and that result MAY be presented adjacent to frozen downstream research
evidence for explanation. The live proposal is NOT the provenance source of
the frozen B2 route or the frozen B3.1/B3.2 evidence. Sequential presentation
MUST NOT be represented as derivation. The frozen route and qualification
evidence retain their independent historical provenance, and the dedicated
replay operation consumes only the exact bound frozen artifacts.

## Frozen evidence binding

The replay binding ID is `FROZEN_B2_B3_2_EVIDENCE_V1`.

| Evidence | Repository-relative path | SHA-256 |
| --- | --- | --- |
| B2 plan | `results/prototype5/scene_calibration/phase_b2_kinematic_plan.json` | `a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554` |
| B3.1 qualification | `results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json` | `004783320d3af4d1de45aaeee3f6da09829d6ad395d49221bac054452fa5af02` |
| B3.2 qualification | `results/prototype5/scene_calibration/phase_b3_2_discrete_route_collision_qualification.json` | `11c8b83f8c4d0545c9a8df604046a335acb00121a51bf6e1d5b39504991c1798` |
| B3.2 specification | `docs/prototype5/phase_b3_2_discrete_route_collision_qualification_spec.md` | `ffdcf517d56e32ae5b5a175bef89e015489a3d23ab7c1a4856c9987da7e4344a` |

The B3.2 specification was frozen at
`a7ca2243c33097c4dd2b4a6afa3c79b1da7e41f2`, Git blob
`5b63ae433315ea94cd58c734bcf379367dafcd71`.

The exact B2 semantic execution tuple is:

```text
scene_id=manufacturing_demo_scene
scene_state_version=1.0.0
operation=MOVE
object=blue_component
source=input_tray_a
destination=assembly_fixture_b
```

Frozen runtime provenance includes PyBullet 3.2.7, API 202010061, KUKA URDF
`pybullet_data/kuka_iiwa/model.urdf`, URDF SHA-256
`5c13c5b4bb88b5265223e0ec9a7706cbf81e9bb21cc0e18534273755a041788c`
and asset-manifest SHA-256
`cee6f5a30f860c1302cb7ef69f0da2c0736a283fe87b87504f0141438c544fb3`.

### Recorded failure terminology

The bounded human-readable replay reference is copied from the authoritative
B3.2 record:

```text
semantic_snapshot_index=352
route_state=DESTINATION_PLACE
phase=RELEASE_BOUNDARY
boundary_snapshot=POST
pair_id=component_environment:destination_floor
pair_index=78
query bodyA=component
query bodyB=destination_floor
signed_distance_m=-9.290505685985613e-07
classification=MATERIAL_PENETRATION
permission=REQUIRED_SUPPORT
decision=B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION
```

The UI MAY reproduce those recorded identifiers and values. It MUST NOT
generalise them into continuous-collision, dynamic, placement-accuracy, or
physical-safety claims.

## Replay claim boundary

Any PyBullet presentation MUST display both:

- `EVIDENCE REPLAY`
- `NOT PHYSICAL EXECUTION`

Replay reconstructs frozen states and consumes immutable evidence. It does
not perform new IK, optimise a trajectory, generate a new collision result,
prove dynamic feasibility, prove physical robot safety, or authorise physical
execution.

Qualification-replay access does not establish a geometric pass. A geometric
pass would not establish physical safety or physical execution authority. The
frozen B3.2 failure does not retroactively change any separately presented
historical governance result.

Discrete sampling cannot prove the absence of collision between evaluated
configurations.

## Fail-closed invariants

For `REJECT` or `CLARIFY`:

- execution eligibility is false;
- no qualification-replay capability is created;
- no replay session advances;
- no B2 route or PyBullet replay starts;
- semantic, ambiguity, safety, or role/action rejection does not trigger
  provider-shopping;
- physical execution authority remains `NOT_IMPLEMENTED`.

For every `GOVERNANCE_ONLY` scenario, ACCEPT still creates no replay
capability and no PyBullet operation.

For B3.2 FAIL, frozen failure evidence MAY be replayed, but no final execution
approval may be claimed. Physical execution authority remains
`NOT_IMPLEMENTED`.

## AUTO provider semantics

The final demonstrator preserves the existing router contract. AUTO may use
bounded fallback for local unavailability, model-not-ready, circuit-open,
rolling-reliability, latency, timeout, transport, empty response, parse, JSON,
or schema-generation failure.

AUTO MUST NOT provider-shop after semantic policy rejection, ambiguity,
safety rejection, role/action-policy rejection, or downstream geometric
qualification failure.

## Voice semantics

```text
WAV
→ STT
→ RAW TRANSCRIPT
→ OPERATOR REVIEW
→ READY TRANSCRIPT
→ SAME CANONICAL GOVERNANCE RUNNER
```

There is no voice-to-robot path. An unavailable STT worker fails closed and
creates no governance or replay session. D0 authorises no new STT research.

## Trace and evidence terminology

- `FROZEN RESEARCH EVIDENCE` is immutable existing research evidence that
  supports bounded dissertation claims.
- `LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE` is mutable operational
  telemetry. It is not an empirical substitute for frozen benchmark or
  qualification evidence.

A live trace MUST identify its trace ID, selected provider, resolved model and
timestamp. D0 does not require a new signing subsystem for live traces.

## Deterministic presentation fallback

Future presentation sources MUST identify themselves as one of:

- `LIVE`
- `RECORDED_FALLBACK`
- `FROZEN_RESEARCH_EVIDENCE`

Permitted fallback sources are a known-good recorded WAV, known-good typed
scenario, previously captured live-demo trace, or frozen evidence replay. A
recorded or cached result MUST NOT be displayed as a fresh model or STT
invocation. Hidden provider substitution is prohibited.

## Input boundary contract

Future endpoints MUST reject null, empty, whitespace-only, absent,
unsupported, or malformed inputs as enumerated in the JSON contract. Invalid
input, proposal, routing, gate, audio, scenario, or replay-operation data must
fail closed and create no replay/session capability.

In particular, zero-byte WAV data is invalid. Unknown JSON fields and unknown
scenario identifiers are rejected. Frontend response decoding must treat
malformed or incomplete API JSON as an error rather than manufacturing a
state.

## Healthcare

Healthcare is `OUT_OF_SCOPE_FOR_FINAL_DEMO`. D0 authorises no healthcare
policy, schema, scenario, backend, or clinical claim.

## D0 scope firewall

D0 changes only this document, the scenario registry, and focused contract
tests. It does not change runtime modules, frontend files, workflows,
dependencies, research source, or frozen evidence. D1 remains unauthorised
until the uncommitted D0 mutation passes manual Principal-Engineering review.
