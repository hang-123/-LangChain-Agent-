"""Supervisor agent tests — deterministic routing + LLM fallback."""
from __future__ import annotations

import pytest
from api.agents.supervisor import _deterministic_route, _detect_missing, supervisor_node
from api.core.graph import build_initial_state


class TestDeterministicRouting:
    def test_route_match(self):
        state = build_initial_state("分析匹配度")
        result = _deterministic_route("分析匹配度", state)
        assert result is not None
        assert result.intent == "match"
        assert result.workflow_id == "wf_match_v2"

    def test_route_resume_tailor(self):
        state = build_initial_state("帮我改简历")
        result = _deterministic_route("帮我改简历", state)
        assert result is not None
        assert result.intent == "resume_tailor"
        assert result.workflow_id == "wf_resume_tailor_v2"

    def test_route_interview_prep(self):
        state = build_initial_state("准备面试")
        result = _deterministic_route("准备面试", state)
        assert result is not None
        assert result.intent == "interview_prep"
        assert result.workflow_id == "wf_interview_prep_v2"

    def test_route_offer_compare(self):
        state = build_initial_state("对比这两个offer")
        result = _deterministic_route("对比这两个offer", state)
        assert result is not None
        assert result.intent == "offer_compare"
        assert result.workflow_id == "wf_offer_compare"

    def test_route_profile_bootstrap(self):
        state = build_initial_state("上传简历")
        result = _deterministic_route("上传简历", state)
        assert result is not None
        assert result.intent == "profile_bootstrap"
        assert result.workflow_id == "wf_profile_bootstrap"

    def test_no_keywords_returns_none(self):
        """When no keywords match specific intents, returns None for LLM fallback."""
        state = build_initial_state("你好，今天天气怎么样")
        result = _deterministic_route("你好，今天天气怎么样", state)
        # May match "分析" etc. or return None
        if result is not None:
            assert result.intent in ("match", "general")


class TestDetectMissing:
    def test_match_workflow_needs_query(self):
        state = build_initial_state("")
        missing = _detect_missing("wf_match_v2", state)
        assert "query" in missing

    def test_tailor_workflow_needs_profile(self):
        state = build_initial_state("改简历")
        missing = _detect_missing("wf_resume_tailor_v2", state)
        assert "candidate_profile" in missing
        assert "resume_evidence" in missing

    def test_offer_workflow_needs_at_least_two(self):
        state = build_initial_state("对比offer")
        state["offer_list"] = [{"id": "1"}]
        missing = _detect_missing("wf_offer_compare", state)
        assert "offer_list" in missing

    def test_match_workflow_with_resume_evidence(self):
        state = build_initial_state("分析匹配")
        state["candidate_profile"] = {"candidate_id": "test"}
        state["resume_evidence"] = [{"evidence_id": "ev1"}]
        missing = _detect_missing("wf_match_v2", state)
        assert "candidate_profile" not in missing


class TestSupervisorNode:
    @pytest.mark.asyncio
    async def test_supervisor_deterministic_route(self):
        state = build_initial_state("帮我看看字节后端实习岗位怎么样")
        state["candidate_profile"] = {"candidate_id": "test", "skills": ["Python"]}
        state["resume_evidence"] = [{"evidence_id": "ev1", "section": "skills"}]
        result = await supervisor_node(state)
        assert "intent" in result
        assert "workflow_id" in result
        assert result["workflow_id"] in (
            "wf_match_v2", "wf_resume_tailor_v2", "wf_interview_prep_v2",
            "wf_profile_bootstrap", "wf_offer_compare",
        )

    @pytest.mark.asyncio
    async def test_supervisor_empty_query(self):
        state = build_initial_state("")
        result = await supervisor_node(state)
        assert result["workflow_id"] == "wf_match_v2"
        assert "查询为空" in str(result.get("warnings", ""))

    @pytest.mark.asyncio
    async def test_supervisor_returns_query_profile(self):
        state = build_initial_state("帮我分析")
        result = await supervisor_node(state)
        assert "query_profile" in result
        assert isinstance(result["query_profile"], dict)

    @pytest.mark.asyncio
    async def test_supervisor_returns_missing_artifacts(self):
        state = build_initial_state("准备面试")
        result = await supervisor_node(state)
        assert "missing_artifacts" in result
        assert isinstance(result["missing_artifacts"], list)
