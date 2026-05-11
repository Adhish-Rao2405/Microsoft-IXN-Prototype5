# Research Questions and Claim Boundaries

## Main Research Question

How can a local-first LLM/SLM task-planning pipeline using Foundry Local be designed and evaluated so that model outputs are treated as untrusted proposals rather than directly executable actions?

## Sub-question 1

Can a local model generate structured task-planning outputs that can be evaluated by a deterministic pipeline?

Evidence:
- Prototype 1.
- Prototype 3.

## Sub-question 2

Can deterministic validation separate model response success from execution eligibility?

Evidence:
- Prototype 2 / 2.1.
- Prototype 3.
- Prototype 4.

## Sub-question 3

What trade-offs exist between local Foundry Local inference and cloud inference on the same task-planning benchmark?

Evidence:
- Prototype 5 Mode C.

## Sub-question 4

What local resource pressure is imposed by live Foundry Local inference during benchmark execution?

Evidence:
- Prototype 5 Mode D.

## Sub-question 5

How can model-family and precision/quantisation evidence be documented when Foundry catalogue metadata is incomplete?

Evidence:
- Prototype 5 Mode B.

## Final Claim

The project demonstrates a local-first zero-trust evaluation framework for LLM/SLM task planning. It does not claim that local inference is universally faster, cheaper, safer or more accurate than cloud inference.

## Claims Explicitly Not Made

- The system is production-ready.
- Local inference is better than cloud inference.
- GPU/NPU acceleration was used.
- Foundry Local exposed native FP16/INT8/INT4 metadata.
- Cost savings were quantitatively measured.
- JSON validity is equivalent to task accuracy.
- Live resource profiling generalises beyond the measured machine and command set.
