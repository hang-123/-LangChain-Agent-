from __future__ import annotations

import json
import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from api.agents.insight_agent import insight_agent_node
from api.agents.intent_router import intent_router_node
from api.agents.quality_gate import quality_gate_node
from api.agents.query_agent import query_agent_node
from api.agents.report_agent import report_agent_node
from api.agents.review_agent import review_agent_node
from api.agents.search_agent import search_agent_node
from api.core.prompts import ReviewAgentResponse


GRAPH_NODE_ORDER = [
    "IntentRouterNode",
    "SearchAgent",
    "QueryAgent",
    "InsightAgent",
    "QualityGate",
    "ReportAgent",
    "ReviewAgent",
]


class AgentState(TypedDict):
    run_id: str
    query: str
    policy: Dict[str, Any]
    run_manifest: Dict[str, Any]
    intent: str
    candidate_profile: Dict[str, Any]
    resume_evidence: List[Dict[str, Any]]
    job_posting: Dict[str, Any]
    query_profile: Dict[str, Any]
    context: Annotated[List[str], operator.add]
    evidence_items: List[Dict[str, Any]]
    external_evidence_pack: Dict[str, Any]
    job_snapshot: Dict[str, Any]
    match_assessment: Dict[str, Any]
    retrieval_diagnostics: Dict[str, Any]
    query_pack: List[Dict[str, Any]]
    insights: Dict[str, Any]
    report_content: str
    tailor_plan: Dict[str, Any]
    resume_version: Dict[str, Any]
    fact_check_report: Dict[str, Any]
    review_feedback: str
    retry_count: int
    quality_mode: str
    warning_message: str
    root_cause: str
    root_cause_history: List[Dict[str, Any]]
    run_trace: List[Dict[str, Any]]
    quality_summary: Dict[str, Any]
    perf_bill: Dict[str, Any]
    perf_bill_path: str
    security_events: List[Dict[str, Any]]
    research_case: Dict[str, Any]
    status: str


def build_initial_state(
    query: str,
    *,
    run_id: str = "",
    candidate_profile: Dict[str, Any] | None = None,
    resume_evidence: List[Dict[str, Any]] | None = None,
    job_posting: Dict[str, Any] | None = None,
    match_assessment: Dict[str, Any] | None = None,
    policy: Dict[str, Any] | None = None,
    run_manifest: Dict[str, Any] | None = None,
    research_case: Dict[str, Any] | None = None,
) -> AgentState:
    return {
        "run_id": run_id,
        "query": query,
        "policy": dict(policy or {}),
        "run_manifest": dict(run_manifest or {}),
        "intent": "",
        "candidate_profile": dict(candidate_profile or {}),
        "resume_evidence": list(resume_evidence or []),
        "job_posting": dict(job_posting or {}),
        "query_profile": {},
        "context": [],
        "evidence_items": [],
        "external_evidence_pack": {},
        "job_snapshot": {},
        "match_assessment": {},
        "retrieval_diagnostics": {},
        "query_pack": [],
        "insights": {},
        "report_content": "",
        "tailor_plan": {},
        "resume_version": {},
        "fact_check_report": {},
        "match_assessment": dict(match_assessment or {}),
        "review_feedback": "",
        "retry_count": 0,
        "quality_mode": "normal",
        "warning_message": "",
        "root_cause": "",
        "root_cause_history": [],
        "run_trace": [],
        "quality_summary": {},
        "perf_bill": {},
        "perf_bill_path": "",
        "security_events": [],
        "research_case": dict(research_case or {}),
        "status": "等待执行",
    }


def _parse_review_feedback(state: AgentState) -> ReviewAgentResponse | None:
    review_raw = str(state.get("review_feedback") or "")
    if not review_raw.strip():
        return None
    try:
        return ReviewAgentResponse.model_validate_json(review_raw)
    except Exception:
        try:
            return ReviewAgentResponse.model_validate(json.loads(review_raw))
        except Exception:
            return None


def route_after_review(state: AgentState) -> str:
    if "熔断" in str(state.get("status") or ""):
        return END  # type: ignore[return-value]

    parsed = _parse_review_feedback(state)
    if parsed is None:
        return "ReportAgent"
    if parsed.passed:
        return END  # type: ignore[return-value]
    if parsed.retry_target == "query":
        return "QueryAgent"
    if parsed.retry_target == "insight":
        return "InsightAgent"
    return "ReportAgent"


