# Job Assistant Agent Architecture Design

## 1. Summary

This design upgrades `job-assistant` from a spec-only workflow concept into a research-enhanced job assistant built on a hybrid `Agent + Service + Artifact` architecture.

The system is intentionally not a "fully agentic society." Only the parts that require evidence synthesis, prioritization, or controlled generation are modeled as Agents. Structured extraction, persistence, and state transitions remain deterministic services or pipelines.

The target product shape is:

- candidate-centered
- evidence-driven
- workflow-orchestrated
- verifier-gated
- incrementally evolvable from the existing BettaFish research engine

## 2. Problem And Goal

The repository currently has two strong but separate directions:

- the existing BettaFish flow is good at researching external job evidence such as real JD signals, company context, interview experience, and technical stack clues
- `job-assistant/specs/` defines a candidate-centric workflow around resume parsing, job matching, tailoring, interview prep, and application tracking

The goal is to combine them without forcing every subsystem to become an Agent.

Success means:

- candidate facts always come from resume evidence or explicit user input
- job-side reasoning can use both manual JD input and external evidence
- matching, tailoring, and interview prep consume shared structured artifacts instead of raw prompt context
- user-visible outputs are checked by a verifier before delivery
- architecture docs and `job-assistant` specs evolve together instead of drifting apart

## 3. Non-Goals

- building a free-form multi-agent conversation system
- replacing deterministic parsing and persistence with LLM-based components
- introducing autonomous application submission
- generating fabricated resume claims, achievements, or interview answers
- redesigning the whole repository in one step

## 4. Recommended System Shape

### 4.1 Architecture Style

Use a hybrid architecture:

- Agents for high-value judgment and controlled generation
- Services/Pipelines for deterministic extraction, persistence, and state transitions
- Shared Artifacts as the only cross-boundary contract

This is preferred over a pure workflow engine because some tasks need synthesis and prioritization, and preferred over a pure multi-agent system because too many components here benefit from determinism.

### 4.2 Agent Layer

#### SupervisorAgent

Responsibilities:

- classify user intent
- choose the workflow
- decide which downstream capabilities are required
- collect intermediate artifacts
- assemble final user responses

It is the orchestration brain, not the place where extraction or generation happens directly.

#### JobIntelligenceAgent

Responsibilities:

- normalize user-provided JD input
- invoke the existing research engine as a job-evidence enhancement subsystem
- merge manual JD facts and external evidence into a job-side snapshot
- surface evidence quality, freshness, and ambiguity

This is the main place where the current BettaFish research pipeline gets absorbed.

#### MatchingAgent

Responsibilities:

- compare candidate-side artifacts and job-side artifacts
- produce a structured `MatchAssessment`
- explain strengths, gaps, risks, and recommendation level

#### ResumeTailorAgent

Responsibilities:

- turn `MatchAssessment` into a tailoring plan and an auditable resume version
- only use allowed candidate evidence when generating candidate-facing edits
- use external job evidence only to shape emphasis and prioritization, never to invent candidate facts

#### InterviewCoachAgent

Responsibilities:

- generate interview questions
- generate answer frameworks
- generate follow-up points and preparation priorities

Boundaries:

- it does not output fully written fabricated answers
- it does not act as a long-running mock interviewer in MVP
- it does not manage practice history

#### VerifierAgent

Responsibilities:

- check fact / inference / recommendation boundaries
- check evidence coverage and conflicts
- enforce downgrade behavior when evidence is weak
- approve, reject, or request regeneration of user-visible artifacts

### 4.3 Service And Pipeline Layer

#### ProfilePipeline

Responsibilities:

- parse resume input
- extract structured profile fields
- create `ResumeEvidence`
- compute completeness and profile gaps
- run deterministic rule validation

Rationale:

This work is mostly structured transformation and should not be modeled as a free-form Agent.

#### ApplicationWorkflowService

Responsibilities:

- create and update application records
- enforce application state transitions
- generate deterministic follow-up reminders
- preserve idempotency

#### ApplicationStore

Responsibilities:

- persist application records and related references
- support lookup, update, and listing

Rationale:

Application tracking is primarily workflow and storage logic, not agentic reasoning.

## 5. Shared Artifact Model

