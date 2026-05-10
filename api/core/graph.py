from __future__ import annotations

import json
import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from api.agents.insight_agent import insight_agent_node
from api.agents.intent_router import intent_router_node
from api.agents.job_intelligence_agent import job_intelligence_agent_node
from api.agents.matching_agent import matching_agent_node
from api.agents.quality_gate import quality_gate_node
from api.agents.query_agent import query_agent_node
from api.agents.report_agent import report_agent_node
from api.agents.resume_tailor_agent import resume_tailor_agent_node
from api.agents.review_agent import review_agent_node
from api.agents.archetype_detector import archetype_detector_node
from api.agents.legitimacy_scorer import legitimacy_scorer_node
from api.agents.memory_retrieval import memory_retrieval_node
from api.agents.offer_evaluator import offer_evaluator_node
from api.agents.search_agent import search_agent_node
from api.core.prompts import ReviewAgentResponse
from api.core.policy_loader import policy_from_state


GRAPH_NODE_ORDER = [
    "IntentRouterNode",
    "MemoryRetrievalNode",
    "SearchAgent",
    "JobIntelligenceAgent",
    "MatchingAgent",
    "ResumeTailorAgent",
    "ArchetypeDetector",
    "LegitimacyScorer",
    "OfferEvaluator",
    "QueryAgent",
    "InsightAgent",
    "QualityGate",
    "ReportAgent",
    "ReviewAgent",
]


class AgentState(TypedDict):
    run_id: str
    query: str
    user_id: str
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
    memory_summary: str
    memory_artifact_refs: Dict[str, Any]
    working_memory: List[Dict[str, Any]]
    memory_hits: List[Dict[str, Any]]
    archetype_detection: Dict[str, Any]
    adaptive_framing: Dict[str, Any]
    legitimacy_assessment: Dict[str, Any]
    offer_evaluation: Dict[str, Any]
    gap_analysis: List[Dict[str, Any]]
    level_strategy: Dict[str, Any]
    score_interpretation: Dict[str, Any]
    # Phase 2 routing fields
    workflow_id: str
    missing_artifacts: List[str]
    warnings: List[str]
    # Phase 2 tool fields
    raw_jd_text: str
    prep_pack: Dict[str, Any]
    interview_prep_pack: Dict[str, Any]
    profile_completeness: float
    profile_gaps: List[str]
    verification_report: Dict[str, Any]
    offer_comparison: Dict[str, Any]
    resume_file: Dict[str, Any]
    resume_source_type: str
    resume_raw_text: str
    resume_content_bytes: Any
    resume_source_name: str
    skip_parse: bool
    offer_list: List[Dict[str, Any]]
    offer_weights: Dict[str, float]
    # Working set analysis
    working_set_analysis: Dict[str, Any]


