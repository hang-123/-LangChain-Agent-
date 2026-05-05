from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.core.executor import ResearchExecutionSession
from api.core.graph import build_career_research_graph
from api.core.persistence import build_repository
from api.core.policy_loader import load_policy
from api.evals.harness import CaseEvaluation, load_research_cases, score_case_result, summarize_eval_suite


DEFAULT_SMOKE_CASE_IDS = [
    "general_bytedance_backend_intern",
    "tech_meituan_backend",
]


def _require_env(name: str) -> None:
    if os.getenv(name, "").strip():
        return
    raise SystemExit(f"Missing required environment variable for CI eval: {name}")


def _render_markdown(summary) -> str:
    lines = [
        "# CI Eval Report",
        "",
        f"- Suite: `{summary.suite_name}`",
        f"- Total cases: `{summary.total_cases}`",
        f"- Passed cases: `{summary.passed_cases}`",
        f"- Failed cases: `{summary.failed_cases}`",
        f"- Average score: `{summary.average_score}`",
        "",
        "## Node Scores",
        "",
        "| Case ID | Score | Retrieval | Attribution | Insight | Report Compliance | Passed |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in summary.case_results:
        lines.append(
            "| {case_id} | {score} | {retrieval} | {attribution} | {insight} | {report_compliance} | {passed} |".format(
                case_id=result.case_id,
                score=result.score,
                retrieval=result.node_scores.retrieval,
                attribution=result.node_scores.attribution,
                insight=result.node_scores.insight,
                report_compliance=result.node_scores.report_compliance,
                passed="yes" if result.passed else "no",
            )
        )

    failing = [result for result in summary.case_results if not result.passed][:5]
    lines.extend(["", "## Top Failed Cases", ""])
    if not failing:
        lines.append("- None")
    else:
        for result in failing:
            failure_text = "; ".join(result.failures[:5]) if result.failures else "Unknown failure"
            lines.append(f"- `{result.case_id}`: {failure_text}")

    return "\n".join(lines) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run smoke evals for CI and emit gate artifacts.")
    parser.add_argument("--case-id", action="append", dest="case_ids", default=[], help="Specific case id to run.")
    parser.add_argument("--output-json", default="logs/ci/eval_results.json", help="Path to eval summary JSON artifact.")
    parser.add_argument("--output-md", default="logs/ci/eval_report.md", help="Path to markdown report artifact.")
    parser.add_argument("--min-score", type=float, default=75.0, help="Minimum average score required to pass CI.")
    args = parser.parse_args()

    _require_env("QUERY_ENGINE_API_KEY")
    _require_env("TAVILY_API_KEY")

    selected_case_ids = args.case_ids or list(DEFAULT_SMOKE_CASE_IDS)
    graph = build_career_research_graph()
    policy = load_policy()
    repository = build_repository(policy)
    cases = [case for case in load_research_cases() if case.case_id in selected_case_ids]
    if not cases:
        raise SystemExit("No eval cases selected for CI.")

    results: list[CaseEvaluation] = []
    for case in cases:
        repository.save_research_case(case)
        session = ResearchExecutionSession(graph, case.query, research_case=case.model_dump())
        async for _ in session.stream_events():
            pass
        result = score_case_result(case, session.state)
        repository.save_eval_result(result)
        results.append(result)

    summary = summarize_eval_suite(f"{policy.eval_policy.suite_name}_smoke", results)
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(summary), encoding="utf-8")

    print(json.dumps(summary.model_dump(), ensure_ascii=False, indent=2))
    if float(summary.average_score) < float(args.min_score):
        raise SystemExit(
            f"CI eval failed: average_score={summary.average_score} is below threshold={args.min_score}"
        )


if __name__ == "__main__":
    asyncio.run(main())
