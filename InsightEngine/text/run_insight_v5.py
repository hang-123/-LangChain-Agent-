"""
V5 test runner: quick smoke tests for current Agents.

Usage:
  python InsightEngine/text/run_insight_v5.py --mode insight --query "近期用户关注的风险点"
  python InsightEngine/text/run_insight_v5.py --mode query --query "全球新能源市场展望"
  python InsightEngine/text/run_insight_v5.py --mode hybrid --query "公司新品上线的舆情风险" --save
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

from InsightEngine.tools.vector_store_pg import index_local_docs
from InsightEngine.agent import InsightAgent
from InsightEngine.text.run_hybrid_agent import run_hybrid, render_combined
from QueryEngine.agent import QueryAgent


def run_insight(query: str) -> str:
    agent = InsightAgent()
    state = agent.run(query)
    return state.markdown_report or "(无输出)"


def run_query(query: str) -> str:
    agent = QueryAgent()
    result = agent.run(query, save_report=False)
    return result.report_markdown


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="V5 smoke tester for Insight/Query/Hybrid agents")
    parser.add_argument(
        "--mode",
        choices=["insight", "query", "hybrid"],
        default="insight",
        help="insight: 内部舆情 (PG 向量 RAG); query: 外网 Tavily; hybrid: 外网+内部补充",
    )
    parser.add_argument("--query", type=str, default="近期用户反馈的主要风险点", help="用户问题")
    parser.add_argument("--no-index", action="store_true", help="跳过向量索引（已有索引时使用）")
    parser.add_argument("--save", action="store_true", help="在 hybrid 模式保存合并报告到 reports_hybrid/")
    args = parser.parse_args()

    if args.mode in {"insight", "hybrid"} and not args.no_index:
        print("[Setup] Running index_local_docs() to refresh PG vector store ...")
        index_local_docs()

    if args.mode == "insight":
        print("[Run] InsightAgent (PG vector RAG)")
        md = run_insight(args.query)
        print(md)
        return

    if args.mode == "query":
        print("[Run] QueryAgent (Tavily)")
        md = run_query(args.query)
        print(md)
        return

    if args.mode == "hybrid":
        print("[Run] Hybrid: QueryAgent + InsightAgent")
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
