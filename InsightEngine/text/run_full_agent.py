"""
End-to-end runner: QueryEngine -> InsightEngine -> MediaEngine -> ReportEngine.
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

from QueryEngine.agent import QueryAgent
from InsightEngine.agent import InsightAgent
from InsightEngine.state.state import InsightState
from MediaEngine.agent import MediaAgent
from ReportEngine.agent import ReportAgent


def _insight_markdown(state: InsightState) -> str:
    if state.markdown_report:
        return state.markdown_report
    if state.report:
        lines = ["# Insight Report"]
        if state.report.main_concerns:
            lines.append("## Main Concerns")
            lines.extend(f"- {item}" for item in state.report.main_concerns)
        return "\n".join(lines)
    return "（暂无内部洞察）"


def run_full_once(query: str, save: bool) -> Tuple[str, str, str, str]:
    query_agent = QueryAgent()
    query_result = query_agent.run(query, save_report=save)

    insight_agent = InsightAgent()
    insight_state = insight_agent.run(query)

    media_agent = MediaAgent()
    media_result = media_agent.run(query, save_report=save)

    sources: List[Tuple[str, str]] = [
        ("External Web Research", query_result.report_markdown),
        ("Internal Knowledge", _insight_markdown(insight_state)),
        ("Media Signals", media_result.report_markdown),
    ]

    report_agent = ReportAgent()
    report_result = report_agent.run(query, sources, save_report=save)

    return (
        query_result.report_markdown,
        _insight_markdown(insight_state),
        media_result.report_markdown,
        report_result.markdown,
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run all BettaFish LangChain agents sequentially.")
    parser.add_argument("--query", required=True, help="User query / task statement.")
    parser.add_argument("--save", action="store_true", help="Persist individual reports to disk.")
    args = parser.parse_args()

    external, internal, media, final_report = run_full_once(args.query, save=args.save)

    combined_lines = [
        f"# 综合多引擎报告：{args.query}\n",
        "## 外网搜索",
        external,
        "\n## 内部洞察",
        internal,
        "\n## 多模态信号",
        media,
        "\n## 综合执行报告",
        final_report,
    ]
    combined = "\n".join(combined_lines)
    print(combined)

    if args.save:
        out_dir = Path("reports_hybrid")
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_query = "".join(c for c in args.query if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        path = out_dir / f"full_pipeline_{safe_query}.md"
        path.write_text(combined, encoding="utf-8")
        print(f"\n[Saved combined report] {path}")


if __name__ == "__main__":
    main()

