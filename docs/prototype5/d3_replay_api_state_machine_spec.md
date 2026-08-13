# D3 Frozen Evidence Replay API and Coordinator State-Machine Specification

Status: normative D3.1 specification

Baseline commit: `6c0706c5117365e4cdb166243732472b09aa191d`

Implementation authority: withheld pending separate D3.2 manual review

## 1. Executive Architecture Summary

### 1.1 Purpose and research alignment

D3 exposes the existing immutable B2/B3.1/B3.2 evidence through one server-owned PyBullet GUI and an examiner-facing browser control surface. Its sole research function is to demonstrate that governance execution eligibility does not establish downstream geometric validity:

```text
UNTRUSTED_PROPOSAL
→ GOVERNANCE_DECISION
→ EXECUTION_ELIGIBILITY
→ QUALIFICATION_REPLAY_ACCESS
→ DOWNSTREAM_GEOMETRIC_QUALIFICATION
→ PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED
```

Passing layer `N` does not establish layer `N+1`. The replay consumes existing evidence; it does not create a new research question, benchmark, model, planner, route, qualification result, or robotics-control claim.

The frozen scientific boundary is:

| Property | Normative value |
|---|---|
| B2 route | `HOME → SOURCE_HIGH → SOURCE_PICK → SOURCE_HIGH_RETURN → DESTINATION_HIGH → DESTINATION_PLACE → DESTINATION_HIGH_RETURN → HOME` |
| B2 artifact SHA-256 | `a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554` |
| B3.2 terminal state | `B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION` |
| B3.2 scientific failures | `118` |
| Failure code | `B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION` |
| Forbidden-contact failures | `0` |
| Support-material-penetration failures | `118` |
| Required-support-missing failures | `0` |
| Physics steps | `0` |
| Physical execution authority | `NOT_IMPLEMENTED` |

The following operations are prohibited throughout D3:

```text
stepSimulation                 = 0 calls
setRealTimeSimulation         = 0 calls
motor-control APIs            = 0 calls
inverse kinematics            = 0 calls
trajectory optimisation       = 0 calls
new planning                  = 0 calls
new collision queries         = 0 calls
new geometric qualification  = 0 executions
synthetic interpolation       = 0 frames
physical execution authority  = NOT_IMPLEMENTED
```

### 1.2 Non-goals

D3 does not:

- modify frozen B2, B3.1, or B3.2 bytes, hashes, geometry, routes, tolerances, observations, results, or claims;
- claim continuous collision freedom, dynamics, velocity, timing, controllability, sim-to-real validity, industrial certification, physical safety, or physical executability;
- stream video, recreate the scene in a browser renderer, introduce WebSockets, or expose a remote graphics protocol;
- enable replay for any scenario other than `FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY`;
- reinterpret the historical D2 field `d2_replay_enabled=false`; D3 capability is an additive contract;
- use browser unload as a server-resource cleanup guarantee;
- add subprocess isolation unless the escalation criteria in Section 2.12 are proven.

### 1.3 Trust and authority boundary

The browser controls navigation only. The server resolves the registered scenario, evidence binding, artifact identities, frame sequence, scene reconstruction, runtime provenance, B3.2 result, and scientific failure metadata.

Browser requests MUST NOT contain:

```text
joint vectors
component poses
robot or component body identifiers
URDF names or paths
scene geometry
route states or route identity
waypoints
collision observations or pair identities
collision tolerances or exclusions
artifact paths or digests
B2/B3 binding selection
scientific result or failure values
physical-execution fields
```

Unknown request properties are rejected. Omission, `null`, empty strings, malformed identifiers, non-finite numbers, stale session tokens, and stale versions fail closed.

The server may return bounded evidence provenance, but never private scientific inputs or filesystem identities. The browser must render server state without deriving authority.

### 1.4 End-to-end ownership architecture

```text
Browser
  │ strict navigation command
  ▼
FastAPI request boundary
  │ immutable command envelope
  ▼
single-slot coordinator command channel
  │ exactly one admitted unsettled mutation
  ▼
one coordinator-owned thread
  │ every PyBullet API call
  ▼
one PyBulletEvidenceReplaySession
  │ exact validated frozen frame assignment/readback
  ▼
native PyBullet GUI
```

HTTP worker threads never access PyBullet, including `isConnected`, readback, camera, and disconnect operations. HTTP GET returns an immutable coordinator state projection protected by coordinator synchronization; it does not query PyBullet.

## 2. Architectural Pillars Assessment (Microsoft WAF Aligned)

### 2.1 Reliability: immutable 469-frame model

`FrozenReplaySnapshot` remains the strict ten-key-snapshot model. D3 adds an immutable `FrozenReplayFrame` for all `469` exact semantic snapshots already present in the SHA-attested B3.2 artifact. The distinction is normative:

```text
FrozenReplayFrame     = one of 469 exact artifact frames
FrozenReplaySnapshot  = one of 10 registered semantic/key boundary frames
```

The frame collection is a tuple. Construction fails before `pb.connect` unless all aggregate and per-frame invariants pass.

#### Whole-sequence invariants

- frame count is exactly `469`;
- semantic snapshot indices are the exact ordered sequence `0..468`;
- route-configuration indices are ordered in `0..466`;
- configuration indices are unique except `118` and `350`, which each occur exactly twice;
- duplicated configuration `118` consists only of semantic snapshots `118 PRE` and `119 POST` at `SOURCE_PICK / ATTACHMENT_BOUNDARY`;
- duplicated configuration `350` consists only of semantic snapshots `351 PRE` and `352 POST` at `DESTINATION_PLACE / RELEASE_BOUNDARY`;
- segment indices are exactly `0..6` in route order;
- segment interval counts are exactly `(78, 40, 38, 154, 40, 38, 78)`;
- each sample index is an integer in `[0, segment_interval_count]`;
- `alpha` is a finite float in `[0.0, 1.0]` and equals `segment_sample_index / segment_interval_count` under the artifact's canonical numeric representation;
- each non-boundary route configuration appears exactly once;
- every frame contains exactly `83` recorded observations;
- no semantic frame is missing, duplicated, reordered, synthesized, or discarded.

#### Per-frame invariants

- exactly seven finite, strict floating-point joint values;
- exactly three finite, strict floating-point component-position values;
- exactly four finite, strict floating-point quaternion values;
- quaternion norm equals `1.0` within the existing frozen replay absolute tolerance `1e-9`;
- phase is one of `SOURCE_SUPPORTED`, `ATTACHMENT_BOUNDARY`, `CARRIED`, `RELEASE_BOUNDARY`, `DESTINATION_SUPPORTED`;
- boundary is one of `NONE`, `PRE`, `POST` and is valid for the phase;
- non-boundary endpoint route states follow the exact B2 route;
- intermediate route state is exactly `INTERPOLATED`;
- each joint vector equals the artifact's frozen application of `q(t) = q0 + t × (q1 - q0)` between its exact adjacent B2 endpoint vectors;
- attachment/release duplicate frames retain the same route configuration and joint vector while preserving their distinct frozen component phase/pose;
- the ten existing `FrozenReplaySnapshot` values are exact projections from frame indices `0, 78, 118, 119, 157, 311, 351, 352, 390, 468`.

Validation arithmetic checks artifact consistency only. It does not generate a frame, collision result, motion plan, or scientific observation.

### 2.2 Security: presentation claim boundary

Every active replay view displays all three strings:

```text
EVIDENCE REPLAY
NOT PHYSICAL EXECUTION
DISCRETE SAMPLED STATES — NO DYNAMIC TIMING
```

The first two are frozen claim labels. The third is a presentation clarification, not an authority-taxonomy state.

Internal frame indices remain the exact zero-based domain `0..468`. Examiner-facing text maps index `i` to `Frame i+1 of 469`, producing `Frame 1 of 469` through `Frame 469 of 469`; this display-only offset never changes evidence identity. The UI MUST NOT label presentation progression as robot time, trajectory time, velocity, acceleration, dynamics, or feasibility. If presentation elapsed time is shown, the label is exactly `Presentation elapsed time` and it is excluded from downloaded scientific evidence.

Smooth visual progression does not establish:

- continuous collision freedom between samples;
- dynamic feasibility;
- controller feasibility;
- physical safety;
- physical execution authority;
- a changed B3.2 result.

### 2.3 Reliability: single-owner coordinator and bounded admission