Artifacts are the collaboration contract across the system. Agents and services should exchange artifacts instead of large free-form context blobs.

### 5.1 Candidate-Side Artifacts

- `ResumeAsset`
- `CandidateProfile`
- `ResumeEvidence`

### 5.2 Job-Side Artifacts

- `JobPosting`
- `JobRequirement`
- `ExternalEvidencePack`
- `JobSnapshot`

`ExternalEvidencePack` is a new artifact. It stores external job-side evidence such as:

- real JD fragments
- company context
- team or domain hints
- technical stack clues
- interview experience signals
- metadata for source, freshness, confidence, and evidence class

`JobSnapshot` is a composed artifact:

- `JobPosting`
- `JobRequirement[]`
- `ExternalEvidencePack`

It becomes the main job-side input for downstream decisions.

### 5.3 Decision And Delivery Artifacts

- `MatchAssessment`
- `ResumeTailoringPlan`
- `ResumeVersion`
- `InterviewPrepPack`
- `ApplicationRecord`
- `VerificationReport`

`VerificationReport` is a new artifact used by the verifier to make pass/reject/downgrade decisions auditable.

## 6. Target Data Flow

The system should be modeled as three converging tracks rather than one giant mutable state object.

### 6.1 Candidate Track

`ResumeAsset -> ProfilePipeline -> CandidateProfile + ResumeEvidence`

Rules:

- candidate facts only come from resume evidence or explicit user patch input
- downstream components may not infer new candidate facts from job-side evidence

### 6.2 Job Track

Input:

- `raw_jd_text`
- `target_company`
- `target_role`
- optional job link or job metadata

Flow:

- normalize manual JD input into `JobPosting` and `JobRequirement`
- invoke external evidence enhancement through `JobIntelligenceAgent`
- create `ExternalEvidencePack`
- merge into `JobSnapshot`

### 6.3 Decision Track

Once `CandidateProfile + ResumeEvidence + JobSnapshot` are ready:

- `MatchingAgent` produces `MatchAssessment`
- `ResumeTailorAgent` produces `ResumeTailoringPlan + ResumeVersion`
- `InterviewCoachAgent` produces `InterviewPrepPack`
- `ApplicationWorkflowService` creates or updates `ApplicationRecord`

### 6.4 Verification Track

Before user-visible delivery:

- `VerifierAgent` checks artifacts
- approved artifacts are persisted
- rejected artifacts are regenerated or downgraded

Core ordering rule:

`facts -> evidence enhancement -> decision -> verification -> persistence -> response`

## 7. How The Existing BettaFish Research Engine Fits

The current flow:

`IntentRouter -> Search -> Query -> Insight -> QualityGate -> Report -> Review`

should no longer define the top-level product architecture.

Instead, it should be repositioned as an internal subsystem used by `JobIntelligenceAgent`.

Recommended mapping:

- `IntentRouter / Search / Query / Insight` become job-side evidence enrichment capabilities
- `ReportAgent` is no longer the main user-facing deliverable for this product line
- `ReviewAgent` principles partially move into the new `VerifierAgent`

This preserves the repository's strongest existing capability without forcing the whole job assistant to inherit a report-first shape.

## 8. Why Some Components Should Not Be Agents

### 8.1 ProfilePipeline Instead Of ProfileAgent

Reason:

- most resume processing is deterministic extraction and validation
- rule-heavy logic is easier to test and maintain
- only limited synthesis is needed, and that can be internal rather than exposed as a standalone Agent

### 8.2 ApplicationWorkflowService Instead Of ApplicationOpsAgent

Reason:

- application updates are state transitions and persistence concerns
- idempotency matters more than agentic flexibility
- "next step suggestion" can be added later as a small advisor component if needed

### 8.3 InterviewCoachAgent Stays An Agent, But Narrowed

Reason:

- question generation and prioritization are synthesis-heavy
- preparation framing benefits from evidence-based reasoning
- but scope must stay narrow to avoid becoming a vague catch-all agent

## 9. Verifier Rules

The verifier should check at least the following:

### 9.1 Boundary Checks

- no candidate fact may be created from external job evidence
- no recommendation may be presented as fact
- no generated resume line may exceed available evidence

