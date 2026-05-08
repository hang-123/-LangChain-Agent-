"""Phase 3 connectivity test — Tools: SearchOrchestrator, JobAnalyzer, MatchingEngine."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.tools.matching_engine import run_matching_engine, _normalize_token, _recommendation
from api.tools.job_analyzer import run_job_analyzer, _build_legitimacy_assessment


def test_matching_normalize():
    assert _normalize_token("Java") == "java"
    assert _normalize_token("  Spring Boot  ") == "spring boot"
    print("✓ Matching normalize OK")


def test_matching_recommendation():
    assert _recommendation(85) == "strong_recommend"
    assert _recommendation(70) == "recommended_with_risks"
    assert _recommendation(55) == "neutral"
    assert _recommendation(30) == "not_recommended"
    print("✓ Matching recommendation OK")


def test_matching_engine_full():
    state = {
        "query": "测试匹配度",
        "candidate_profile": {
            "candidate_id": "cand_001",
            "skills": ["Python", "Java", "Redis"],
            "years_of_experience": 2,
            "education": [{"school": "测试大学", "degree": "学士"}],
            "target_roles": ["后端开发"],
        },
        "resume_evidence": [
            {"evidence_id": "e1", "section": "project", "text": "使用Python开发后端服务", "normalized_skills": ["Python", "Redis"]},
        ],
        "job_snapshot": {
            "job_id": "job_001",
            "job_requirements": [
                {"requirement_id": "req_1", "name": "Python", "requirement_level": "must_have"},
                {"requirement_id": "req_2", "name": "Go", "requirement_level": "must_have"},
                {"requirement_id": "req_3", "name": "Docker", "requirement_level": "nice_to_have"},
            ],
            "job_posting": {"job_title": "后端开发工程师", "city": "北京"},
            "evidence_quality": {"ambiguity_notes": []},
        },
        "legitimacy_assessment": {"tier": "High Confidence"},
    }
    result = asyncio.run(run_matching_engine(state))
    assert "match_assessment" in result
    ma = result["match_assessment"]
    assert ma["overall_score"] > 0
    assert ma["overall_score"] <= 100
    assert ma["recommendation"] in ("strong_recommend", "recommended_with_risks", "neutral", "not_recommended")
    print(f"✓ MatchingEngine OK — score: {ma['overall_score']}, recommendation: {ma['recommendation']}")


def test_matching_engine_no_resume():
    state = {
        "candidate_profile": {"candidate_id": "cand_001", "skills": []},
        "resume_evidence": [],
        "job_snapshot": {
            "job_id": "job_001",
            "job_requirements": [
                {"requirement_id": "req_1", "name": "Python", "requirement_level": "must_have"},
            ],
            "job_posting": {},
            "evidence_quality": {},
        },
        "legitimacy_assessment": {},
    }
    result = asyncio.run(run_matching_engine(state))
    ma = result["match_assessment"]
    assert ma["overall_score"] <= 58  # Conservative cap
    print(f"✓ MatchingEngine (no resume) OK — score capped at: {ma['overall_score']}")


def test_matching_engine_empty_snapshot():
    state = {
        "candidate_profile": {},
        "resume_evidence": [],
        "job_snapshot": {},
    }
    result = asyncio.run(run_matching_engine(state))
    assert result["match_assessment"] == {}
    print("✓ MatchingEngine (empty snapshot) OK — returns empty")


def test_legitimacy_assessment():
    result = _build_legitimacy_assessment(
        all_text="需要3年Python开发经验，熟悉Docker、Kubernetes、CI/CD，有分布式系统设计经验",
        evidence_items=[],
        jd_text="需要3年Python开发经验",
    )
    assert result["tier"] in ("High Confidence", "Proceed with Caution", "Suspicious")
    assert "signals_table" in result
    print(f"✓ LegitimacyAssessment OK — tier: {result['tier']}")


def test_legitimacy_suspicious():
    result = _build_legitimacy_assessment(
        all_text="this job has expired. Position has been filled.",
        evidence_items=[{"snippet": "公司裁员50%", "source_class": "company_profile"}],
        jd_text="short",
    )
    assert result["tier"] == "Suspicious"
    print("✓ LegitimacyAssessment (Suspicious) OK")


if __name__ == "__main__":
    test_matching_normalize()
    test_matching_recommendation()
    test_matching_engine_full()
    test_matching_engine_no_resume()
    test_matching_engine_empty_snapshot()
    test_legitimacy_assessment()
    test_legitimacy_suspicious()
    print("\n=== Phase 3 connectivity: ALL TESTS PASSED ===")