The coordinator owns exactly one non-daemon worker thread and at most one `PyBulletEvidenceReplaySession`. The coordinator starts during FastAPI lifespan startup and terminates during lifespan shutdown.

All PyBullet calls occur on the owner thread:

```text
connect
resetSimulation
scene/body creation
joint/pose assignment
joint/pose readback
camera reset
isConnected
disconnect
```

The command channel capacity is exactly one admitted unsettled mutating command, including the command currently executing. There is no pending-command backlog. A coordinator-state lock protects both the admission flag and the authoritative session/control projection; `Queue(maxsize=1)` alone is insufficient because it does not count an item already removed for execution. Admission is non-blocking:

- free slot: accept one immutable command;
- occupied slot: HTTP `429`, code `REPLAY_COMMAND_CHANNEL_FULL`, zero mutation;
- shutdown started: HTTP `503`, code `REPLAY_SERVER_SHUTTING_DOWN`, zero mutation.

HTTP waiter settlement and coordinator command settlement are distinct lifecycles. A condition/future transfers an owner result to the waiting HTTP handler, but handler detachment never settles an executing command. The admission slot remains occupied and `command_in_flight` remains `true` until the owner reaches exactly one of:

- committed success;
- stable failure;
- pre-execution deadline expiry with zero mutation.

Publishing `504 REPLAY_CONTROL_SETTLEMENT_UNKNOWN` releases only the HTTP waiter. It does not release admission, clear `command_in_flight`, cancel the owner operation, or permit another mutation. Any new mutation while the detached command remains unsettled returns `429 REPLAY_COMMAND_CHANNEL_FULL`. The channel stores no historical command stream.

Expired commands that have not started are rejected as `REPLAY_COMMAND_EXPIRED` and never execute. Once a PyBullet call starts, HTTP timeout cannot cancel or roll back it; Section 2.9 governs recovery.

Shutdown rejects new admissions and resolves an admitted but unstarted command as `REPLAY_SERVER_SHUTTING_DOWN`. If a native call has started, the shutdown deadline bounds waiting and detection only; it cannot force Python or native-thread settlement. The coordinator never drains a backlog because no backlog exists.

### 2.4 Reliability: lifecycle state machine

Internal replay-session lifecycle states while the coordinator service is running are closed and exhaustive:

```text
IDLE
STARTING
PAUSED
PLAYING
COMPLETED
STOPPING
FAILED
CLEANUP_FAILED
```

`STARTING` and `STOPPING` are transient internal command phases only. They are never emitted in `Prototype5ReplayStateV1.lifecycle_state`. The public lifecycle enum is exactly `IDLE | PAUSED | PLAYING | COMPLETED | FAILED | CLEANUP_FAILED`. While an internal transient executes, the public projection retains the last committed stable lifecycle and `command_in_flight=true` reports unsettled ownership. During provisional START, that stable public projection is canonical IDLE. Poll requests are single-flight and browser operation identity prevents an earlier equal-version poll from replacing local command ownership.

FastAPI lifespan termination is outside the replay-session lifecycle enum. It creates neither a ninth internal replay-session state nor another public lifecycle value.

Two independent session-scoped monotonically increasing versions are mandatory:

```text
control_version     compare-and-set token for client mutation ownership
projection_version  ordering token for every committed authoritative projection
```

Both are strict integers in `[0, 9007199254740991]` and are monotonic only within one non-null `session_id`. Versions from different session IDs are not numerically comparable. Canonical IDLE is exact:

```text
lifecycle_state    = IDLE
session_id         = null
control_version    = 0
projection_version = 0
current_frame      = null
command_in_flight  = false
last_error_code    = null
available_controls = (START)
```

During unsettled provisional START, the public committed projection remains `IDLE/null/0/0/null`, `last_error_code=null`, with `command_in_flight=true` and `available_controls=()` until owner settlement. START success initializes the new session at `control_version=1` and `projection_version=1`. A stable START failure that retains the newly allocated failed session also initializes that session at `1/1` in `FAILED` or `CLEANUP_FAILED`; it is not described as an increment from IDLE.

No version wraps, saturates, changes sign, or loses integer precision. Exact exhaustion behavior is frozen below.

Version advancement is exact:

| Committed event | `control_version` | `projection_version` |
|---|---:|---:|
| START success | initialize new session to `1` | initialize new session to `1` |
| stable START failure retaining session | initialize failed session to `1` | initialize failed session to `1` |
| RESUME | `+1` | `+1` |
| automatic intermediate playback frame | unchanged | `+1` |
| PAUSE | `+1` | `+1` |
| NEXT/PREVIOUS | `+1` | `+1` |
| RESET_VIEW | `+1` | `+1` |
| automatic final-frame transition to COMPLETED | `+1` | `+1` |
| GUI closure or frame/readback failure | `+1` | `+1` |
| idle expiry, cleanup succeeds | terminate session; canonical IDLE `0` | terminate session; canonical IDLE `0` |
| idle expiry, cleanup fails | same session `+1` | same session `+1` |
| STOP cleanup succeeds | terminate session; canonical IDLE `0` | terminate session; canonical IDLE `0` |
| STOP cleanup fails | same session `+1` | same session `+1` |
| GET | unchanged | unchanged |

Version exhaustion is one fatal service-fault model for requested and automatic events. If any PAUSE, RESUME, NEXT, PREVIOUS, RESET_VIEW, STOP, automatic intermediate-frame advancement, automatic final-frame completion, failure publication, or idle-expiry publication would increment either counter beyond `9007199254740991`:

1. the requested or internal frame/state mutation does not occur;
2. both counters and the last committed projection remain unchanged;
3. future cadence scheduling stops;
4. the coordinator latches persistent `REPLAY_VERSION_EXHAUSTED`;
5. the owner thread attempts exact-client cleanup;
6. no new START or control is accepted;
7. every replay endpoint, including GET, returns only `503 {"code":"REPLAY_VERSION_EXHAUSTED"}`;
8. no successful replay DTO is emitted after the latch is set;
9. application restart is required and D3.2 qualification fails.

The latch is never cleared during the process lifetime. If cleanup succeeds, exact client/session ownership is released and the internal coordinator may settle to canonical IDLE, but the HTTP replay surface remains code-only `503` until restart. If cleanup fails, exact client/session ownership and the last committed projection remain internally retained; shutdown still attempts final exact-client cleanup, while the HTTP replay surface remains code-only `503` until restart. Detection by an automatic cadence/completion/timer event has the same outcome as detection by an HTTP-originated command and requires no waiting requester. A request-driven overflow is caused by the admitted external command itself: its mutation does not occur, its waiter receives code-only `503`, and admission releases after fatal settlement. An automatic event cannot latch exhaustion while a different external command is already admitted but unexecuted under Section 2.7 arbitration. The fault never fabricates an unversioned lifecycle transition, wraps a counter, or creates a ninth public lifecycle state.

Automatic intermediate frames therefore never invalidate PAUSE or STOP compare-and-set ownership. The browser supplies `expected_control_version`. Active projection ordering is the pair `(session_id, projection_version)`, never `projection_version` alone. Browser acceptance order is fixed:

1. reject a response whose local browser operation identity is obsolete;
2. verify session identity or an explicitly owned authoritative session transition;
3. compare `projection_version` only when both non-null session IDs are equal.

A response for a no-longer-current session is stale even when its numeric projection version exceeds the current session's version. A successful locally owned START response may establish a new session from local IDLE; an authoritative reconciliation GET may establish the server session after unknown START settlement; a successful current-session STOP response or authoritative reconciliation GET may establish IDLE. All other session replacement is rejected. An IDLE projection has `session_id=null` and is a distinct coordinator state; its version is never numerically ordered against an active-session projection.

#### Control/state matrix

| State | START | PAUSE | RESUME | NEXT | PREVIOUS | STOP | RESET_VIEW |
|---|---|---|---|---|---|---|---|
| `IDLE` | `STARTING` | stale `409` | stale `409` | stale `409` | stale `409` | unexpired exact tombstone retry only while no newer session exists; otherwise stale `409` | stale `409` |
| `STARTING` | active `409` | busy `429` | busy `429` | busy `429` | busy `429` | busy `429` | busy `429` |
| `PAUSED` | active `409` | invalid `409` | `PLAYING` | adjacent frame or boundary `409` | adjacent frame or boundary `409` | `STOPPING` | `PAUSED` |
| `PLAYING` | active `409` | `PAUSED` | invalid `409` | invalid `409` | invalid `409` | `STOPPING` | `PLAYING` |
| `COMPLETED` | active `409` | invalid `409` | invalid `409` | boundary `409` | frame `467`, then `PAUSED` | `STOPPING` | `COMPLETED` |
| `STOPPING` | active `409` | busy `429` | busy `429` | busy `429` | busy `429` | busy `429` until tombstone exists | busy `429` |
| `FAILED` | active `409` | invalid `409` | invalid `409` | invalid `409` | invalid `409` | cleanup to `IDLE` or `CLEANUP_FAILED` | invalid `409` |
| `CLEANUP_FAILED` | cleanup `503` | invalid `409` | invalid `409` | invalid `409` | invalid `409` | retry cleanup | invalid `409` |

