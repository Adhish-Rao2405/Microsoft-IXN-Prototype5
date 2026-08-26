# Prototype 5 Phase B3.2 Discrete Route Collision Qualification Specification

## Document status

```text
B3_2_SPEC_DOCUMENT = READY_FOR_MANUAL_REVIEW
B3_2_IMPLEMENTATION = NOT AUTHORIZED
```

This document defines the proposed frozen B3.2 contract. It does not authorize production code, tests, route execution, evidence generation, commit, push, or PR mutation.

## 1. Purpose and scope

B3.2 is a deterministic, static, discrete geometric qualification gate for the already-frozen B2 joint-space route.

The architectural boundary is:

```text
PLANNING CAPABILITY
!= EXECUTION ELIGIBILITY
!= EXECUTION AUTHORITY
!= SIMULATED / PHYSICAL EXECUTION
```

B3.2 consumes frozen B2 route configurations and B3.1 collision-query semantics. It does not calculate IK, plan, replan, optimize, time-parameterize, control, or dynamically execute the robot.

The maximum successful claim is:

> No forbidden collision/contact was observed at any configuration sampled along the frozen B2 route under the declared deterministic discrete B3.2 protocol.

B3.2 must not claim:

- trajectory collision freedom;
- continuous collision freedom;
- impossibility of inter-sample collision;
- safe robot motion;
- dynamic executability or controller stability;
- grasp-physics validity;
- placement or settling accuracy;
- real-robot validation;
- industrial safety or certification.

Discrete route sampling cannot prove the absence of collision between evaluated configurations.

## 2. Immutable predecessor contract

The authoritative repository baseline is:

```text
branch:
feature/s1-pybullet-governed-simulation

B3.1 production/evidence commit:
4953197e9e4fcb6a1e2d92e49e975fee257fc093

R1.1 exact-SHA CI correction commit:
8d0ef61262396b55782f492a0010a0e0c59af9ed
```

Frozen evidence identities are:

| Input | Repository-relative identity | SHA-256 |
|---|---|---|
| B1.2 | `results/prototype5/scene_calibration/phase_b1_2_results.jsonl` | `b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c` |
| B2 | `results/prototype5/scene_calibration/phase_b2_kinematic_plan.json` | `a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554` |
| B3.1 | `results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json` | `004783320d3af4d1de45aaeee3f6da09829d6ad395d49221bac054452fa5af02` |

Frozen runtime identities are:

```text
PyBullet package:
3.2.7

PyBullet API:
202010061

PyBullet binary SHA-256:
e8a99694353e508f9e934a57494c177ddb9317cde94781da8bb68670c2334e40

KUKA URDF SHA-256:
5c13c5b4bb88b5265223e0ec9a7706cbf81e9bb21cc0e18534273755a041788c

KUKA asset-manifest SHA-256:
cee6f5a30f860c1302cb7ef69f0da2c0736a283fe87b87504f0141438c544fb3
```

B3.2 must fail closed on predecessor, runtime, repository-lineage, binary, URDF, or asset-manifest drift.

The R1.1 commit `8d0ef61262396b55782f492a0010a0e0c59af9ed` is the required frozen ancestor of subsequent B3.2 work. It is not required to remain the exact HEAD after later authorized commits.

After this specification is independently reviewed, committed, pushed, and remotely qualified, the resulting B3.2 specification-freeze commit becomes the immediate authorized starting HEAD for B3.2 implementation. B3.2 implementation must descend from both:

- R1.1 commit `8d0ef61262396b55782f492a0010a0e0c59af9ed`;
- the future B3.2 specification-freeze commit.

The current HEAD must not be hard-coded as a permanent future runtime requirement.

B3.2 must not change the frozen:

- KUKA URDF, base pose, fixed-base mode, controlled joints, or link convention;
- layout C source or destination coordinates;
- component, platform, floor, or fixture-wall geometry;
- HOME or six task waypoint vectors;
- route ordering;
- virtual TCP or lift;
- virtual component transform or predicted release pose;
- B3.1 contact policy or 21-pair self-collision inventory;
- predecessor artifacts, digests, or provenance constants.

A scientific B3.2 failure must not trigger silent modification of frozen inputs.

## 3. Numerical contact contract

Frozen constants:

```text
NUMERICAL_CONTACT_EPSILON_M = 1.0e-12
CLOSEST_POINT_QUERY_HORIZON_M = 0.050
```

For a found closest-point result with finite signed distance `d`:

```text
d < -1.0e-12
    MATERIAL_PENETRATION

-1.0e-12 <= d <= +1.0e-12
    NUMERICAL_CONTACT_BAND

d > +1.0e-12
    SEPARATED
```

