from __future__ import annotations

import pytest

from api.agents.job_intelligence_agent import build_external_evidence_pack, job_intelligence_agent_node
from api.agents.query_agent import query_agent_node


def test_build_external_evidence_pack_preserves_research_metadata():
    evidence_items = [
        {
            "source_id": "source-1",
            "source_class": "jd",
            "query": "字节 后端 JD",
            "url": "https://jobs.example.com/backend",
            "title": "后端开发实习生",
            "snippet": "熟悉 Redis、MySQL、消息队列",
            "published": "2026-04-01",
            "relevance_hint": "命中目标公司",
            "company_specific": True,
            "freshness_score": 95,
            "quality_score": 88,
        },
        {
            "source_id": "source-2",
            "source_class": "interview",
            "query": "字节 后端 面经",
            "url": "https://interview.example.com/backend",
            "title": "后端一面面经",
            "snippet": "重点追问缓存设计与项目深挖",
            "published": "2026-03-21",
            "relevance_hint": "高质量面经",
            "company_specific": True,
            "freshness_score": 85,
            "quality_score": 79,
        },
    ]
    insights = {
        "company_signals": ["交易中台", "高并发服务"],
        "interview_expectations": ["项目深挖", "缓存设计"],
        "coverage_gaps": ["团队归属仍有轻微歧义"],
    }

    pack = build_external_evidence_pack(job_id="job_001", evidence_items=evidence_items, insights=insights)

    assert pack.job_id == "job_001"
    assert [source.source_id for source in pack.sources] == ["source-1", "source-2"]
    assert pack.sources[0].evidence_class == "jd"
    assert pack.sources[0].confidence == pytest.approx(0.88)
    assert pack.company_signals == ["交易中台", "高并发服务"]
    assert "团队归属仍有轻微歧义" in pack.risk_flags


@pytest.mark.asyncio
async def test_job_intelligence_agent_node_builds_job_snapshot_from_state():
    state = {
        "query_profile": {
            "company": "字节跳动",
            "role": "后端开发实习",
            "domain_hint": "交易中台",
        },
        "evidence_items": [
            {
                "source_id": "source-1",
                "source_class": "jd",
                "query": "字节 后端 JD",
                "url": "https://jobs.example.com/backend",
                "title": "后端开发实习生",
                "snippet": "熟悉 Redis、MySQL、消息队列",
                "published": "2026-04-01",
                "relevance_hint": "命中目标公司",
                "company_specific": True,
                "freshness_score": 95,
                "quality_score": 88,
            },
            {
                "source_id": "source-2",
                "source_class": "company_profile",
                "query": "字节 交易中台",
                "url": "https://tech.example.com/trade",
                "title": "交易中台技术实践",
                "snippet": "服务高并发交易链路",
                "published": "2025-12-01",
                "relevance_hint": "命中业务域",
                "company_specific": True,
                "freshness_score": 85,
                "quality_score": 83,
            },
        ],
        "insights": {
            "company": "字节跳动",
            "role": "后端开发实习",
            "company_signals": ["交易中台"],
            "business_domain_hints": ["交易中台"],
            "company_specific_requirements": ["JD 证据明确强调 Redis 与 MySQL 等中间件能力。"],
            "common_requirements": ["项目叙事必须能讲清背景、取舍、指标和复盘。"],
            "technical_stack_requirements": ["Redis", "MySQL", "消息队列"],
            "interview_expectations": ["项目深挖", "缓存设计"],
            "coverage_gaps": ["团队归属仍有轻微歧义"],
            "context_quality_score": 78,
        },
    }

    update = await job_intelligence_agent_node(state)
    snapshot = update["job_snapshot"]

    assert snapshot["job_id"] == "job::字节跳动::后端开发实习"
    assert snapshot["job_posting"]["company_name"] == "字节跳动"
    assert snapshot["job_requirements"][0]["requirement_level"] == "must_have"
    assert snapshot["evidence_quality"]["freshness"] == 90
    assert "团队归属仍有轻微歧义" in snapshot["evidence_quality"]["ambiguity_notes"]
    assert update["external_evidence_pack"]["company_signals"] == ["交易中台"]


@pytest.mark.asyncio
async def test_query_agent_node_returns_job_intelligence_artifacts(monkeypatch):
    async def fail_structured_output(*_args, **_kwargs):
        raise RuntimeError("force heuristic path")

    monkeypatch.setattr("api.agents.query_agent.invoke_structured_output", fail_structured_output)
    state = {
        "query": "帮我研究字节跳动后端开发实习",
        "intent": "general",
        "candidate_profile": {
            "candidate_id": "cand_001",
            "target_roles": ["后端开发工程师"],
            "skills": ["Redis", "MySQL"],
            "education": [{"school": "某大学"}],
            "years_of_experience": 1.0,
        },
        "resume_evidence": [
            {
                "evidence_id": "evi_001",
                "text": "在项目中使用 Redis 和 MySQL 处理高并发读写。",
                "normalized_skills": ["Redis", "MySQL"],
            }
        ],
        "query_profile": {
            "company": "字节跳动",
            "role": "后端开发实习",
            "domain_hint": "交易中台",
        },
        "evidence_items": [
            {
                "source_id": "source-1",
                "source_class": "jd",
                "query": "字节 后端 JD",
                "url": "https://jobs.example.com/backend",
                "title": "后端开发实习生",
                "snippet": "熟悉 Redis、MySQL、消息队列",
                "published": "2026-04-01",
                "relevance_hint": "命中目标公司",
                "company_specific": True,
                "freshness_score": 95,
                "quality_score": 88,
            }
        ],
        "insights": {
            "company": "字节跳动",
            "role": "后端开发实习",
            "context_quality_score": 78,
            "company_specific_source_count": 2,
            "company_signals": ["交易中台"],
            "business_domain_hints": ["交易中台"],
        },
    }

    update = await query_agent_node(state)

    assert update["job_snapshot"]["job_posting"]["company_name"] == "字节跳动"
    assert update["job_snapshot"]["external_evidence_pack_id"].startswith("jep::")
    assert update["external_evidence_pack"]["sources"][0]["source_id"] == "source-1"
    assert update["match_assessment"]["candidate_id"] == "cand_001"
    assert update["match_assessment"]["job_id"].startswith("job::")
