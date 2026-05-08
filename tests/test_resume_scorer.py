from __future__ import annotations

from api.core.contracts import ResearchCase
from api.evals.harness import _score_resume, score_case_result


def _case(ground_truth: dict) -> ResearchCase:
    return ResearchCase(
        case_id="test-resume",
        query="测试简历",
        expected_intent="general",
        resume_ground_truth=ground_truth,
    )


def test_score_resume_factual_passes():
    gt = {
        "fact_check_status": "passed",
        "min_keyword_covered": 1,
        "min_section_actions": 1,
        "forbidden_phrases": ["精通", "负责过1000万DAU"],
        "require_keywords": ["Java", "后端"],
    }
    state = {
        "resume_version": {
            "resume_version_id": "rv_1",
            "summary_text": "具备Java和Spring Boot项目经验的后端开发候选人",
            "project_bullets": ["使用 Spring Boot 开发电商订单系统"],
            "keyword_insertions": ["Java", "Spring Boot"],
            "fact_check_status": "passed",
        },
        "fact_check_report": {
            "status": "passed",
            "blocked_claims": [],
        },
        "tailor_plan": {
            "keyword_coverage": {
                "covered": ["Java", "Spring Boot"],
                "missing": [],
            },
            "section_actions": [
                {"section": "projects", "action": "rewrite", "instruction": "强调后端开发经验"},
            ],
        },
    }
    score, failures = _score_resume(_case(gt), state)
    assert score == 100, f"Expected 100, got {score}: {failures}"
    assert not failures


def test_score_resume_fabrication_zeroes():
    gt = {
        "fact_check_status": "passed",
        "forbidden_phrases": ["精通"],
        "min_keyword_covered": 0,
        "min_section_actions": 0,
        "require_keywords": [],
    }
    state = {
        "resume_version": {
            "resume_version_id": "rv_1",
            "summary_text": "精通分布式系统设计，负责过1000万DAU项目",
            "project_bullets": [],
            "keyword_insertions": [],
            "fact_check_status": "passed",
        },
        "fact_check_report": {"status": "passed"},
        "tailor_plan": {
            "keyword_coverage": {"covered": [], "missing": []},
            "section_actions": [],
        },
    }
    score, failures = _score_resume(_case(gt), state)
    assert score == 0, f"Expected 0 for fabrication, got {score}: {failures}"


def test_score_resume_rejected_status_zeroes():
    gt = {
        "fact_check_status": "passed",
        "forbidden_phrases": [],
        "min_keyword_covered": 0,
        "min_section_actions": 0,
        "require_keywords": [],
    }
    state = {
        "resume_version": {
            "resume_version_id": "rv_1",
            "summary_text": "some text",
            "project_bullets": [],
            "keyword_insertions": [],
            "fact_check_status": "rejected",
        },
        "fact_check_report": {"status": "rejected", "blocked_claims": ["虚构指标"]},
        "tailor_plan": {"keyword_coverage": {}, "section_actions": []},
    }
    score, failures = _score_resume(_case(gt), state)
    assert score == 0, f"Expected 0 for rejected, got {score}: {failures}"


def test_score_resume_missing_keywords_penalized():
    gt = {
        "fact_check_status": "passed",
        "min_keyword_covered": 2,
        "min_section_actions": 1,
        "forbidden_phrases": [],
        "require_keywords": ["Java", "Kafka", "系统设计"],
    }
    state = {
        "resume_version": {
            "resume_version_id": "rv_1",
            "summary_text": "后端候选人",
            "project_bullets": [],
            "keyword_insertions": [],
            "fact_check_status": "passed",
        },
        "fact_check_report": {"status": "passed"},
        "tailor_plan": {
            "keyword_coverage": {"covered": [], "missing": ["Java", "Kafka"]},
            "section_actions": [
                {"section": "skills", "action": "prioritize", "instruction": "add skills"},
            ],
        },
    }
    score, failures = _score_resume(_case(gt), state)
    assert score < 100
    assert any("keyword_coverage" in f for f in failures)


def test_score_resume_no_ground_truth_returns_perfect():
    state = {
        "resume_version": {
            "resume_version_id": "rv_x",
            "summary_text": "bad text 精通一切",
            "project_bullets": [],
            "keyword_insertions": [],
            "fact_check_status": "rejected",
        },
        "fact_check_report": {"status": "rejected"},
        "tailor_plan": {},
    }
    score, failures = _score_resume(
        ResearchCase(case_id="x", query="q", expected_intent="general"),
        state,
    )
    assert score == 100


def test_score_resume_downgraded_partial_penalty():
    gt = {
        "fact_check_status": "passed",
        "min_keyword_covered": 0,
        "min_section_actions": 0,
        "forbidden_phrases": [],
        "require_keywords": [],
    }
    state = {
        "resume_version": {
            "resume_version_id": "rv_1",
            "summary_text": "text",
            "project_bullets": [],
            "keyword_insertions": [],
            "fact_check_status": "downgraded",
        },
        "fact_check_report": {"status": "downgraded"},
        "tailor_plan": {"keyword_coverage": {}, "section_actions": []},
    }
    score, failures = _score_resume(_case(gt), state)
    assert 50 < score < 100


def test_full_case_evaluation_includes_resume():
    case = ResearchCase(
        case_id="full-resume",
        query="test",
        expected_intent="general",
        minimum_evidence_count=2,
        resume_ground_truth={
            "fact_check_status": "passed",
            "min_keyword_covered": 1,
            "min_section_actions": 1,
            "forbidden_phrases": [],
            "require_keywords": ["Java"],
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
        "resume_version": {
            "resume_version_id": "rv_1",
            "summary_text": "具备Java项目经验的后端候选人",
            "project_bullets": ["Java电商项目"],
            "keyword_insertions": ["Java"],
            "fact_check_status": "passed",
        },
        "fact_check_report": {"status": "passed"},
        "tailor_plan": {
            "keyword_coverage": {"covered": ["Java"], "missing": []},
            "section_actions": [{"section": "projects", "action": "rewrite", "instruction": "do X"}],
        },
    }
    result = score_case_result(case, final_state)
    assert result.node_scores.resume > 0
    assert result.passed is True
