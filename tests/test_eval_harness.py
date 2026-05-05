from __future__ import annotations

from api.evals.harness import ResearchCase, score_case_result, summarize_eval_suite


def test_score_case_result_passes_when_thresholds_met():
    case = ResearchCase(
        case_id="case-1",
        query="test",
        expected_intent="general",
        minimum_evidence_count=4,
        company_assertions=["字节"],
        allow_conservative=True,
    )
    final_state = {
        "run_id": "run-123",
        "intent": "general",
        "quality_mode": "normal",
        "root_cause": "retrieval",
        "run_manifest": {
            "prompt_version": "prompt-v1",
            "policy_version": "policy-v1",
            "code_version": "code-v1",
            "model_name": "qwen-plus",
        },
        "report_content": (
            "# 专属求职研究报告\n\n"
            "## 一、岗位与公司概览\n字节 后端\n\n"
            "## 二、岗位能力要求拆解\n字节 团队要求\n\n"
            "## 三、真实面经与面试官追问\n你做过什么？\n\n"
            "## 四、候选人风险点与准备建议\n如果项目映射不清会失分。\n\n"
            "## 五、一周行动清单\nDay 1\n\n"
            "## 附：证据来源\nhttps://a.com\nhttps://b.com\n字节"
        ),
        "quality_summary": {"root_cause": "retrieval"},
        "insights": {
            "evidence_count": 5,
            "company_specific_requirements": ["字节 团队要求"],
            "action_plan_source_coverage": 80,
            "candidate_risks": ["项目映射风险"],
            "interviewer_questions": ["你做过什么？"],
            "action_plan_items": [{"day": 1}],
            "quality_metrics": {"claim_evidence_coverage": 75},
            "company_specific_source_count": 3,
        },
    }
    result = score_case_result(case, final_state)
    assert result.passed is True
    assert result.score == 100
    assert result.node_scores.retrieval == 100
    assert result.metadata.prompt_version == "prompt-v1"


def test_summarize_eval_suite_counts_root_causes():
    summary = summarize_eval_suite(
        "suite",
        [
            score_case_result(
                ResearchCase(case_id="a", query="q", expected_intent="general"),
                {
                    "intent": "general",
                    "quality_mode": "normal",
                    "root_cause": "retrieval",
                    "report_content": (
                        "# 专属求职研究报告\n\n"
                        "## 一、岗位与公司概览\n\n"
                        "## 二、岗位能力要求拆解\n\n"
                        "## 三、真实面经与面试官追问\n?\n\n"
                        "## 四、候选人风险点与准备建议\n风险\n\n"
                        "## 五、一周行动清单\nDay 1\n\n"
                        "## 附：证据来源\nhttps://a.com\nhttps://b.com"
                    ),
                    "quality_summary": {"root_cause": "retrieval"},
                    "insights": {
                        "evidence_count": 4,
                        "company_specific_requirements": [],
                        "action_plan_source_coverage": 50,
                        "candidate_risks": ["风险"],
                        "interviewer_questions": ["问题"],
                        "action_plan_items": [{"day": 1}],
                        "quality_metrics": {"claim_evidence_coverage": 50},
                        "company_specific_source_count": 2,
                    },
                },
            )
        ],
    )
    assert summary.total_cases == 1
    assert summary.root_cause_breakdown["retrieval"] == 1