A valid empty `getClosestPoints()` result is:

```text
found = false
signed_distance_m = null
separation_lower_bound_m = 0.050
classification = SEPARATED_BEYOND_QUERY_HORIZON
```

The epsilon is a numerical-zero classifier only. It is not:

- a safety margin;
- allowed material penetration;
- a placement tolerance;
- a Bullet collision margin;
- a geometry expansion;
- a continuous-collision allowance.

The frozen decision matrix is:

| Pair policy | `MATERIAL_PENETRATION` | `NUMERICAL_CONTACT_BAND` | `SEPARATED` | `SEPARATED_BEYOND_QUERY_HORIZON` |
|---|---|---|---|---|
| `FORBIDDEN` | `B3_2_FAIL_FORBIDDEN_CONTACT` | `B3_2_FAIL_FORBIDDEN_CONTACT` | PASS | PASS |
| `PERMITTED_SUPPORT` | `B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION` | PASS | PASS | PASS |
| `REQUIRED_SUPPORT` | `B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION` | PASS | `B3_2_FAIL_REQUIRED_SUPPORT_MISSING` | `B3_2_FAIL_REQUIRED_SUPPORT_MISSING` |

Material penetration is never permitted for a support pair. The epsilon must not be widened after route results are observed.

## 4. Known destination release condition

Frozen B1.2/B3.1 evidence records:

```text
component_bottom_z_m = 0.01999898956417289
destination_floor_top_z_m = 0.02
bottom_minus_floor_top_m = -1.010435827109718e-06
```

This is measured frozen geometry, not the B3.1 primitive collision-kernel uncertainty envelope.

If B3.2 `getClosestPoints()` reproduces destination-floor material penetration below `-1.0e-12 m`, the scientific route result must be FAIL and must include `B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION`.

B3.2 must not increase the epsilon, snap the component, move the floor, change a waypoint, change lift, re-run IK, or otherwise alter frozen inputs to manufacture PASS.

## 5. Component phase and boundary snapshot contract

The boundary snapshot enum is:

```text
NONE
PRE
POST
```

Contact-policy lookup must use:

```text
component phase + boundary snapshot + semantic pair
```

The component phase machine is:

| Route location | Phase | Boundary snapshot | Component pose | Support obligation |
|---|---|---|---|---|
| Initial HOME through SOURCE_PICK interior | `SOURCE_SUPPORTED` | `NONE` | Frozen source-supported pose | Source platform `REQUIRED_SUPPORT` |
| SOURCE_PICK endpoint before attachment | `ATTACHMENT_BOUNDARY` | `PRE` | Frozen source-supported pose | Source platform `REQUIRED_SUPPORT` |
| SOURCE_PICK endpoint after attachment | `ATTACHMENT_BOUNDARY` | `POST` | Terminal-link world pose composed with frozen virtual-component transform | Source platform `PERMITTED_SUPPORT` |
| SOURCE_PICK POST through DESTINATION_PLACE interior | `CARRIED` | `NONE` | Terminal-link world pose composed with frozen virtual-component transform | Environment support surfaces `FORBIDDEN` |
| DESTINATION_PLACE before release | `RELEASE_BOUNDARY` | `PRE` | Carried pose | Destination floor `PERMITTED_SUPPORT` |
| DESTINATION_PLACE after release | `RELEASE_BOUNDARY` | `POST` | Frozen actual predicted-release pose | Destination floor `REQUIRED_SUPPORT` |
| DESTINATION_PLACE POST through final HOME | `DESTINATION_SUPPORTED` | `NONE` | Frozen actual predicted-release pose | Destination floor `REQUIRED_SUPPORT` |

The following contact-policy matrix is normative:

| Semantic pair | Phase / boundary snapshot | Policy |
|---|---|---|
| Component ↔ source platform | `SOURCE_SUPPORTED / NONE` | `REQUIRED_SUPPORT` |
| Component ↔ source platform | `ATTACHMENT_BOUNDARY / PRE` | `REQUIRED_SUPPORT` |
| Component ↔ source platform | `ATTACHMENT_BOUNDARY / POST` | `PERMITTED_SUPPORT` |
| Component ↔ source platform | Every other phase/boundary state | `FORBIDDEN` |
| Component ↔ destination floor | `RELEASE_BOUNDARY / PRE` | `PERMITTED_SUPPORT` |
| Component ↔ destination floor | `RELEASE_BOUNDARY / POST` | `REQUIRED_SUPPORT` |
| Component ↔ destination floor | `DESTINATION_SUPPORTED / NONE` | `REQUIRED_SUPPORT` |
| Component ↔ destination floor | Every other phase/boundary state | `FORBIDDEN` |
| Component ↔ any destination wall | Every phase/boundary state | `FORBIDDEN` |
| Component ↔ robot base or link | Every phase/boundary state | `FORBIDDEN` |
| Robot ↔ environment | Every phase/boundary state | `FORBIDDEN` |
| Authoritative non-adjacent robot self-pair | Every phase/boundary state | `FORBIDDEN` |

