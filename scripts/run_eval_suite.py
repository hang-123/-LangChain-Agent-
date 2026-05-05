from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from api.core.executor import ResearchExecutionSession
from api.core.graph import build_career_research_graph
from api.core.persistence import build_repository
from api.core.policy_loader import load_policy
from api.evals.harness import load_research_cases, score_case_result, summarize_eval_suite


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BettaFish regression eval suite.")
    parser.add_argument("--case-id", action="append", dest="case_ids", default=[], help="Specific case id to run.")
    parser.add_argument("--output", default="logs/eval_suite_latest.json", help="Output path for suite results.")
    args = parser.parse_args()

    graph = build_career_research_graph()
    policy = load_policy()
    repository = build_repository(policy)
    cases = [case for case in load_research_cases() if not args.case_ids or case.case_id in args.case_ids]
    results = []
    for case in cases:
        repository.save_research_case(case)
        session = ResearchExecutionSession(graph, case.query, research_case=case.model_dump())
        async for _ in session.stream_events():
            pass
        result = score_case_result(case, session.state)
        repository.save_eval_result(result)
        results.append(result)

    summary = summarize_eval_suite(policy.eval_policy.suite_name, results)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps(summary.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
