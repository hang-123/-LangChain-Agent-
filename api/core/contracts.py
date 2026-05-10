from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


RootCause = Literal["retrieval", "attribution", "synthesis", "llm_runtime"]
QualityMode = Literal["normal", "conservative", "fallback"]
RetryTarget = Literal["query", "report", "insight"]
IssueSeverity = Literal["low", "medium", "high"]
ResearchIntent = Literal[
    "general", "tech_coding", "salary_culture",
    "match", "resume_tailor", "interview_prep", "offer_compare", "profile_bootstrap",
]


class QueryProfile(BaseModel):
    company: str = Field(..., description="目标公司。")
    role: str = Field(..., description="目标岗位，尽量保留细分描述。")
    team_hint: str = Field(default="", description="若用户提到具体团队/方向，如推荐后端、广告后端、数据平台后端。")
    job_level: str = Field(default="", description="职级提示，如实习、校招、社招。")
    domain_hint: str = Field(default="", description="业务域提示，如推荐、广告、风控、电商、基础架构。")
    priority_topics: list[str] = Field(default_factory=list, description="本轮最值得优先深挖的主题。")


class EvidenceItem(BaseModel):
    source_id: str = Field(..., description="证据唯一标识。")
    source_class: str = Field(..., description="证据类别。")
    query: str = Field(default="", description="触发检索时的查询语句。")
    url: str = Field(default="", description="原始来源链接。")
    title: str = Field(default="无标题", description="来源标题。")
    snippet: str = Field(default="", description="来源摘要。")
    published: str = Field(default="未知", description="来源发布时间。")
    relevance_hint: str = Field(default="", description="相关性说明。")
    company_specific: bool = Field(default=False, description="是否为公司/团队特异性证据。")
    freshness_score: int = Field(default=0, ge=0, le=100, description="时效性评分。")
    quality_score: int = Field(default=0, ge=0, le=100, description="质量评分。")


class RetrievalDiagnostics(BaseModel):
    coverage_by_class: dict[str, int] = Field(default_factory=dict)
    missing_classes: list[str] = Field(default_factory=list)
    company_specific_ratio: float = Field(default=0.0, ge=0.0)
    generic_source_ratio: float = Field(default=0.0, ge=0.0)
    failures: list[str] = Field(default_factory=list)
    failure_breakdown: dict[str, int] = Field(default_factory=dict)
    cached: bool = False
    cache_backend: str = "disabled"
    query_pack_size: int = Field(default=0, ge=0)
    query_pack: list[dict[str, Any]] = Field(default_factory=list)
    source_tier_counts: dict[str, int] = Field(default_factory=dict)
    guardrail_blocked_sources: int = Field(default=0, ge=0)


class Claim(BaseModel):
    claim_id: str = Field(..., description="claim 的唯一标识。")
    claim_type: Literal[
        "company_specific_requirement",
        "common_requirement",
        "technical_stack",
        "salary_signal",
        "interview_expectation",
        "company_signal",
        "role_signal",
    ] = Field(..., description="claim 类型。")
    statement: str = Field(..., description="结构化后的事实或结论。")
    evidence_refs: list[str] = Field(default_factory=list, description="该 claim 绑定的证据引用。")
    confidence: int = Field(default=0, ge=0, le=100, description="对该 claim 的置信度。")
    company_specific: bool = Field(default=False, description="该 claim 是否体现当前公司/团队特异性。")


class ActionPlanItem(BaseModel):
    day: int = Field(..., ge=1, le=7, description="执行日。")
    priority: Literal["high", "medium", "low"] = Field(default="medium", description="行动项优先级。")
    goal: str = Field(..., description="这一天的核心目标。")
    task: str = Field(..., description="具体动作。")
    why_this_company: str = Field(..., description="为什么这项动作与当前公司/岗位强相关。")
    expected_outcome: str = Field(..., description="当天产出的可交付物。")
    evidence_refs: list[str] = Field(default_factory=list, description="对应的证据引用。")


class ReviewIssueDetail(BaseModel):
    issue_code: str = Field(..., description="结构化问题编码。")
    severity: IssueSeverity = Field(default="medium", description="问题严重程度。")
    retry_target: RetryTarget = Field(default="report", description="该问题推荐的回退节点。")
    root_cause: RootCause = Field(default="synthesis", description="该问题更偏向哪个根因层。")
    message: str = Field(..., description="对这个问题的简要描述。")


