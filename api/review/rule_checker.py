from __future__ import annotations

import re
from typing import Any

from api.core.contracts import ReviewAgentResponse, ReviewIssueDetail
from api.core.policy_loader import policy_from_state
from api.review.issue_catalog import build_issue


GENERIC_ACTION_PLAN_PHRASES = [
    "通读真实 JD / 面经证据",
    "做一次 45 分钟模拟面试",
    "补齐证据链接",
    "最终版自我介绍",
    "一页答题索引",
]


def _count_markdown_headings(md: str) -> int:
    return len(re.findall(r"^#{1,6}\s+\S+", md, flags=re.MULTILINE))


def _estimate_word_count(md: str) -> int:
    tokens = re.split(r"\s+", md.strip())
    tokens = [token for token in tokens if token]
    return len(tokens) + int(len(md) / 20)


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


def _extract_section(md: str, heading: str, next_heading: str | None = None) -> str:
    if heading not in md:
        return ""
    start = md.index(heading) + len(heading)
    if next_heading and next_heading in md[start:]:
        end = md.index(next_heading, start)
        return md[start:end].strip()
    return md[start:].strip()


def _extract_tech_hints(insights: dict[str, Any]) -> list[str]:
    tech = insights.get("technical_stack_requirements")
    if isinstance(tech, list):
        return [str(item).strip() for item in tech if str(item).strip()]
    return []


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


def _action_plan_issues(report: str, insights: dict[str, Any], state: dict[str, Any]) -> list[ReviewIssueDetail]:
    policy = policy_from_state(state)
    quality_policy = policy.quality_policy
    issue_details: list[ReviewIssueDetail] = []
    section = _extract_section(report, "## 五、一周行动清单", "## 附：证据来源")
    action_plan_items = insights.get("action_plan_items") if isinstance(insights.get("action_plan_items"), list) else []
    coverage = int(insights.get("action_plan_source_coverage") or 0)
    company = str(insights.get("company") or "")

    day_hits = len(re.findall(r"Day\s*[1-7]", section, flags=re.IGNORECASE))
    generic_phrase_hits = sum(1 for phrase in GENERIC_ACTION_PLAN_PHRASES if phrase in section)
    if day_hits >= 6 and generic_phrase_hits >= 2:
        issue_details.append(
            build_issue(
                "templated_action_plan",
                "模板化行动清单：行动项仍然像固定 Day1-Day7 骨架，而不是依据证据动态生成。",
                policy=policy,
            )
        )

    if action_plan_items:
        company_specific_count = 0
        evidence_bound_count = 0
        for item in action_plan_items:
            if not isinstance(item, dict):
                continue
            why = str(item.get("why_this_company") or "")
            refs = item.get("evidence_refs") or []
            if company and company in why:
                company_specific_count += 1
            if isinstance(refs, list) and any(str(ref).strip() for ref in refs):
                evidence_bound_count += 1
        if company_specific_count < quality_policy.min_company_specific_action_items:
            issue_details.append(
                build_issue(
                    "action_plan_company_specificity_low",
                    "公司特异性不足：行动清单里缺少足够多直接绑定目标公司的任务。",
                    policy=policy,
                )
            )
        if evidence_bound_count < min(quality_policy.min_evidence_bound_action_items, len(action_plan_items)):
            issue_details.append(
                build_issue(
                    "action_plan_evidence_binding_low",
                    "证据归因不足：行动清单没有把关键动作绑定到真实证据来源。",
                    policy=policy,
                )
            )
    elif "Day" in section or "###" in section:
        issue_details.append(
            build_issue(
                "action_plan_missing_structured_input",
                "行动清单与风险点脱节：报告里出现了计划结构，但 InsightAgent 没有提供结构化 action_plan_items。",
                policy=policy,
            )
        )

    if coverage and coverage < quality_policy.min_action_plan_source_coverage:
        issue_details.append(
            build_issue(
                "action_plan_source_coverage_low",
                "证据归因不足：action_plan_source_coverage 偏低，行动项与证据绑定不够。",
                policy=policy,
            )
        )

    return issue_details


def _company_specificity_issues(report: str, insights: dict[str, Any], state: dict[str, Any]) -> list[ReviewIssueDetail]:
    policy = policy_from_state(state)
    retrieval_policy = policy.retrieval_policy
    quality_policy = policy.quality_policy
    issue_details: list[ReviewIssueDetail] = []
    company = str(insights.get("company") or "")
    company_specific_requirements = insights.get("company_specific_requirements") or []
    business_domain_hints = insights.get("business_domain_hints") or []
    company_specific_source_count = int(insights.get("company_specific_source_count") or 0)
    has_explicit_gap_note = any(token in report for token in ["证据不足", "暂不能判断", "证据缺口"])

    if company and report.count(company) < quality_policy.min_company_mentions:
        issue_details.append(
            build_issue(
                "company_mentions_too_few",
                "公司特异性不足：报告对目标公司的显式提及过少，看起来像可以替换到任何同类岗位。",
                policy=policy,
            )
        )

    if company_specific_source_count < retrieval_policy.min_company_specific_sources and not has_explicit_gap_note:
        issue_details.append(
            build_issue(
                "company_specific_sources_low",
                "公司特异性证据偏少：QueryAgent 需要重新压实公司画像和团队差异。",
                policy=policy,
            )
        )

    if company_specific_requirements and not any(str(item)[:18] in report for item in company_specific_requirements[:2]):
        issue_details.append(
            build_issue(
                "company_specific_requirement_missing",
                "公司特异性不足：公司/团队特有要求没有被有效写进报告正文。",
                policy=policy,
            )
        )

    if business_domain_hints and not any(str(item) in report for item in business_domain_hints[:2]):
        issue_details.append(
            build_issue(
                "business_domain_missing",
                "公司特异性不足：业务域线索没有被写实到报告中。",
                policy=policy,
            )
        )

    return issue_details


