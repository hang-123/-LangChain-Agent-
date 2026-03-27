"""
Simple regression runner to sanity check Agent modes.

Usage:
  python InsightEngine/tests/run_regression_smoke.py --modes insight query hybrid
"""

from __future__ import annotations

import argparse
from typing import Dict, List

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

from InsightEngine.tools.vector_store_pg import index_local_docs
from InsightEngine.agent import InsightAgent
from InsightEngine.text.run_hybrid_agent import run_hybrid
from QueryEngine.agent import QueryAgent


DEFAULT_QUERIES: Dict[str, List[str]] = {
    "insight": [
        "近期用户对新品有哪些关注点",
        "分析一下售后体验的风险",
    ],
    "query": [
        "全球新能源市场展望",
        "人工智能行业最新监管动态",
    ],
    "hybrid": [
        "公司新品发布的舆情风险",
    ],
}


def run_insight(query: str) -> str:
    state = InsightAgent().run(query)
    return state.markdown_report or ""


def run_query(query: str) -> str:
    result = QueryAgent().run(query, save_report=False)
    return result.report_markdown


def run_hybrid_mode(query: str) -> str:
    external_md, internal_sections = run_hybrid(query)
    chunks = [external_md] + [md for _, md in internal_sections]
    return "\n\n".join(chunks)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Agent regression smoke tests")
    parser.add_argument("--modes", nargs="*", choices=["insight", "query", "hybrid"], default=["insight", "query", "hybrid"])
    parser.add_argument("--no-index", action="store_true", help="Skip vector indexing (if already up-to-date).")
    args = parser.parse_args()

    if any(mode in {"insight", "hybrid"} for mode in args.modes) and not args.no_index:
        print("[Regression] indexing local docs for PG vector store ...")
        index_local_docs()

    total = 0
    failures = 0

    for mode in args.modes:
        for query in DEFAULT_QUERIES.get(mode, []):
            total += 1
            print(f"[Regression] mode={mode} query={query}")
            try:
                if mode == "insight":
                    output = run_insight(query)
                elif mode == "query":
                    output = run_query(query)
                else:
                    output = run_hybrid_mode(query)

                if not output.strip():
                    raise ValueError("empty response")
                print(f"  ✔ success (length={len(output)})")
            except Exception as exc:  # pragma: no cover
                failures += 1
                print(f"  ✗ failed: {exc}")

    print(f"\n[Regression] completed {total} cases, failures={failures}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