class QualitySummary(BaseModel):
    run_id: str = ""
    quality_mode: QualityMode = "normal"
    warning_message: str = ""
    root_cause: str = ""
    root_cause_history: list[dict[str, Any]] = Field(default_factory=list)
    evidence_count: int = Field(default=0, ge=0)
    company_specific_source_count: int = Field(default=0, ge=0)
    claim_evidence_coverage: int = Field(default=0, ge=0, le=100)
    action_plan_source_coverage: int = Field(default=0, ge=0, le=100)
    fallback_report: bool = False
    fallback_query: bool = False
    fallback_insight: bool = False
    retrieval_cached: bool = False
    query_pack_size: int = Field(default=0, ge=0)
    guardrail_events: int = Field(default=0, ge=0)


class RunTraceEntry(BaseModel):
    run_id: str = ""
    node: str
    phase: str
    detail: str
    timestamp: str
    retry_count: int = Field(default=0, ge=0)
    root_cause: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class SecurityAuditEvent(BaseModel):
    run_id: str = ""
    rail_type: str
    reason_code: str
    action_taken: Literal["warn", "block", "redact"]
    content_hash: str
    content_summary: str = ""
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodePerf(BaseModel):
    node_name: str
    attempt: int = Field(default=1, ge=1)
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    token_in: int = Field(default=0, ge=0)
    token_out: int = Field(default=0, ge=0)
    token_total: int = Field(default=0, ge=0)
    token_estimated: bool = False
    fallback_triggered: bool = False
    fallback_target: str = ""
    models: list[str] = Field(default_factory=list)
    error_count: int = Field(default=0, ge=0)


class PerfBill(BaseModel):
    run_id: str
    generated_at: str
    total_duration_ms: int = Field(default=0, ge=0)
    total_llm_calls: int = Field(default=0, ge=0)
    total_tool_calls: int = Field(default=0, ge=0)
    total_token_in: int = Field(default=0, ge=0)
    total_token_out: int = Field(default=0, ge=0)
    total_token_total: int = Field(default=0, ge=0)
    node_count: int = Field(default=0, ge=0)
    nodes: list[NodePerf] = Field(default_factory=list)


class ResearchCase(BaseModel):
    case_id: str
    query: str
    expected_intent: ResearchIntent
    minimum_evidence_count: int = Field(default=4, ge=0)
    company_assertions: list[str] = Field(default_factory=list)
    allow_conservative: bool = True
    risk_tags: list[str] = Field(default_factory=list)
    candidate_profile: dict[str, Any] = Field(default_factory=dict)
    resume_evidence: list[dict[str, Any]] = Field(default_factory=list)
    match_ground_truth: dict[str, Any] = Field(default_factory=dict)
    resume_ground_truth: dict[str, Any] = Field(default_factory=dict)


class IntentRouterResponse(BaseModel):
    intent: ResearchIntent = Field(..., description="用户本轮查询的意图。")
    reason: str = Field(..., description="判定该意图的简要原因。")
    query_profile: QueryProfile = Field(..., description="当前查询的公司、岗位和细分方向画像。")


class QueryAgentResponse(BaseModel):
    company: str = Field(..., description="目标公司。")
    role: str = Field(..., description="目标岗位。")
    company_signals: list[str] = Field(default_factory=list, description="从公司画像证据中抽出的关键特征。")
    role_signals: list[str] = Field(default_factory=list, description="从岗位画像证据中抽出的关键特征。")
    business_domain_hints: list[str] = Field(default_factory=list, description="当前岗位涉及的业务域线索。")
    core_evaluation_points: list[str] = Field(default_factory=list, description="面试官真正关注的核心能力点。")
    company_specific_requirements: list[str] = Field(default_factory=list, description="当前公司/团队更特有的要求。")
    common_requirements: list[str] = Field(default_factory=list, description="行业通用要求。")
    technical_stack_requirements: list[str] = Field(default_factory=list, description="从真实 JD / 面经中提取的技术栈要求。")
    salary_signals: list[str] = Field(default_factory=list, description="薪资区间、职级或待遇线索。")
    interview_expectations: list[str] = Field(default_factory=list, description="面试官对候选人的能力预期。")
    claims: list[Claim] = Field(default_factory=list, description="基于证据生成的中间 claim 列表。")
    evidence_map: dict[str, list[str]] = Field(default_factory=dict, description="结论与证据的对应关系。")
    quality_metrics: dict[str, Any] = Field(default_factory=dict, description="Query 阶段的质量指标。")
    context_quality_score: int = Field(default=0, ge=0, le=100, description="当前证据质量评分。")
    coverage_gaps: list[str] = Field(default_factory=list, description="当前仍然缺失的证据类型。")