For carried states:

```text
world_T_component = world_T_terminal_link * terminal_link_T_component
```

The terminal transform is the frozen B1.2 virtual-component-local transform. The post-release pose is the frozen actual predicted-release pose, not the nominal destination center.

The following remain prohibited:

- nominal-pose snapping;
- a gripper model;
- `createConstraint`;
- grasp physics;
- component/robot contact exceptions.

Component contact with robot base `-1` and links `0..6` is `FORBIDDEN` in every phase and boundary snapshot.

Destination-wall contact is `FORBIDDEN` in every phase and boundary snapshot. Robot/environment contact and the 21 authoritative non-adjacent robot self-pairs are always `FORBIDDEN`.

## 6. Discrete interpolation contract

Frozen constant:

```text
BASE_MAX_JOINT_STEP_RAD = 0.010
```

For each frozen B2 route leg:

```text
q(t) = q0 + t * (q1 - q0)

max_abs_joint_delta = max(abs(q1[j] - q0[j]) for j in 0..6)

coarse_N = max(1, ceil(max_abs_joint_delta / 0.010))
fine_N = 2 * coarse_N
```

The fine grid is authoritative. The coarse grid is nested sensitivity evidence only. `fine_N` must not be independently calculated with `ceil(delta / 0.005)`.

Expected interval counts are:

| Leg | Coarse intervals | Fine intervals |
|---|---:|---:|
| HOME → SOURCE_HIGH | 39 | 78 |
| SOURCE_HIGH → SOURCE_PICK | 20 | 40 |
| SOURCE_PICK → SOURCE_HIGH_RETURN | 19 | 38 |
| SOURCE_HIGH_RETURN → DESTINATION_HIGH | 77 | 154 |
| DESTINATION_HIGH → DESTINATION_PLACE | 20 | 40 |
| DESTINATION_PLACE → DESTINATION_HIGH_RETURN | 19 | 38 |
| DESTINATION_HIGH_RETURN → HOME | 39 | 78 |

Expected counts are:

```text
coarse route configurations = 234
coarse semantic snapshots = 236

fine route configurations = 467
fine semantic snapshots = 469
```

Every emitted semantic snapshot must contain:

```text
route_configuration_index
semantic_snapshot_index
segment_index
segment_sample_index
segment_interval_count
alpha
route_state
phase
boundary_snapshot
joint_vector
```

All indexes are zero-based integers. `route_configuration_index` and `semantic_snapshot_index` must each be contiguous and monotonically increasing in emission order.

Snapshot emission order is frozen:

- normally, one route configuration emits one `NONE` snapshot;
- at SOURCE_PICK, the endpoint configuration emits `PRE` followed immediately by `POST`; no `NONE` snapshot is emitted for that configuration;
- at DESTINATION_PLACE, the endpoint configuration emits `PRE` followed immediately by `POST`; no `NONE` snapshot is emitted for that configuration.

Therefore each pass emits exactly two more semantic snapshots than route configurations, not four more.

`route_state` semantics are frozen:

- if the configuration is exactly a frozen B2 route state, `route_state` is that exact frozen state name:
  - `HOME`
  - `SOURCE_HIGH`
  - `SOURCE_PICK`
  - `SOURCE_HIGH_RETURN`
  - `DESTINATION_HIGH`
  - `DESTINATION_PLACE`
  - `DESTINATION_HIGH_RETURN`
- if the configuration is strictly interior to a route segment (`0 < alpha < 1`), `route_state` is exactly `INTERPOLATED`;
- `SOURCE_PICK` PRE and POST both use `route_state = SOURCE_PICK`;
- `DESTINATION_PLACE` PRE and POST both use `route_state = DESTINATION_PLACE`;
- `route_state` must never be null, inferred from the nearest waypoint, or populated with a free-form segment description.

The maximum fine-grid joint increment must be no greater than `0.005 rad`.

Sampling rules:

- the first route segment includes `k=0`;
- every later segment omits `k=0` to avoid duplicate shared endpoints;
- `k=0` uses the exact stored `q0` tuple;
- `k=N` uses the exact stored `q1` tuple;
- only interior configurations use arithmetic interpolation with `t=k/N`;
- every coarse configuration must equal fine configuration `2k` exactly;
- no angle wrapping or shortest-angle reinterpretation is permitted;
- no timing, velocity, acceleration, jerk, or controller interpretation is permitted.