def build_career_research_graph() -> Any:
    builder: StateGraph = StateGraph(AgentState)  # type: ignore[assignment]

    builder.add_node("IntentRouterNode", intent_router_node)
    builder.add_node("SearchAgent", search_agent_node)
    builder.add_node("QueryAgent", query_agent_node)
    builder.add_node("InsightAgent", insight_agent_node)
    builder.add_node("QualityGate", quality_gate_node)
    builder.add_node("ReportAgent", report_agent_node)
    builder.add_node("ReviewAgent", review_agent_node)

    builder.set_entry_point("IntentRouterNode")
    builder.add_edge("IntentRouterNode", "SearchAgent")
    builder.add_edge("SearchAgent", "QueryAgent")
    builder.add_edge("QueryAgent", "InsightAgent")
    builder.add_edge("InsightAgent", "QualityGate")
    builder.add_edge("QualityGate", "ReportAgent")
    builder.add_edge("ReportAgent", "ReviewAgent")
    builder.add_conditional_edges(
        "ReviewAgent",
        route_after_review,
        {
            "QueryAgent": "QueryAgent",
            "InsightAgent": "InsightAgent",
            "ReportAgent": "ReportAgent",
            END: END,
        },
    )

    return builder.compile()


def merge_state_update(state: AgentState, update: Dict[str, Any]) -> None:
    for key, value in update.items():
        if key in {"policy", "run_manifest"} and isinstance(value, dict):
            merged = dict(state.get(key) or {})
            merged.update(value)
            state[key] = merged  # type: ignore[index]
            continue
        if key == "context" and isinstance(value, list):
            state["context"] = list(state.get("context") or []) + value
            continue
        if key == "evidence_items" and isinstance(value, list):
            state["evidence_items"] = list(value)
            continue
        if key == "resume_evidence" and isinstance(value, list):
            state["resume_evidence"] = list(value)
            continue
        if key == "query_pack" and isinstance(value, list):
            state["query_pack"] = list(value)
            continue
        if key == "security_events" and isinstance(value, list):
            state["security_events"] = list(state.get("security_events") or []) + value
            continue
        state[key] = value  # type: ignore[index]


