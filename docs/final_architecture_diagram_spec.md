# Final Architecture Diagram Specification

## Purpose

This diagram specifies the final zero-trust local-first task-planning evidence architecture for the dissertation.

## Required Flow

User command -> benchmark/live input -> Foundry Local SLM / optional cloud baseline -> raw model response -> parser -> JSON validity -> schema validator -> semantic validator -> uncertainty/ambiguity gate -> safety gate -> execution eligibility decision -> evidence logger -> optional PyBullet industrial workcell visualiser.

## Side Evidence Components

- benchmark dataset
- metric taxonomy
- claims matrix
- evidence manifest
- resource profiler
- local-vs-cloud comparator
- model/run cards

## Mermaid Source

See `figures/final_zero_trust_architecture.mmd`.
