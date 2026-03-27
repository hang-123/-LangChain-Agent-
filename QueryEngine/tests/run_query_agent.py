"""
Smoke test for QueryAgent.

Usage:
  python QueryEngine/tests/run_query_agent.py --query "话题" [--save]
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from QueryEngine.agent import QueryAgent


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run QueryAgent end-to-end.")
    parser.add_argument("--query", default="近期中国经济热点", help="User query text.")
    parser.add_argument("--save", action="store_true", help="Save markdown/state files.")
    args = parser.parse_args()

    agent = QueryAgent()
    result = agent.run(args.query, save_report=args.save)

    print("\n=== QueryAgent Smoke Test ===")
    print(f"Query: {args.query}")
    print(f"Paragraphs: {len(result.state.paragraphs)}")
    print(f"Report snippet:\n{result.report_markdown[:500]}...")
    if args.save and result.report_file:
        print(f"[Saved report] {result.report_file}")
    if args.save and result.state_file:
        print(f"[Saved state] {result.state_file}")


if __name__ == "__main__":
    main()