class InsightAgentResponse(BaseModel):
    candidate_risks: list[str] = Field(default_factory=list, description="候选人最容易被追问或暴露短板的风险点。")
    interviewer_questions: list[str] = Field(default_factory=list, description="面试官视角下的高压追问。")
    prep_strategy: list[str] = Field(default_factory=list, description="对应的准备动作和强化建议。")
    interview_angle: str = Field(..., description="站在面试官视角对候选人的定性判断。")
    evidence_gap_summary: list[str] = Field(default_factory=list, description="当前仍需补充的证据缺口。")
    action_plan_items: list[ActionPlanItem] = Field(default_factory=list, description="动态生成的一周行动项。")
    action_plan_source_coverage: int = Field(default=0, ge=0, le=100, description="行动项绑定证据的覆盖率。")
    root_cause_hint: str = Field(default="", description="当前质量瓶颈更偏向 retrieval / attribution / synthesis。")
    quality_metrics: dict[str, Any] = Field(default_factory=dict, description="Insight 阶段的质量指标。")


class ReviewAgentResponse(BaseModel):
    passed: bool = Field(..., description="报告是否达到交付标准。")
    quality_score: int = Field(default=0, ge=0, le=100, description="0-100 的报告质量分。")
    issues: list[str] = Field(default_factory=list, description="本轮报告存在的具体问题。")
    issue_details: list[ReviewIssueDetail] = Field(default_factory=list, description="结构化问题详情。")
    feedback_markdown: str = Field(..., description="给 QueryAgent / InsightAgent / ReportAgent 的可执行修改建议。")
    retry_target: RetryTarget = Field(default="report", description="若需重试，应回退到哪个节点。")
    root_cause: RootCause = Field(default="synthesis", description="本轮报告的主问题更偏向哪个根因层。")


class NodeScorecard(BaseModel):
    retrieval: int = Field(default=0, ge=0, le=100)
    attribution: int = Field(default=0, ge=0, le=100)
    insight: int = Field(default=0, ge=0, le=100)
    report_compliance: int = Field(default=0, ge=0, le=100)
    matching: int = Field(default=0, ge=0, le=100)
    resume: int = Field(default=0, ge=0, le=100)


class EvalMetadata(BaseModel):
    run_id: str = ""
    case_id: str = ""
    prompt_version: str = "unknown"
    policy_version: str = "unknown"
    code_version: str = "unknown"
    model_name: str = "unknown"
    experiment_id: str = ""
    variant: str = "control"


class CaseEvaluation(BaseModel):
    case_id: str
    passed: bool
    score: int = Field(default=0, ge=0, le=100)
    expected_intent: str
    actual_intent: str
    failures: list[str] = Field(default_factory=list)
    root_cause: str = ""
    quality_mode: str = "normal"
    metrics: dict[str, Any] = Field(default_factory=dict)
    node_scores: NodeScorecard = Field(default_factory=NodeScorecard)
    metadata: EvalMetadata = Field(default_factory=EvalMetadata)


class EvalSuiteSummary(BaseModel):
    suite_name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    average_score: float
    root_cause_breakdown: dict[str, int] = Field(default_factory=dict)
    case_results: list[CaseEvaluation] = Field(default_factory=list)


class UserFeedbackRecord(BaseModel):
    run_id: str
    user_id: str = ""
    score: int = Field(default=0, ge=0, le=5)
    comment: str = ""
    created_at: str


class ExternalEvidenceItem(BaseModel):
    source_id: str
    source_type: str = Field(..., description="来源类型，如 job_board、company_site、interview_note。")
    title: str = Field(default="无标题")
    url: str = Field(default="")
    snippet: str = Field(default="")
    freshness_score: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_class: str = Field(default="", description="证据类别，如 real_jd、company_context、interview_signal。")


