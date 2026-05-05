from __future__ import annotations

from typing import Any

from api.core.context_utils import clip_text, coerce_evidence_items, parse_context_items, unique_strings
from api.core.contracts import ActionPlanItem
from api.core.policies import HarnessPolicy


def _render_bullets(items: list[str], empty_text: str) -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in cleaned)


def _coerce_action_plan_items(raw_items: Any) -> list[ActionPlanItem]:
    items: list[ActionPlanItem] = []
    if not isinstance(raw_items, list):
        return items
    for raw_item in raw_items:
        try:
            items.append(ActionPlanItem.model_validate(raw_item))
        except Exception:
            continue
    items.sort(key=lambda item: item.day)
    return items


def _render_action_plan(items: list[ActionPlanItem]) -> str:
    if not items:
        return "- 当前证据仍不足以产出可信行动清单，请先补齐公司画像、最新 JD 和真实面经。"

    blocks: list[str] = []
    for item in items:
        refs = "；".join(unique_strings(item.evidence_refs)[:3]) or "当前行动项主要用于补证据"
        blocks.extend(
            [
                f"### Day {item.day} · {item.goal}",
                f"- 优先级：{item.priority}",
                f"- 任务：{item.task}",
                f"- 为什么是这家公司：{item.why_this_company}",
                f"- 预期产出：{item.expected_outcome}",
                f"- 证据绑定：{refs}",
                "",
            ]
        )
    return "\n".join(blocks).strip()


