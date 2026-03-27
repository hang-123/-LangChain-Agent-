"""
CLI entrypoint for running the ForumEngine orchestrator.
"""

from __future__ import annotations

import argparse

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from .forum import ForumEngine


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run all agents under the ForumEngine.")
    parser.add_argument("--query", required=True, help="User query or task statement.")
    args = parser.parse_args()

    forum = ForumEngine()
    session = forum.run_session(args.query)

    print(f"\n=== ForumEngine Session: {args.query} ===")
    for message in session.messages:
        print(f"[{message.timestamp}] {message.speaker}:")
        print(message.content)
        print("-" * 40)


if __name__ == "__main__":
    main()

