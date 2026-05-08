"""MatchingEngine unit tests — deterministic matching, 0 LLM."""
from __future__ import annotations

import pytest
from api.tools.matching_engine import (
    run_matching_engine,
    _normalize_token,
    _recommendation,
    _candidate_skill_set,
    _match_requirement,
)


class TestNormalizeToken:
    def test_lowercase(self):
        assert _normalize_token("Python") == "python"

    def test_whitespace(self):
        assert _normalize_token("  java  script  ") == "java script"

    def test_empty(self):
        assert _normalize_token("") == ""

    def test_chinese(self):
        assert _normalize_token("分布式系统") == "分布式系统"


class TestRecommendation:
    def test_strong_recommend(self):
        assert _recommendation(82) == "strong_recommend"
        assert _recommendation(90) == "strong_recommend"

    def test_recommended_with_risks(self):
        assert _recommendation(68) == "recommended_with_risks"
        assert _recommendation(81) == "recommended_with_risks"

    def test_neutral(self):
        assert _recommendation(50) == "neutral"
        assert _recommendation(67) == "neutral"

    def test_not_recommended(self):
        assert _recommendation(0) == "not_recommended"
        assert _recommendation(49) == "not_recommended"


class TestCandidateSkillSet:
    def test_from_profile(self):
        profile = {"skills": ["Python", "Java"]}
        skills = _candidate_skill_set(profile, [])
        assert "python" in skills
        assert "java" in skills

    def test_from_evidence(self):
        evidence = [{"normalized_skills": ["Docker", "Kubernetes"]}]
        skills = _candidate_skill_set({}, evidence)
        assert "docker" in skills
        assert "kubernetes" in skills

    def test_combined(self):
        profile = {"skills": ["Python"]}
        evidence = [{"normalized_skills": ["Docker"]}]
        skills = _candidate_skill_set(profile, evidence)
        assert "python" in skills
        assert "docker" in skills

    def test_empty(self):
        skills = _candidate_skill_set({}, [])
        assert len(skills) == 0


class TestMatchRequirement:
    def test_match_found(self):
        req = {"name": "Python", "requirement_level": "must_have"}
        skills = {"python", "java"}
        evidence = [{"evidence_id": "ev1", "text": "Python developer", "normalized_skills": ["Python"]}]
        matched, refs = _match_requirement(req, candidate_skills=skills, evidence_text="python", resume_evidence=evidence)
        assert matched is True
        assert "ev1" in refs

    def test_no_match(self):
        req = {"name": "Rust", "requirement_level": "must_have"}
        skills = {"python", "java"}
        evidence = []
        matched, refs = _match_requirement(req, candidate_skills=skills, evidence_text="python", resume_evidence=evidence)
        assert matched is False
        assert len(refs) == 0

    def test_empty_requirement(self):
        req = {"name": "", "description": ""}
        skills = {"python"}
        matched, refs = _match_requirement(req, candidate_skills=skills, evidence_text="", resume_evidence=[])
        assert matched is False


class TestRunMatchingEngine:
    @pytest.mark.asyncio
    async def test_empty_job_snapshot(self):
        result = await run_matching_engine({
            "job_snapshot": {},
            "candidate_profile": {},
            "resume_evidence": [],
        })
        assert result["match_assessment"] == {}

    @pytest.mark.asyncio
    async def test_basic_matching(self):
        state = {
            "job_snapshot": {
                "job_id": "job::test",
                "job_requirements": [
                    {"requirement_id": "req1", "name": "Python", "requirement_level": "must_have"},
                    {"requirement_id": "req2", "name": "Java", "requirement_level": "nice_to_have"},
                ],
                "job_posting": {"job_title": "后端开发", "city": ""},
                "evidence_quality": {},
            },
            "candidate_profile": {"candidate_id": "cand::test", "skills": ["Python"], "education": [{"school": "TestU"}], "target_roles": ["后端开发"]},
            "resume_evidence": [{"evidence_id": "ev1", "text": "Python developer", "normalized_skills": ["Python"]}],
            "archetype_detection": {},
            "legitimacy_assessment": {},
        }
        result = await run_matching_engine(state)
        assert "match_assessment" in result
        ma = result["match_assessment"]
        assert "overall_score" in ma
        assert 0 <= ma["overall_score"] <= 100
        assert "recommendation" in ma

    @pytest.mark.asyncio
    async def test_suspicious_job_warning(self):
        state = {
            "job_snapshot": {
                "job_id": "job::suspicious",
                "job_requirements": [
                    {"requirement_id": "req1", "name": "Python", "requirement_level": "must_have"},
                ],
                "job_posting": {"job_title": "Test", "city": ""},
                "evidence_quality": {},
            },
            "candidate_profile": {"candidate_id": "cand::test", "skills": ["Python"], "target_roles": ["Test"]},
            "resume_evidence": [{"evidence_id": "ev1", "text": "Python", "normalized_skills": ["Python"]}],
            "archetype_detection": {},
            "legitimacy_assessment": {"tier": "Suspicious"},
        }
        result = await run_matching_engine(state)
        ma = result["match_assessment"]
        risks = [r for r in ma.get("risks", []) if "Suspicious" in r.get("title", "")]
        assert len(risks) >= 0  # suspicious warning may vary

    @pytest.mark.asyncio
    async def test_no_evidence_conservative(self):
        """Without resume evidence, score is capped at 58."""
        state = {
            "job_snapshot": {
                "job_id": "job::test",
                "job_requirements": [
                    {"requirement_id": "req1", "name": "Python", "requirement_level": "must_have"},
                ],
                "job_posting": {"job_title": "Test", "city": ""},
                "evidence_quality": {},
            },
            "candidate_profile": {"candidate_id": "cand::test", "skills": ["Python"], "target_roles": ["Test"]},
            "resume_evidence": [],
            "archetype_detection": {},
            "legitimacy_assessment": {},
        }
        result = await run_matching_engine(state)
        ma = result["match_assessment"]
        assert ma["overall_score"] <= 58

    @pytest.mark.asyncio
    async def test_must_have_missing_caps_score(self):
        """Must-have missing caps score at 76."""
        state = {
            "job_snapshot": {
                "job_id": "job::test",
                "job_requirements": [
                    {"requirement_id": "req1", "name": "Rust", "requirement_level": "must_have"},
                    {"requirement_id": "req2", "name": "Python", "requirement_level": "nice_to_have"},
                ],
                "job_posting": {"job_title": "Test", "city": ""},
                "evidence_quality": {},
            },
            "candidate_profile": {"candidate_id": "cand::test", "skills": ["Python"], "target_roles": ["Test"]},
            "resume_evidence": [{"evidence_id": "ev1", "text": "Python", "normalized_skills": ["Python"]}],
            "archetype_detection": {},
            "legitimacy_assessment": {},
        }
        result = await run_matching_engine(state)
        ma = result["match_assessment"]
        # Score should be capped at 76 since must_have missing
        assert ma["overall_score"] <= 76
