# Phase 1 SDK Limitations and Next Steps

## Limitations

- The SDK migration is bounded integration evidence, not production deployment evidence.
- The mini replays use five commands, not the full 30-command benchmark.
- The action-envelope replay improved schema compatibility but did not produce execution-eligible cases.
- Semantic evaluation for the mini replay remains bounded by the available mini-case metadata.
- Safety validation remains deterministic software validation and does not certify physical robot safety.
- The evaluated model and endpoint are local-environment specific.
- Voice control has not been implemented.

## Non-Claims

The project does not claim production robotics safety, certified robot safety, universal local SLM reliability, or completed voice-control readiness.

## Next Steps

1. Keep the Phase 1 SDK migration frozen as the integration baseline.
2. Begin Phase 2 with a voice-control baseline and safety specification.
3. Treat voice as an input modality only.
4. Require voice-derived commands to pass through the same backend, validation, and evidence boundaries.
5. Decide separately whether a future full 30-command SDK benchmark is needed.

## Phase 2 Guardrails

Voice must not bypass deterministic validators. Stop/proceed intents require explicit safety tiering. Ambiguous, low-confidence, unsafe, or unsupported voice-derived commands must fail closed.
