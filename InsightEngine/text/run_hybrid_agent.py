"""
Hybrid runner: combine QueryEngine (external web search) with InsightEngine (internal PG vector RAG).

Usage:
  python InsightEngine/text/run_hybrid_agent.py --query "产品近期舆情风险"
  Optional: --save will write a combined markdown to ./reports_hybrid/
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

from QueryEngine.agent import QueryAgent
from InsightEngine.agent import InsightAgent


def run_hybrid(query: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Run QueryAgent first, then augment each paragraph with InsightAgent (internal RAG)."""
    query_agent = QueryAgent()
    qa_result = query_agent.run(query, save_report=False)

    internal_sections: List[Tuple[str, str]] = []
    insight_agent = InsightAgent()
    for para in qa_result.state.paragraphs:
        sub_query = f"{para.title} - {para.expectation}"
        internal_state = insight_agent.run(sub_query)
        md = internal_state.markdown_report or "(暂无内部补充)"
        internal_sections.append((para.title, md))

    return qa_result.report_markdown, internal_sections


def render_combined(external_md: str, internal_sections: List[Tuple[str, str]], query: str) -> str:
    lines = []
    lines.append(f"# 综合报告：{query}\n")
    lines.append("## 外网搜索报告\n")
    lines.append(external_md)
    lines.append("\n## 内部舆情补充\n")
    if not internal_sections:
        lines.append("- （暂无内部补充）")
    else:
        for title, md in internal_sections:
            lines.append(f"### {title}")
            lines.append(md)
            lines.append("")
    return "\n".join(lines)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Hybrid runner: QueryEngine + InsightEngine")
    parser.add_argument("--query", type=str, required=True, help="User query")
    parser.add_argument("--save", action="store_true", help="Save combined report to ./reports_hybrid/")
    args = parser.parse_args()

    external_md, internal_sections = run_hybrid(args.query)
    combined = render_combined(external_md, internal_sections, args.query)

    print(combined)

    if args.save:
        out_dir = Path("reports_hybrid")
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_query = "".join(c for c in args.query if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        path = out_dir / f"hybrid_{safe_query}.md"
        path.write_text(combined, encoding="utf-8")
        print(f"\n[Saved] {path}")


if __name__ == "__main__":
    main()
