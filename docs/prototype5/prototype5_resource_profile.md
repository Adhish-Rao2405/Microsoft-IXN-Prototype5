# Prototype 5 Resource Profile

## Purpose of Mode D
Quantify the resource footprint and throughput stability of the local Prototype 5 evidence-processing workload.

## Microsoft Brief Requirement
Mode D addresses the requirement to benchmark resource utilisation, CPU/GPU/NPU pressure and throughput stability for the local-first evaluation pipeline.

## Profiling Method
Mode D is a resource/throughput profiling layer, not a new model benchmark. Default Mode D uses evidence replay unless live local execution is explicitly enabled. Replay profiling measures the profiling harness and evidence-processing workload, not a fresh Foundry model inference run. No cloud calls are made in Mode D.

## Workload Mode Used
Workload mode: evidence_replay. Live local status: NOT_REQUESTED.

## Metrics Recorded
CPU percentage, memory RSS/VMS, system memory pressure, throughput commands per minute, rolling latency, GPU/NPU visibility fields and device metadata.

## Device Metadata
OS: Windows. Python: 3.12.10. Machine: AMD64. CPU logical count: 16. Total memory MB: 15720.25. Foundry model ID: Phi-3-mini-4k-instruct-generic-cpu:3. Profiler backend: PSUTIL_AVAILABLE.

## CPU and Memory Summary
CPU profile: PRESENT. Mean process CPU: 0.0. Peak process CPU: 0.0. Mean system CPU: 2.02. Peak system CPU: 66.7.
Memory profile: PRESENT. Before RSS MB: 19.05. After RSS MB: 19.13. Peak RSS MB: 19.13. Delta RSS MB: 0.08.

## GPU/NPU Visibility and Limitations
GPU profile: NOT_DETECTED. NPU profile: NOT_DETECTED. GPU/NPU fields are reported only if measurable; otherwise they are recorded as unavailable.

## Throughput Stability Results
Total commands: 30. Successful commands: 30. Mean latency ms: 7028.0. P95 latency ms: 9151.82. Throughput commands/min: 8.54.

## Limitations
- Mode D is a resource/throughput profiling layer, not a new model benchmark.
- Default Mode D uses evidence replay unless live local execution is explicitly enabled.
- Replay profiling measures the profiling harness and evidence-processing workload, not a fresh Foundry model inference run.
- Live local inference profiling can be added if Foundry Local live-call integration is enabled.
- GPU/NPU fields are reported only if measurable; otherwise they are recorded as unavailable.
- If psutil is not installed, install it with pip install psutil to enable CPU and memory counters.
- No cloud calls are made in Mode D.

## Dissertation Wording Unlocked
- The project includes a resource profiling layer aligned with the Microsoft IXN requirement for resource-utilisation evaluation.
- The profiling layer records CPU, memory, throughput and hardware visibility metrics for the local evidence-processing workload.
- GPU/NPU metrics are reported cautiously and only where measurable.
- The results separate local inference/evidence latency from resource pressure and throughput stability.
- The project avoids unsupported claims where live Foundry or hardware counters are unavailable.