class ExternalEvidencePack(BaseModel):
    evidence_pack_id: str
    job_id: str
    sources: list[ExternalEvidenceItem] = Field(default_factory=list)
    company_signals: list[str] = Field(default_factory=list)
    interview_signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class JobSnapshot(BaseModel):
    job_snapshot_id: str
    job_id: str
    job_posting: dict[str, Any] = Field(default_factory=dict)
    job_requirements: list[dict[str, Any]] = Field(default_factory=list)
    external_evidence_pack_id: str = ""
    evidence_quality: dict[str, Any] = Field(default_factory=dict)


class MatchAssessment(BaseModel):
    assessment_id: str
    candidate_id: str
    job_id: str
    overall_score: int = Field(default=0, ge=0, le=100)
    recommendation: Literal["strong_recommend", "recommended_with_risks", "neutral", "not_recommended"] = "neutral"
    strengths: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    reasoning_notes: list[str] = Field(default_factory=list)
    created_at: str


class ResumeTailorSectionAction(BaseModel):
    section: str = Field(..., description="需要改写或强调的简历 section。")
    action: Literal["rewrite", "prioritize", "compress", "guidance"] = Field(
        default="rewrite",
        description="对该 section 的建议动作。",
    )
    instruction: str = Field(..., description="可执行的改写指令。")
    allowed_evidence_refs: list[str] = Field(default_factory=list, description="可用于支持该动作的证据引用。")


class ResumeTailoringPlan(BaseModel):
    tailor_plan_id: str
    candidate_id: str
    job_id: str
    target_role: str = Field(default="", description="目标岗位名称。")
    headline_suggestion: str = Field(default="", description="建议放到简历头部的简洁摘要。")
    keyword_coverage: dict[str, list[str]] = Field(default_factory=dict)
    section_actions: list[ResumeTailorSectionAction] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class ResumeVersion(BaseModel):
    resume_version_id: str
    candidate_id: str
    job_id: str
    source_resume_id: str = Field(default="", description="原始简历资产 ID。")
    version_label: str = Field(default="", description="面向该岗位的版本标签。")
    summary_text: str = Field(default="", description="岗位定制后的简历摘要。")
    project_bullets: list[str] = Field(default_factory=list)
    keyword_insertions: list[str] = Field(default_factory=list)
    omissions: list[str] = Field(default_factory=list)
    fact_check_status: str = Field(default="passed")
    created_at: str


class FactCheckReport(BaseModel):
    verification_id: str
    artifact_type: str
    artifact_id: str
    status: Literal["passed", "downgraded", "rejected"] = Field(default="passed")
    blocked_claims: list[str] = Field(default_factory=list)
    checked_rules: list[str] = Field(default_factory=list)
    created_at: str


class VerificationIssue(BaseModel):
    rule_code: str
    severity: Literal["low", "medium", "high"] = "medium"
    message: str


class VerificationReport(BaseModel):
    verification_id: str
    artifact_type: str
    artifact_id: str
    status: Literal["passed", "downgraded", "rejected"] = "passed"
    issues: list[VerificationIssue] = Field(default_factory=list)
    checked_rules: list[str] = Field(default_factory=list)
    created_at: str


# ═══════════════════════════════════════════════════════════════
# career-ops Integration Models (Level 1 — Data Contracts)
# ═══════════════════════════════════════════════════════════════


# ── Archetype Detection ──


class Archetype(str, Enum):
    """Job role archetypes — matches career-ops classification system."""

    LLMOPS = "AI Platform / LLMOps"
    AGENTIC = "Agentic / Automation"
    AI_PM = "Technical AI PM"
    SOLUTIONS_ARCHITECT = "AI Solutions Architect"
    FORWARD_DEPLOYED = "AI Forward Deployed"
    TRANSFORMATION = "AI Transformation"


class ArchetypeDetection(BaseModel):
    """Output of archetype classification for a job posting."""

    primary: Archetype
    secondary: Archetype | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    keyword_matches: list[str] = Field(default_factory=list)
    reasoning: str = ""


# ── Legitimacy Assessment (Ghost Job Detection) ──


