"""Phase 4 connectivity test — ResumeTailor, ResumeParser, InterviewCoach, OfferEvaluator."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.tools.resume_tailor import run_resume_tailor
from api.tools.resume_parser import run_resume_parser, _compute_profile_completeness, _extract_raw_text
from api.tools.offer_evaluator import run_offer_evaluator


# ── ResumeTailor ──

def test_resume_tailor_empty():
    state = {"candidate_profile": {}, "resume_evidence": [], "job_snapshot": {}, "match_assessment": {}}
    result = asyncio.run(run_resume_tailor(state))
    assert result["tailor_plan"] == {} or result["resume_version"] == {}
    print("✓ ResumeTailor (empty) OK — returns empty artifacts")


def test_resume_tailor_full():
    state = {
        "candidate_profile": {"candidate_id": "c1", "skills": ["Python", "Java"]},
        "resume_evidence": [
            {"evidence_id": "e1", "section": "projects", "text": "使用Python开发后端服务", "normalized_skills": ["Python"]},
        ],
        "job_snapshot": {
            "job_id": "job_001",
            "job_requirements": [
                {"requirement_id": "r1", "name": "Python", "requirement_level": "must_have"},
            ],
            "job_posting": {"job_title": "后端开发"},
        },
        "match_assessment": {"assessment_id": "m1", "overall_score": 75},
    }
    result = asyncio.run(run_resume_tailor(state))
    assert "tailor_plan" in result
    assert "resume_version" in result
    assert "fact_check_report" in result
    tp = result["tailor_plan"]
    if tp:
        assert "keyword_coverage" in tp
    print("✓ ResumeTailor (full) OK")


# ── ResumeParser ──

def test_extract_raw_text():
    text = _extract_raw_text("txt", "this is test resume content", None)
    assert text == "this is test resume content"
    text2 = _extract_raw_text("txt", "", "this is bytes resume content".encode())
    assert "resume" in text2
    print("✓ ResumeParser extract OK")


def test_completeness():
    cp = {"name": "测试", "skills": ["Java"], "education": [{"school": "大学"}]}
    ev = [{"evidence_id": "e1"}, {"evidence_id": "e2"}, {"evidence_id": "e3"}]
    score = _compute_profile_completeness(cp, ev)
    assert score > 0.5
    print(f"✓ ResumeParser completeness OK — score: {score}")


# ── OfferEvaluator ──

def test_offer_evaluator_empty():
    state = {"offers": []}
    result = asyncio.run(run_offer_evaluator(state))
    assert result["offer_evaluation"] == {}
    print("✓ OfferEvaluator (empty) OK")


def test_offer_evaluator_full():
    state = {
        "offers": [
            {"offer_id": "offer_a", "company": "字节跳动", "north_star_alignment": 85, "cv_match": 78,
             "seniority_level": 70, "compensation": 65, "growth_trajectory": 80, "remote_quality": 90,
             "company_reputation": 75, "tech_stack_modernity": 85, "speed_to_offer": 60, "cultural_signals": 70},
            {"offer_id": "offer_b", "company": "腾讯", "north_star_alignment": 70, "cv_match": 85,
             "seniority_level": 80, "compensation": 85, "growth_trajectory": 65, "remote_quality": 50,
             "company_reputation": 85, "tech_stack_modernity": 70, "speed_to_offer": 90, "cultural_signals": 80},
        ],
    }
    result = asyncio.run(run_offer_evaluator(state))
    assert "offer_comparison" in result
    comp = result["offer_comparison"]
    assert "weighted_totals" in comp
    assert "ranking" in comp
    assert len(comp["ranking"]) == 2
    print(f"✓ OfferEvaluator (full) OK — ranking: {comp['ranking']}, recommendation: {comp['recommendation'][:80]}")


if __name__ == "__main__":
    test_resume_tailor_empty()
    test_resume_tailor_full()
    test_extract_raw_text()
    test_completeness()
    test_offer_evaluator_empty()
    test_offer_evaluator_full()
    print("\n=== Phase 4 connectivity: ALL TESTS PASSED ===")
