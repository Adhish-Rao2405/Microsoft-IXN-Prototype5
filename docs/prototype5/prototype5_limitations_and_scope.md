# Prototype 5 Limitations and Scope

Prototype 5 distinguishes safe dissertation wording from unsupported claims. Missing evidence is not converted into a positive result.

## Explicit Limitations
| limitation                                | status  | safe_interpretation                                                                   |
| ----------------------------------------- | ------- | ------------------------------------------------------------------------------------- |
| custom FP16/INT8/INT4 precision artifacts | PRESENT | Explicit Prototype 5 custom metadata proves FP16, INT8, and INT4 precision artifacts. |
| built-in Foundry Local precision metadata | MISSING | Built-in Foundry catalogue precision metadata is still not proven.                    |
| Phi-family evaluation                     | MISSING | No explicit Phi-family result file is present.                                        |
| cloud-vs-local comparison                 | MISSING | No cloud baseline evidence is present.                                                |
| GPU/NPU profiling                         | MISSING | No GPU or NPU profiling evidence is present.                                          |
| memory footprint measurement              | MISSING | No memory-footprint evidence is present.                                              |
| physical robot execution                  | MISSING | Prototype 5 consolidates simulation and execution-record evidence only.               |

## Missing Claims
| claim                                                 | status  | evidence_source                                                                     | safe_dissertation_wording                                                                                                                         | unsafe_wording_to_avoid                                                          |
| ----------------------------------------------------- | ------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Built-in Foundry Local precision metadata is missing. | MISSING | No built-in Foundry catalogue precision field was available in the loaded evidence. | Built-in Foundry Local catalogue metadata did not expose explicit precision fields; the precision claim is based on custom Prototype 5 artifacts. | Built-in Foundry Local CPU/GPU model labels prove FP16, INT8, or INT4 precision. |
| cloud-vs-local comparison is missing.                 | MISSING | No explicit Prototype 5 input evidence found.                                       | cloud-vs-local comparison is missing.                                                                                                             | Do not claim cloud-vs-local performance or safety comparison.                    |
| GPU/NPU profiling is missing.                         | MISSING | No explicit Prototype 5 input evidence found.                                       | GPU/NPU profiling is missing.                                                                                                                     | Do not claim GPU or NPU profiling evidence.                                      |
| memory footprint measurement is missing.              | MISSING | No explicit Prototype 5 input evidence found.                                       | memory footprint measurement is missing.                                                                                                          | Do not claim measured memory footprint.                                          |
| physical robot execution is not proven.               | MISSING | No explicit Prototype 5 input evidence found.                                       | physical robot execution is not proven.                                                                                                           | Do not claim physical robot execution or deployment validation.                  |
