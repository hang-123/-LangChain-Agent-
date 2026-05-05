from __future__ import annotations

from dataclasses import dataclass

from api.core.contracts import ReviewIssueDetail
from api.core.policies import HarnessPolicy


@dataclass(frozen=True)
class IssueTemplate:
    severity: str
    retry_target: str
    root_cause: str


ISSUE_CATALOG: dict[str, IssueTemplate] = {
    "empty_report": IssueTemplate("high", "report", "synthesis"),
    "missing_markdown_section": IssueTemplate("high", "report", "synthesis"),
    "markdown_heading_count_low": IssueTemplate("medium", "report", "synthesis"),
    "report_too_short": IssueTemplate("medium", "report", "synthesis"),
    "tech_coverage_low": IssueTemplate("high", "report", "synthesis"),
    "tech_not_evidence_backed": IssueTemplate("high", "query", "attribution"),
    "missing_tech_stack": IssueTemplate("high", "query", "retrieval"),
    "insufficient_source_urls": IssueTemplate("high", "report", "synthesis"),
    "stale_context_placeholder": IssueTemplate("medium", "report", "synthesis"),
    "generic_interviewer_questions": IssueTemplate("high", "insight", "synthesis"),
    "weak_evidence_section_layout": IssueTemplate("medium", "report", "synthesis"),
    "generic_risk_section": IssueTemplate("high", "insight", "synthesis"),
    "company_mentions_too_few": IssueTemplate("high", "query", "attribution"),
    "company_specific_sources_low": IssueTemplate("high", "query", "retrieval"),
    "company_specific_requirement_missing": IssueTemplate("high", "query", "attribution"),
    "business_domain_missing": IssueTemplate("medium", "query", "attribution"),
    "templated_action_plan": IssueTemplate("high", "insight", "synthesis"),
    "action_plan_company_specificity_low": IssueTemplate("high", "insight", "attribution"),
    "action_plan_evidence_binding_low": IssueTemplate("high", "insight", "attribution"),
    "action_plan_missing_structured_input": IssueTemplate("high", "insight", "synthesis"),
    "action_plan_source_coverage_low": IssueTemplate("medium", "insight", "attribution"),
}


def build_issue(
    issue_code: str,
    message: str,
    *,
    policy: HarnessPolicy,
    severity: str | None = None,
    retry_target: str | None = None,
    root_cause: str | None = None,
) -> ReviewIssueDetail:
    template = ISSUE_CATALOG.get(issue_code, IssueTemplate("medium", "report", "synthesis"))
    override_target = policy.retry_policy.issue_retry_targets.get(issue_code)
    return ReviewIssueDetail(
        issue_code=issue_code,
        severity=(severity or template.severity),  # type: ignore[arg-type]
        retry_target=(retry_target or override_target or template.retry_target),  # type: ignore[arg-type]
        root_cause=(root_cause or template.root_cause),  # type: ignore[arg-type]
        message=message,
    )