Every route vector must contain exactly seven finite numbers and remain within the frozen B2 joint limits. An invalid vector is an infrastructure failure, not a scientific collision result.

## 7. Canonical collision-pair inventory

Category order is frozen:

```text
1. ROBOT_SELF
2. ROBOT_ENVIRONMENT
3. COMPONENT_ROBOT
4. COMPONENT_ENVIRONMENT
```

Robot collision-body order is:

```text
-1, 0, 1, 2, 3, 4, 5, 6
```

Environment order is:

```text
source_platform
destination_floor
destination_wall_x_minus
destination_wall_x_plus
destination_wall_y_minus
destination_wall_y_plus
```

Pair construction and query direction are:

| Category | Construction order | Count | Query direction |
|---|---|---:|---|
| `ROBOT_SELF` | Reuse the B3.1 authoritative non-adjacent tuple order exactly | 21 | `bodyA=robot`, `bodyB=robot`, `linkA=first`, `linkB=second` |
| `ROBOT_ENVIRONMENT` | Robot order outer, environment order inner | 48 | `bodyA=robot`, `bodyB=environment` |
| `COMPONENT_ROBOT` | Robot order above | 8 | `bodyA=component`, `bodyB=robot` |
| `COMPONENT_ENVIRONMENT` | Environment order above | 6 | `bodyA=component`, `bodyB=environment` |

Every pair receives one immutable global integer `pair_index` in `0..82`. `pair_index` equals the pair's zero-based position in the complete canonical 83-pair tuple.

Every pair also receives one immutable `pair_id` with this exact encoding:

```text
ROBOT_SELF:
robot_self:<first_link>:<second_link>

ROBOT_ENVIRONMENT:
robot_environment:<robot_link>:<environment_semantic_id>

COMPONENT_ROBOT:
component_robot:<robot_link>

COMPONENT_ENVIRONMENT:
component_environment:<environment_semantic_id>
```

Examples:

```text
robot_self:-1:1
robot_environment:6:destination_floor
component_robot:6
component_environment:destination_wall_x_plus
```

`pair_id` must be unique across all 83 entries. Pair identity must not use UUIDs, PyBullet runtime body IDs, Python object IDs, or memory addresses.

Pair metadata is frozen once in `collision_pair_inventory`. Every per-snapshot observation must reference both `pair_index` and `pair_id`.

The full Bullet query signature is frozen:

| Category | `bodyA` | `bodyB` | `linkIndexA` | `linkIndexB` |
|---|---|---|---:|---:|
| `ROBOT_SELF` | Robot | Robot | First robot link | Second robot link |
| `ROBOT_ENVIRONMENT` | Robot | Environment body | Robot link | `-1` |
| `COMPONENT_ROBOT` | Component | Robot | `-1` | Robot link |
| `COMPONENT_ENVIRONMENT` | Component | Environment body | `-1` | `-1` |

Every query must also pass:

```text
distance = 0.050
physicsClientId = current explicit pass-local client ID
```

No body, link, distance, or client argument may rely on a PyBullet default.

Frozen invariant:

```text
EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT = 83
MAX_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT = 83
```

Both fewer and greater than 83 queries are infrastructure failures. Direct-parent robot pairs are excluded. No other ancestor pair is excluded. Component/robot pairs must not be duplicated in the reverse direction.

## 8. PyBullet execution contract

B3.2 uses three fresh, independent PyBullet DIRECT sessions:

```text
1. coarse sensitivity pass
2. authoritative fine pass 1
3. fine reproducibility pass 2
```

Physics steps for every pass:

```text
0
```

Allowed APIs and operations are:

- `connect(DIRECT)`;
- `resetSimulation()` during setup;
- `resetJointState()`;
- `resetBasePositionAndOrientation()`;
- `getLinkState()`;
- B3.1 `closest_point_query()` and its `getClosestPoints()` primitive;
- `disconnect()`.

Terminal-link FK must use:

```text
getLinkState(
    ...,
    computeForwardKinematics=True,
    physicsClientId=client_id,
)

position = link_state[4]
orientation = link_state[5]
```

Indices `4/5` are the world URDF link-frame pose. Indices `0/1` are COM/inertial-frame values and must not be substituted.

Forbidden APIs and behaviour are:

- `stepSimulation`;
- `setRealTimeSimulation`;
- `calculateInverseKinematics`;
- `createConstraint`;
- `setJointMotorControl*`;
- `getContactPoints` as authoritative route evidence;
- gravity, motor, controller, grasp, settling, or other dynamic execution.

Every Bullet call that accepts a client identifier must use the current explicit pass-local `physicsClientId`. Clients must be disconnected in fail-safe cleanup.