#### Event transition table

| Source | Command/event | Guard | Side effect | Destination | HTTP/result |
|---|---|---|---|---|---|
| `IDLE` | `START` | registered scenario; slot free | allocate opaque session; attest; open the server-configured replay client; apply frame `0` | `PAUSED` | `200`; control/projection versions `1/1` |
| `IDLE` | `START` | scenario unknown | none | `IDLE` | `404 REPLAY_SCENARIO_NOT_FOUND` |
| `IDLE` | `START` | scenario not replay-compatible | none | `IDLE` | `409 REPLAY_SCENARIO_NOT_REPLAYABLE` |
| `STARTING` | open/apply succeeds | same admitted start | publish frame `0` | `PAUSED` | `200`; initialize retained session `1/1` |
| `STARTING` | runtime attestation fails | same admitted start | no PyBullet client created; retain failed session | `FAILED` | `503 REPLAY_RUNTIME_INTEGRITY_FAILED`; initialize failed session `1/1`; `last_error_code=REPLAY_RUNTIME_INTEGRITY_FAILED` |
| `STARTING` | scene/apply fails, cleanup succeeds | same owned client | disconnect exact client; retain failed session for acknowledgement | `FAILED` | `500 REPLAY_SCENE_FAILED`; initialize failed session `1/1`; `last_error_code=REPLAY_SCENE_FAILED` |
| `STARTING` | cleanup fails | exact ownership retained | retain cleanup ownership | `CLEANUP_FAILED` | `503 REPLAY_CLEANUP_UNRESOLVED`; initialize failed session `1/1`; `last_error_code=REPLAY_CLEANUP_UNRESOLVED` |
| `PAUSED` | `RESUME` | session/control version current; not final frame | start presentation scheduler | `PLAYING` | `200`; control/projection `+1/+1` |
| `PLAYING` | cadence event | client connected; no external mutation admitted; next intermediate frame exists | apply/read back exactly one frame | `PLAYING` | internal; control/projection `+0/+1` |
| `PLAYING` | cadence event | no external mutation admitted; frame `468` committed | stop scheduler | `COMPLETED` | internal; control/projection `+1/+1` |
| `PLAYING` | `PAUSE` | session/control version current | stop scheduling before next frame | `PAUSED` | `200`; control/projection `+1/+1` |
| `PAUSED` | `NEXT_SNAPSHOT` | index `<468` | apply/read back index `+1` | `PAUSED` or `COMPLETED` at `468` | `200`; control/projection `+1/+1` |
| `PAUSED` | `PREVIOUS_SNAPSHOT` | index `>0` | apply/read back index `-1` | `PAUSED` | `200`; control/projection `+1/+1` |
| `PAUSED/PLAYING/COMPLETED` | `RESET_VIEW` | session/control version current | mode-specific view reset; scientific state unchanged | same state | `200`; control/projection `+1/+1` |
| `PAUSED/PLAYING/COMPLETED/FAILED/CLEANUP_FAILED` | `STOP` | session/control version current | stop scheduler; disconnect exact client | canonical `IDLE` or same-session `CLEANUP_FAILED` | success: `200`, IDLE/null/0/0, `last_error_code=null`, tombstone; failure: `503`, same-session `+1/+1`, `last_error_code=REPLAY_CLEANUP_UNRESOLVED` |
| `PAUSED/PLAYING/COMPLETED` | GUI liveness loss | owner observes disconnected client | attempt exact ownership settlement | `FAILED` or `CLEANUP_FAILED` | settled: `FAILED`, `last_error_code=REPLAY_GUI_CLOSED`; unresolved: `CLEANUP_FAILED`, `last_error_code=REPLAY_CLEANUP_UNRESOLVED`; control/projection `+1/+1` |
| any active state | frame/application/readback failure | exact owner | stop scheduler; attempt disconnect | `FAILED` or `CLEANUP_FAILED` | cleanup succeeds: `FAILED`, `last_error_code=REPLAY_SCENE_FAILED`; cleanup fails: `CLEANUP_FAILED`, `last_error_code=REPLAY_CLEANUP_UNRESOLVED`; control/projection `+1/+1` |
| any active state | idle lifetime expires | no accepted client mutation for `600000 ms` | stop scheduler; disconnect exact client | canonical `IDLE` or same-session `CLEANUP_FAILED` | success: IDLE/null/0/0, no tombstone, `last_error_code=null`; failure: same-session `+1/+1`, `last_error_code=REPLAY_CLEANUP_UNRESOLVED` |
| any state | FastAPI shutdown | lifespan shutdown initiated | reject admission; settle command; close; join | terminated or shutdown failure | bounded outcome |

The matrix assumes syntactically valid input, correct session, current control version, no shutdown, and no command already in flight. Section 2.6 freezes higher-precedence failures. Under those guards, any state/control pair not explicitly allowed returns `409 REPLAY_CONTROL_INVALID_STATE` with zero mutation.

### 2.5 Security and reliability: control semantics

Only these D0-registered controls exist:

```text
START
PAUSE
RESUME
NEXT_SNAPSHOT
PREVIOUS_SNAPSHOT
STOP
RESET_VIEW
```

#### START

- accepted only through `/api/v1/replay/start` for the registered replay scenario;
- allocates a cryptographically random 256-bit URL-safe `session_id`;
- attests all artifact/runtime identities before GUI connection;
- opens exactly one server-configured session (`GUI` in the examiner runtime; `DIRECT` in deterministic CI) and applies exact frame zero;
- returns `PAUSED`;
- duplicate start while any non-`IDLE` session exists returns `409 REPLAY_SESSION_ACTIVE`;
- start while cleanup is unresolved returns `503 REPLAY_CLEANUP_UNRESOLVED`.

Session allocation during admission is provisional until owner settlement. If START expires before owner execution begins, the coordinator removes that provisional allocation, publishes no active session, clears `command_in_flight`, releases admission, and returns `504 REPLAY_COMMAND_EXPIRED` with zero mutation. If owner execution begins, Section 2.9 governs unknown settlement; START is never automatically retried.

#### PAUSE and RESUME

`PAUSE` stops presentation scheduling only. It does not pause physics because no physics executes. `RESUME` schedules sequential exact frames from the current index. Neither command changes frame state directly.

#### NEXT_SNAPSHOT and PREVIOUS_SNAPSHOT

Navigation changes exactly one frame index. There is no clamping, wrapping, skipping, interpolation, or synthesized state. Lower/upper bounds return `409 REPLAY_FRAME_BOUNDARY` with zero mutation.

#### RESET_VIEW

`RESET_VIEW` is mode-dependent and always preserves scientific state:

- `GUI`: the owner thread invokes the registered `resetDebugVisualizerCamera` operation; no HTTP worker calls the camera API;
- `DIRECT`: the coordinator performs a deterministic presentation no-op and invokes no graphical/debug-camera API.

Both modes return normal authoritative success and preserve:

```text
frame index
semantic snapshot index
route configuration
joint readback
component pose readback
qualification metadata
scientific failure values
```

It increments `control_version` and `projection_version` once because an accepted presentation control committed, not because scientific state changed. DIRECT and GUI responses are contract-identical except for server-internal connection mode, which is not exposed.

#### STOP and retry idempotency

An active `STOP` requires the current `scenario_id`, `session_id`, and `expected_control_version`. A stale session can never stop a newer session.

On successful stop, the exact session terminates and the returned projection is canonical IDLE: null session, versions `0/0`, null frame, `command_in_flight=false`, `last_error_code=null`, and `available_controls=(START)`. No successor session-scoped version exists after termination. The coordinator retains one immutable terminal tombstone for exactly `60000 ms`. The tombstone is keyed by the exact tuple:

```text
(scenario_id, session_id, expected_control_version, STOP)
```

