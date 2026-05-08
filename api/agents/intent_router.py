# DEPRECATED (Phase 2): absorbed into api/agents/supervisor.py.
# Retained for backward compatibility only. Do not add new features here.
from __future__ import annotations

from typing import Any

from api.core.job_query import build_query_profile
from api.core.llm import invoke_structured_output
from api.core.prompts import IntentRouterResponse, QueryProfile, SYSTEM_PROMPT_INTENT_ROUTER


def _heuristic_intent(query: str) -> IntentRouterResponse:
    text = query.lower()
    intent = "general"
    if any(token in text for token in ["技术栈", "算法", "编码", "code", "system design", "系统设计"]):
        intent = "tech_coding"
        reason = "用户更关注技术栈、算法、系统设计或编码考察。"
    elif any(token in text for token in ["薪资", "待遇", "文化", "wlb", "work life", "团队氛围", "口碑"]):
        intent = "salary_culture"
        reason = "用户更关注薪资、文化、工作节奏或组织口碑。"
    else:
        reason = "用户整体目标是通用岗位调研与求职准备。"

    return IntentRouterResponse(
        intent=intent,
        reason=reason,
        query_profile=QueryProfile.model_validate(build_query_profile(query, intent=intent)),
    )


async def intent_router_node(state: dict[str, Any]) -> dict[str, Any]:
    query = str(state.get("query") or "").strip()
    if not query:
        raise ValueError("query is empty")

    try:
        parsed = await invoke_structured_output(
            IntentRouterResponse,
            system_prompt=SYSTEM_PROMPT_INTENT_ROUTER,
            human_prompt="用户输入：\n{query}\n\n请判断意图并输出 JSON。",
            variables={"query": query},
            temperature=0.0,
        )
    except Exception:
        parsed = _heuristic_intent(query)

    insights = dict(state.get("insights") or {})
    query_profile = parsed.query_profile.model_dump()
    insights.update(
        {
            "intent_reason": parsed.reason,
            "company": query_profile.get("company"),
            "role": query_profile.get("role"),
            "business_domain_hints": [query_profile.get("domain_hint")] if query_profile.get("domain_hint") else [],
            "fallback_flags": {
                "query": False,
                "insight": False,
                "report": False,
            },
        }
    )
    return {
        "intent": parsed.intent,
        "query_profile": query_profile,
        "insights": insights,
        "status": (
            f"🧭 已识别当前任务意图为 {parsed.intent}，"
            f"岗位画像已定位到 {query_profile.get('company')} / {query_profile.get('role')}。"
        ),
    }
