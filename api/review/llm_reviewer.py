from __future__ import annotations

import json

from api.core.contracts import ReviewAgentResponse
from api.core.llm import invoke_structured_output
from api.core.policy_loader import policy_from_state
from api.core.prompts import SYSTEM_PROMPT_REVIEW


async def run_llm_reviewer(state: dict[str, object]) -> ReviewAgentResponse | None:
    policy = policy_from_state(state)
    if not policy.quality_policy.enable_soft_llm_reviewer:
        return None

    report = str(state.get("report_content") or "")
    insights = dict(state.get("insights") or {})
    evidence_items = list(state.get("evidence_items") or [])
    context = list(state.get("context") or [])

    return await invoke_structured_output(
        ReviewAgentResponse,
        system_prompt=SYSTEM_PROMPT_REVIEW,
        human_prompt=(
            "用户原始问题：\n{query}\n\n"
            "当前 quality_mode={quality_mode}, warning_message={warning_message}, root_cause={root_cause}\n\n"
            "结构化 evidence_items（优先事实源）：\n{evidence_items}\n\n"
            "SearchAgent 原始展示层 context：\n{context}\n\n"
            "QueryAgent + InsightAgent 的结构化结果：\n{insights}\n\n"
            "待审查 Markdown 报告：\n{report}\n\n"
            "你只负责软质量问题：表达是否清晰、追问是否自然、风险提示是否像真实面试官口吻。"
            "不要重复报告规则检查已经能稳定发现的硬约束问题。"
        ),
        variables={
            "query": str(state.get("query") or ""),
            "quality_mode": str(state.get("quality_mode") or "normal"),
            "warning_message": str(state.get("warning_message") or ""),
            "root_cause": str(state.get("root_cause") or "synthesis"),
            "evidence_items": json.dumps(evidence_items[:8], ensure_ascii=False, indent=2),
            "context": "\n\n".join(context)[:8000],
            "insights": json.dumps(insights, ensure_ascii=False, indent=2),
            "report": report[:16000],
        },
        temperature=0.0,
    )
