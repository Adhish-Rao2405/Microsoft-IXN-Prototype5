# Foundry SDK Backend Smoke Summary

Status: COMPLETE_BACKEND_SMOKE

## Scope

This is a bounded adapter smoke test only. It does not replace Prototype 3/4/5 evidence and does not perform schema, semantic, safety, or execution validation.

## Configuration

- Base URL: `http://127.0.0.1:53402`
- Model alias: `qwen2.5-coder-0.5b-instruct-generic-cpu:4`
- Prompt count: `1`
- Success count: `1`
- Failure count: `0`

## Architectural Boundary

- Parses JSON: `false`
- Validates schema: `false`
- Repairs model output: `false`
- Infers execution eligibility: `false`
- Calls orchestrator: `false`
- Runs benchmark: `false`

## Result Rows

| Case ID | Success | Backend | Model alias | Latency ms | Error type |
|---|---:|---|---|---:|---|
| smoke_001 | true | foundry_local_openai_compatible | qwen2.5-coder-0.5b-instruct-generic-cpu:4 | 1065.217 | None |

## Raw Text

### smoke_001

````text
```json
{
  "status": "ok",
  "action": "noop"
}
```
````
