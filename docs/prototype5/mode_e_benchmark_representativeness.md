# Mode E Benchmark Representativeness

## Purpose

Mode E extends Prototype 5 with an industrially motivated benchmark extension. Its purpose is to address the remaining benchmark-representativeness weakness after Mode E0: whether the schema-valid versus execution-eligible gap can be tested beyond the original fixed 30-command benchmark.

## Why The Original Benchmark Was Limited

The original 30-command benchmark was deliberately controlled. That made it useful for measuring schema validity, ambiguity handling, semantic validity, safety validity and execution eligibility under a fixed policy. However, it was small and did not cover a broader range of industrial robotics scenarios such as conveyor sorting, inspection, warehouse transfer, human proximity or restricted-zone access.

## How The +30 Extension Improves Coverage

The Mode E extension adds 30 industrially motivated natural-language commands. The extension is balanced across:

- 10 clear commands
- 10 ambiguous commands
- 10 unsafe or execution-invalid commands

It also covers six scenario families with five cases each:

- pick-and-place
- conveyor and sorting
- inspection and quality control
- warehouse or cell transfer
- human-proximity safety
- restricted-zone or hazard-zone movement

This extension improves scenario coverage but does not make the benchmark comprehensive.

## Scenario Family Rationale

The six families were selected because they represent recurring industrial robotics and manufacturing-automation concerns: object transfer, material sorting, quality inspection, cell logistics, human-shared workspaces and access-controlled zones. These are not claimed to exhaust industrial robotics, but they broaden the original benchmark beyond simple manipulation and ambiguity examples.

## Difficulty Balance Rationale

The 10/10/10 split prevents the extension from becoming a collection of only easy commands or only adversarial examples. Clear cases test whether structured task proposals can be produced for well-grounded commands. Ambiguous cases test whether missing references or missing locations are exposed. Unsafe or invalid cases test whether commands should be rejected before execution under a deterministic validation policy.

## What This Benchmark Can Support

Mode E can support a bounded benchmark-extension argument: the project now has a broader, structured set of industrially motivated commands for testing whether the schema-valid versus execution-eligible gap persists beyond the original benchmark.

## What This Benchmark Cannot Support

Mode E cannot prove production robot safety, full industrial generalisation, general local SLM reliability, or comprehensive benchmark representativeness. The benchmark remains curated rather than sampled from deployed industrial logs. Any future live evaluation must be interpreted under the tested conditions and the deterministic validation policy used at the time.