def build_initial_state(
    query: str,
    *,
    user_id: str = "",
    run_id: str = "",
    candidate_profile: Dict[str, Any] | None = None,
    resume_evidence: List[Dict[str, Any]] | None = None,
    job_posting: Dict[str, Any] | None = None,
    match_assessment: Dict[str, Any] | None = None,
    raw_jd_text: str = "",
    resume_file: Dict[str, Any] | None = None,
    offer_list: List[Dict[str, Any]] | None = None,
    policy: Dict[str, Any] | None = None,
    run_manifest: Dict[str, Any] | None = None,
    research_case: Dict[str, Any] | None = None,
) -> AgentState:
    resume_payload = dict(resume_file or {})
    return {
        "run_id": run_id,
        "query": query,
        "user_id": user_id,
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
        "memory_summary": "",
        "memory_artifact_refs": {},
        "working_memory": [],
        "memory_hits": [],
        "archetype_detection": {},
        "adaptive_framing": {},
        "legitimacy_assessment": {},
        "offer_evaluation": {},
        "gap_analysis": [],
        "level_strategy": {},
        "score_interpretation": {},
        # Phase 2 routing fields
        "workflow_id": "",
        "missing_artifacts": [],
        "warnings": [],
        # Phase 2 tool fields
        "raw_jd_text": str(raw_jd_text or ""),
        "prep_pack": {},
        "interview_prep_pack": {},
        "profile_completeness": 0.0,
        "profile_gaps": [],
        "verification_report": {},
        "offer_comparison": {},
        "resume_file": resume_payload,
        "resume_source_type": str(resume_payload.get("source_type") or ""),
        "resume_raw_text": str(resume_payload.get("raw_text") or ""),
        "resume_content_bytes": resume_payload.get("content_bytes"),
        "resume_source_name": str(resume_payload.get("source_name") or ""),
        "skip_parse": bool(candidate_profile or resume_evidence),
        "offer_list": list(offer_list or []),
        "offer_weights": {},
        # Working set analysis
        "working_set_analysis": {},
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
    builder.add_node("MemoryRetrievalNode", memory_retrieval_node)
    builder.add_node("SearchAgent", search_agent_node)
    builder.add_node("JobIntelligenceAgent", job_intelligence_agent_node)
    builder.add_node("MatchingAgent", matching_agent_node)
    builder.add_node("ResumeTailorAgent", resume_tailor_agent_node)
    builder.add_node("ArchetypeDetector", archetype_detector_node)
    builder.add_node("LegitimacyScorer", legitimacy_scorer_node)
    builder.add_node("OfferEvaluator", offer_evaluator_node)
    builder.add_node("QueryAgent", query_agent_node)
    builder.add_node("InsightAgent", insight_agent_node)
    builder.add_node("QualityGate", quality_gate_node)
    builder.add_node("ReportAgent", report_agent_node)
    builder.add_node("ReviewAgent", review_agent_node)

    builder.set_entry_point("IntentRouterNode")
    builder.add_edge("IntentRouterNode", "MemoryRetrievalNode")
    builder.add_edge("MemoryRetrievalNode", "SearchAgent")
    builder.add_edge("SearchAgent", "JobIntelligenceAgent")
    builder.add_edge("JobIntelligenceAgent", "MatchingAgent")
    builder.add_edge("MatchingAgent", "ResumeTailorAgent")
    builder.add_edge("ResumeTailorAgent", "ArchetypeDetector")
    builder.add_edge("ArchetypeDetector", "LegitimacyScorer")
    builder.add_edge("LegitimacyScorer", "OfferEvaluator")
    builder.add_edge("OfferEvaluator", "QueryAgent")
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


# ── Phase 2: Workflow-aware graph ──

# Phase 2 node order (replaces GRAPH_NODE_ORDER when using Phase 2 graph)
PHASE2_NODE_ORDER = [
    "Supervisor",
    "MemoryRetrievalNode",
    "SearchOrchestrator",
    "JobAnalyzer",
    "MatchingEngine",
    "ResumeTailor",
    "ResumeParser",
    "InterviewCoach",
    "OfferEvaluator",
    "ApplicationStore",
    "AnalysisAgent",
    "ReportAgent",
    "Gate",
]

# Workflow definitions: {workflow_id: [node_sequence]}
PHASE2_WORKFLOWS: dict[str, list[str]] = {
    "wf_match_v2": [
        "SearchOrchestrator", "JobAnalyzer", "MatchingEngine",
        "AnalysisAgent", "ReportAgent", "Gate",
    ],
    "wf_resume_tailor_v2": [
        "JobAnalyzer", "MatchingEngine", "ResumeTailor",
        "AnalysisAgent", "ReportAgent", "Gate",
    ],
    "wf_interview_prep_v2": [
        "JobAnalyzer", "MatchingEngine", "InterviewCoach",
        "AnalysisAgent", "ReportAgent", "Gate",
    ],
    "wf_profile_bootstrap": [
        "ResumeParser", "Gate",
    ],
    "wf_offer_compare": [
        "OfferEvaluator", "ReportAgent", "Gate",
    ],
    "wf_application_followup_v1": [
        "ApplicationStore", "Gate",
    ],
}


def _resolve_node_fn(node_name: str) -> Any:
    """Resolve a node name to its callable function."""
    from api.agents.supervisor import supervisor_node
    from api.agents.memory_retrieval import memory_retrieval_node
    from api.agents.analysis_agent import run_analysis_agent
    from api.tools.search_orchestrator import run_search_orchestrator
    from api.tools.job_analyzer import run_job_analyzer
    from api.tools.matching_engine import run_matching_engine
    from api.tools.resume_tailor import run_resume_tailor
    from api.tools.resume_parser import run_resume_parser
    from api.tools.interview_coach import run_interview_coach
    from api.tools.offer_evaluator import run_offer_evaluator
    from api.tools.application_store import run_application_store

    mapping: dict[str, Any] = {
        "Supervisor": supervisor_node,
        "MemoryRetrievalNode": memory_retrieval_node,
        "SearchOrchestrator": run_search_orchestrator,
        "JobAnalyzer": run_job_analyzer,
        "MatchingEngine": run_matching_engine,
        "ResumeTailor": run_resume_tailor,
        "ResumeParser": run_resume_parser,
        "InterviewCoach": run_interview_coach,
        "OfferEvaluator": run_offer_evaluator,
        "ApplicationStore": run_application_store,
        "AnalysisAgent": run_analysis_agent,
        "ReportAgent": report_agent_node,
        "Gate": _gate_node,
    }
    return mapping.get(node_name)


async def _gate_node(state: AgentState) -> dict[str, Any]:  # type: ignore[valid-type]
    """Gate node wrapper for LangGraph compatibility."""
    from api.core.gate import run_gate

    background = {
        "request": {"query": state.get("query"), "query_profile": dict(state.get("query_profile") or {})},
        "candidate": {
            "candidate_profile": dict(state.get("candidate_profile") or {}),
            "resume_evidence": list(state.get("resume_evidence") or []),
        },
        "policy": dict(state.get("policy") or {}),
    }
    working_set = {
        "retrieval": {"evidence_items": list(state.get("evidence_items") or [])},
        "analysis": state.get("insights", {}),
    }
    artifacts = {
        "job": {"job_snapshot": dict(state.get("job_snapshot") or {})},
        "matching": {"match_assessment": dict(state.get("match_assessment") or {})},
        "resume": {"resume_version": dict(state.get("resume_version") or {})},
        "report": {"report_content": str(state.get("report_content") or "")},
    }

    result = run_gate(
        artifacts=artifacts,
        working_set=working_set,
        background=background,
        report_content=str(state.get("report_content") or ""),
    )

    verification_report = result.model_dump(mode="json")
    review_feedback = _parse_review_feedback(state)
    gate_root_cause = str(state.get("root_cause") or "")
    retry_count = int(state.get("retry_count") or 0)

    if review_feedback is not None and not review_feedback.passed:
        verification_report["status"] = "rejected"
        verification_report["issues"] = list(verification_report.get("issues") or []) + [
            {
                "rule": "report_self_review",
                "status": "rejected",
                "message": review_feedback.feedback_markdown,
                "retry_target": review_feedback.retry_target,
            }
        ]
        gate_root_cause = str(review_feedback.root_cause or gate_root_cause or "synthesis")
    elif not gate_root_cause:
        issue_rules = [str(issue.get("rule") or "") for issue in result.issues]
        if any(rule in {"evidence_sufficiency", "company_specificity", "missing_classes"} for rule in issue_rules):
            gate_root_cause = "retrieval"
        elif any(rule in {"evidence_refs", "claim_evidence_coverage", "candidate_fact_boundary", "fiction_detection", "forbidden_phrases"} for rule in issue_rules):
            gate_root_cause = "attribution"
        elif any(rule == "action_plan_source_coverage" for rule in issue_rules):
            gate_root_cause = "synthesis"

    if verification_report.get("status") == "rejected":
        retry_count += 1

    return {
        "verification_report": verification_report,
        "quality_mode": "conservative" if verification_report.get("status") == "downgraded" else ("normal" if verification_report.get("status") == "passed" else "fallback"),
        "warning_message": "; ".join(i.get("message", "") for i in verification_report.get("issues", [])) if verification_report.get("issues") else "",
        "root_cause": gate_root_cause,
        "retry_count": retry_count,
        "status": f"Gate 校验完成: {verification_report.get('status')}",
    }


def route_after_supervisor(state: AgentState) -> str:  # type: ignore[valid-type]
    """Route to MemoryRetrievalNode after Supervisor."""
    return "MemoryRetrievalNode"


def route_after_memory_retrieval(state: AgentState) -> str:  # type: ignore[valid-type]
    """Route to the first node of the selected workflow after memory retrieval."""
    workflow_id = str(state.get("workflow_id") or "")
    if workflow_id not in PHASE2_WORKFLOWS:
        workflow_id = "wf_match_v2"

    nodes = PHASE2_WORKFLOWS[workflow_id]
    if nodes:
        return nodes[0]
    return "Gate"


def route_after_matching_engine(state: AgentState) -> str:  # type: ignore[valid-type]
    """Route after MatchingEngine depending on workflow."""
    workflow_id = str(state.get("workflow_id") or "")
    if workflow_id == "wf_resume_tailor_v2":
        return "ResumeTailor"
    if workflow_id == "wf_interview_prep_v2":
        return "InterviewCoach"
    return "AnalysisAgent"


def _gate_retry_target(state: AgentState) -> str:
    workflow_id = str(state.get("workflow_id") or "")
    workflow_nodes = PHASE2_WORKFLOWS.get(workflow_id, PHASE2_WORKFLOWS["wf_match_v2"])
    root_cause = str(state.get("root_cause") or "")

    if root_cause == "retrieval":
        if "SearchOrchestrator" in workflow_nodes:
            return "SearchOrchestrator"
        if "JobAnalyzer" in workflow_nodes:
            return "JobAnalyzer"
        return workflow_nodes[0]
    if root_cause == "attribution":
        return "AnalysisAgent" if "AnalysisAgent" in workflow_nodes else "ReportAgent"
    return "ReportAgent"


def route_after_gate(state: AgentState) -> str:  # type: ignore[valid-type]
    verification_report = dict(state.get("verification_report") or {})
    gate_status = str(verification_report.get("status") or "passed")
    if gate_status != "rejected":
        return END  # type: ignore[return-value]

    policy = policy_from_state(state)
    retry_count = int(state.get("retry_count") or 0)
    if retry_count >= int(policy.retry_policy.max_retries or 0):
        return END  # type: ignore[return-value]

    return _gate_retry_target(state)


def build_phase2_graph() -> Any:
    """Build the Phase 2 workflow-based graph with Supervisor routing.

    Structure:
      Supervisor → MemoryRetrievalNode → [first workflow node]
      → ... → Gate → END

    Each workflow follows its own Tool→Agent→Gate sequence.
    Conditional routing is only used at actual branch points.
    """
    builder: StateGraph = StateGraph(AgentState)  # type: ignore[assignment]

    # Add all nodes
    builder.add_node("Supervisor", _resolve_node_fn("Supervisor"))
    builder.add_node("MemoryRetrievalNode", _resolve_node_fn("MemoryRetrievalNode"))
    builder.add_node("SearchOrchestrator", _resolve_node_fn("SearchOrchestrator"))
    builder.add_node("JobAnalyzer", _resolve_node_fn("JobAnalyzer"))
    builder.add_node("MatchingEngine", _resolve_node_fn("MatchingEngine"))
    builder.add_node("ResumeTailor", _resolve_node_fn("ResumeTailor"))
    builder.add_node("ResumeParser", _resolve_node_fn("ResumeParser"))
    builder.add_node("InterviewCoach", _resolve_node_fn("InterviewCoach"))
    builder.add_node("OfferEvaluator", _resolve_node_fn("OfferEvaluator"))
    builder.add_node("ApplicationStore", _resolve_node_fn("ApplicationStore"))
    builder.add_node("AnalysisAgent", _resolve_node_fn("AnalysisAgent"))
    builder.add_node("ReportAgent", _resolve_node_fn("ReportAgent"))
    builder.add_node("Gate", _resolve_node_fn("Gate"))

    # Entry: Supervisor
    builder.set_entry_point("Supervisor")

    # Supervisor → MemoryRetrievalNode (always)
    builder.add_edge("Supervisor", "MemoryRetrievalNode")

    # MemoryRetrievalNode → first workflow node (conditional)
    builder.add_conditional_edges(
        "MemoryRetrievalNode",
        route_after_memory_retrieval,
        {
            "SearchOrchestrator": "SearchOrchestrator",
            "JobAnalyzer": "JobAnalyzer",
            "ResumeParser": "ResumeParser",
            "OfferEvaluator": "OfferEvaluator",
            "ApplicationStore": "ApplicationStore",
            "Gate": "Gate",
        },
    )

    # Linear edges (no branching needed)
    builder.add_edge("SearchOrchestrator", "JobAnalyzer")
    builder.add_edge("JobAnalyzer", "MatchingEngine")

    # MatchingEngine → conditional branch (ResumeTailor, InterviewCoach, or AnalysisAgent)
    builder.add_conditional_edges(
        "MatchingEngine",
        route_after_matching_engine,
        {
            "ResumeTailor": "ResumeTailor",
            "InterviewCoach": "InterviewCoach",
            "AnalysisAgent": "AnalysisAgent",
        },
    )

    # Tool → AnalysisAgent edges
    builder.add_edge("ResumeTailor", "AnalysisAgent")
    builder.add_edge("InterviewCoach", "AnalysisAgent")

    # Special paths that skip AnalysisAgent
    builder.add_edge("ResumeParser", "Gate")
    builder.add_edge("OfferEvaluator", "ReportAgent")
    builder.add_edge("ApplicationStore", "Gate")

    # AnalysisAgent → ReportAgent → Gate
    builder.add_edge("AnalysisAgent", "ReportAgent")
    builder.add_edge("ReportAgent", "Gate")

    # Gate → END or retry source node
    builder.add_conditional_edges(
        "Gate",
        route_after_gate,
        {
            "SearchOrchestrator": "SearchOrchestrator",
            "JobAnalyzer": "JobAnalyzer",
            "AnalysisAgent": "AnalysisAgent",
            "ReportAgent": "ReportAgent",
            "ResumeParser": "ResumeParser",
            "OfferEvaluator": "OfferEvaluator",
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

    if agent == "JobIntelligenceAgent":
        job_snapshot = dict(state.get("job_snapshot") or {})
        external_evidence_pack = dict(state.get("external_evidence_pack") or {})
        return {
            "type": "message",
            "speaker": "JobIntelligenceAgent",
            "content": "JobIntelligenceAgent 已融合外部证据生成岗位快照与证据包。",
            "metadata": {
                "job_snapshot_id": job_snapshot.get("job_snapshot_id"),
                "evidence_pack_id": external_evidence_pack.get("evidence_pack_id"),
                "job_id": job_snapshot.get("job_id"),
                "requirement_count": len(list(job_snapshot.get("job_requirements") or [])),
                "evidence_source_count": len(list(external_evidence_pack.get("sources") or [])),
                "freshness": (job_snapshot.get("evidence_quality") or {}).get("freshness"),
                "coverage": (job_snapshot.get("evidence_quality") or {}).get("coverage"),
            },
            "timestamp": now,
        }

    if agent == "MatchingAgent":
        match_assessment = dict(state.get("match_assessment") or {})
        return {
            "type": "message",
            "speaker": "MatchingAgent",
            "content": "MatchingAgent 已完成候选人-岗位匹配分析。",
            "metadata": {
                "assessment_id": match_assessment.get("assessment_id"),
                "overall_score": match_assessment.get("overall_score"),
                "recommendation": match_assessment.get("recommendation"),
                "strength_count": len(list(match_assessment.get("strengths") or [])),
                "gap_count": len(list(match_assessment.get("gaps") or [])),
                "risk_count": len(list(match_assessment.get("risks") or [])),
                "dimension_scores": match_assessment.get("dimension_scores"),
            },
            "timestamp": now,
        }

    if agent == "ResumeTailorAgent":
        tailor_plan = dict(state.get("tailor_plan") or {})
        resume_version = dict(state.get("resume_version") or {})
        fact_check_report = dict(state.get("fact_check_report") or {})
        return {
            "type": "message",
            "speaker": "ResumeTailorAgent",
            "content": "ResumeTailorAgent 已生成简历定制计划、岗位版本和事实校验结果。",
            "metadata": {
                "tailor_plan_id": tailor_plan.get("tailor_plan_id"),
                "resume_version_id": resume_version.get("resume_version_id"),
                "target_role": tailor_plan.get("target_role"),
                "fact_check_status": fact_check_report.get("status") or resume_version.get("fact_check_status"),
                "keyword_covered": list((tailor_plan.get("keyword_coverage") or {}).get("covered") or [])[:4],
                "keyword_missing": list((tailor_plan.get("keyword_coverage") or {}).get("missing") or [])[:4],
                "section_action_count": len(list(tailor_plan.get("section_actions") or [])),
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
    "PHASE2_NODE_ORDER",
    "PHASE2_WORKFLOWS",
    "build_agent_message_event",
    "build_career_research_graph",
    "build_phase2_graph",
    "build_initial_state",
    "merge_state_update",
    "parse_review_feedback_json",
    "route_after_review",
    "route_after_supervisor",
    "route_after_memory_retrieval",
    "route_after_matching_engine",
    "route_after_gate",
]
