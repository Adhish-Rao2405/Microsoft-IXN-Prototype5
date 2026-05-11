# Threats to Validity

## Internal Validity

The evaluation uses deterministic validation stages to reduce ambiguity in result interpretation. However, errors in schema design, safety-rule design or benchmark labelling could affect validity.

Mitigation:
- Unit tests were used across the Prototype 5 suite.
- Prototype 5 test suite passed with 54 tests.
- Metrics are separated to avoid conflating request success with safety or execution validity.

## Construct Validity

The project does not use a single generic "accuracy" metric. This is intentional because task-planning validity has multiple dimensions.

Mitigation:
- Metrics are separated into request success, parse success, JSON validity, schema validity, semantic validity, safety result and execution validity.
- The final claims matrix distinguishes proven claims from missing, partial or bounded claims.

## External Validity

The benchmark contains 30 commands. This supports controlled comparison but does not prove generalisation to all robot-planning tasks or production deployments.

Mitigation:
- The dissertation frames the benchmark as prototype-level controlled evaluation.
- Future work should expand benchmark size and task diversity.

## Statistical Conclusion Validity

The project does not claim broad statistical significance. The results are used as controlled engineering evidence rather than population-level statistical inference.

Mitigation:
- Claims are bounded to the benchmark and hardware environment.
- The dissertation avoids unsupported statistical generalisation.

## Reproducibility Validity

Local inference results may vary across hardware, Foundry Local versions, model availability and runtime conditions.

Mitigation:
- Final evidence files are retained.
- Test commands and orchestrator outputs are documented.
- Hardware/resource caveats are stated.

## Deployment Validity

The system evaluates planning and execution eligibility but does not complete a production physical robot-control deployment.

Mitigation:
- The dissertation frames the work as a local-first task-planning safety testbed.
- Future work proposes physical executor integration under strict safety constraints.