An exact retry during tombstone retention returns the cached successful terminal response without another disconnect and without incrementing either version only when every condition holds under the coordinator-state lock:

- lifecycle is `IDLE`;
- no active or newer session exists;
- scenario, session, expected control version, and `STOP` match the tombstone exactly;
- the tombstone TTL has not expired.

If any active/newer session exists, the old tombstone is ineligible for response and the stale request returns `409 REPLAY_SESSION_STALE` with zero mutation. A new START therefore invalidates an older tombstone for response purposes even if its bounded storage has not yet expired. A cached S1 terminal projection must never be returned while S2 is active. Any different session, control version, scenario, control, or expired tombstone also returns `409 REPLAY_SESSION_STALE`. There is no anonymous, global, or sessionless stop operation, and exactly one bounded tombstone is retained.

### 2.6 Security: compare-and-set concurrency contract

Every active-session mutation request contains exactly:

```json
{
  "scenario_id": "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
  "session_id": "<opaque server-issued token>",
  "expected_control_version": 17,
  "control": "PAUSE"
}
```

`session_id` is an opaque concurrency/ownership token. It is not a scientific, replay-binding, execution-permit, or physical-authority identity.

Every registered replay route first executes a thread-safe, route-local fatal-fault preflight before request-body/model validation. If it observes persistent `REPLAY_VERSION_EXHAUSTED`, the route returns only `503 {"code":"REPLAY_VERSION_EXHAUSTED"}` without validating or resolving the request. If clear, normal closed validation and scenario resolution proceed.

The server then executes one deterministic mutating admission transaction. Steps 4–12 run under the same coordinator-state lock; the mandatory exhaustion re-check closes the race between route preflight and admission, and validation/reservation have no time-of-check/time-of-use gap:

1. perform the route-local version-exhaustion preflight;
2. validate the closed request schema and reject unknown fields;
3. resolve the sole server-registered replay scenario;
4. acquire the coordinator-state lock;
5. re-check persistent version exhaustion and return code-only `503` with zero mutation if latched;
6. reject server shutdown;
7. if lifecycle is `IDLE`, no active/newer session exists, and the request is an exact unexpired STOP tombstone match, return the cached terminal response;
8. otherwise compare `session_id` with the current active session; an active/newer session makes every older tombstone request stale;
9. compare `expected_control_version` with current `control_version`;
10. if `command_in_flight=true`, return `429 REPLAY_COMMAND_CHANNEL_FULL`;
11. validate the control against the current lifecycle state and frame boundary;
12. atomically set `command_in_flight=true`, reserve the sole admission slot, snapshot the immutable command/deadline, and release the state lock;
13. dispatch at most one mutation to the owner thread;
14. on owner committed success/stable failure, update both versions according to Section 2.4, publish one immutable projection, set `command_in_flight=false`, and release admission under the state lock;
15. on pre-execution expiry, publish zero mutation, set `command_in_flight=false`, and release admission under the state lock;
16. on HTTP waiter timeout after owner execution begins, detach the waiter only; retain `command_in_flight=true` and the admission slot until step 14.

START uses the same route preflight, validation sequence, state lock, and mandatory under-lock exhaustion re-check. After that re-check its exact precedence is:

1. reject a persistent version-exhaustion fault with `503 REPLAY_VERSION_EXHAUSTED`;
2. reject server shutdown with `503 REPLAY_SERVER_SHUTTING_DOWN`;
3. reject `CLEANUP_FAILED` with `503 REPLAY_CLEANUP_UNRESOLVED`;
4. reject any non-IDLE/current session with `409 REPLAY_SESSION_ACTIVE`;
5. reject an otherwise inconsistent occupied slot with `429 REPLAY_COMMAND_CHANNEL_FULL`;
6. atomically invalidate any older tombstone for response purposes, provisionally allocate the session, set `command_in_flight=true`, reserve admission, and dispatch one START command.

Concurrent START requests therefore produce exactly one admission and one `409 REPLAY_SESSION_ACTIVE`; they cannot both observe IDLE.

Failure before owner execution performs zero mutation. Request linearisation is exact: a replay request whose route preflight observes exhaustion returns `503` regardless of body validity. A request that passed preflight before the fault latched may finish non-mutating parsing/validation, but no mutation can pass the under-lock exhaustion re-check after the latch is visible. Error precedence is:

```text
route exhaustion preflight       → 503 REPLAY_VERSION_EXHAUSTED
request schema/scenario          → 404/409/422 scenario/request code
coordinator exhaustion re-check  → 503 REPLAY_VERSION_EXHAUSTED
server shutdown                  → 503 REPLAY_SERVER_SHUTTING_DOWN
eligible IDLE STOP tombstone retry → cached 200 terminal response
wrong session                    → 409 REPLAY_SESSION_STALE
wrong expected_control_version   → 409 REPLAY_CONTROL_VERSION_STALE
existing unsettled mutation      → 429 REPLAY_COMMAND_CHANNEL_FULL
illegal lifecycle/control        → 409 REPLAY_CONTROL_INVALID_STATE
frame boundary violation         → 409 REPLAY_FRAME_BOUNDARY
```

The state matrix in Section 2.4 applies only after all higher-precedence guards pass. Every guard has exactly one HTTP outcome; no table entry permits alternative status codes.

Stable consistency failures are:

| HTTP | Code | Meaning |
|---:|---|---|
| `404` | `REPLAY_SCENARIO_NOT_FOUND` | unknown scenario |
| `409` | `REPLAY_SCENARIO_NOT_REPLAYABLE` | registered but non-replay scenario |
| `409` | `REPLAY_SESSION_ACTIVE` | start attempted while session exists |
| `409` | `REPLAY_SESSION_STALE` | session token differs or tombstone unavailable |
| `409` | `REPLAY_CONTROL_VERSION_STALE` | expected control version differs |
| `409` | `REPLAY_CONTROL_INVALID_STATE` | control not legal in lifecycle state |
| `409` | `REPLAY_FRAME_BOUNDARY` | previous/next outside `0..468` |
| `422` | `REPLAY_REQUEST_INVALID` | null, empty, malformed, omitted, or unknown field |
| `429` | `REPLAY_COMMAND_CHANNEL_FULL` | one mutation already unsettled |
| `503` | `REPLAY_CLEANUP_UNRESOLVED` | exact client ownership not settled |
| `503` | `REPLAY_SERVER_SHUTTING_DOWN` | lifespan shutdown started |
| `503` | `REPLAY_RUNTIME_INTEGRITY_FAILED` | runtime/artifact identity mismatch |
| `503` | `REPLAY_VERSION_EXHAUSTED` | persistent fatal safe-integer exhaustion; every replay endpoint remains code-only `503` until restart |
| `500` | `REPLAY_SCENE_FAILED` | scene/frame application failed |
| `504` | `REPLAY_COMMAND_EXPIRED` | admitted command expired before owner execution; zero mutation |
| `504` | `REPLAY_START_TIMEOUT` | started START waiter detached; owner settlement remains authoritative |
| `504` | `REPLAY_CONTROL_SETTLEMENT_UNKNOWN` | started mutation did not settle before HTTP deadline |

### 2.7 Performance efficiency: playback

The server-owned presentation cadence is exactly `50 ms` per scheduled frame (`20` requested presentation frames/s). Frame `0` is applied by START; RESUME schedules the remaining `468` frame applications. The uninterrupted nominal cadence contribution is therefore `468 × 50 ms = 23.40 s`, excluding application/readback overhead. These values are UI operational parameters, not scientific measurements.

Playback rules:

- frame zero is applied by `START` and returned in `PAUSED`;
- `RESUME` schedules increasing frame indices;
- each cadence event applies and reads back exactly one frozen frame;
- scheduling never invokes a physics step;
- playback terminates at frame `468` in `COMPLETED`;
- no automatic looping, wrapping, interpolation, catch-up frame skipping, or time dilation;
- if frame application exceeds one cadence interval, the next frame waits; frames are never skipped;
- pause takes effect before the next not-yet-started frame;
- manual NEXT/PREVIOUS is prohibited while `PLAYING`.

Owner-thread arbitration is deterministic across all periodic internal work:

```text
ADMITTED EXTERNAL MUTATING CONTROL
>
ANY NOT-YET-STARTED PERIODIC INTERNAL EVENT
```

