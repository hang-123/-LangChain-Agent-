from __future__ import annotations

from pydantic import BaseModel, Field

from api.core.guardrails import sanitize_output_text
from api.core.llm import get_chat_model
from api.core.policy_loader import policy_from_state
from api.core.prompts import ReviewAgentResponse
from api.reporting.renderer import build_overview_lines, render_report_markdown


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

    fallback_flags = dict(insights.get("fallback_flags") or {})
    fallback_flags["report"] = False
    new_insights = insights.copy()
    new_insights["fallback_flags"] = fallback_flags
    new_insights["render_strategy"] = "renderer_first"

    polish_status = "已结合局部润色" if used_polish else "未使用 LLM 局部润色"
    return {
        "report_content": rendered_report,
        "insights": new_insights,
        "quality_mode": quality_mode,
        "warning_message": warning_message,
        "root_cause": root_cause,
        "security_events": [event.model_dump(mode="json") for event in security_events],
        "status": (
            "📝 已完成 renderer-first 专属求职研究报告撰写。"
            if quality_mode == "normal"
            else f"📝 已完成 {quality_mode} 模式的 renderer-first 专属求职研究报告撰写。"
        )
        + f"（{polish_status}）",
    }