## 9. Null, missing, and empty contract

Required field handling is frozen:

```text
required field absent
    infrastructure failure

required field explicitly null
    infrastructure failure unless this section explicitly permits null
```

Closest-point observation invariants are:

| Condition | Result |
|---|---|
| `found=true` and finite `signed_distance_m` | Valid found observation |
| `found=true` and `signed_distance_m=null` | Infrastructure failure |
| `found=false` and `signed_distance_m!=null` | Infrastructure failure |
| `found=false` and `separation_lower_bound_m!=0.050` | Infrastructure failure |
| `found=false`, `signed_distance_m=null`, lower bound `0.050` | Valid bounded no-result observation |

`signed_distance_m=null` is permitted only when `found=false`.

Additional invariants:

- an empty B2 `ordered_plan` is an infrastructure failure;
- a B2 route with other than eight ordered states or seven legs is an infrastructure failure;
- an empty collision-pair inventory is an infrastructure failure;
- duplicate pairs are an infrastructure failure;
- an empty `getClosestPoints()` result after successful identity and collision-geometry validation is valid and maps to `SEPARATED_BEYOND_QUERY_HORIZON`;
- required JSON fields must use presence checks rather than permissive `.get()` semantics that conflate missing with explicit null.

## 10. Scientific result model

Scientific violations must not short-circuit any remaining planned collision query.

The overall result is exactly one of:

```text
B3_2_PASS_DISCRETE_ROUTE_QUALIFICATION
B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION
```

The result section must include:

```text
overall_result
scientific_failures
failure_summary
failure_codes_present
```

`scientific_failures` is the complete canonical ordered list. Its ordering key is:

```text
semantic_snapshot_index
pair_index
failure code
```

Required failure codes include:

```text
B3_2_FAIL_FORBIDDEN_CONTACT
B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION
B3_2_FAIL_REQUIRED_SUPPORT_MISSING
```

`failure_summary` contains counts for every defined failure code. `failure_codes_present` preserves first-appearance ordering from the already canonical `scientific_failures` sequence and contains each code at most once.

The first route failure must not define or replace `overall_result`. If a `primary_failure` convenience field exists:

- it is `null` on PASS;
- it is reporting metadata only on FAIL;
- it must not suppress any failure category or observation.

Scientific FAIL is valid research evidence. It must not trigger route, geometry, epsilon, phase, or pair-policy mutation.

## 11. Infrastructure failure model

Infrastructure and contract failures include:

- frozen evidence or digest drift;
- runtime, binary, URDF, or KUKA asset drift;
- repository-lineage failure;
- malformed, missing, null, empty, or non-finite required input;
- incorrect route or vector dimensions;
- invalid or disconnected physics client;
- invalid body/link identity or missing collision geometry;
- collision-pair inventory mismatch or duplication;
- route sample, semantic snapshot, or query-count mismatch;
- malformed or internally inconsistent closest-point evidence;
- reproducibility contradiction;
- serialization, portability, write, or digest-verification failure.

Infrastructure failures must:

- stop fail-closed;
- remain distinct from scientific collision FAIL;
- return non-zero from the runner;
- not intentionally finalize a canonical JSON/digest result pair;
- never be converted into PASS, clearance, or scientific collision evidence.

## 12. Reproducibility contract

Frozen constant:

```text
ROUTE_REPRODUCIBILITY_REPEAT_COUNT = 2
```

The two independent fine passes must agree on:

- route configuration count;
- semantic snapshot count;
- phase and boundary-snapshot ordering;
- pair identity, direction, and ordering;
- `found` flags;
- lower-bound semantics;
- numerical classification;
- contact permission and decision;
- complete scientific-failure identities;
- overall scientific result.

Distance comparison is:

```text
found in both:
    abs(d1 - d2) <= 1.0e-12 m

found in only one:
    infrastructure/reproducibility failure

not found in both:
    signed_distance_m = null
    separation_lower_bound_m = 0.050
```

Every coarse configuration must equal its nested fine configuration exactly and must produce the same collision decisions at the shared configuration. A coarse/fine contradiction is an infrastructure/reproducibility failure, not a scientific route result.

Full authoritative route observations are stored once for fine pass 1. Fine pass 2 stores a deterministic comparison summary rather than duplicating the complete route evidence.

## 13. Query accounting and hard caps

Exact expected query accounting is:

```text
coarse:
236 semantic snapshots * 83 = 19,588

fine pass 1:
469 semantic snapshots * 83 = 38,927

fine pass 2:
469 semantic snapshots * 83 = 38,927

complete protocol:
1,174 semantic snapshots
97,442 collision queries
```