Periodic internal events are playback cadence, GUI-liveness polling, and idle-expiry evaluation. An owner/PyBullet operation already executing is atomic and finishes without interruption. Request arrival is not command admission: the atomic admission transaction is serialized after any already-started periodic operation publishes its result, so CAS validation observes that committed state. Immediately afterward, the owner checks and reserves the external-command slot before starting any new periodic event. If PAUSE, STOP, RESET_VIEW, or another lifecycle-valid external mutation is admitted, the owner processes it first. Once an external command is atomically admitted, no cadence frame, GUI-liveness poll, or idle-expiry action may start before that command executes; periodic work cannot mutate lifecycle or version state between completed external admission and execution.

After the admitted mutation settles, every periodic deadline is re-evaluated from the new authoritative state. Atomic admission of an accepted mutating control invalidates any pending idle-expiry eligibility; after settlement, the idle deadline is measured from that control's accepted activity. Continuously due periodic work cannot starve an admitted external control. If RESET_VIEW preserves PLAYING, the next exact sequential frame may start only after RESET_VIEW settles. PAUSE and STOP prevent further cadence execution according to their destination states. Deferred cadence work causes no wrapping, synthesis, catch-up, or frame skipping. Shutdown remains higher execution priority than an admitted external mutation because it is service termination rather than a periodic event; this shutdown priority does not clear or weaken a previously latched version-exhaustion fault or its HTTP envelope.

Computational bounds:

```text
frame storage            O(469) = O(1) for the frozen contract
per-frame assignment     O(7) joints = O(1)
command admission        O(1)
session lookup           O(1)
control-version comparison O(1)
projection ordering       O(1)
history retained         O(1): current state + one stop tombstone
```

### 2.8 Reliability: GUI liveness and manual closure

Only the owner thread calls `pb.isConnected`. While lifecycle is `PAUSED`, `PLAYING`, or `COMPLETED`, the owner checks GUI liveness every `500 ms`, independent of playback cadence.

External GUI closure produces:

```text
state             FAILED
last_error_code   REPLAY_GUI_CLOSED
frame identity    last successfully committed frame
new START         prohibited
required recovery STOP with current session/control version
```

The owner invokes the existing exact-client close path to settle local ownership. If close confirms the client already disconnected, ownership is settled but the coordinator remains `FAILED` with `last_error_code=REPLAY_GUI_CLOSED` until the client acknowledges with STOP. If cleanup throws or ownership cannot be proven, state becomes `CLEANUP_FAILED` with `last_error_code=REPLAY_CLEANUP_UNRESOLVED`; only current-session STOP may retry cleanup.

### 2.9 Reliability: timeout and lost-response semantics

The following invariant is absolute:

```text
browser abort/timeout
≠ HTTP task cancellation proof
≠ coordinator command cancellation proof
≠ PyBullet mutation rollback proof
≠ server/provider termination proof
```

An admitted command carries a monotonic deadline. If it expires before owner execution begins, it is discarded with `REPLAY_COMMAND_EXPIRED`, performs zero mutation, clears `command_in_flight`, and releases admission. For START, the provisional session allocation is also removed and authoritative state remains IDLE with no active session. If non-START execution has begun, the HTTP handler may detach and return `504 REPLAY_CONTROL_SETTLEMENT_UNKNOWN`; the owner continues to a committed outcome or stable failure while `command_in_flight=true` and admission remains occupied. If START execution has begun, the handler may detach and returns `504 REPLAY_START_TIMEOUT` under the identical ownership rule: `command_in_flight` remains true, admission remains occupied, and the owner continues to committed success or stable failure. The deadline bounds HTTP waiting/detection, not native execution.

The browser MUST NOT automatically retry a mutating request, including START, after timeout, network loss, abort, or unknown settlement. Recovery is:

```text
GET /api/v1/replay/state
→ wait/reconcile while command_in_flight remains true
→ recover authoritative session_id, control_version, projection_version,
  lifecycle_state, and last_error_code after owner settlement
→ replace local projection
→ issue a new command only from that state
```

The sole retry exception is eligible exact STOP retry under Section 2.5. A START failure that settles as `FAILED` or `CLEANUP_FAILED` remains server-owned even when the failed POST returned no successful DTO. The browser obtains the session ID and versions through GET, displays the stable failure, and may then issue only a lifecycle-valid recovery such as current-session STOP. No failed or timed-out START leaves browser ownership recovery undefined.

### 2.10 Operational excellence: strict HTTP contracts

#### `POST /api/v1/replay/start`

Request fields:

```text
scenario_id: literal FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY
```

No client session ID, frame, binding, or scientific input is accepted.

#### `POST /api/v1/replay/control`

Request fields:

```text
scenario_id:            registered replay scenario
session_id:             nonblank server-issued token, maximum 200 characters
expected_control_version: integer in [0, 9007199254740991]
control:                PAUSE | RESUME | NEXT_SNAPSHOT |
                        PREVIOUS_SNAPSHOT | STOP | RESET_VIEW
```

`START` is invalid on this endpoint.

#### `GET /api/v1/replay/state`

GET returns the immutable coordinator projection. It performs no PyBullet call, renews no lifetime, changes neither version nor `updated_at_utc`, and acquires no mutation slot. The frontend permits at most one poll request in flight. It first rejects obsolete local operation ownership, then validates session identity, and only for the same non-null session compares `projection_version`. A delayed S1 response is stale after S2 becomes current even when S1 has a larger numeric version. IDLE/null-session and active-session projections are accepted only through an explicitly owned authoritative transition or reconciliation path and are never ordered by numeric version alone.

#### Response DTO

Every successful endpoint returns `Prototype5ReplayStateV1`:

| Field | Type/invariant |
|---|---|
| `contract_id` | literal `PROTOTYPE5_D3_REPLAY_STATE_V1` |
| `contract_version` | literal `1.0.0` |
| `scenario_id` | literal registered replay scenario |
| `binding_id` | literal `FROZEN_B2_B3_2_EVIDENCE_V1` |
| `session_id` | opaque string for retained session; exactly `null` in canonical IDLE |
| `control_version` | integer in `[0,9007199254740991]`; exactly `0` in canonical IDLE; session-scoped CAS token otherwise |
| `projection_version` | integer in `[0,9007199254740991]`; exactly `0` in canonical IDLE; session-scoped ordering token otherwise |
| `lifecycle_state` | public closed enum `IDLE | PAUSED | PLAYING | COMPLETED | FAILED | CLEANUP_FAILED`; never `STARTING` or `STOPPING` |
| `command_in_flight` | strict boolean |
| `current_frame` | bounded frame summary for retained session; exactly `null` in canonical IDLE |
| `frame_count` | literal `469` |
| `key_snapshot_indices` | exact tuple `(0,78,118,119,157,311,351,352,390,468)` |
| `allowed_controls` | exact D0 order |
| `available_controls` | exact state-derived subset defined below; never authority-derived |
| `presentation_cadence_ms` | literal `50` |
| `b2_sha256` | frozen digest |
| `b3_2_sha256` | frozen digest `11c8b83f8c4d0545c9a8df604046a335acb00121a51bf6e1d5b39504991c1798` |
| `qualification` | exact immutable B3.2 projection |
| `presentation_labels` | exact three-label tuple |
| `physical_execution_authority` | literal `NOT_IMPLEMENTED` |
| `last_error_code` | exact `ReplayLastErrorCode` union defined below |
| `updated_at_utc` | UTC timestamp of the latest committed authoritative projection mutation; GET generation never changes it |

`ReplayLastErrorCode` is closed exactly:

```text
REPLAY_RUNTIME_INTEGRITY_FAILED
REPLAY_SCENE_FAILED
REPLAY_GUI_CLOSED
REPLAY_CLEANUP_UNRESOLVED
null
```

Projection mapping is deterministic:

| Committed projection/outcome | Exact `last_error_code` |
|---|---|
| canonical `IDLE` after successful STOP, successful idle expiry, or successful current-session STOP recovery | `null` |
| `PAUSED`, `PLAYING`, or `COMPLETED` | `null` |
| START runtime-attestation failure in `FAILED` | `REPLAY_RUNTIME_INTEGRITY_FAILED` |
| START scene/apply failure with successful cleanup in `FAILED` | `REPLAY_SCENE_FAILED` |
| START cleanup failure in `CLEANUP_FAILED` | `REPLAY_CLEANUP_UNRESOLVED` |
| frame/application/readback failure with successful cleanup in `FAILED` | `REPLAY_SCENE_FAILED` |
| frame/application/readback failure with failed cleanup in `CLEANUP_FAILED` | `REPLAY_CLEANUP_UNRESOLVED` |
| GUI closure with settled ownership in `FAILED` | `REPLAY_GUI_CLOSED` |
| GUI closure with unresolved cleanup/ownership in `CLEANUP_FAILED` | `REPLAY_CLEANUP_UNRESOLVED` |
| STOP cleanup failure in `CLEANUP_FAILED` | `REPLAY_CLEANUP_UNRESOLVED` |
| idle-expiry cleanup failure in `CLEANUP_FAILED` | `REPLAY_CLEANUP_UNRESOLVED` |