def build_agent_message_event(agent: str, state: AgentState) -> dict[str, Any] | None:
    insights = dict(state.get("insights") or {})
    now = datetime.now(timezone.utc).isoformat()

    if agent == "IntentRouterNode":
        return {
            "type": "message",
            "speaker": "IntentRouterNode",
            "content": "IntentRouterNode 已完成意图识别与确定性分流。",
            "metadata": {
                "intent": state.get("intent"),
                "intent_reason": insights.get("intent_reason"),
                "company": state.get("query_profile", {}).get("company"),
                "role": state.get("query_profile", {}).get("role"),
                "team_hint": state.get("query_profile", {}).get("team_hint"),
                "domain_hint": state.get("query_profile", {}).get("domain_hint"),
            },
            "timestamp": now,
        }

    if agent == "SearchAgent":
        return {
            "type": "message",
            "speaker": "SearchAgent",
            "content": "SearchAgent 已完成并发检索，context 已可供下游节点无损读取。",
            "metadata": {
                "intent": state.get("intent"),
                "company": insights.get("company"),
                "role": insights.get("role"),
                "used_tools": insights.get("used_tools"),
                "search_queries": insights.get("search_queries"),
                "query_pack": state.get("query_pack"),
                "source_urls": insights.get("source_urls"),
                "evidence_count": insights.get("evidence_count"),
                "company_specific_source_count": insights.get("company_specific_source_count"),
                "generic_source_count": insights.get("generic_source_count"),
                "context_quality_score": insights.get("context_quality_score"),
                "retrieval_diagnostics": state.get("retrieval_diagnostics"),
                "business_domain_hints": insights.get("business_domain_hints"),
                "search_failures": insights.get("search_failures"),
            },
            "timestamp": now,
        }

    if agent == "QueryAgent":
        return {
            "type": "message",
            "speaker": "QueryAgent",
            "content": "QueryAgent 已输出岗位要求、技术栈、薪资线索和面试官期待。",
            "metadata": {
                "intent": state.get("intent"),
                "company": insights.get("company"),
                "role": insights.get("role"),
                "company_signals": insights.get("company_signals"),
                "role_signals": insights.get("role_signals"),
                "company_specific_requirements": insights.get("company_specific_requirements"),
                "common_requirements": insights.get("common_requirements"),
                "coverage_gaps": insights.get("coverage_gaps"),
                "context_quality_score": insights.get("context_quality_score"),
                "claims_count": len(insights.get("claims") or []),
                "claim_evidence_coverage": (insights.get("quality_metrics") or {}).get("claim_evidence_coverage"),
                "core_evaluation_points": insights.get("core_evaluation_points"),
                "technical_stack_requirements": insights.get("technical_stack_requirements"),
                "salary_signals": insights.get("salary_signals"),
                "interview_expectations": insights.get("interview_expectations"),
                "job_snapshot_id": (state.get("job_snapshot") or {}).get("job_snapshot_id"),
                "external_evidence_pack_id": (state.get("external_evidence_pack") or {}).get("evidence_pack_id"),
                "match_assessment_id": (state.get("match_assessment") or {}).get("assessment_id"),
                "match_recommendation": (state.get("match_assessment") or {}).get("recommendation"),
                "tailor_plan_id": (state.get("tailor_plan") or {}).get("tailor_plan_id"),
                "resume_version_id": (state.get("resume_version") or {}).get("resume_version_id"),
                "fact_check_status": (state.get("fact_check_report") or {}).get("status"),
                "fallback_query": bool((insights.get("fallback_flags") or {}).get("query")),
            },
            "timestamp": now,
        }

    if agent == "InsightAgent":
        return {
            "type": "message",
            "speaker": "InsightAgent",
            "content": "InsightAgent 已输出风险点、面试官追问和准备策略。",
            "metadata": {
                "candidate_risks": insights.get("candidate_risks"),
                "interviewer_questions": insights.get("interviewer_questions"),
                "prep_strategy": insights.get("prep_strategy"),
                "interview_angle": insights.get("interview_angle"),
                "evidence_gap_summary": insights.get("evidence_gap_summary"),
                "action_plan_source_coverage": insights.get("action_plan_source_coverage"),
                "action_plan_items_count": len(insights.get("action_plan_items") or []),
                "fallback_insight": bool((insights.get("fallback_flags") or {}).get("insight")),
            },
            "timestamp": now,
        }

    if agent == "QualityGate":
        return {
            "type": "message",
            "speaker": "QualityGate",
            "content": "QualityGate 已完成成稿前质量闸门判定。",
            "metadata": {
                "quality_mode": state.get("quality_mode"),
                "warning_message": state.get("warning_message"),
                "root_cause": state.get("root_cause"),
                "evidence_count": insights.get("evidence_count"),
                "company_specific_source_count": insights.get("company_specific_source_count"),
                "claim_evidence_coverage": (insights.get("quality_metrics") or {}).get("claim_evidence_coverage"),
                "action_plan_source_coverage": insights.get("action_plan_source_coverage"),
            },
            "timestamp": now,
        }

    if agent == "ReportAgent":
        return {
            "type": "message",
            "speaker": "ReportAgent",
            "content": "ReportAgent 已完成本轮流式成稿。",
            "metadata": {
                "retry_count": state.get("retry_count", 0),
                "status": state.get("status"),
                "quality_mode": state.get("quality_mode"),
                "warning_message": state.get("warning_message"),
                "root_cause": state.get("root_cause"),
                "fallback_report": bool((insights.get("fallback_flags") or {}).get("report")),
            },
            "timestamp": now,
        }

    if agent == "ReviewAgent":
        parsed = _parse_review_feedback(state)
        return {
            "type": "message",
            "speaker": "ReviewAgent",
            "content": "ReviewAgent 已完成本轮审查。",
            "metadata": parsed.model_dump() if parsed is not None else {"raw": state.get("review_feedback")},
            "timestamp": now,
        }

    return None


def parse_review_feedback_json(state: AgentState) -> dict[str, Any] | None:
    parsed = _parse_review_feedback(state)
    return parsed.model_dump() if parsed is not None else None


__all__ = [
    "AgentState",
    "GRAPH_NODE_ORDER",
    "build_agent_message_event",
    "build_career_research_graph",
    "build_initial_state",
    "merge_state_update",
    "parse_review_feedback_json",
    "route_after_review",
]
