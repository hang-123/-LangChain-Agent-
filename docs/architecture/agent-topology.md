# Job Assistant Agent Topology

## Agents

- `SupervisorAgent`: orchestration and response assembly
- `JobIntelligenceAgent`: job-side fact synthesis and evidence enhancement
- `MatchingAgent`: candidate/job comparison
- `ResumeTailorAgent`: resume tailoring plan and version generation
- `InterviewCoachAgent`: interview preparation pack generation
- `VerifierAgent`: fact boundary and evidence verification

## Services And Pipelines

- `ProfilePipeline`: resume parsing and evidence extraction
- `ApplicationWorkflowService`: application state transitions and reminders
- `ApplicationStore`: application persistence

## Collaboration Contract

All cross-boundary communication happens through shared artifacts instead of raw prompt context.