### 9.2 Evidence Checks

- every major strength/gap/risk should reference supporting artifacts
- stale or weak external evidence should lower confidence or trigger downgrade
- conflicting evidence should be surfaced, not silently merged

### 9.3 Output Checks

- matching output must explain recommendation level
- tailoring output must retain fact-check status
- interview prep must distinguish question framing from answer content

### 9.4 Recovery Behavior

- if candidate evidence is weak, stay conservative
- if job evidence is weak, reduce specificity and flag uncertainty
- if artifacts conflict, prefer higher-coverage evidence and record the conflict

## 10. Documentation Strategy

Do not update the repository only through scattered edits in existing specs. Use three layers.

### 10.1 Architecture Docs

Add:

- `docs/architecture/overview.md`
- `docs/architecture/data-flow.md`
- `docs/architecture/agent-topology.md`

These documents define the global structure and must stay stable as the source of truth for system shape.

### 10.2 Domain Specs Under `job-assistant/specs`

Update:

- `00-product-prd.md`
- `02-domain-model.md`

Key additions:

- `ExternalEvidencePack`
- `JobSnapshot`
- `VerificationReport`
- optionally `WorkflowCheckpoint` if resumability becomes first-class

### 10.3 Capability Specs Under `job-assistant/specs`

Recommended updates:

- `10-supervisor-agent.md`: upgrade from lightweight router to orchestration coordinator
- `11-profile-agent.md`: convert into `11-profile-pipeline.md`
- `12-jd-analyst-agent.md`: evolve into `12-job-intelligence-agent.md`
- `13-matching-agent.md`: update to consume `JobSnapshot`
- `14-resume-tailor-agent.md`: clarify job evidence usage boundaries
- `15-interview-coach-agent.md`: narrow responsibilities
- `16-workflow-agent.md`: rewrite around artifact-driven workflow execution
- add `17-verifier-agent.md`
- keep `22-tool-application-store.md`, but pair it later with an application workflow service spec

## 11. Phased Rollout

### Phase 1: Spec And Contract Alignment

- write architecture docs
- update domain model
- realign agent/service boundaries in specs

### Phase 2: Job Intelligence Refactor

- carve job-side enrichment out of the current research graph
- define `ExternalEvidencePack` and `JobSnapshot`
- keep existing retrieval logic, but change its architectural role

### Phase 3: Workflow Integration

- wire `SupervisorAgent` to candidate track, job track, matching track, and verifier
- update downstream tailoring and interview flows to consume shared artifacts

### Phase 4: Application Workflow Integration

- connect application persistence and reminders to the new artifact model

## 12. Testing Strategy

### 12.1 Contract Tests

- artifact schema tests
- backward-compatibility checks where needed

### 12.2 Workflow Tests

- candidate-only input
- job-only input
- combined candidate + JD input
- weak evidence downgrade scenarios
- conflict scenarios between manual JD and external evidence

### 12.3 Guardrail Tests

- fabricated fact rejection
- evidence coverage enforcement
- verifier downgrade enforcement

### 12.4 Regression Tests

- preserve current external evidence retrieval quality
- ensure new orchestration does not regress existing research strengths

## 13. Risks And Tradeoffs

### Risk 1: Over-Agentification

If too many stable modules are modeled as Agents, the system becomes harder to control and test.

Mitigation:

- keep extraction, persistence, and state transitions deterministic

### Risk 2: Artifact Explosion

Too many poorly defined artifacts can increase complexity.

Mitigation:

- introduce only the artifacts that create a clear contract boundary

### Risk 3: Job Evidence Leaking Into Candidate Facts

This is the main semantic risk of the combined design.

Mitigation:

- enforce a strict verifier rule and tailoring boundary

### Risk 4: Reusing The Old Research Graph Too Literally

If the old graph stays the product backbone, the new assistant will remain report-first instead of workflow-first.

Mitigation:

- demote the old graph into a job-side subsystem

## 14. Final Recommendation

Adopt the hybrid architecture with:

- Agents where synthesis and prioritization matter
- Services where determinism matters
- Artifacts as the shared language
- the current research engine repositioned as job evidence enhancement

This gives the project a real agent-system character without sacrificing controllability, auditability, or implementation clarity.
