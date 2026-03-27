"""
Smoke test for InsightAgent.

Usage:
  python InsightEngine/tests/run_insight_agent.py --query "话题"
"""

from __future__ import annotations

import argparse

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from InsightEngine.agent import InsightAgent


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run InsightAgent pipeline.")
    parser.add_argument("--query", default="企业品牌口碑", help="User query or topic.")
    args = parser.parse_args()

    agent = InsightAgent()
    state = agent.run(args.query)

    print("\n=== InsightAgent Smoke Test ===")
    print(f"Question: {state.question}")
    print(f"Keywords: {state.keywords}")
    if state.markdown_report:
        print(f"Markdown length: {len(state.markdown_report)}")
        print(state.markdown_report[:500] + "...")
    else:
        print("No markdown report produced.")


if __name__ == "__main__":
    main()

