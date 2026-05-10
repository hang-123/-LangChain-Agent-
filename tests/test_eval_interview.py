from __future__ import annotations

from api.evals.harness import _score_interview


def test_score_interview_perfect_pack():
    case = {
        "interview_ground_truth": {
            "min_behavioral_questions": 2,
            "min_technical_questions": 1,
            "min_project_deep_dive": 1,
            "required_risk_questions": 1,
            "expected_role_keywords": ["后端"],
            "forbidden_phrases": [],
        }
    }
    state = {
        "prep_pack": {
            "behavioral_questions": [
                {"question": "说说你的项目经验", "category": "behavioral", "evidence_refs": ["ev1"]},
                {"question": "如何处理冲突", "category": "behavioral", "evidence_refs": ["ev2"]},
            ],
            "technical_questions": [
                {"question": "Python GIL 后端开发相关问题", "category": "technical", "evidence_refs": ["ev3"]},
            ],
            "project_deep_dive": [
                {"question": "详细介绍你的后端项目架构", "category": "project_deep_dive", "evidence_refs": ["ev4"]},
            ],
            "risk_questions": [
                {"question": "你的技术栈和后端岗位有什么差距", "category": "project_deep_dive"},
            ],
            "practice_advice": ["多做mock interview", "复习系统设计"],
        }
    }
    score = _score_interview(case, state)
    assert score >= 90, f"Expected >= 90, got {score}"


def test_score_interview_missing_deep_dive():
    case = {
        "interview_ground_truth": {
            "min_behavioral_questions": 2,
            "min_technical_questions": 1,
            "min_project_deep_dive": 1,
            "required_risk_questions": 0,
            "expected_role_keywords": [],
            "forbidden_phrases": [],
        }
    }
    state = {
        "prep_pack": {
            "behavioral_questions": [{"question": "Q1", "evidence_refs": []}],
            "technical_questions": [{"question": "Q1", "evidence_refs": []}],
            "project_deep_dive": [],
            "risk_questions": [],
            "practice_advice": [],
        }
    }
    score = _score_interview(case, state)
    assert score < 85, f"Expected penalty for missing deep dive, got {score}"


def test_score_interview_empty_pack():
    case = {
        "interview_ground_truth": {
            "min_behavioral_questions": 1,
            "min_technical_questions": 1,
            "min_project_deep_dive": 1,
            "required_risk_questions": 0,
            "expected_role_keywords": [],
            "forbidden_phrases": [],
        }
    }
    state = {"prep_pack": {}}
    score = _score_interview(case, state)
    assert score == 0, f"Expected 0 for empty pack, got {score}"
