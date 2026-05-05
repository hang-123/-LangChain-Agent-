# Job Assistant Data Flow

## Candidate Track

`ResumeAsset -> ProfilePipeline -> CandidateProfile + ResumeEvidence`

Candidate-side facts are only allowed to come from resume evidence or explicit user patch input.

## Job Track

`raw_jd_text + target_company + target_role -> JobIntelligenceAgent -> JobPosting + JobRequirement + ExternalEvidencePack -> JobSnapshot`

Job-side evidence combines manual JD parsing and external evidence enhancement, while preserving freshness and ambiguity notes.

## Decision Track

`CandidateProfile + ResumeEvidence + JobSnapshot -> MatchingAgent -> MatchAssessment`

Downstream consumers:

- `ResumeTailorAgent -> ResumeTailoringPlan + ResumeVersion`
- `InterviewCoachAgent -> InterviewPrepPack`
- `ApplicationWorkflowService -> ApplicationRecord`

## Verification Track

`user-visible artifact -> VerifierAgent -> approve | downgrade | reject`

Core ordering rule:

`facts -> evidence enhancement -> decision -> verification -> persistence -> response`
