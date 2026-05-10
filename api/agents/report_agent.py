from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from api.core.guardrails import sanitize_output_text
from api.core.llm import get_chat_model
from api.core.policy_loader import policy_from_state
from api.core.prompts import ReviewAgentResponse
from api.reporting.renderer import build_overview_lines, render_report_markdown
from api.review.rule_checker import run_rule_checker


class ReportPolishResponse(BaseModel):
    overview_lead: str = Field(default="")
    interview_angle: str = Field(default="")


async def _polish_fragments(
    *,
    query: str,
    insights: dict[str, object],
    overview_seed: str,
    interview_angle_seed: str,
) -> ReportPolishResponse | None:
    llm = get_chat_model(temperature=0.1, streaming=False)
    payload = (
        "你是报告语言润色器，只能做局部表达优化，不能新增事实、不能改章节结构、不能改 URL、"
        "不能把保守判断改成高置信度结论。\n\n"
        f"研究问题：{query}\n\n"
        f"结构化上下文：{insights}\n\n"
        f"overview_seed：{overview_seed}\n\n"
        f"interview_angle_seed：{interview_angle_seed}\n\n"
        "请返回 JSON，字段只有 overview_lead 和 interview_angle。"
        "overview_lead 最多 2 句，适合作为“岗位与公司概览”开头。"
        "interview_angle 只允许润色原有判断，不得改变事实和强弱程度。"
    )
    response = await llm.with_structured_output(ReportPolishResponse).ainvoke(payload)
    if isinstance(response, ReportPolishResponse):
        return response
    return ReportPolishResponse.model_validate(response)


class MildReviewResponse(BaseModel):
    has_hollow_sections: bool = Field(default=False)
    hollow_sections: list[str] = Field(default_factory=list)
    has_contradictions: bool = Field(default=False)
    contradiction_notes: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)
    severity: Literal["ok", "minor", "major"] = "ok"


async def _mild_llm_review(
    *,
    report_content: str,
    required_sections: list[str],
) -> MildReviewResponse | None:
    """LLM mild check for content hollowness and contradiction detection.

    Only triggered after deterministic rule checker finds warnings.
    Per spec 25 section 6 step 2.
    """
    from api.core.llm import invoke_structured_output
    from api.core.settings import get_settings

    settings = get_settings()
    if not settings.enable_report_llm_self_review:
        return None

    try:
        result = await invoke_structured_output(
            MildReviewResponse,
            system_prompt=(
                "你是报告质量审查员。只检查以下两个问题：\n"
                "1. Section 内容空洞：section 标题下有实质内容还是只有占位符/一两句空话？\n"
                "2. 矛盾陈述：报告中是否存在前后矛盾的事实判断？\n\n"
                "规则：\n"
                "- 只报告确实存在的问题，不要鸡蛋里挑骨头\n"
                "- severity: ok=无问题, minor=有小问题可内部修复, major=有严重问题需打回\n"
                "- hollow_sections 列出内容明显空洞的 section 名称\n"
                "- contradiction_notes 列出矛盾的具体描述\n"
                "- revision_suggestions 给出具体可执行的修改建议"
            ),
            human_prompt=(
                f"预期必需 section：{chr(10).join(required_sections)}\n\n"
                f"报告内容：\n{report_content[:6000]}\n\n"
                "请审查报告质量。"
            ),
            variables={},
            temperature=0.2,
        )
        return result
    except Exception:
        return None


