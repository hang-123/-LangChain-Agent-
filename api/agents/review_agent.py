# DEPRECATED (Phase 2): absorbed into api/core/gate.py + api/agents/report_agent.py self-review.
# Retained for backward compatibility. Do not add new features here.
from __future__ import annotations

import json

from api.core.contracts import ReviewAgentResponse, ReviewIssueDetail
from api.core.policy_loader import policy_from_state
from api.review.llm_reviewer import run_llm_reviewer
from api.review.rule_checker import run_rule_checker


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = item.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _dedupe_issue_details(issue_details: list[ReviewIssueDetail]) -> list[ReviewIssueDetail]:
    seen: set[str] = set()
    result: list[ReviewIssueDetail] = []
    for issue in issue_details:
        key = f"{issue.issue_code}|{issue.message}"
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _pick_retry_target(issue_details: list[ReviewIssueDetail], llm_target: str | None = None) -> str:
    if any(issue.retry_target == "query" for issue in issue_details):
        return "query"
    if any(issue.retry_target == "insight" for issue in issue_details):
        return "insight"
    if llm_target in {"query", "report", "insight"}:
        return llm_target
    return "report"


def _pick_root_cause(issue_details: list[ReviewIssueDetail], fallback: str = "synthesis") -> str:
    for candidate in ("retrieval", "attribution", "synthesis", "llm_runtime"):
        if any(issue.root_cause == candidate for issue in issue_details):
            return candidate
    return fallback


def _merge_reviews(rule_review: ReviewAgentResponse, llm_review: ReviewAgentResponse | None) -> ReviewAgentResponse:
    if llm_review is None:
        return rule_review

    issue_details = _dedupe_issue_details(list(rule_review.issue_details) + list(llm_review.issue_details or []))
    issues = _dedupe([issue.message for issue in issue_details] + rule_review.issues + llm_review.issues)
    passed = rule_review.passed and llm_review.passed and not issues
    llm_score = llm_review.quality_score or rule_review.quality_score

    feedback_parts: list[str] = []
    if issues:
        feedback_parts.append("请优先修复以下问题：")
        feedback_parts.extend(f"- {issue}" for issue in issues[:8])
    else:
        feedback_parts.append("审查通过：报告已满足交付标准。")

    llm_feedback = (llm_review.feedback_markdown or "").strip()
    if llm_feedback and llm_feedback not in "\n".join(feedback_parts):
        feedback_parts.extend(["", "LLM 审查补充：", llm_feedback])

    return ReviewAgentResponse(
        passed=passed,
        quality_score=min(rule_review.quality_score, llm_score),
        issues=issues,
        issue_details=issue_details,
        feedback_markdown="\n".join(feedback_parts).strip(),
        retry_target=_pick_retry_target(issue_details, llm_review.retry_target),
        root_cause=_pick_root_cause(issue_details, llm_review.root_cause),
    )


async def review_agent_node(state: dict[str, object]) -> dict[str, object]:
    policy = policy_from_state(state)
    max_retries = policy.retry_policy.max_retries
    retry_count = int(state.get("retry_count") or 0)
    report = str(state.get("report_content") or "")

    rule_review = run_rule_checker(state)
    try:
        llm_review = await run_llm_reviewer(state)
    except Exception:
        llm_review = None

    response = _merge_reviews(rule_review, llm_review)
    feedback_json = json.dumps(response.model_dump(), ensure_ascii=False)

    if not response.passed and retry_count >= max_retries:
        final_warning = "⚠️ 系统已尽最大努力生成，当前为最终调优版本"
        if final_warning not in report:
            report = final_warning + "\n\n" + report
        return {
            "report_content": report,
            "review_feedback": feedback_json,
            "warning_message": str(state.get("warning_message") or "ReviewAgent 在最大重试次数内仍未完全通过审查。"),
            "root_cause": response.root_cause,
            "status": f"⚠️ 审查未完全通过，已触发熔断（MAX_RETRIES={max_retries}）。",
        }

    if not response.passed and retry_count < max_retries:
        return {
            "retry_count": retry_count + 1,
            "review_feedback": feedback_json,
            "report_content": report,
            "root_cause": response.root_cause,
            "status": f"⚖️ 审查未通过，将回退到 {response.retry_target} 节点继续重写（已累计重试 {retry_count + 1} 次）。",
        }

    return {
        "review_feedback": feedback_json,
        "root_cause": response.root_cause,
        "status": f"✅ 质量审查通过（score={response.quality_score}）。",
    }
