export type AgentName =
  | "User"
  | "IntentRouterNode"
  | "SearchAgent"
  | "QueryAgent"
  | "InsightAgent"
  | "QualityGate"
  | "ReportAgent"
  | "ReviewAgent"
  | "System";

export type AgentRunState = "idle" | "running" | "done" | "error";

export interface AgentStatus {
  agent: AgentName;
  status: AgentRunState;
  detail: string;
  retryCount: number;
}

export interface StreamLogEntry {
  id: string;
  kind: "user" | "status" | "message" | "error";
  agent: AgentName;
  title: string;
  content: string;
  runId?: string;
  node?: string;
  metadata?: Record<string, unknown> | null;
  timestamp: string;
}

export type NoticeLevel = "info" | "warning" | "error";

export interface UiNotice {
  level: NoticeLevel;
  title: string;
  message: string;
  hints?: string[];
}

export type QualityMode = "normal" | "conservative" | "fallback";

export type ReportRenderMode = "waiting" | "streaming" | "ready" | "conservative" | "fallback";

export type WorkflowStatus = "running" | "completed" | "recoverable" | "verifier-approved";

export interface WorkflowSummary {
  workflow_status: WorkflowStatus;
  completed_steps: string[];
  pending_steps: string[];
  next_recommended_action: string;
}

export interface MatchAssessmentStrength {
  title?: string;
  evidence_refs?: string[];
}

export interface MatchAssessmentGap {
  title?: string;
  severity?: string;
  evidence_refs?: string[];
}

export interface MatchAssessmentRisk {
  title?: string;
  severity?: string;
}

export interface MatchAssessmentArtifact {
  assessment_id?: string;
  candidate_id?: string;
  job_id?: string;
  overall_score?: number;
  recommendation?: string;
  strengths?: MatchAssessmentStrength[];
  gaps?: MatchAssessmentGap[];
  risks?: MatchAssessmentRisk[];
  dimension_scores?: Record<string, number>;
  reasoning_notes?: string[];
  created_at?: string;
}

export interface TailorPlanSectionAction {
  section?: string;
  action?: string;
  instruction?: string;
  allowed_evidence_refs?: string[];
}

export interface TailorPlanArtifact {
  tailor_plan_id?: string;
  candidate_id?: string;
  job_id?: string;
  target_role?: string;
  headline_suggestion?: string;
  keyword_coverage?: {
    covered?: string[];
    missing?: string[];
    overused?: string[];
  };
  section_actions?: TailorPlanSectionAction[];
  risk_notes?: string[];
}

export interface ResumeVersionArtifact {
  resume_version_id?: string;
  candidate_id?: string;
  job_id?: string;
  source_resume_id?: string;
  version_label?: string;
  summary_text?: string;
  project_bullets?: string[];
  keyword_insertions?: string[];
  omissions?: string[];
  fact_check_status?: string;
  created_at?: string;
}

export interface FactCheckReportArtifact {
  status?: string;
  blocked_claims?: Array<string | { claim?: string; reason?: string }>;
  checked_rules?: string[];
  issues?: string[];
  created_at?: string;
}

export interface ResumeTailoringArtifacts {
  matchAssessment: MatchAssessmentArtifact | null;
  tailorPlan: TailorPlanArtifact | null;
  resumeVersion: ResumeVersionArtifact | null;
  factCheckReport: FactCheckReportArtifact | null;
}

export interface ResumeTailoringArtifactsPayload {
  match_assessment?: MatchAssessmentArtifact | null;
  tailor_plan?: TailorPlanArtifact | null;
  resume_version?: ResumeVersionArtifact | null;
  fact_check_report?: FactCheckReportArtifact | null;
}

export interface ReportQualitySummary {
  runId?: string;
  qualityMode: QualityMode;
  warningMessage: string;
  rootCause: string;
  rootCauseHistory?: Array<Record<string, unknown>>;
  evidenceCount: number;
  companySpecificSourceCount: number;
  claimEvidenceCoverage: number;
  actionPlanSourceCoverage: number;
  fallbackReport: boolean;
}

export interface ResearchRunResponse {
  run_id: string;
  report_markdown: string;
  insights: Record<string, unknown>;
  review?: Record<string, unknown> | null;
  match_assessment?: MatchAssessmentArtifact | null;
  tailor_plan?: TailorPlanArtifact | null;
  resume_version?: ResumeVersionArtifact | null;
  fact_check_report?: FactCheckReportArtifact | null;
  resume_artifacts?: ResumeTailoringArtifactsPayload | null;
  resume_tailoring?: ResumeTailoringArtifactsPayload | null;
  retry_count: number;
  quality_summary: Record<string, unknown>;
  trace: Array<Record<string, unknown>>;
  quality_mode: QualityMode;
  warning_message: string;
  root_cause: string;
  workflow_status?: WorkflowStatus;
  completed_steps?: string[];
  pending_steps?: string[];
  next_recommended_action?: string;
  workflow_summary?: WorkflowSummary | null;
}

export interface ResearchSessionInput {
  query: string;
  candidate_profile?: Record<string, unknown>;
  resume_evidence?: Record<string, unknown>[];
  job_posting?: Record<string, unknown>;
  match_assessment?: Record<string, unknown>;
}

export interface StreamMetaEvent {
  type: "meta";
  run_id: string;
  query: string;
  max_retries: number;
  started_at: string;
  timestamp: string;
  metrics?: Record<string, unknown>;
}

export interface StreamStatusEvent {
  type: "status";
  run_id: string;
  node: string;
  agent: AgentName;
  phase: "started" | "completed";
  detail: string;
  timestamp: string;
  metrics?: Record<string, unknown>;
  retry_count?: number;
}

export interface StreamMessageEvent {
  type: "message";
  run_id: string;
  node: string;
  speaker: AgentName;
  content: string;
  metrics?: Record<string, unknown>;
  metadata?: Record<string, unknown> | null;
  timestamp?: string;
}

export interface StreamChunkEvent {
  type: "chunk";
  run_id: string;
  node: string;
  timestamp: string;
  content: string;
}

export interface StreamDoneEvent {
  type: "done";
  run_id: string;
  node: string;
  timestamp: string;
  report_markdown?: string | null;
  match_assessment?: MatchAssessmentArtifact | null;
  tailor_plan?: TailorPlanArtifact | null;
  resume_version?: ResumeVersionArtifact | null;
  fact_check_report?: FactCheckReportArtifact | null;
  resume_artifacts?: ResumeTailoringArtifactsPayload | null;
  resume_tailoring?: ResumeTailoringArtifactsPayload | null;
  retry_count?: number;
  quality_summary?: Record<string, unknown>;
  trace?: Array<Record<string, unknown>>;
  metrics?: Record<string, unknown>;
  workflow_status?: WorkflowStatus;
  completed_steps?: string[];
  pending_steps?: string[];
  next_recommended_action?: string;
  workflow_summary?: WorkflowSummary | null;
}

export interface StreamErrorEvent {
  type: "error";
  run_id?: string;
  node?: string;
  timestamp?: string;
  detail: string;
  error_type?: string;
  traceback?: string;
}

export type ResearchStreamEvent =
  | StreamMetaEvent
  | StreamStatusEvent
  | StreamMessageEvent
  | StreamChunkEvent
  | StreamDoneEvent
  | StreamErrorEvent;
