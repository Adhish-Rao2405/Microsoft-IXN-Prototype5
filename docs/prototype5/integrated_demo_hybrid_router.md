# Prototype 5 hybrid inference router

## Milestone

`H1 - Hybrid inference router`

## Routing modes

`LOCAL` calls only the configured Foundry Local provider. If local availability
or model readiness fails, the request ends as an explicit error. It never
silently uses cloud.

`CLOUD` calls only the configured cloud provider and then applies the same
canonical governance runner.

`AUTO` is local-first. It may fall back to cloud only for the operational and
structural reasons represented by `FallbackReason`:

```text
LOCAL_UNAVAILABLE
LOCAL_MODEL_NOT_READY
LOCAL_TIMEOUT
LOCAL_TRANSPORT_ERROR
LOCAL_EMPTY_RESPONSE
LOCAL_PARSE_FAILURE
LOCAL_JSON_FAILURE
LOCAL_SCHEMA_FAILURE
LOCAL_CIRCUIT_OPEN
LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD
LOCAL_LATENCY_THRESHOLD_EXCEEDED
```

Safety, authority, ambiguity, and semantic results are not visible to the
router. A structurally valid local proposal always enters the canonical
gateway. A downstream rejection or clarification cannot trigger a second model
request.

## Health and timeout model

The local transport remains responsible for enforcing its native request
timeout. The router supplies the configured timeout in provider context,
classifies provider timeout errors, and rejects measured responses that exceed
the same threshold.

The router tracks:

* consecutive local failures;
* rolling structured success rate;
* rolling p50 and p95 provider latency;
* service availability and model readiness;
* circuit state and last circuit transition.

Circuit states are `CLOSED`, `OPEN`, and `HALF_OPEN`. A half-open probe is a
normal local request after the configured cooldown. Success closes the circuit;
failure reopens it.

The routing thresholds in
`configs/prototype5/hybrid_routing_policy_v1.json` are engineering defaults for
the demonstrator. They are not dissertation findings.

## Provider boundary

Both providers implement the existing `PlannerBackend` transport contract.
The router does not parse domain policy and does not issue execution permits.
It selects one final provider response and passes that response to
`CanonicalGovernanceRunner.evaluate_response`.

The complete result contains:

* the canonical governance result;
* requested mode and selected provider;
* fallback state and reason;
* local and cloud latency;
* routing-policy version and SHA-256;
* local health snapshot.

## Scope exclusions

H1 does not configure real credentials, contact Foundry Local, call a cloud
service, process audio, run PyBullet, or write dissertation evidence. All
tests use fake providers and availability probes.