`REPLAY_VERSION_EXHAUSTED` is excluded because a persistent exhaustion latch emits no successful replay DTO. `REPLAY_OWNER_THREAD_SURVIVED` is excluded because it is lifespan/shutdown qualification evidence outside the live replay DTO. Request-validation, scenario, session, control-version, busy, boundary, pre-execution-expiry, timeout, and unknown-settlement HTTP errors commit no replay-session failure projection and therefore do not mutate `last_error_code`.

`available_controls` is deterministic and preserves D0 control order. If `command_in_flight=true` or FastAPI shutdown has begun, it is the empty tuple. A persistent version-exhaustion fault returns no successful DTO. Otherwise:

| Public lifecycle | Exact available controls |
|---|---|
| `IDLE` | `START` |
| `PAUSED` | `RESUME`; `NEXT_SNAPSHOT` only when index `<468`; `PREVIOUS_SNAPSHOT` only when index `>0`; `STOP`; `RESET_VIEW` |
| `PLAYING` | `PAUSE`; `STOP`; `RESET_VIEW` |
| `COMPLETED` | `PREVIOUS_SNAPSHOT`; `STOP`; `RESET_VIEW` |
| `FAILED` | `STOP` |
| `CLEANUP_FAILED` | `STOP` |

Internal STARTING/STOPPING phases have no public lifecycle value and no independent control availability; their public stable projection exposes `available_controls=()` because `command_in_flight=true`.

`current_frame`, when present, contains only:

```text
frame_index
semantic_snapshot_index
route_configuration_index
route_state
phase
boundary_snapshot
is_key_snapshot
```

Responses MUST NOT expose joint vectors, component poses, URDF identity/path, body IDs, local paths, geometry, waypoints, collision tolerances, raw observations, pair inventories, or browser-selectable B2/B3 identity.

Error responses use a strict closed envelope containing `code` only. Native exception text, filesystem information, PyBullet client IDs, and stack traces are not exposed.

Replay-specific `422 {"code":"REPLAY_REQUEST_INVALID"}` normalization is scoped only to the three replay routes. It MUST NOT install an application-global FastAPI validation handler or change any D0–D2.3 governance, manifest, status, speech, or voice error response. Regression tests compare all pre-existing non-replay validation responses before and after replay route registration.

The persistent version-exhaustion gate is replay-route scoped and precedes replay request-body/model validation. Once latched, syntactically valid or invalid requests to START, CONTROL, and STATE all receive only `503 {"code":"REPLAY_VERSION_EXHAUSTED"}`; no replay handler emits `422`, another replay error, or a successful DTO until process restart. Mutating routes also re-check the latch under the coordinator-state lock immediately before any admission decision. A request that passed preflight before latching may complete non-mutating validation, but the under-lock re-check returns code-only `503` and permits zero mutation. This priority does not alter any non-replay D0–D2.3 route contract and does not install an application-global validation handler.

### 2.11 Operational excellence: bounded lifetime and shutdown

Frozen operational constants:

| Constant | Value | Operational justification |
|---|---:|---|
| `REPLAY_COMMAND_CAPACITY` | `1` | one examiner, one mutable GUI, zero backlog |
| `REPLAY_STARTUP_DEADLINE_MS` | `15000` | bounded native GUI/runtime attestation startup margin |
| `REPLAY_CONTROL_SETTLEMENT_DEADLINE_MS` | `5000` | bounded local control/readback wait |
| `REPLAY_IDLE_SESSION_LIFETIME_MS` | `600000` | prevents orphan GUI while allowing a ten-minute explanation interval |
| `REPLAY_OWNER_SHUTDOWN_DEADLINE_MS` | `5000` | matches existing bounded local-process shutdown policy |
| `REPLAY_GUI_LIVENESS_POLL_MS` | `500` | at most 0.5 s external-close detection latency |
| `REPLAY_PRESENTATION_CADENCE_MS` | `50` | 20 presentation frames/s; no dynamic meaning |
| `REPLAY_STOP_TOMBSTONE_TTL_MS` | `60000` | bounded exact STOP response-loss recovery |

None of these constants is scientific evidence. They MUST NOT enter B2/B3 artifacts, evaluation results, trajectory/dynamics claims, or dissertation performance claims without a separate measured experiment.

Idle lifetime is measured from the last accepted mutating control. GET does not renew it. Expiry is owner-thread initiated and uses the same exact disconnect ownership checks as STOP, but it is not a STOP command and never creates a STOP retry tombstone. Successful expiry produces canonical IDLE: null session, versions `0/0`, null frame, `command_in_flight=false`, `last_error_code=null`, and `available_controls=(START)`; every later command carrying the expired session, including STOP, returns `409 REPLAY_SESSION_STALE`. Cleanup failure retains the same session in `CLEANUP_FAILED`, advances that session's versions once, and permits current-session STOP recovery.

FastAPI lifespan owns coordinator startup and shutdown. Shutdown executes:

1. reject new commands;
2. mark shutdown requested;
3. resolve an admitted but unstarted command as `REPLAY_SERVER_SHUTTING_DOWN`;
4. stop future frame scheduling;
5. wait at most the applicable frozen startup/control deadline for a started native call; this bounds waiting only and does not terminate the call;
6. if the native call settles, close the exact owned session on the owner thread;
7. join the owner thread for at most `5000 ms`;
8. inspect `is_alive()` after the join and verify owned-client disconnection only if the owner reached cleanup;
9. if the owner survives, report `REPLAY_OWNER_THREAD_SURVIVED`, never claim clean shutdown, fail D3.2 qualification, and trigger the process-isolation escalation gate;
10. if the owner terminates but exact-client ownership remains unresolved, report `REPLAY_CLEANUP_UNRESOLVED` and fail qualification.

No infinite queue wait, `join`, disconnect wait, or browser-unload dependency is permitted. Thread confinement provides serialization, not cancellation; `join(timeout)` only bounds the caller's wait.

### 2.12 Reliability trade-off: process-isolation escalation

D3.2 remains one process plus one owner thread. Subprocess isolation is eligible only if measured implementation evidence proves at least one condition:

- GUI shutdown exceeds `REPLAY_OWNER_SHUTDOWN_DEADLINE_MS`;
- external GUI closure destabilizes FastAPI request handling;
- PyBullet rejects or corrupts same-owner-thread access;
- the owner thread survives bounded shutdown;
- native GUI lifecycle corrupts coordinator state or client ownership.

Any trigger causes `D3_2_IMPLEMENTATION = HOLD` and requires a separate process-isolation architecture review. IPC, subprocess supervision, and cross-process state reconciliation are prohibited without that gate.

### 2.13 Security: recorded B3.2 failure presentation

The UI exposes this frozen evidence row:

```text
RECORDED FAILURE EXAMPLE
Semantic snapshot: 352
Route state: DESTINATION_PLACE
Phase: RELEASE_BOUNDARY
Boundary: POST
Pair index: 78
Signed distance: -9.290505685985613e-7 m
Decision: B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION
```

The adjacent text states:

```text
This is one recorded example from 118 scientific failures.
It is not the sole B3.2 failure.
B3.2 remains FAIL independently of governance acceptance.
```

The UI does not recompute the distance, collision classification, or failure decision.

## 3. Milestone-Based Plan of Action (POA)

### Phase 0 — D3.1 specification freeze

#### Objectives and deliverables

- review this document against D0–D3.0;
- prove exact scientific identities and no authority expansion;
- freeze state machine, API, constants, file surface, and acceptance matrix;
- stage/commit only after a separate exact-byte review.

#### Definition of Done

- no production/test/config mutation;
- no unspecified state, transition, deadline, queue behavior, or retry behavior;
- manual architectural approval recorded;
- D3.2 receives a separate mutation instruction.

### Phase 1 — D3.2 core domain and coordinator