def _render_evidence_section(context: list[str], evidence_items: list[dict[str, Any]], policy: HarnessPolicy) -> str:
    max_rows = policy.report_policy.max_evidence_rows
    if evidence_items:
        rows = [
            "| 证据类别 | 来源 URL | 标题 | 相关性说明 | 关键摘要 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item in evidence_items[:max_rows]:
            source_cls = str(item.get("source_class") or "unknown").replace("|", "\\|")
            url = str(item.get("url") or "未知来源").replace("|", "\\|")
            title = str(item.get("title") or "无标题").replace("|", "\\|")
            hint = clip_text(str(item.get("relevance_hint") or "未提供"), 60).replace("|", "\\|")
            snippet = clip_text(str(item.get("snippet") or "无摘要"), 120).replace("|", "\\|")
            rows.append(f"| {source_cls} | {url} | {title} | {hint} | {snippet} |")
        return "\n".join(rows)

    parsed_items = parse_context_items(context)
    if not parsed_items:
        return "- context 缺失：本轮未抓到 Tavily 证据，请检查 TAVILY_API_KEY 或重试检索。"

    rows = [
        "| 证据类别 | 来源 URL | 标题 | 相关性说明 | 关键摘要 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for parsed in parsed_items[:max_rows]:
        source_cls = parsed.get("SOURCE_CLASS", parsed.get("TYPE", "unknown")).replace("|", "\\|")
        url = parsed.get("URL", "未知来源").replace("|", "\\|")
        title = parsed.get("TITLE", "无标题").replace("|", "\\|")
        hint = clip_text(parsed.get("RELEVANCE_HINT", "未提供"), 60).replace("|", "\\|")
        snippet = clip_text(parsed.get("SNIPPET", "无摘要"), 120).replace("|", "\\|")
        rows.append(f"| {source_cls} | {url} | {title} | {hint} | {snippet} |")
    return "\n".join(rows)


def build_quality_banner(quality_mode: str, warning_message: str, root_cause: str) -> list[str]:
    if quality_mode == "fallback":
        return [
            "> ⚠️ 当前为 fallback 模式：局部润色不可用，系统已直接输出 renderer 版本。",
            f"> 根因判断：{root_cause or 'llm_runtime'}",
            f"> 说明：{warning_message or '请优先检查 LLM 运行环境、依赖和模型可用性。'}",
        ]
    if quality_mode == "conservative":
        return [
            "> ⚠️ 当前为证据不足保守版：系统拒绝把本轮结果包装成高置信度定制报告。",
            f"> 根因判断：{root_cause or 'retrieval'}",
            f"> 说明：{warning_message or '请优先补公司画像、JD、面经或 claim 归因。'}",
        ]
    return []


def build_overview_lines(query: str, insights: dict[str, Any]) -> list[str]:
    company = str(insights.get("company") or "目标公司")
    role = str(insights.get("role") or "目标岗位")
    domain_hints = [str(item) for item in insights.get("business_domain_hints") or []]
    company_signals = [str(item) for item in insights.get("company_signals") or []]
    role_signals = [str(item) for item in insights.get("role_signals") or []]
    salary_signals = [str(item) for item in insights.get("salary_signals") or []]
    quality_metrics = dict(insights.get("quality_metrics") or {})

    lines = [
        f"本轮研究目标是 {query}，当前聚焦公司为 {company}，岗位方向为 {role}。",
        (
            f"现有证据质量分约为 {int(insights.get('context_quality_score') or 0)}，"
            f"公司特异性证据条数为 {int(insights.get('company_specific_source_count') or 0)}，"
            f"claim 证据覆盖率约为 {int(quality_metrics.get('claim_evidence_coverage') or 0)}。"
        ),
    ]
    if domain_hints:
        lines.append(f"从公司画像和岗位证据看，这个岗位更贴近 {', '.join(domain_hints[:3])} 等业务语境，而不是泛化岗位标签。")
    if company_signals:
        lines.append(f"公司侧关键信号：{company_signals[0]}")
    if role_signals:
        lines.append(f"岗位侧关键信号：{role_signals[0]}")
    if salary_signals:
        lines.append(f"目前可见的薪资/待遇线索包括：{'；'.join(salary_signals[:3])}。")
    return unique_strings(lines)[:6]


def render_report_markdown(
    *,
    query: str,
    insights: dict[str, Any],
    context: list[str],
    retry_count: int,
    review_feedback: str,
    quality_mode: str,
    warning_message: str,
    root_cause: str,
    policy: HarnessPolicy,
    overview_lead: str = "",
    interview_angle: str = "",
) -> str:
    company = str(insights.get("company") or "目标公司")
    role = str(insights.get("role") or "目标岗位")
    action_plan_items = _coerce_action_plan_items(insights.get("action_plan_items") or [])
    evidence_items = coerce_evidence_items(insights.get("evidence_items"), context)
    evidence_gap_summary = [str(item) for item in insights.get("evidence_gap_summary") or []]
    quality_banner = build_quality_banner(quality_mode, warning_message, root_cause)
    resolved_interview_angle = interview_angle or str(
        insights.get("interview_angle") or "当前证据仍不足以给出高置信度定性。"
    )

    title = policy.report_policy.title
    lines = [
        f"# {title}",
        "",
        f"> 研究目标：{query}",
        f"> 目标公司：{company}",
        f"> 目标岗位：{role}",
    ]
    if quality_banner:
        lines.extend(quality_banner)
    if retry_count > 0 and review_feedback.strip():
        lines.append(f"> 本轮已根据 ReviewAgent 第 {retry_count} 次审查意见进行重写。")

    section_blocks = {
        "## 一、岗位与公司概览": "\n".join(
            [
                overview_lead.strip() if overview_lead.strip() else "",
                _render_bullets(
                    build_overview_lines(query, insights),
                    "当前概览证据不足，请先补齐公司画像和最新岗位信息。",
                ),
            ]
        ).strip(),
        "## 二、岗位能力要求拆解": "\n".join(
            [
                "### 公司特异性要求",
                _render_bullets(
                    [str(item) for item in insights.get("company_specific_requirements") or []],
                    "当前还不能稳健判断公司差异，说明公司画像/JD/面经证据仍需补强。",
                ),
                "",
                "### 通用要求",
                _render_bullets(
                    [str(item) for item in insights.get("common_requirements") or []],
                    "当前只能保守判断会考工程基础和项目真实性。",
                ),
                "",
                "### 真实技术栈 / JD 要求",
                _render_bullets(
                    [str(item) for item in insights.get("technical_stack_requirements") or []],
                    "技术栈证据偏弱，建议补更明确的 JD / 面经。",
                ),
                "",
                "### 面试官期待画像",
                _render_bullets(
                    [str(item) for item in insights.get("interview_expectations") or []],
                    "面试官期待画像仍不够稳定，建议继续补充定向面经。",
                ),
            ]
        ),
        "## 三、真实面经与面试官追问": _render_bullets(
            [str(item) for item in insights.get("interviewer_questions") or []],
            "当前缺少足够强的真实面经追问样本。",
        ),
        "## 四、候选人风险点与准备建议": "\n".join(
            [
                "### 风险点提示",
                _render_bullets(
                    [str(item) for item in insights.get("candidate_risks") or []],
                    "当前无法高置信度判断风险点，请先补更多公司特异性证据。",
                ),
                "",
                "### 准备建议",
                _render_bullets(
                    [str(item) for item in insights.get("prep_strategy") or []],
                    "当前更建议先补证据，再收紧准备动作。",
                ),
                "",
                "### 证据缺口",
                _render_bullets(evidence_gap_summary, "暂无额外缺口说明。"),
                "",
                f"> 面试官视角定性：{resolved_interview_angle}",
            ]
        ),
        "## 五、一周行动清单": _render_action_plan(action_plan_items),
        "## 附：证据来源": _render_evidence_section(context, evidence_items, policy),
    }

    for heading in policy.report_policy.section_order:
        block = section_blocks.get(heading)
        if block is None:
            continue
        lines.extend(["", heading, block])

    return "\n".join(lines).strip() + "\n"
