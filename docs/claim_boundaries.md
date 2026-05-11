# Claim Boundaries and Statistical Humility

## What The Project Claims

- Local SLMs can be served through Microsoft Foundry Local for controlled industrial robot task-planning evaluation.
- Local SLMs can produce structured robot action proposals, but validity varies by model and run.
- Schema validity is not enough to prove semantic correctness, safety or execution eligibility.
- Deterministic zero-trust validation can block model-level false accepts from becoming pipeline-level false accepts in the available evidence.
- Local-vs-cloud comparison shows a deployment trade-off, not a universal winner.
- Live local inference has measurable latency, CPU and memory implications on the profiled host.
- Prototype 5 consolidates evidence into a dissertation-facing evidence pack.

## What The Project Does Not Claim

- It does not prove production robot safety.
- It does not prove physical robot execution.
- It does not prove population-level model reliability.
- It does not prove that every local SLM or every hardware target behaves similarly.
- It does not prove built-in Foundry Local precision metadata where the catalogue does not expose it.
- It does not prove GPU/NPU acceleration where counters were not detected.
- It does not provide a quantitative cloud cost model unless token/cost evidence is present.

## Benchmark Limitation

The benchmark is not statistically powered for population-level inference. Its purpose is controlled engineering comparison and failure-mode discovery. Multi-model consistency strengthens the observed pattern but does not remove the need for larger future benchmarks.

## Model Limitation

Detected evidence covers specific local model families and a cloud baseline. It should not be generalised to all SLMs, all quantisation variants or all serving backends.

## Simulation Limitation

Any PyBullet layer, if added, is a visual execution-context demonstrator only. It does not prove physical execution, safety certification or industrial deployment readiness.

## Safety Limitation

The safety evidence is based on deterministic prototype gates and benchmark-defined constraints. Real industrial deployment would require certified safety systems, risk assessment, emergency-stop integration and domain-specific validation.

## Resource Profiling Limitation

Mode D resource profiling is hardware-specific. CPU utilisation is approximate and GPU/NPU counters were not detected, so no acceleration claim is made.

## Local-vs-Cloud Limitation

Mode C compares measured local evidence with a cloud baseline on the same 30-command benchmark. It does not establish a universal winner. Cloud inference was faster and more JSON-consistent in the measured evidence, while local inference preserved privacy and offline-resilience properties.

## PyBullet Limitation

PyBullet should not become the core proof. It may demonstrate accepted versus rejected proposals visually, but the dissertation claim must rest on benchmark evidence, zero-trust validation, local-vs-cloud comparison, resource profiling and claim traceability.
