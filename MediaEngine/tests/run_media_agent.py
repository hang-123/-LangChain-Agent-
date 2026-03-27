"""
Smoke test for MediaAgent.

Usage:
  python MediaEngine/tests/run_media_agent.py --query "话题" [--save]
"""

from __future__ import annotations

import argparse

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from MediaEngine.agent import MediaAgent


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run MediaAgent multimedia brief.")
    parser.add_argument("--query", default="AI 安全 舆情", help="Topic to analyze.")
    parser.add_argument("--save", action="store_true", help="Save markdown to disk.")
    args = parser.parse_args()

    agent = MediaAgent()
    result = agent.run(args.query, save_report=args.save)

    print("\n=== MediaAgent Smoke Test ===")
    print(f"Query: {args.query}")
    print(f"Articles collected: {len(result.state.articles)}")
    print(f"Visuals collected: {len(result.state.visuals)}")
    print(result.report_markdown[:400] + "...")
    if args.save and result.report_file:
        print(f"[Saved media brief] {result.report_file}")


if __name__ == "__main__":
    main()