class LegitimacyTier(str, Enum):
    """Three-tier classification for posting legitimacy."""

    HIGH_CONFIDENCE = "High Confidence"
    PROCEED_CAUTION = "Proceed with Caution"
    SUSPICIOUS = "Suspicious"


class LegitimacySignal(BaseModel):
    """A single observed signal contributing to the legitimacy assessment."""

    signal_name: str
    finding: str
    weight: Literal["Positive", "Neutral", "Concerning"]
    reliability: Literal["High", "Medium", "Low"]


class LegitimacyAssessment(BaseModel):
    """Block G output — independent of the 1-5 global score."""

    tier: LegitimacyTier
    posting_age_days: int | None = None
    apply_button_active: bool | None = None
    tech_specificity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    requirements_realism_score: float = Field(default=1.0, ge=0.0, le=1.0)
    layoff_signals: list[str] = Field(default_factory=list)
    repost_count_90d: int = 0
    signals_table: list[LegitimacySignal] = Field(default_factory=list)
    context_notes: str = ""
    # Batch mode flag: Playwright not available → freshness signals unverified
    batch_mode: bool = False


# ── Match Gap Analysis ──


class GapSeverity(str, Enum):
    """Four-level gap classification."""

    HARD_BLOCKER = "hard_blocker"
    SIGNIFICANT = "significant"
    NICE_TO_HAVE = "nice_to_have"
    SOFT = "soft"


class MatchGap(BaseModel):
    """A single gap between JD requirements and candidate capabilities."""

    description: str
    severity: GapSeverity
    adjacent_experience: str | None = None
    portfolio_coverage: str | None = None
    mitigation_plan: str = ""


# ── Offer Comparison (10-Dimension Weighted Matrix) ──


class OfferDimension(str, Enum):
    """Weighted dimensions for multi-offer comparison."""

    NORTH_STAR = "north_star_alignment"
    CV_MATCH = "cv_match"
    SENIORITY = "seniority_level"
    COMPENSATION = "compensation"
    GROWTH = "growth_trajectory"
    REMOTE = "remote_quality"
    REPUTATION = "company_reputation"
    TECH_STACK = "tech_stack_modernity"
    SPEED = "speed_to_offer"
    CULTURE = "cultural_signals"


# Default weights from career-ops ofertas mode
DEFAULT_OFFER_WEIGHTS: dict[OfferDimension, float] = {
    OfferDimension.NORTH_STAR: 0.25,
    OfferDimension.CV_MATCH: 0.15,
    OfferDimension.SENIORITY: 0.15,
    OfferDimension.COMPENSATION: 0.10,
    OfferDimension.GROWTH: 0.10,
    OfferDimension.REMOTE: 0.05,
    OfferDimension.REPUTATION: 0.05,
    OfferDimension.TECH_STACK: 0.05,
    OfferDimension.SPEED: 0.05,
    OfferDimension.CULTURE: 0.05,
}


class OfferComparison(BaseModel):
    """Multi-offer comparison result."""

    dimensions: dict[str, float] = Field(default_factory=dict)
    scores: dict[str, dict[str, float]] = Field(default_factory=dict)
    weighted_totals: dict[str, float] = Field(default_factory=dict)
    ranking: list[str] = Field(default_factory=list)
    recommendation: str = ""


# ── STAR+R Stories ──


class STARStory(BaseModel):
    """A STAR+R story for interview preparation.

    The Reflection field distinguishes senior candidates (who extract
    lessons) from junior candidates (who only describe what happened).
    """

    story_id: str
    title: str = ""
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    reflection: str = ""
    archetypes: list[Archetype] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


# ── Adaptive Framing ──


class AdaptiveFraming(BaseModel):
    """Archetype-specific narrative angles for the same underlying experience.

    Maps "Technical builder" persona to different presentation angles
    depending on the target role archetype.
    """

    archetype: Archetype
    headline: str = ""
    emphasize: list[str] = Field(default_factory=list)
    de_emphasize: list[str] = Field(default_factory=list)
    proof_point_priority: list[str] = Field(default_factory=list)


# ── Follow-up Cadence ──


class FollowupUrgency(str, Enum):
    URGENT = "urgent"
    OVERDUE = "overdue"
    WAITING = "waiting"
    COLD = "cold"


