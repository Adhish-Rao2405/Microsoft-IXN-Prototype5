# Prototype 5 Limitations and Scope

Prototype 5 distinguishes safe dissertation wording from unsupported claims. Missing evidence is not converted into a positive result.

## Explicit Limitations
| limitation                                | status  | safe_interpretation                                                                                                              |
| ----------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------- |
| custom FP16/INT8/INT4 precision artifacts | PRESENT | Explicit Prototype 5 custom metadata proves FP16, INT8, and INT4 precision artifacts.                                            |
| built-in Foundry Local precision metadata | MISSING | Built-in Foundry catalogue precision metadata is still not proven.                                                               |
| Phi-family evaluation                     | PRESENT | Phi-family Foundry Local response evidence is present; semantic validity remains NOT_EVALUATED.                                  |
| cloud-vs-local comparison                 | PRESENT | Mode C local-vs-cloud benchmark evidence is present; semantic equivalence is not claimed.                                        |
| GPU/NPU profiling                         | LIMITED | Mode D records hardware visibility, but GPU/NPU counters were NOT_DETECTED/NOT_DETECTED; no hardware acceleration claim is made. |
| memory footprint measurement              | PRESENT | Mode D live Foundry profiling records process memory deltas for the measured local run.                                          |
| physical robot execution                  | MISSING | Prototype 5 consolidates simulation and execution-record evidence only.                                                          |

## Missing Claims
| claim                                                 | status  | evidence_source                                                                     | safe_dissertation_wording                                                                                                                         | unsafe_wording_to_avoid                                                          |
| ----------------------------------------------------- | ------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Built-in Foundry Local precision metadata is missing. | MISSING | No built-in Foundry catalogue precision field was available in the loaded evidence. | Built-in Foundry Local catalogue metadata did not expose explicit precision fields; the precision claim is based on custom Prototype 5 artifacts. | Built-in Foundry Local CPU/GPU model labels prove FP16, INT8, or INT4 precision. |
| physical robot execution is not proven.               | MISSING | No explicit Prototype 5 input evidence found.                                       | physical robot execution is not proven.                                                                                                           | Do not claim physical robot execution or deployment validation.                  |