async def report_agent_node(state: dict[str, object], config=None) -> dict[str, object]:
    del config
    run_id = str(state.get("run_id") or "")
    query = str(state.get("query") or "").strip()
    context = list(state.get("context") or [])
    insights = dict(state.get("insights") or {})
    retry_count = int(state.get("retry_count") or 0)
    review_feedback_raw = str(state.get("review_feedback") or "")
    quality_mode = str(state.get("quality_mode") or "normal")
    warning_message = str(state.get("warning_message") or "")
    root_cause = str(state.get("root_cause") or insights.get("root_cause_hint") or "synthesis")
    policy = policy_from_state(state)

    try:
        review_feedback_parsed = ReviewAgentResponse.model_validate_json(review_feedback_raw) if review_feedback_raw else None
    except Exception:
        review_feedback_parsed = None

    review_feedback = (
        review_feedback_parsed.feedback_markdown if review_feedback_parsed is not None else (review_feedback_raw or "无")
    )
    overview_seed = " ".join(build_overview_lines(query, insights))
    interview_angle_seed = str(insights.get("interview_angle") or "当前证据仍不足以给出高置信度定性。")

    overview_lead = overview_seed
    interview_angle = interview_angle_seed
    used_polish = False
    if policy.report_policy.enable_llm_polish:
        try:
            polish = await _polish_fragments(
                query=query,
                insights=insights,
                overview_seed=overview_seed,
                interview_angle_seed=interview_angle_seed,
            )
        except Exception:
            polish = None
        if polish is not None:
            overview_lead = polish.overview_lead.strip() or overview_seed
            interview_angle = polish.interview_angle.strip() or interview_angle_seed
            used_polish = True

    rendered_report = render_report_markdown(
        query=query,
        insights=insights,
        context=context,
        retry_count=retry_count,
        review_feedback=review_feedback,
        quality_mode=quality_mode,
        warning_message=warning_message,
        root_cause=root_cause,
        policy=policy,
        overview_lead=overview_lead,
        interview_angle=interview_angle,
    )
    rendered_report, security_events = sanitize_output_text(run_id, rendered_report)

    review_state = dict(state)
    review_state["report_content"] = rendered_report
    review_state["quality_mode"] = quality_mode
    review_state["warning_message"] = warning_message
    review_state["root_cause"] = root_cause
    review_result = run_rule_checker(review_state)
    review_feedback_json = json.dumps(review_result.model_dump(mode="json"), ensure_ascii=False)

    fallback_flags = dict(insights.get("fallback_flags") or {})
    fallback_flags["report"] = False
    new_insights = insights.copy()
    new_insights["fallback_flags"] = fallback_flags
    new_insights["render_strategy"] = "renderer_first"

    polish_status = "已结合局部润色" if used_polish else "未使用 LLM 局部润色"
    review_status = (
        f"内置自审通过（score={review_result.quality_score}）"
        if review_result.passed
        else f"内置自审发现问题，建议回退到 {review_result.retry_target}（score={review_result.quality_score}）"
    )

    # ── LLM Mild Self-Review (spec 25 section 6 step 2) ──
    mild_review: MildReviewResponse | None = None
    if not review_result.passed or review_result.quality_score < 90:
        report_policy_sections = list(policy.report_policy.required_sections or [])
        mild_review = await _mild_llm_review(
            report_content=rendered_report,
            required_sections=report_policy_sections,
        )

    if mild_review is not None and mild_review.severity == "major":
        fallback_flags["mild_review_major"] = True
        new_insights["mild_review"] = mild_review.model_dump()
        review_status = "内置自审+LLM轻审发现问题（严重），建议回退修复"
    elif mild_review is not None and mild_review.severity == "minor":
        new_insights["mild_review"] = mild_review.model_dump()
        review_status += f"；LLM轻审发现{mild_review.severity}问题"

    return {
        "report_content": rendered_report,
        "insights": new_insights,
        "review_feedback": review_feedback_json,
        "quality_mode": quality_mode,
        "warning_message": warning_message,
        "root_cause": review_result.root_cause or root_cause,
        "security_events": [event.model_dump(mode="json") for event in security_events],
        "status": (
            "📝 已完成 renderer-first 专属求职研究报告撰写。"
            if quality_mode == "normal"
            else f"📝 已完成 {quality_mode} 模式的 renderer-first 专属求职研究报告撰写。"
        )
        + f"（{polish_status}；{review_status}）",
    }
