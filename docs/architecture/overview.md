# Job Assistant Architecture Overview

## Summary

Job Assistant uses a hybrid `Agent + Service + Artifact` architecture.

- Agents handle synthesis, prioritization, and controlled generation.
- Services and pipelines handle deterministic extraction, persistence, and state transitions.
- Shared artifacts are the only cross-boundary collaboration contract.

## Primary Runtime Shape

- `SupervisorAgent`
- `JobIntelligenceAgent`
- `MatchingAgent`
- `ResumeTailorAgent`
- `InterviewCoachAgent`
- `VerifierAgent`
- `ProfilePipeline`
- `ApplicationWorkflowService`
- `ApplicationStore`

## Architectural Rules

1. Candidate facts only come from resume evidence or explicit user input.
2. Job-side reasoning may use manual JD data and external evidence.
3. User-visible outputs must pass verifier checks before delivery.
4. The existing BettaFish research graph is a subsystem under `JobIntelligenceAgent`, not the product backbone.
