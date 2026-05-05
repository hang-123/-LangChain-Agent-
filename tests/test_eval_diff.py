from __future__ import annotations

from api.core.contracts import EvalSuiteSummary
from api.evals.diffing import build_eval_diff, render_eval_diff_markdown


def test_build_eval_diff_reports_regressions_and_improvements():
    baseline = EvalSuiteSummary.model_validate(
        {
            "suite_name": "baseline",
            "total_cases": 2,
            "passed_cases": 2,
            "failed_cases": 0,
            "average_score": 90.0,
            "root_cause_breakdown": {"retrieval": 1},
            "case_results": [
                {
                    "case_id": "a",
                    "passed": True,
                    "score": 100,
                    "expected_intent": "general",
                    "actual_intent": "general",
                    "failures": [],
                    "root_cause": "retrieval",
                    "quality_mode": "normal",
                    "metrics": {},
                    "node_scores": {},
                    "metadata": {"run_id": "run-a"},
                },
                {
                    "case_id": "b",
                    "passed": True,
                    "score": 80,
                    "expected_intent": "general",
                    "actual_intent": "general",
                    "failures": [],
                    "root_cause": "synthesis",
                    "quality_mode": "normal",
                    "metrics": {},
                    "node_scores": {},
                    "metadata": {"run_id": "run-b"},
                },
            ],
        }
    )
    current = EvalSuiteSummary.model_validate(
        {
            "suite_name": "current",
            "total_cases": 2,
            "passed_cases": 1,
            "failed_cases": 1,
            "average_score": 82.0,
            "root_cause_breakdown": {"retrieval": 2},
            "case_results": [
                {
                    "case_id": "a",
                    "passed": False,
                    "score": 70,
                    "expected_intent": "general",
                    "actual_intent": "general",
                    "failures": ["missing evidence"],
                    "root_cause": "retrieval",
                    "quality_mode": "normal",
                    "metrics": {},
                    "node_scores": {},
                    "metadata": {"run_id": "run-a2"},
                },
                {
                    "case_id": "b",
                    "passed": True,
                    "score": 94,
                    "expected_intent": "general",
                    "actual_intent": "general",
                    "failures": [],
                    "root_cause": "retrieval",
                    "quality_mode": "normal",
                    "metrics": {},
                    "node_scores": {},
                    "metadata": {"run_id": "run-b2"},
                },
            ],
        }
    )

    diff = build_eval_diff(baseline, current)
    markdown = render_eval_diff_markdown(diff)

    assert diff["average_score_delta"] == -8.0
    assert diff["regressions"][0]["case_id"] == "a"
    assert diff["improvements"][0]["case_id"] == "b"
    assert "Top Regressions" in markdown
