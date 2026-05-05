from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.core.contracts import RetryTarget


DEFAULT_REQUIRED_SECTIONS = [
    "## 一、岗位与公司概览",
    "## 二、岗位能力要求拆解",
    "## 三、真实面经与面试官追问",
    "## 四、候选人风险点与准备建议",
    "## 五、一周行动清单",
    "## 附：证据来源",
]


class RetrievalPolicy(BaseModel):
    min_evidence_count: int = Field(default=4, ge=0)
    min_company_specific_sources: int = Field(default=2, ge=0)
    generic_source_cap: int = Field(default=3, ge=0)
    context_limit: int = Field(default=12, ge=1)
    cache_ttl_seconds: int = Field(default=600, ge=0)
    required_source_classes: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "general": ["company_profile", "jd", "interview"],
            "tech_coding": ["company_profile", "jd", "interview", "tech_stack"],
            "salary_culture": ["company_profile", "jd", "interview", "salary_culture"],
        }
    )


class QualityPolicy(BaseModel):
    min_claim_count: int = Field(default=4, ge=0)
    min_claim_evidence_coverage: int = Field(default=70, ge=0, le=100)
    min_action_plan_source_coverage: int = Field(default=60, ge=0, le=100)
    min_company_mentions: int = Field(default=2, ge=0)
    min_markdown_headings: int = Field(default=8, ge=0)
    min_report_word_estimate: int = Field(default=320, ge=0)
    min_company_specific_action_items: int = Field(default=2, ge=0)
    min_evidence_bound_action_items: int = Field(default=2, ge=0)
    enable_soft_llm_reviewer: bool = True


class RetryPolicy(BaseModel):
    max_retries: int = Field(default=3, ge=0)
    allow_degraded_output: bool = True
    issue_retry_targets: dict[str, RetryTarget] = Field(
        default_factory=lambda: {
            "company_specific_sources_low": "query",
            "company_specific_requirement_missing": "query",
            "business_domain_missing": "query",
            "missing_tech_stack": "query",
            "tech_not_evidence_backed": "query",
            "generic_interviewer_questions": "insight",
            "generic_risk_section": "insight",
            "templated_action_plan": "insight",
            "action_plan_company_specificity_low": "insight",
            "action_plan_evidence_binding_low": "insight",
            "action_plan_missing_structured_input": "insight",
            "missing_markdown_section": "report",
            "report_too_short": "report",
            "weak_evidence_section_layout": "report",
        }
    )


class ReportPolicy(BaseModel):
    title: str = "专属求职研究报告"
    required_sections: list[str] = Field(default_factory=lambda: list(DEFAULT_REQUIRED_SECTIONS))
    section_order: list[str] = Field(default_factory=lambda: list(DEFAULT_REQUIRED_SECTIONS))
    max_evidence_rows: int = Field(default=10, ge=1)
    min_source_urls_in_report: int = Field(default=2, ge=0)
    renderer_first: bool = True
    enable_llm_polish: bool = True
    polish_overview: bool = True
    polish_interview_angle: bool = True


class EvalPolicy(BaseModel):
    suite_name: str = "bettafish_harness_suite"
    min_retrieval_score: int = Field(default=60, ge=0, le=100)
    min_attribution_score: int = Field(default=60, ge=0, le=100)
    min_insight_score: int = Field(default=60, ge=0, le=100)
    min_report_compliance_score: int = Field(default=70, ge=0, le=100)


class PersistencePolicy(BaseModel):
    enabled: bool = True
    base_dir: str = "logs/harness"
    persist_run_traces: bool = True
    persist_eval_results: bool = True


class HarnessPolicy(BaseModel):
    version: str = "2026-04-04"
    retrieval_policy: RetrievalPolicy = Field(default_factory=RetrievalPolicy)
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    report_policy: ReportPolicy = Field(default_factory=ReportPolicy)
    eval_policy: EvalPolicy = Field(default_factory=EvalPolicy)
    persistence_policy: PersistencePolicy = Field(default_factory=PersistencePolicy)

    def as_serializable(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
