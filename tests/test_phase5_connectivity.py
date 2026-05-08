"""Phase 5 connectivity test — Agents + Workflows + Graph."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_phase2_graph_builds():
    """Verify the Phase 2 graph can be built without errors."""
    from api.core.graph import build_phase2_graph, PHASE2_WORKFLOWS, PHASE2_NODE_ORDER, AgentState, build_initial_state

    # Verify workflow definitions
    assert "wf_match_v2" in PHASE2_WORKFLOWS
    assert "wf_profile_bootstrap" in PHASE2_WORKFLOWS
    assert "wf_offer_compare" in PHASE2_WORKFLOWS
    assert len(PHASE2_WORKFLOWS) == 6

    # Verify match workflow sequence
    match_wf = PHASE2_WORKFLOWS["wf_match_v2"]
    assert "SearchOrchestrator" in match_wf
    assert "JobAnalyzer" in match_wf
    assert "MatchingEngine" in match_wf
    assert "AnalysisAgent" in match_wf
    assert "ReportAgent" in match_wf
    assert "Gate" in match_wf
    assert match_wf[-1] == "Gate"

    # Verify bootstrap workflow
    bs_wf = PHASE2_WORKFLOWS["wf_profile_bootstrap"]
    assert "ResumeParser" in bs_wf
    assert bs_wf[-1] == "Gate"

    # Verify initial state
    state = build_initial_state("test query", user_id="test")
    assert state["query"] == "test query"
    assert state["user_id"] == "test"

    # Build the graph
    graph = build_phase2_graph()
    assert graph is not None
    print("✓ Phase 2 graph built OK")


def test_graph_routing():
    """Test the routing functions."""
    from api.core.graph import route_after_supervisor, route_after_memory_retrieval, route_after_matching_engine, AgentState, build_initial_state

    state = build_initial_state("分析匹配度")

    # Supervisor now routes to MemoryRetrievalNode first
    result = route_after_supervisor(state)
    assert result == "MemoryRetrievalNode"

    # MemoryRetrievalNode routes to first workflow node
    state["workflow_id"] = "wf_match_v2"
    result = route_after_memory_retrieval(state)
    assert result == "SearchOrchestrator"

    state["workflow_id"] = "wf_profile_bootstrap"
    result = route_after_memory_retrieval(state)
    assert result == "ResumeParser"

    state["workflow_id"] = "wf_offer_compare"
    result = route_after_memory_retrieval(state)
    assert result == "OfferEvaluator"

    state["workflow_id"] = "unknown"
    result = route_after_memory_retrieval(state)
    assert result == "SearchOrchestrator"  # default to match

    # MatchingEngine routing
    state["workflow_id"] = "wf_resume_tailor_v2"
    result = route_after_matching_engine(state)
    assert result == "ResumeTailor"

    state["workflow_id"] = "wf_interview_prep_v2"
    result = route_after_matching_engine(state)
    assert result == "InterviewCoach"

    state["workflow_id"] = "wf_match_v2"
    result = route_after_matching_engine(state)
    assert result == "AnalysisAgent"
    print("✓ Graph routing OK")


def test_analysis_agent_import():
    """Verify AnalysisAgent module loads."""
    from api.agents.analysis_agent import run_analysis_agent
    assert run_analysis_agent is not None
    print("✓ AnalysisAgent import OK")


def test_gate_node_sync():
    """Test the Gate node."""
    from api.core.graph import _gate_node, build_initial_state

    state = build_initial_state("test")
    state["report_content"] = "正常的分析报告，包含有效证据。"
    state["evidence_items"] = [{"company_specific": True}, {"company_specific": True}]
    state["candidate_profile"] = {"candidate_id": "c1", "skills": ["Python"]}
    state["resume_evidence"] = [{"evidence_id": "e1", "normalized_skills": ["Python"]}]

    result = asyncio.run(_gate_node(state))
    assert "verification_report" in result
    vr = result["verification_report"]
    assert vr["status"] in ("passed", "downgraded", "rejected")
    print(f"✓ Gate node OK — status: {vr['status']}")


def test_supervisor_import():
    """Verify Supervisor module loads."""
    from api.agents.supervisor import supervisor_node
    assert supervisor_node is not None
    print("✓ Supervisor import OK")


def test_all_phase2_imports():
    """Verify all Phase 2 modules import cleanly."""
    from api.core.settings import get_settings
    from api.core.constants import FORBIDDEN_PHRASES, PHASE2_INTENTS
    from api.core.contracts import SupervisorResponse, GateOutput
    from api.core.gate import run_gate
    from api.agents.supervisor import supervisor_node
    from api.agents.analysis_agent import run_analysis_agent
    from api.tools.matching_engine import run_matching_engine
    from api.tools.job_analyzer import run_job_analyzer
    from api.tools.resume_tailor import run_resume_tailor
    from api.tools.resume_parser import run_resume_parser
    from api.tools.interview_coach import run_interview_coach
    from api.tools.offer_evaluator import run_offer_evaluator
    from api.tools.search_orchestrator import run_search_orchestrator
    assert all([
        get_settings, FORBIDDEN_PHRASES, PHASE2_INTENTS,
        SupervisorResponse, GateOutput, run_gate,
        supervisor_node, run_analysis_agent,
        run_matching_engine, run_job_analyzer,
        run_resume_tailor, run_resume_parser,
        run_interview_coach, run_offer_evaluator,
        run_search_orchestrator,
    ])
    print("✓ All Phase 2 imports OK")


if __name__ == "__main__":
    test_phase2_graph_builds()
    test_graph_routing()
    test_analysis_agent_import()
    test_supervisor_import()
    test_gate_node_sync()
    test_all_phase2_imports()
    print("\n=== Phase 5 connectivity: ALL TESTS PASSED ===")
