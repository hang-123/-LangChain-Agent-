"""
Simple CLI runner to test the LangChain-based Query Agent.
Usage:
  python -m QueryEngine.runner --check-config
  python -m QueryEngine.runner --query "武汉大学 舆情"
Optional flags:
  --no-save    Do not write markdown/state files to disk
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

from .config import QueryEngineConfig
from .agent import QueryAgent


def mask(value: Optional[str]) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 6:
        return "***"
    return value[:3] + "***" + value[-3:]


def print_config_summary(cfg: QueryEngineConfig) -> None:
    print("\n[Config Summary]")
    print(f"  LLM model      : {cfg.llm_model}")
    print(f"  LLM base_url   : {cfg.llm_base_url or '(default)'}")
    print(f"  LLM api_key    : {mask(cfg.llm_api_key)}")
    print(f"  Tavily api_key : {mask(cfg.tavily_api_key)}")
    print(f"  paragraphs     : {cfg.max_paragraphs}")
    print(f"  reflections    : {cfg.max_reflections}")
    print(f"  output_dir     : {cfg.output_dir}")


def main():
    # Load .env if present (optional)
    load_dotenv()

    parser = argparse.ArgumentParser(description="Query Agent runner")
    parser.add_argument("--check-config", action="store_true", help="Validate and print configuration")
    parser.add_argument("--query", type=str, default="", help="Run with a single query string")
    parser.add_argument("--no-save", action="store_true", help="Do not save markdown/state files")
    args = parser.parse_args()

    try:
        cfg = QueryEngineConfig.from_env()
        cfg.validate()
    except Exception as e:
        print(f"[Config Error] {e}")
        print("Hint: set QUERY_ENGINE_API_KEY / QUERY_ENGINE_MODEL_NAME / TAVILY_API_KEY (and QUERY_ENGINE_BASE_URL if needed).")
        sys.exit(1)

    if args.check_config:
        print_config_summary(cfg)
        sys.exit(0)

    if not args.query:
        print("Please provide --query \"...\" or use --check-config")
        sys.exit(2)

    agent = QueryAgent(cfg)
    result = agent.run(args.query, save_report=not args.no_save)

    print("\n[Run Result]")
    print(f"  Report length  : {len(result.report_markdown)} chars")
    print(f"  Saved report   : {result.report_file or '(not saved)'}")
    print(f"  Saved state    : {result.state_file or '(not saved)'}")


if __name__ == "__main__":
    main()