Hard caps are:

```text
MAX_ROUTE_SEGMENTS = 7
MAX_FINE_ROUTE_CONFIGURATIONS = 1024
MAX_FINE_SEMANTIC_SNAPSHOTS = 1024
MAX_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT = 83
MAX_TOTAL_COLLISION_QUERIES = 150000
```

Exact expected counts are stronger invariants than caps. Reaching a cap does not justify truncation or partial PASS evidence. Count mismatch is an infrastructure failure.

Scientific violations must not reduce the expected query count through early termination.

## 14. Synchronous and timeout contract

B3.2 core is:

```text
single process
synchronous
bounded loops
PyBullet DIRECT
no network
no background work
```

Asynchronous timeout handling is not applicable.

B3.2 must not introduce:

- `asyncio`;
- threads;
- worker or process pools;
- retries;
- network calls;
- background execution.

Work is bounded by exact route, snapshot, pair, and total-query invariants. The repository CI/job timeout remains an external harness control.

No hardware-dependent wall-clock PASS threshold may be introduced before implementation runtime has been measured and separately reviewed.

## 15. Evidence schema

Frozen identities:

```text
schema_identifier = prototype5.scene_collision_route_qualification.b3_2
schema_version = 1.0.0
gate_identifier = B3_2_DISCRETE_ROUTE_COLLISION_QUALIFICATION
```

Required top-level sections are:

```text
provenance
frozen_input_contract
numeric_contact_contract
interpolation_contract
collision_pair_inventory
component_phase_contract
coarse_sensitivity_summary
authoritative_fine_route
reproducibility_summary
aggregate_clearance_summary
result
claim_boundaries
```

Stable pair metadata must be stored once in `collision_pair_inventory` and referenced by pair ID from observations.

Every closest-point observation must preserve:

```text
pair_index
pair_id
found
signed_distance_m
separation_lower_bound_m
classification
permission
decision
```

`aggregate_clearance_summary` scope is frozen to:

`AUTHORITATIVE_FINE_PASS_1_ONLY`

All fields in `aggregate_clearance_summary` are derived exclusively from the 469 semantic snapshots and 38,927 collision queries of authoritative fine pass 1.

Therefore:

```text
total_query_count = 38,927
found_query_count + censored_no_result_count = 38,927
```

The coarse sensitivity pass is summarized only in `coarse_sensitivity_summary`.

Fine reproducibility pass 2 is summarized only in `reproducibility_summary`.

Neither coarse observations nor fine pass 2 observations may be included in `aggregate_clearance_summary` minima, event counts, or failure counts.

This prevents duplicated observations from weighting scientific aggregate evidence more than once.

`aggregate_clearance_summary` has this exact schema:

```text
total_query_count
found_query_count
censored_no_result_count

minimum_observed_signed_distance:
    null
    OR
    {
        signed_distance_m,
        semantic_snapshot_index,
        pair_index,
        pair_id
    }

minimum_forbidden_observed_signed_distance:
    null
    OR
    {
        signed_distance_m,
        semantic_snapshot_index,
        pair_index,
        pair_id
    }

contact_band_event_count
material_penetration_event_count
forbidden_failure_count
support_material_penetration_count
required_support_missing_count
```

`minimum_observed_signed_distance` may be null only when `found_query_count` is zero. `minimum_forbidden_observed_signed_distance` may be null only when the found-query population governed by `FORBIDDEN` is zero.

The `0.050 m` lower bound from a no-result query must never be inserted into either observed signed-distance minimum. It remains censored lower-bound evidence only.

No-result evidence is censored. `0.050 m` is a separation lower bound, not an exact clearance. Aggregate evidence must distinguish observed signed-distance minima from censored lower bounds.

B3.2 must not copy historical absolute paths from B2 provenance. New evidence records repository-relative or logical identities plus exact hashes only.

The artifact must contain no timestamp, username, home-directory path, temporary path, drive-qualified path, or other machine-local identity.

## 16. Exact serialization contract

B3.2 inherits the exact B3.1 canonical serialization contract:

```python
json.dumps(
    artifact,
    sort_keys=True,
    indent=2,
    allow_nan=False,
    ensure_ascii=False,
) + "\n"
```

The resulting text is encoded as UTF-8. It contains one trailing LF.

Portable-evidence validation must run against the complete serialized text before any canonical write. SHA-256 is calculated over the exact serialized bytes, not a reparsed or reformatted representation.

No alternative serializer or environment-dependent line-ending conversion is permitted.

## 17. Artifact write and partial-failure contract

The writer must refuse overwrite if either canonical JSON or its companion digest already exists.

Handled write sequence:

1. construct and validate the complete in-memory artifact;
2. serialize deterministically and run portable-evidence validation;
3. create the JSON exclusively;
4. write, flush, and `fsync` the JSON;
5. create the companion digest exclusively;
6. write, flush, and `fsync` the digest;
7. independently verify companion structure and the exact JSON SHA-256.

If handled digest creation fails after JSON creation, the writer must remove the newly created JSON before propagating the failure.

A canonical B3.2 result is valid only when:

1. the JSON exists;
2. the companion digest exists;
3. the companion content is structurally exact;
4. the SHA-256 verifies against the exact JSON bytes.

An orphaned JSON or digest caused by abnormal process or OS termination is invalid evidence. Subsequent verification must fail closed.

This protocol does not claim impossible two-file crash atomicity. Handled infrastructure failures must not intentionally finalize a canonical evidence pair.

Scientific PASS and scientific FAIL both retain a valid, verified evidence pair. Infrastructure failure does not produce an accepted scientific result.

## 18. Test plan

### Entry criteria

Implementation and qualification may begin only after all entry criteria are explicitly authorized:

- B3.1 remote freeze is PASS;
- PR #5 metadata reconciliation is PASS;
- B3.2 specification review and freeze are PASS;
- the working tree is clean before implementation;
- branch and repository lineage match the authorized baseline;
- frozen predecessor artifacts and companion digests verify;
- the exact qualified PyBullet/KUKA runtime is available;
- implementation scope and expected files are separately authorized.

### Required tests

Numeric tests:

- `None`, boolean, string, NaN, positive infinity, and negative infinity rejection;
- exact `-epsilon`, zero, and `+epsilon` classification;
- `math.nextafter()` on both sides of `-epsilon` and `+epsilon`;
- finite signed-distance preservation without absolute-value conversion.

Input and structure tests:

- missing required field versus explicit null;
- empty B2 route;
- route with other than eight states or seven legs;
- six-joint and eight-joint vectors;
- empty and duplicate pair inventories;
- unknown body or link;
- disconnected or invalid client;
- malformed found/no-result evidence combinations.

Interpolation tests:

- zero movement;
- exact step;
- just-over-step;
- mixed signed deltas;
- exact endpoint tuple preservation;
- shared-endpoint de-duplication;
- coarse/fine exact nesting;
- expected interval counts;
- `234/236` coarse configuration/snapshot accounting;
- `467/469` fine configuration/snapshot accounting;
- seven-dimensional finite joint-limit validation.

Component-phase tests:

- every route segment and final HOME semantic state;
- SOURCE_PICK PRE and POST at identical robot q;
- DESTINATION_PLACE PRE and POST at identical robot q;
- carried pose composition from world link frame and frozen local transform;
- fixed actual predicted-release pose after release;
- no nominal destination snapping;
- component/robot forbidden for base and every link.

Collision-policy and inventory tests:

- complete `FORBIDDEN`, `PERMITTED_SUPPORT`, and `REQUIRED_SUPPORT` decision matrix;
- all 21 robot-self pairs in exact B3.1 order;
- all 48 robot/environment pairs in exact nested order;
- all eight component/robot pairs;
- all six component/environment pairs;
- exact query direction for every category;
- exactly 83 queries per semantic snapshot;
- exactly 97,442 queries for a complete non-short-circuited protocol;
- support permission boundaries;
- forbidden numerical-band contact;
- support material penetration;
- required-support missing for both separated and beyond-horizon observations.

FK and API-boundary tests:

- terminal world link fields `4/5` are used;
- COM/inertial fields `0/1` cannot satisfy the test;
- explicit `physicsClientId` scoping;
- prohibited executable calls detected through AST or equivalent executable-code inspection rather than naive text matching.

Scientific and infrastructure result tests:

- scientific failures accumulate without short-circuiting;
- multiple simultaneous failure categories remain visible;
- `overall_result` is independent of first-failure category;
- scientific FAIL retains a valid deterministic artifact and digest;
- handled infrastructure failure does not intentionally finalize an evidence pair;
- orphan JSON or digest is rejected;
- malformed or incomplete evidence cannot become PASS.

Reproducibility tests:

- two genuinely fresh fine DIRECT sessions;
- matching found/no-result states;
- found/no-result mismatch fails closed;
- signed-distance spread enforcement;
- identical phases, pair order, decisions, failures, and overall result;
- coarse observations agree with nested fine observations.

Mutation and provenance tests:

- B1.2, B2, and B3.1 artifact-byte drift;
- companion-digest drift;
- PyBullet package/API/binary drift;
- KUKA URDF and asset-manifest drift;
- epsilon and query-horizon drift;
- waypoint, transform, phase, pair-order, and interpolation drift;
- repository lineage failure;
- machine-path contamination.

