# Prototype 5 Mode D Final Live Resource Profile

## Final status

Prototype 5 Mode D is complete with a live Foundry Local resource profile.

- Final Mode D status: COMPLETE_LIVE_PROFILE
- Live workload mode: manual_live_foundry_process
- Model: Phi-3-mini-4k-instruct-generic-cpu:3
- Foundry process ID: 29080
- Total live commands: 30
- Successful live requests: 30/30
- JSON-valid outputs: 24/30
- JSON-valid rate: 0.8
- Mean latency: 7896.97 ms
- Min latency: 4117.67 ms
- Max latency: 19007.83 ms

## CPU and memory profile

The live profile measured the actual Foundry Local serving process, not only the PowerShell client.

- Logical CPU cores: 16
- Raw mean approximate Foundry CPU: 772.98%
- Raw peak approximate Foundry CPU: 788.49%
- Normalized mean Foundry CPU share: 48.31% of total logical CPU capacity
- Normalized peak Foundry CPU share: 49.28% of total logical CPU capacity
- Mean working-set delta per request: 0.82 MB
- Mean private-memory delta per request: 0.54 MB
- Current Foundry working set: 2827.12 MB
- Current Foundry private memory: 6899.72 MB

Raw process CPU can exceed 100% because a model-serving process can use multiple logical cores. The normalized CPU figure divides raw process CPU by the 16 logical CPU cores detected on the machine.

## Interpretation

The live profile shows that the local Foundry Phi model completed all 30 benchmark requests, but only 24 out of 30 responses were JSON-valid. This reinforces the dissertation argument that local model output must be treated as an untrusted proposal and passed through deterministic validation before execution.

Compared with the Mode C cloud baseline, local live inference is slower and uses substantial local compute capacity. However, it preserves the local-first properties of privacy, local data retention and offline resilience.

## Limitations

- This profile is hardware-specific to the test machine.
- CPU utilisation is approximated using process CPU-time deltas around each request.
- GPU and NPU counters were not detected, so no hardware acceleration claim is made.
- Mode D does not claim semantic correctness, schema validity or safety validity unless those gates are separately evaluated.
- The result is strongest as an operational resource profile, not as a replacement for the safety benchmark.

## Dissertation claim unlocked

Prototype 5 Mode D provides a live local resource-utilisation evaluation for Foundry Local inference. Across the 30-command benchmark, the local Phi model completed 30/30 live requests with a mean latency of 7896.97 ms and a JSON-valid rate of 0.8. The Foundry serving process used approximately 48.31% of total logical CPU capacity on average during requests. This evidence directly supports the Microsoft IXN requirement to evaluate resource utilisation and throughput stability for local model deployment.
