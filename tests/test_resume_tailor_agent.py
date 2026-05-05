from __future__ import annotations

import pytest

from api.agents.query_agent import query_agent_node
from api.agents.resume_tailor_agent import build_resume_tailoring_artifacts


@pytest.mark.asyncio
async def test_query_agent_node_builds_resume_tailor_artifacts_without_fabricating_missing_requirements(monkeypatch):
    async def fail_structured_output(*_args, **_kwargs):
        raise RuntimeError("force heuristic path")

    monkeypatch.setattr("api.agents.query_agent.invoke_structured_output", fail_structured_output)
    state = {
        "query": "帮我研究字节跳动后端开发实习",
        "intent": "general",
        "candidate_profile": {
            "candidate_id": "cand_001",
            "target_roles": ["后端开发工程师"],
            "skills": ["Java", "Redis", "MySQL"],
            "education": [{"school": "某大学"}],
            "years_of_experience": 1.0,
        },
        "resume_evidence": [
            {
                "evidence_id": "evi_001",
                "evidence_type": "project",
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
                "snippet": "熟悉 Redis、MySQL、Kafka",
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

    plan = update["tailor_plan"]
    version = update["resume_version"]
    fact_check = update["fact_check_report"]

    assert "Redis" in plan["headline_suggestion"]
    assert "MySQL" in plan["headline_suggestion"]
    assert plan["keyword_coverage"]["missing"] == ["Kafka"]
    assert plan["section_actions"][0]["allowed_evidence_refs"] == ["evi_001"]
    assert "Kafka" not in version["keyword_insertions"]
    assert version["fact_check_status"] == "downgraded"
    assert fact_check["status"] == "downgraded"
    assert fact_check["blocked_claims"]
    assert "Kafka" in fact_check["blocked_claims"][0]


def test_resume_tailor_artifacts_use_evidence_ids_and_section_names():
    artifacts = build_resume_tailoring_artifacts(
        candidate_profile={
            "candidate_id": "cand_001",
            "source_resume_id": "resume_raw_001",
            "target_roles": ["后端开发工程师"],
            "skills": ["Java", "Redis"],
        },
        resume_evidence=[
            {
                "evidence_id": "evi_project_001",
                "resume_id": "resume_raw_001",
                "evidence_type": "project",
                "text": "在订单系统项目中使用 Redis 和 MySQL 处理高并发读写。",
                "normalized_skills": ["Redis", "MySQL"],
            },
            {
                "evidence_id": "evi_exp_001",
                "resume_id": "resume_raw_001",
                "evidence_type": "work_experience",
                "text": "负责 Java 后端接口开发和联调。",
                "normalized_skills": ["Java"],
            },
        ],
        job_snapshot={
            "job_id": "job_001",
            "job_posting": {"job_title": "后端开发工程师"},
            "job_requirements": [
                {
                    "requirement_id": "req_001",
                    "name": "Redis",
                    "requirement_level": "must_have",
                    "description": "熟悉缓存设计与常见使用场景",
                    "evidence_text": "熟悉 Redis 和 MySQL",
                },
                {
                    "requirement_id": "req_002",
                    "name": "Kafka",
                    "requirement_level": "must_have",
                    "description": "熟悉消息队列",
                    "evidence_text": "熟悉 Kafka",
                },
            ],
        },
        match_assessment={
            "assessment_id": "match_001",
            "candidate_id": "cand_001",
            "job_id": "job_001",
        },
    )

    plan = artifacts["tailor_plan"]
    assert plan["section_actions"][0]["section"] == "projects"
    assert plan["section_actions"][0]["allowed_evidence_refs"] == ["evi_project_001"]
    skills_action = next(item for item in plan["section_actions"] if item["section"] == "skills")
    assert skills_action["allowed_evidence_refs"]
    assert all(ref.startswith("evi_") for ref in skills_action["allowed_evidence_refs"])


def test_resume_tailor_artifacts_normalize_section_aliases():
    artifacts = build_resume_tailoring_artifacts(
        candidate_profile={
            "candidate_id": "cand_002",
            "target_roles": ["后端开发工程师"],
            "skills": ["Redis"],
        },
        resume_evidence=[
            {
                "evidence_id": "evi_project_002",
                "resume_id": "resume_raw_002",
                "section": "project",
                "text": "在订单系统项目中使用 Redis。",
                "normalized_skills": ["Redis"],
            }
        ],
        job_snapshot={
            "job_id": "job_002",
            "job_posting": {"job_title": "后端开发工程师"},
            "job_requirements": [
                {
                    "requirement_id": "req_001",
                    "name": "Redis",
                    "requirement_level": "must_have",
                    "description": "熟悉缓存设计",
                    "evidence_text": "熟悉 Redis",
                }
            ],
        },
        match_assessment={
            "assessment_id": "match_002",
            "candidate_id": "cand_002",
            "job_id": "job_002",
        },
    )

    project_action = next(
        item for item in artifacts["tailor_plan"]["section_actions"] if item["allowed_evidence_refs"] == ["evi_project_002"]
    )
    assert project_action["section"] == "projects"


def test_resume_tailor_artifacts_fail_closed_on_malformed_evidence_items():
    with pytest.raises(ValueError, match="resume_evidence\\[1\\] must include evidence_id"):
        build_resume_tailoring_artifacts(
            candidate_profile={
                "candidate_id": "cand_003",
                "skills": ["Redis"],
            },
            resume_evidence=[
                {
                    "resume_id": "resume_raw_003",
                    "section": "projects",
                    "text": "在订单系统项目中使用 Redis。",
                }
            ],
            job_snapshot={
                "job_id": "job_003",
                "job_posting": {"job_title": "后端开发工程师"},
                "job_requirements": [],
            },
            match_assessment={
                "assessment_id": "match_003",
                "candidate_id": "cand_003",
                "job_id": "job_003",
            },
        )


@pytest.mark.parametrize(
    ("candidate_profile", "job_snapshot", "expected_error"),
    [
        (
            {"skills": ["Java"]},
            {
                "job_id": "job_001",
                "job_posting": {"job_title": "后端开发工程师"},
                "job_requirements": [],
            },
            "candidate_profile.candidate_id",
        ),
        (
            {"candidate_id": "cand_001"},
            {
                "job_posting": {"job_title": "后端开发工程师"},
                "job_requirements": [],
            },
            "job_snapshot.job_id",
        ),
    ],
)
def test_resume_tailor_artifacts_fail_closed_on_malformed_inputs(candidate_profile, job_snapshot, expected_error):
    with pytest.raises(ValueError, match=expected_error):
        build_resume_tailoring_artifacts(
            candidate_profile=candidate_profile,
            resume_evidence=[
                {
                    "evidence_id": "evi_001",
                    "resume_id": "resume_raw_001",
                    "evidence_type": "project",
                    "text": "在订单系统项目中使用 Redis。",
                    "normalized_skills": ["Redis"],
                }
            ],
            job_snapshot=job_snapshot,
            match_assessment={
                "assessment_id": "match_001",
                "candidate_id": "cand_001",
                "job_id": "job_001",
            },
        )