class FollowupRecommendation(BaseModel):
    """A single follow-up recommendation for an active application."""

    application_id: str
    company: str
    role: str
    status: str
    days_since_application: int = 0
    days_since_last_followup: int | None = None
    followup_count: int = 0
    urgency: FollowupUrgency = FollowupUrgency.WAITING
    next_followup_date: str | None = None
    days_until_next: int | None = None


# ═══════════════════════════════════════════════════════════════
# Phase 2 — Supervisor, Gate, Interview, Offer Contracts
# ═══════════════════════════════════════════════════════════════

GateStatus = Literal["passed", "downgraded", "rejected"]
WorkflowId = Literal[
    "wf_match_v2", "wf_resume_tailor_v2", "wf_interview_prep_v2",
    "wf_profile_bootstrap", "wf_offer_compare", "wf_application_followup_v1",
]


class SupervisorResponse(BaseModel):
    """Supervisor output: intent + workflow selection + missing param detection."""
    intent: ResearchIntent = Field(default="general")
    workflow_id: WorkflowId = Field(default="wf_match_v2")
    query_profile: QueryProfile = Field(default_factory=QueryProfile)
    missing_artifacts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reasoning: str = ""


class GateInput(BaseModel):
    """Input to the Gate from workflow state."""
    artifacts: dict[str, Any] = Field(default_factory=dict)
    working_set: dict[str, Any] = Field(default_factory=dict)
    background: dict[str, Any] = Field(default_factory=dict)


class GateOutput(BaseModel):
    """Gate output: three-state decision."""
    status: GateStatus = "passed"
    issues: list[dict[str, Any]] = Field(default_factory=list)
    checked_rules: list[str] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    question: str = ""
    category: Literal["behavioral", "technical", "project_deep_dive"] = "behavioral"
    evidence_refs: list[str] = Field(default_factory=list)
    answer_framework: str = ""


class InterviewPrepPack(BaseModel):
    prep_id: str = ""
    candidate_id: str = ""
    job_id: str = ""
    behavioral_questions: list[InterviewQuestion] = Field(default_factory=list)
    technical_questions: list[InterviewQuestion] = Field(default_factory=list)
    project_deep_dive: list[InterviewQuestion] = Field(default_factory=list)
    practice_advice: list[str] = Field(default_factory=list)
    risk_questions: list[InterviewQuestion] = Field(default_factory=list)


class OfferData(BaseModel):
    offer_id: str = ""
    company: str = ""
    role: str = ""
    north_star_alignment: float = 0.0
    cv_match: float = 0.0
    seniority_level: float = 0.0
    compensation: float = 0.0
    growth_trajectory: float = 0.0
    remote_quality: float = 0.0
    company_reputation: float = 0.0
    tech_stack_modernity: float = 0.0
    speed_to_offer: float = 0.0
    cultural_signals: float = 0.0


class ResumeParseResult(BaseModel):
    resume_id: str = ""
    candidate_id: str = ""
    candidate_profile: dict[str, Any] = Field(default_factory=dict)
    resume_evidence: list[dict[str, Any]] = Field(default_factory=list)
    profile_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    profile_gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_type: str = ""
    source_name: str = ""
    language: str = "zh-CN"
    parsed_at: str = ""


# ── Application Store Models ──

ApplicationStatus = Literal[
    "draft", "planned", "applied", "screening",
    "written_test", "interviewing", "offer",
    "rejected", "withdrawn",
]


class ApplicationNote(BaseModel):
    note_id: str = ""
    content: str = ""
    created_at: str = ""


class ApplicationRecord(BaseModel):
    application_id: str = ""
    candidate_id: str = ""
    job_id: str = ""
    company: str = ""
    role: str = ""
    status: ApplicationStatus = "draft"
    notes: list[ApplicationNote] = Field(default_factory=list)
    created_at: str = ""
    last_updated_at: str = ""


ApplicationStoreOperation = Literal[
    "create_application", "update_status", "append_note",
    "list_applications", "get_application",
]


class ApplicationStoreRequest(BaseModel):
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ApplicationStoreResponse(BaseModel):
    ok: bool = True
    application_record: ApplicationRecord | None = None
    application_records: list[ApplicationRecord] | None = None
    error_code: str = ""
    message: str = ""