def run_rule_checker(state: dict[str, Any]) -> ReviewAgentResponse:
    policy = policy_from_state(state)
    report_policy = policy.report_policy
    quality_policy = policy.quality_policy

    report = str(state.get("report_content") or "")
    insights = dict(state.get("insights") or {})
    evidence_items = list(state.get("evidence_items") or [])
    context = list(state.get("context") or [])
    issue_details: list[ReviewIssueDetail] = []

    if not report.strip():
        issue = build_issue("empty_report", "报告为空：无法进入后续质量审查。", policy=policy)
        return ReviewAgentResponse(
            passed=False,
            quality_score=0,
            issues=[issue.message],
            issue_details=[issue],
            feedback_markdown="请重新生成完整报告，当前输出为空。",
            retry_target=issue.retry_target,
            root_cause=issue.root_cause,
        )

    for section in report_policy.required_sections:
        if section not in report:
            issue_details.append(
                build_issue(
                    "missing_markdown_section",
                    f"缺少标准 Markdown 章节：{section}",
                    policy=policy,
                )
            )

    if _count_markdown_headings(report) < quality_policy.min_markdown_headings:
        issue_details.append(
            build_issue(
                "markdown_heading_count_low",
                "Markdown 排版疑似不完整（章节数量不足）。",
                policy=policy,
            )
        )

    if _estimate_word_count(report) < quality_policy.min_report_word_estimate:
        issue_details.append(
            build_issue(
                "report_too_short",
                "字数/细节明显不足（达不到深度研究的期望）。",
                policy=policy,
            )
        )

    tech_hints = _extract_tech_hints(insights)
    evidence_map = dict(insights.get("evidence_map") or {})
    if tech_hints:
        tech_hits = sum(1 for token in tech_hints[:6] if token and token in report)
        if tech_hits < 2:
            issue_details.append(
                build_issue(
                    "tech_coverage_low",
                    "技术栈覆盖不足：未把真实 JD / 面经中的工具与技术栈写实到报告里。",
                    policy=policy,
                )
            )
        if not evidence_map.get("technical_stack_requirements"):
            issue_details.append(
                build_issue(
                    "tech_not_evidence_backed",
                    "技术栈未证据化：技术词存在，但没有明确对应的证据映射。",
                    policy=policy,
                )
            )
    else:
        issue_details.append(
            build_issue(
                "missing_tech_stack",
                "缺少结构化技术栈字段（technical_stack_requirements）。",
                policy=policy,
            )
        )

    url_hits = len(re.findall(r"https?://", report))
    evidence_bound = evidence_items if evidence_items else context
    if evidence_bound and url_hits < min(report_policy.min_source_urls_in_report, len(evidence_bound)):
        issue_details.append(
            build_issue(
                "insufficient_source_urls",
                "证据来源展示不足：报告没有充分引用 SearchAgent 抓取到的真实 URL。",
                policy=policy,
            )
        )

    if "context 缺失" in report and evidence_bound:
        issue_details.append(
            build_issue(
                "stale_context_placeholder",
                "报告仍残留 context 缺失占位，但当前其实已有真实检索证据。",
                policy=policy,
            )
        )

    question_section = _extract_section(report, "## 三、真实面经与面试官追问", "## 四、候选人风险点与准备建议")
    if question_section and "?" not in question_section and "？" not in question_section:
        issue_details.append(
            build_issue(
                "generic_interviewer_questions",
                "追问泛化：真实面经与追问部分不够具体，缺少真正像面试官会问的问题。",
                policy=policy,
            )
        )

    if "## 附：证据来源" in report and "|" not in report and evidence_bound:
        issue_details.append(
            build_issue(
                "weak_evidence_section_layout",
                "证据来源章节排版偏弱，建议至少用 Markdown 表格或清晰列表展示来源。",
                policy=policy,
            )
        )

    risk_section = _extract_section(report, "## 四、候选人风险点与准备建议", "## 五、一周行动清单")
    if risk_section and "如果" not in risk_section and "风险" not in risk_section:
        issue_details.append(
            build_issue(
                "generic_risk_section",
                "风险点泛化：风险提示更像通用建议，缺少明确的失分场景和判断逻辑。",
                policy=policy,
            )
        )

    issue_details.extend(_company_specificity_issues(report, insights, state))
    issue_details.extend(_action_plan_issues(report, insights, state))
    issue_details = _dedupe_issue_details(issue_details)

    issues = [issue.message for issue in issue_details]
    passed = not issues
    feedback = (
        "审查通过：报告已经具备真实证据、公司差异和动态行动项，可直接交付。"
        if passed
        else "请按以下要点修复：\n- " + "\n- ".join(_dedupe(issues)[:8])
    )

    retry_target = _pick_retry_target(issue_details)
    root_cause = _pick_root_cause(issue_details)
    return ReviewAgentResponse(
        passed=passed,
        quality_score=max(0, 100 - len(issue_details) * 10),
        issues=issues,
        issue_details=issue_details,
        feedback_markdown=feedback,
        retry_target=retry_target,  # type: ignore[arg-type]
        root_cause=root_cause,  # type: ignore[arg-type]
    )


__all__ = ["run_rule_checker"]
