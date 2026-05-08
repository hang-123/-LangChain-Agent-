from __future__ import annotations

from api.core.contracts import ResearchCase
from api.evals.harness import _score_matching, score_case_result


def _case(ground_truth: dict) -> ResearchCase:
    return ResearchCase(
        case_id="test-match",
        query="测试匹配",
        expected_intent="general",
        match_ground_truth=ground_truth,
    )


def test_score_matching_strong_fit_passes():
    gt = {
        "expected_recommendation": "strong_recommend",
        "min_overall_score": 75,
        "min_must_have_match_ratio": 0.4,
        "min_strengths": 1,
        "max_gaps": 3,
    }
    state = {
        "match_assessment": {
            "overall_score": 82,
            "recommendation": "strong_recommend",
            "strengths": [
                {"title": "已覆盖 Java 要求", "evidence_refs": ["ev_001"]},
                {"title": "已覆盖 微服务 要求", "evidence_refs": ["ev_002"]},
            ],
            "gaps": [
                {"title": "缺少 Go 证据", "severity": "medium"},
            ],
            "risks": [],
            "dimension_scores": {"skills": 80},
        },
    }
    score, failures = _score_matching(_case(gt), state)
    assert score == 100, f"Expected 100, got {score}: {failures}"
    assert not failures


def test_score_matching_wrong_recommendation_is_penalized():
    gt = {
        "expected_recommendation": "strong_recommend",
        "min_overall_score": 70,
        "min_must_have_match_ratio": 0.3,
        "min_strengths": 0,
        "max_gaps": 10,
    }
    state = {
        "match_assessment": {
            "overall_score": 45,
            "recommendation": "not_recommended",
            "strengths": [],
            "gaps": [{"title": "缺 Java"}, {"title": "缺 Go"}, {"title": "缺 微服务"}],
            "risks": [],
            "dimension_scores": {"skills": 30},
        },
    }
    score, failures = _score_matching(_case(gt), state)
    assert score < 100
    assert any("recommendation_accuracy" in f for f in failures)


def test_score_matching_missing_assessment_returns_zero():
    gt = {"expected_recommendation": "strong_recommend"}
    score, failures = _score_matching(_case(gt), {})
    assert score == 0
    assert any("missing" in f for f in failures)


def test_score_matching_no_ground_truth_returns_perfect():
    state = {
        "match_assessment": {
            "overall_score": 10,
            "recommendation": "not_recommended",
            "strengths": [],
            "gaps": [],
            "risks": [],
            "dimension_scores": {},
        },
    }
    score, failures = _score_matching(
        ResearchCase(case_id="x", query="q", expected_intent="general"),
        state,
    )
    assert score == 100


def test_score_matching_low_overall_score_penalized():
    gt = {
        "expected_recommendation": "recommended_with_risks",
        "min_overall_score": 65,
        "min_must_have_match_ratio": 0.3,
        "min_strengths": 0,
        "max_gaps": 10,
    }
    state = {
        "match_assessment": {
            "overall_score": 50,
            "recommendation": "recommended_with_risks",
            "strengths": [{"title": "ok", "evidence_refs": ["x"]}],
            "gaps": [{"title": "gap"}],
            "risks": [],
            "dimension_scores": {"skills": 50},
        },
    }
    score, failures = _score_matching(_case(gt), state)
    assert any("score_alignment" in f for f in failures)
    assert score < 100


def test_full_case_evaluation_includes_matching():
    case = ResearchCase(
        case_id="full-match",
        query="test",
        expected_intent="general",
        minimum_evidence_count=2,
        match_ground_truth={
            "expected_recommendation": "strong_recommend",
            "min_overall_score": 70,
            "min_must_have_match_ratio": 0.3,
            "min_strengths": 0,
            "max_gaps": 10,
        },
    )
    final_state = {
        "run_id": "run-1",
        "intent": "general",
        "quality_mode": "normal",
        "root_cause": "retrieval",
        "run_manifest": {"prompt_version": "v1", "policy_version": "v1", "code_version": "v1", "model_name": "x"},
        "report_content": "# 专属求职研究报告\n\n## 一、岗位与公司概览\n\n## 二、岗位能力要求拆解\n\n## 三、真实面经与面试官追问\n?\n\n## 四、候选人风险点与准备建议\n风险\n\n## 五、一周行动清单\nDay 1\n\n## 附：证据来源\nhttps://a.com\nhttps://b.com",
        "quality_summary": {},
        "insights": {
            "evidence_count": 5,
            "company_specific_source_count": 3,
            "action_plan_source_coverage": 70,
            "candidate_risks": ["风险"],
            "interviewer_questions": ["问题"],
            "action_plan_items": [{"day": 1}],
            "quality_metrics": {"claim_evidence_coverage": 70},
        },
        "match_assessment": {
            "overall_score": 80,
            "recommendation": "strong_recommend",
            "strengths": [{"title": "s1", "evidence_refs": ["e1"]}],
            "gaps": [{"title": "g1"}],
            "risks": [],
            "dimension_scores": {"skills": 80},
        },
    }
    result = score_case_result(case, final_state)
    assert result.node_scores.matching > 0
    assert result.passed is True
