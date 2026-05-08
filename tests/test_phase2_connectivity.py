"""Phase 2 connectivity test — Supervisor Agent."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.agents.supervisor import supervisor_node, _deterministic_route


def test_deterministic_match():
    state = {"query": "帮我分析字节后端实习是否匹配", "candidate_profile": {}, "resume_evidence": []}
    result = _deterministic_route(state["query"], state)
    assert result is not None
    assert result.intent == "match"
    assert result.workflow_id == "wf_match_v2"
    print("✓ Det-match OK")


def test_deterministic_tailor():
    state = {"query": "帮我改简历", "candidate_profile": {}, "resume_evidence": []}
    result = _deterministic_route(state["query"], state)
    assert result is not None
    assert result.intent == "resume_tailor"
    assert result.workflow_id == "wf_resume_tailor_v2"
    print("✓ Det-tailor OK")


def test_deterministic_interview():
    state = {"query": "准备面试", "candidate_profile": {}, "resume_evidence": []}
    result = _deterministic_route(state["query"], state)
    assert result is not None
    assert result.intent == "interview_prep"
    assert result.workflow_id == "wf_interview_prep_v2"
    print("✓ Det-interview OK")


def test_deterministic_offer():
    state = {"query": "对比这两个offer", "candidate_profile": {}, "resume_evidence": []}
    result = _deterministic_route(state["query"], state)
    assert result is not None
    assert result.intent == "offer_compare"
    assert result.workflow_id == "wf_offer_compare"
    print("✓ Det-offer OK")


def test_deterministic_profile():
    state = {"query": "上传简历", "resume_file": "resume.pdf", "candidate_profile": {}}
    result = _deterministic_route(state["query"], state)
    assert result is not None
    assert result.intent == "profile_bootstrap"
    assert result.workflow_id == "wf_profile_bootstrap"
    print("✓ Det-profile OK")


def test_missing_params():
    state = {"query": "改简历", "candidate_profile": {}, "resume_evidence": []}
    result = _deterministic_route(state["query"], state)
    assert result is not None
    assert "candidate_profile" in result.missing_artifacts
    print("✓ Missing params OK")


def test_supervisor_node_sync():
    """Test supervisor_node with deterministic routing (no LLM needed)."""
    state = {
        "query": "分析匹配度",
        "user_id": "test",
        "candidate_profile": {"candidate_id": "c1", "name": "测试"},
        "resume_evidence": [{"evidence_id": "e1", "section": "project"}],
        "insights": {},
    }
    result = asyncio.run(supervisor_node(state))
    assert result["intent"] in ("match", "general")
    assert result["workflow_id"] in ("wf_match_v2",)
    print("✓ Supervisor node OK")


if __name__ == "__main__":
    test_deterministic_match()
    test_deterministic_tailor()
    test_deterministic_interview()
    test_deterministic_offer()
    test_deterministic_profile()
    test_missing_params()
    test_supervisor_node_sync()
    print("\n=== Phase 2 connectivity: ALL TESTS PASSED ===")
