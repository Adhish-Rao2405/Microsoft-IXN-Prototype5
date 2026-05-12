# Mode E Dissertation Wording

## Methodology Wording

To address benchmark representativeness, Prototype 5 Mode E introduced an additional industrial scenario benchmark extension. The extension added 30 natural-language robot task commands across six industrially motivated scenario families: pick-and-place, conveyor sorting, inspection and quality control, warehouse transfer, human proximity and restricted-zone movement. The extension was balanced across 10 clear commands, 10 ambiguous commands and 10 unsafe or execution-invalid commands.

The purpose of this extension was not to create a new robot-control prototype. Instead, it provided a structured benchmark artefact for assessing whether the schema-valid versus execution-eligible gap observed in the original benchmark could be tested against broader industrial task coverage. The benchmark was validated using a repository-local audit script that checks case count, identifier format, difficulty distribution, scenario-family distribution, risk-class labels, issue labels and duplicate commands.

## Results Wording

The Mode E benchmark audit confirmed that the industrial extension contains 30 cases, with 10 clear, 10 ambiguous and 10 unsafe or execution-invalid commands. Each of the six scenario families contributes five commands. This gives the dissertation a broader benchmark basis than the original 30-command set and directly addresses the representativeness concern raised after the initial evidence pack.

At this stage, Mode E should be read as benchmark-extension evidence rather than live model-performance evidence. It improves the evaluation design by adding industrially motivated command coverage, but it does not by itself demonstrate that the schema-valid versus execution-eligible gap persists on those commands. That claim requires a separate live or replay evaluation using a deterministic validation policy adapted to the industrial vocabulary.

## Limitations Wording

The benchmark remains small. It is curated rather than sampled from deployed industrial logs. The evaluation uses a single local model/runtime unless additional models are explicitly tested. The result does not prove real robot safety. The result does not establish full industrial generalisation.

Mode E improves scenario coverage but does not make the benchmark comprehensive. It should be used to strengthen the dissertation's benchmark-design argument, not to claim production readiness, industrial safety certification or general local SLM reliability.
