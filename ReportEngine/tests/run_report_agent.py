"""
Smoke test for ReportAgent.

Usage:
  python ReportEngine/tests/run_report_agent.py --query "话题" \
      --source external=reports/sample_external.md \
      --source media=reports/sample_media.md \
      [--save]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from ReportEngine.agent import ReportAgent


def _parse_source(spec: str) -> Tuple[str, str]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError("source must be label=path")
    label, path = spec.split("=", 1)
    text = Path(path).read_text(encoding="utf-8")
    return label.strip(), text


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run ReportAgent with supplied sources.")
    parser.add_argument("--query", default="公司声誉洞察", help="Main report topic.")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="label=path",
        help="Label and file path for a source markdown snippet.",
    )
    parser.add_argument("--save", action="store_true", help="Persist final markdown.")
    args = parser.parse_args()

    if args.source:
        sources: List[Tuple[str, str]] = [_parse_source(spec) for spec in args.source]
    else:
        sources = [
            ("External Web Research", "（示例）外网搜索结果：......"),
            ("Internal Insights", "（示例）内部数据库洞察：......"),
        ]

    agent = ReportAgent()
    result = agent.run(args.query, sources, save_report=args.save)

    print("\n=== ReportAgent Smoke Test ===")
    print(f"Query: {args.query}")
    print(f"Sections planned: {len(result.state.sections)}")
    print(result.markdown[:500] + "...")
    if args.save and result.report_file:
        print(f"[Saved final report] {result.report_file}")


if __name__ == "__main__":
    main()

