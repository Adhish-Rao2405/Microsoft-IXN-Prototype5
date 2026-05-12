# Benchmark Representativeness

## 1. Purpose Of The Benchmark

The benchmark provides a controlled way to compare local SLM action proposals, deterministic validation and execution eligibility for industrial robot task-planning commands.

## 2. Why A Fixed Benchmark Is Used

A fixed benchmark makes outputs comparable across models, pipeline configurations and local/cloud conditions. It also allows failures to be traced back to stable command categories rather than changing prompt sets.

## 3. Why 30 Commands Is Appropriate For Exploratory MSc Evaluation

The 30-command benchmark is not claimed to be exhaustive or representative of all industrial robotics commands. It is a controlled exploratory benchmark designed to expose differences between syntactic validity, schema validity, semantic validity, safety validity and execution eligibility.

Thirty commands are sufficient for the dissertation's bounded claim because the main contribution is not broad robot-task coverage, but the demonstrated measurement gap between schema-valid model outputs and execution-eligible action proposals under deterministic validation.

## 4. Clear / Moderate / High Ambiguity Split

The benchmark includes commands intended to exercise clear instructions, moderate ambiguity and high ambiguity. This supports analysis of rejection, clarification and false-accept risk.

## 5. Coverage Of Valid Commands

Valid commands test whether a model can produce structured proposals that pass early syntactic and schema checks and may become execution-eligible under the policy.

## 6. Coverage Of Malformed Or Underspecified Commands

Malformed or underspecified commands test whether the pipeline fails closed instead of interpreting incomplete instructions as executable actions.

## 7. Coverage Of Semantic Mismatch

Semantic mismatch cases expose the gap between structurally valid output and action proposals that correctly match the intended task.

## 8. Coverage Of Safety-Sensitive Cases

Safety-sensitive cases exercise deterministic safety rules and help measure whether unsafe model proposals are blocked by the zero-trust pipeline.

## 9. Coverage Of Unsupported Or Out-Of-Scope Actions

Unsupported commands test whether the system rejects tasks beyond the benchmark policy or workcell assumptions.

## 10. Why The Benchmark Is Sufficient For Bounded Claims

The benchmark is sufficient for the dissertation's bounded claim because it demonstrates why schema validity alone is not enough and why execution eligibility should be the system-level decision metric.

## 11. What The Benchmark Does Not Prove

The benchmark does not prove factory deployment readiness, certified safety, exhaustive industrial coverage, all-object manipulation performance or statistical generalisation.

## 12. Future Scaling

Future work should expand command count, object types, workcell states, manipulation tasks, human clarification cases, policy complexity and hardware coverage.