Artifact tests:

- exact canonical JSON formatting and UTF-8 bytes;
- exactly one trailing LF;
- deterministic ordering;
- finite-only serialization;
- portable logical paths only;
- no timestamp or machine-local data;
- byte-reproducible regeneration;
- overwrite refusal;
- structurally exact companion digest;
- independent SHA-256 verification.

No percentage code-coverage target is introduced by this specification.

### Exit criteria

B3.2 implementation may be proposed for freeze only when:

- every focused B3.2 test passes;
- B1/B2/B3.1 predecessor regression passes;
- the meaningful full Prototype 5 regression passes;
- any direct-workspace environmental failures are classified separately from product assertions;
- the B3.2 artifact reproduces deterministically;
- the companion digest independently verifies;
- all predecessor hashes remain unchanged;
- `git diff --check` passes;
- changed-file scope equals the separately authorized implementation allowlist;
- no file is staged, committed, pushed, or used to update the PR before manual review;
- claims remain within section 20.

## 19. Security and integrity threat model

B3.2 is an offline deterministic qualification component. Relevant threats and controls are:

| Threat | Required mitigation |
|---|---|
| Frozen artifact tampering | Artifact and companion SHA verification; immutable allowlist |
| Dependency or binary drift | Exact package/API/binary hashes; exact qualified wheel in CI |
| KUKA URDF or mesh drift | URDF and complete KUKA asset-manifest hashes |
| Collision-pair suppression or reordering | Frozen pair identities, directions, ordering, and exact count 83 |
| Epsilon manipulation | Literal frozen epsilon and direct mutation tests |
| Sampling-resolution manipulation | Frozen interval algorithm and exact configuration counts |
| Component-phase manipulation | Explicit phase and PRE/POST state machine with direct tests |
| Scientific failure suppression | Complete non-short-circuited failure list and summary counts |
| Evidence tampering or partial evidence | Canonical serialization, exclusive writes, companion digest, fail-closed verification |
| Machine-local provenance leakage | Logical paths and full serialized-text portability validation |
| Wrong commit qualified in CI | Exact triggering-SHA checkout and predecessor-lineage verification |

The following controls are not applicable to B3.2 core because it has no corresponding attack surface:

```text
SQL injection
IAM
web authentication
web-session threats
network request timeout
horizontal scaling
cache invalidation
```

No untrusted model output may control the epsilon, sampling resolution, phase state machine, collision-pair inventory, evidence serializer, or result aggregation.

## 20. Claim matrix

| Claim | Permitted |
|---|---:|
| “No forbidden collision/contact was observed at any configuration sampled along the frozen B2 route under the declared deterministic discrete B3.2 protocol.” | Yes, only on scientific PASS |
| “The frozen route was evaluated at the declared authoritative fine grid.” | Yes, if evidence verifies |
| “The repeated fine pass reproduced within the declared tolerance.” | Yes, if evidence verifies |
| “The trajectory is collision-free.” | No |
| “Continuous collision freedom was proven.” | No |
| “Inter-sample collision is impossible.” | No |
| “The robot motion is dynamically executable or safe.” | No |
| “Controller, velocity, acceleration, grasp, placement, or settling was validated.” | No |
| “The simulated result validates the physical KUKA robot.” | No |
| “Industrial safety or certification was established.” | No |

A scientific FAIL supports only the recorded discrete geometric failure under the frozen B3.2 protocol. It does not establish dynamic or real-world failure beyond that model.

## 21. Dissertation connection

B3.2 extends the project’s zero-trust boundary downstream of language-model proposal and deterministic governance:

```text
UNTRUSTED MODEL PROPOSAL
        ↓
STRUCTURAL / SEMANTIC / AMBIGUITY / SAFETY VALIDATION
        ↓
EXECUTION ELIGIBILITY
        ↓
EXECUTION AUTHORITY
        ↓
DETERMINISTIC DISCRETE GEOMETRIC QUALIFICATION
        ↓
ONLY THEN: POTENTIAL SIMULATED EXECUTION
```

An AI-generated plan does not obtain simulated execution legitimacy merely because it is structurally valid, semantically valid, policy-accepted, or authority-bearing. The frozen route remains subject to an independent deterministic geometric qualification gate.

A scientific B3.2 FAIL is valid dissertation evidence. It demonstrates that upstream validity and authority do not guarantee downstream geometric qualification. Such a failure must be preserved and must never trigger silent alteration of frozen route inputs.

## 22. Specification gate

```text
B3_2_SPEC_DOCUMENT = READY_FOR_MANUAL_REVIEW
B3_2_IMPLEMENTATION = NOT AUTHORIZED
```
