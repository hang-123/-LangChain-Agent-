from __future__ import annotations

import pytest

from api.agents.matching_agent import matching_agent_node


@pytest.mark.asyncio
async def test_matching_agent_node_scores_candidate_against_job_snapshot():
    state = {
        "candidate_profile": {
            "candidate_id": "cand_001",
            "target_roles": ["后端开发工程师"],
            "years_of_experience": 1.5,
            "location_preferences": ["上海"],
            "education": [{"school": "某大学"}],
            "skills": ["Java", "Redis", "MySQL"],
        },
        "resume_evidence": [
            {
                "evidence_id": "evi_001",
                "evidence_type": "project",
                "text": "负责订单服务接口开发，使用 Redis 与 MySQL 支撑高峰请求。",
                "normalized_skills": ["Java", "Redis", "MySQL"],
            },
            {
                "evidence_id": "evi_002",
                "evidence_type": "work_experience",
                "text": "后端实习经历，负责服务接口与缓存优化。",
                "normalized_skills": ["Java", "Redis"],
            },
        ],
        "job_snapshot": {
            "job_snapshot_id": "js_001",
            "job_id": "job_001",
            "job_posting": {
                "job_title": "后端开发工程师",
                "city": "上海",
                "business_domain": "交易中台",
            },
            "job_requirements": [
                {"requirement_id": "req_001", "name": "Redis", "requirement_level": "must_have", "category": "skill"},
                {"requirement_id": "req_002", "name": "MySQL", "requirement_level": "must_have", "category": "skill"},
                {"requirement_id": "req_003", "name": "Kafka", "requirement_level": "nice_to_have", "category": "skill"},
            ],
            "evidence_quality": {"ambiguity_notes": ["团队归属仍有轻微歧义"]},
        },
    }

    update = await matching_agent_node(state)
    assessment = update["match_assessment"]

    assert assessment["candidate_id"] == "cand_001"
    assert assessment["job_id"] == "job_001"
    assert assessment["overall_score"] >= 70
    assert assessment["recommendation"] == "recommended_with_risks"
    assert any(item["title"].startswith("已覆盖 Redis") for item in assessment["strengths"])
    assert any(item["title"].startswith("缺少 Kafka") for item in assessment["gaps"])
    assert any("团队归属仍有轻微歧义" in item["title"] for item in assessment["risks"])


@pytest.mark.asyncio
async def test_matching_agent_node_requires_job_snapshot_for_formal_score():
    update = await matching_agent_node(
        {
            "candidate_profile": {"candidate_id": "cand_001", "skills": ["Redis"]},
            "resume_evidence": [{"evidence_id": "evi_001", "text": "使用 Redis", "normalized_skills": ["Redis"]}],
            "job_snapshot": {},
        }
    )

    assert update["match_assessment"] == {}
    assert "缺少 JobSnapshot" in update["status"]