#### Objectives and deliverables

- validate all 469 immutable frames before PyBullet connection;
- extend replay session with exact-frame application and view-only reset;
- implement single-slot/single-owner coordinator;
- add strict API DTOs and FastAPI lifespan ownership.

#### Definition of Done

- all frame-integrity and coordinator state-machine tests pass;
- 469/469 DIRECT readback passes;
- zero forbidden scientific API calls;
- every timeout and cleanup path reaches a bounded stable outcome;
- no frontend or D3.4 harness mutation occurs during D3.2.

### Phase 2 — D3.3 frontend integration and security

#### Objectives and deliverables

- strict runtime decoding;
- server session/control/projection-version reconciliation;
- exact registered controls;
- examiner-facing evidence/failure/claim-boundary presentation;
- D2.1-style operation ownership, abort, deadline, polling, and unmount cleanup.

#### Definition of Done

- no scientific input crosses browser-to-server boundary;
- stale responses and stale controls produce zero UI/server mutation;
- unknown/null/empty/malformed responses fail closed;
- no physical/dynamic authority is implied;
- accessibility and responsive semantics pass.

### Phase 3 — D3.4 hardening and qualification

#### Objectives and deliverables

- real browser/FastAPI/coordinator/DIRECT CI qualification;
- bounded local Windows GUI qualification;
- manual GUI-close and cleanup-failure rehearsal;
- complete D0–D2.3 regression.

#### Definition of Done

- 469/469 DIRECT readback;
- 469/469 Windows GUI readback;
- all valid and invalid transitions covered;
- zero residual PyBullet client or owner thread;
- exact authority/evidence labels visible;
- 600 px and 980 px layouts pass without overflow;
- repository cleanliness and frozen-artifact hashes pass.

### Phase 4 — D3 freeze and operational handoff

#### Objectives and deliverables

- manual source/diff audit;
- exact staging, staged-byte, committed-byte, GitHub-only push, exact-SHA CI, and reconciliation gates;
- documented local GUI launch/stop rehearsal.

#### Definition of Done

- exact-SHA CI passes;
- branch/local/remote divergence is `0 0`;
- worktree and index are clean;
- D3 is frozen before D4 begins.

### 3.1 Mandatory D3.2–D3.4 acceptance matrix

#### Frame integrity

- exact count `469` and ordered indices `0..468`;
- configuration indices `0..466`;
- duplicates only at configurations `118` and `350` with exact PRE/POST semantics;
- interval/sample/alpha formula and bounds;
- seven finite joints; finite position; normalized finite quaternion;
- exact B2 endpoint/key-snapshot relationship;
- exact `83` observations per frame;
- null, empty, omitted, duplicate, reordered, boolean-as-integer, non-finite, malformed-phase, malformed-boundary, and extra-field payloads rejected;
- artifact/hash corruption rejected before `pb.connect`.

#### PyBullet

- 469/469 exact DIRECT assignment/readback;
- 469/469 exact Windows GUI assignment/readback;
- zero `stepSimulation`, real-time simulation, motor-control, IK, planner, collision, closest-point, or contact calls;
- manual GUI closure detection in PAUSED, PLAYING, and COMPLETED;
- disconnect exception and retry ownership;
- GUI RESET_VIEW invokes the owner-thread debug-camera operation and preserves exact frame/scientific state;
- DIRECT RESET_VIEW invokes no graphical/debug-camera API, returns success, advances both versions once, and preserves exact frame/scientific state;
- no connected client after success, failure, interruption, or shutdown.

#### Coordinator

- every legal transition and every invalid state/control pair;
- concurrent START;
- concurrent navigation;
- PAUSE/cadence race: an executing frame completes, then admitted PAUSE precedes the next frame;
- STOP/cadence race: an executing frame completes, then admitted STOP precedes the next frame;
- RESET_VIEW/cadence race: admitted RESET_VIEW precedes the next frame; playback resumes sequentially afterward with no skipped frame;
- STOP versus GUI-liveness poll: an already-started poll settles, otherwise admitted STOP executes first;
- PAUSE versus GUI-liveness poll: an already-started poll settles, otherwise admitted PAUSE executes first;
- control admitted at the idle-expiry boundary executes before an unstarted expiry action and renews/re-evaluates the idle deadline;
- no cadence, liveness, or idle-expiry mutation starts between atomic external admission and owner execution;
- continuously due periodic events cannot starve an admitted external mutation;
- no external command interrupts an already-started frame or liveness operation;
- stale session and stale control version;
- automatic intermediate frames advance projection version without invalidating control version;
- control/projection versions initialize per session and are monotonic only within that session;
- canonical IDLE is exactly null session, versions `0/0`, null frame, and no command in flight;
- provisional START publicly retains IDLE/null/0/0/null with `command_in_flight=true` until settlement;
- `(session_id, projection_version)` ordering rejects delayed high-version S1 GET/mutation responses after low-version S2 becomes current;
- IDLE/null-session projections are never numerically ordered against active-session projections;
- atomic session/control-version/busy/state validation and reservation under one lock;
- exact error precedence for wrong session, wrong control version, unsettled mutation, and illegal state;
- exact control/projection-version behavior for START initialization, every retained-session event, successful session termination, failure, expiry, STOP, and GET;
- successful STOP returns canonical IDLE/null/0/0 and creates exactly one retry tombstone;
- failed STOP cleanup retains the session in CLEANUP_FAILED, advances its versions once, and projects only `REPLAY_CLEANUP_UNRESOLVED`;
- successful idle expiry returns canonical IDLE/null/0/0, creates no tombstone, and makes old-session STOP stale;
- failed idle-expiry cleanup retains the session in CLEANUP_FAILED, advances its versions once, and projects only `REPLAY_CLEANUP_UNRESOLVED`;
- START runtime-integrity, scene/apply, and cleanup failures project exactly their registered error enum member;
- frame/application/readback failure projects `REPLAY_SCENE_FAILED` after successful cleanup or `REPLAY_CLEANUP_UNRESOLVED` after failed cleanup;
- GUI closure projects `REPLAY_GUI_CLOSED` only when ownership settles or `REPLAY_CLEANUP_UNRESOLVED` when cleanup remains unresolved;
- every successful `FAILED` or `CLEANUP_FAILED` DTO contains exactly one permitted non-null `ReplayLastErrorCode`; healthy stable DTOs contain `null`;
- exact STOP tombstone retry and tombstone expiry while IDLE;
- delayed S1 STOP tombstone retry after S2 starts returns `409 REPLAY_SESSION_STALE`, never cached S1 state;
- HTTP timeout before execution and unknown settlement after execution begins;
- unknown HTTP settlement retains `command_in_flight` and admission until actual owner settlement;
- START pre-execution expiry removes provisional session ownership with zero mutation;
- started START timeout returns `REPLAY_START_TIMEOUT`, remains admitted until owner settlement, and is reconciled by GET without retry;
- stable FAILED/CLEANUP_FAILED START settlement exposes recoverable session identity/version through GET;
- no automatic mutation retry;
- command-channel full rejection;
- cleanup failure blocks new START;
- request-driven safe-integer exhaustion performs no requested mutation, preserves counters, latches the fatal fault, and yields only code-only `503` thereafter;
- automatic intermediate/final-frame exhaustion performs no internal mutation, preserves counters, latches the same fatal fault without an HTTP waiter, and stops scheduling;
- failure-publication and idle-expiry-publication exhaustion use the identical persistent fault path;
- automatic-event-first race: the periodic event began before external admission; the concurrent request cannot complete admission; the event detects exhaustion and publishes the fatal latch; the request is never admitted and receives code-only `503` from preflight/re-check with zero request mutation;
- external-command-first race: completed external admission prevents new periodic work; if that command itself would overflow, its requested mutation does not occur, it commits the fatal latch, its waiter receives code-only `503`, admission releases after fatal settlement, and no periodic state mutation intervenes;
- exhaustion cleanup success releases exact ownership internally but does not clear the latch or restore the replay HTTP surface;
- exhaustion cleanup failure retains exact ownership/last projection internally and shutdown retries final cleanup;
- GET and START after either exhaustion cleanup outcome return code-only `503 REPLAY_VERSION_EXHAUSTED` until restart;
- no exhaustion path wraps a counter, emits a successful DTO, or creates another lifecycle state;
- shutdown in STARTING, PAUSED, PLAYING, COMPLETED, STOPPING, FAILED, and CLEANUP_FAILED;
- one-GUI invariant;
- owner-thread-only PyBullet access;
- bounded owner-thread waiting/detection and idle expiry;
- surviving owner thread reports `REPLAY_OWNER_THREAD_SURVIVED`, fails qualification, and triggers the isolation gate;
- no unbounded queue, timer, thread, future, or retained history.

