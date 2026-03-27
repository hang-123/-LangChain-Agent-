"""
Interactive chat runner for current Agents.

Usage:
  python InsightEngine/text/run_chat_agent.py --mode hybrid
Options:
  --mode {insight,query,hybrid}   默认 hybrid（先外网 QueryAgent，再内部 InsightAgent 补充）
  --no-index                      跳过向量索引（已有索引时可加快启动）
  --once                          只问一次就退出

Commands in chat:
  exit / quit    退出
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


def run_insight_once(query: str) -> str:
    agent = InsightAgent()
    state = agent.run(query)
    return state.markdown_report or "(无输出)"


def run_query_once(query: str) -> str:
    agent = QueryAgent()
    result = agent.run(query, save_report=False)
    return result.report_markdown


def run_hybrid_once(query: str) -> str:
    external_md, internal_sections = run_hybrid(query)
    return render_combined(external_md, internal_sections, query)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chat runner for Insight/Query/Hybrid agents")
    parser.add_argument("--mode", choices=["insight", "query", "hybrid"], default="hybrid")
    parser.add_argument("--no-index", action="store_true", help="Skip PG vector indexing at startup")
    parser.add_argument("--once", action="store_true", help="Ask only one question then exit")
    args = parser.parse_args()

    if args.mode in {"insight", "hybrid"} and not args.no_index:
        print("[Setup] Running index_local_docs() to refresh PG vector store ...")
        index_local_docs()

    print(f"[Chat] Mode = {args.mode}. 输入问题，exit/quit 退出。\n")

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见 👋")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("再见 👋")
            break

        if args.mode == "insight":
            reply = run_insight_once(user_input)
        elif args.mode == "query":
            reply = run_query_once(user_input)
        else:  # hybrid
            reply = run_hybrid_once(user_input)

        print("\n=========【回答】=========")
        print(reply)
        print("=========【结束】=========\n")

        if args.once:
            break


if __name__ == "__main__":
    main()