#### API

- malformed START after the route preflight observes exhaustion returns code-only `503`, not `422`;
- malformed CONTROL after the route preflight observes exhaustion returns code-only `503`, not `422`;
- GET after exhaustion returns code-only `503`;
- exhaustion latching after route preflight but before coordinator admission is caught by the under-lock re-check with zero mutation;
- strict unknown-field rejection;
- missing/null/empty/malformed scenario, session, control version, and control rejection;
- control/projection safe-integer boundary and overflow rejection;
- canonical IDLE DTO fields are exactly null session, versions `0/0`, null frame, `command_in_flight=false`, `last_error_code=null`, and `available_controls=(START)`;
- strict decoding accepts only `REPLAY_RUNTIME_INTEGRITY_FAILED`, `REPLAY_SCENE_FAILED`, `REPLAY_GUI_CLOSED`, `REPLAY_CLEANUP_UNRESOLVED`, or `null` for `last_error_code`;
- strict decoding rejects every unregistered error code, including `REPLAY_VERSION_EXHAUSTED` and `REPLAY_OWNER_THREAD_SURVIVED`, inside a successful DTO;
- request-validation/session/version/busy/boundary/timeout/unknown-settlement HTTP errors leave the committed `last_error_code` unchanged;
- public lifecycle decoding rejects internal `STARTING` and `STOPPING` values;
- exact `available_controls` values for every stable lifecycle, frame boundary, command-in-flight state, and shutdown;
- persistent exhaustion fault exposes no successful DTO and makes GET return code-only `503 REPLAY_VERSION_EXHAUSTED`;
- forbidden joint/pose/path/hash/geometry/route/collision/B2/B3 inputs rejected;
- stable HTTP/error-code matrix and route-scoped replay validation envelope;
- unchanged D0–D2.3 non-replay validation response regression;
- `updated_at_utc` changes only with committed projection mutation and remains byte-identical across GET-only observations;
- no private/scientific payload leakage;
- GET performs zero PyBullet calls and zero mutation;
- GET recovers authoritative START session/version/lifecycle/error state after unknown or failed START settlement;
- response qualification remains exact `FAIL / 118 / (0,118,0)`;
- physical authority always `NOT_IMPLEMENTED`.

#### Frontend

- stale operation response suppressed;
- stale server session/control version reconciled;
- local browser operation ownership is checked before server projection acceptance;
- response session identity is checked before numeric projection version;
- lower projection-version polls are discarded only within the same session;
- equal-version obsolete polls are rejected by local request operation identity;
- delayed high-version S1 response cannot replace low-version current S2;
- IDLE/null-session transition and new-session establishment require an explicitly owned START/STOP or authoritative reconciliation path;
- double-submit and concurrent-control ownership;
- lost-response GET recovery and no automatic retry;
- started START timeout is never retried and GET recovers server-issued session identity and stable outcome;
- failed START recovery permits only controls valid for the recovered FAILED/CLEANUP_FAILED projection;
- controls render exactly from `available_controls`; an unsettled mutation exposes no available control;
- canonical IDLE and active-session projections are never conflated by version magnitude;
- polling timer cleanup on stop, failure, scenario switch, and unmount;
- abort/deadline classification does not claim server rollback;
- scenario switch cannot transfer replay ownership;
- no active model-inference semantics on replay scenario;
- `SERVER_REGISTERED_ONLY` never renders as `GRANTED`;
- recorded failure example never rewrites governance;
- three replay claim labels present as text, not color alone;
- keyboard, focus, live-region, reduced-motion, 600 px and 980 px qualification.
- internal frame `0..468` renders exactly as examiner-facing `Frame 1 of 469` through `Frame 469 of 469`.

#### End-to-end

- browser → real FastAPI → real coordinator → real DIRECT session in CI;
- local Windows browser → real FastAPI → real GUI;
- complete START/PAUSE/RESUME/NEXT/PREVIOUS/RESET_VIEW/STOP sequence;
- PAUSE, STOP, and RESET_VIEW win owner arbitration over the next not-yet-started cadence frame;
- STOP S1, START S2, then delayed exact STOP S1 returns stale `409` and never an S1 cached projection;
- delayed high-version S1 GET/mutation responses cannot replace low-version S2 presentation;
- START timeout/failed START reconciliation recovers the server-issued session through GET without automatic START retry;
- automatic-event-first exhaustion prevents the concurrent browser control from becoming admitted and returns code-only `503` with zero request mutation;
- external-command-first overflow blocks periodic work, performs zero requested mutation, returns code-only `503`, and releases admission after fatal settlement;
- malformed replay START/CONTROL and GET all return the fatal `503` envelope after exhaustion, while non-replay D0–D2.3 validation remains unchanged;
- all 469 frames displayed without synthesis or skipping;
- manual GUI-close recovery;
- exact STOP response-loss reconciliation;
- GUI and DIRECT RESET_VIEW mode contracts;
- native-call shutdown overrun produces explicit failure rather than clean-shutdown claim;
- zero residual client/thread/process;
- complete D0–D2.3 regression and frozen predecessor hashes.

### 3.2 Phase-partitioned candidate file surfaces

Implementation is not authorised by this document. These candidate surfaces preserve the master-plan gates; each phase requires a separate manual mutation review and authorisation.

#### D3.2 backend candidate surface

```text
MOD src/prototype5/frozen_evidence_replay.py
MOD src/prototype5/pybullet_evidence_replay.py
ADD src/prototype5/replay_coordinator.py
MOD src/prototype5/demo_runtime.py
MOD src/prototype5/demo_api.py
MOD tests/prototype5/test_frozen_evidence_replay.py
ADD tests/prototype5/test_replay_coordinator.py
MOD tests/prototype5/test_demo_api.py
```

#### D3.3 frontend candidate surface

```text
MOD frontend/src/types.ts
MOD frontend/src/runtimeContracts.ts
MOD frontend/src/api.ts
MOD frontend/src/demoState.ts
MOD frontend/src/authorityPresentation.ts
MOD frontend/src/App.tsx
MOD frontend/src/styles.css
MOD frontend/tests/runtimeContracts.test.ts
MOD frontend/tests/demoState.test.ts
MOD frontend/tests/App.test.tsx
```

#### D3.4 qualification candidate surface

```text
MOD tests/prototype5/d2_3_e2e_server.py
MOD frontend/tests/e2e/demo.spec.ts
MOD frontend/tests/real-e2e/real-stack.spec.ts
```

No D3.2 instruction may mutate a D3.3 or D3.4 candidate path. Candidate listing is not mutation authority; every phase remains HOLD until its own manual gate.

No mutation is authorised for:

```text
configs/prototype5/final_demo_scenarios_v1.json
src/prototype5/final_demo_contract.py
src/prototype5/final_demo_presentation.py
src/prototype5/demo_service.py
B2/B3.1/B3.2 artifacts
planning/IK/collision/provider/speech code
```

Any additional file requires a new manual scope review before mutation.

## 4. Risk Matrix and Mitigation

| Risk | Severity | Mechanism | Mandatory mitigation |
|---|---:|---|---|
| Automatic counter exhaustion has no HTTP requester and silently leaves replay operable | Critical | cadence/completion publication exceeds the safe-integer domain outside request settlement | one persistent fatal latch for requested/automatic events; zero triggering mutation; exact cleanup attempt; every replay endpoint code-only `503` until restart |
| Periodic timer mutates lifecycle/version after external CAS admission | Critical | cadence, GUI-liveness, or idle-expiry work starts before the admitted command executes | request arrival is not admission; already-started work settles first; completed admission outranks every not-yet-started periodic event; timer-race tests prove zero intervening mutation |
| Canonical IDLE leaks terminated-session error/control state | Critical | successful STOP/expiry resets identity and counters but retains stale projection fields | ordinary canonical IDLE is exactly null session, `0/0`, null frame/error, no in-flight command, and `(START)` availability; exhaustion emits no successful IDLE DTO |

```text
D3_1_SPECIFICATION_COMPLETE
D3_2_IMPLEMENTATION_REQUIRES_SEPARATE_MANUAL_REVIEW
```
