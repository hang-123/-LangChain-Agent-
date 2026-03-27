"""
Smoke test for ForumEngine orchestrator.
"""

from __future__ import annotations

import argparse

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from ForumEngine.forum import ForumEngine


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run ForumEngine coordination loop.")
    parser.add_argument("--query", default="字节跳动后端开发暑期实习", help="Session topic.")
    args = parser.parse_args()

    engine = ForumEngine()
    session = engine.run_session(args.query)

    print(f"\n=== ForumEngine Conversation ({len(session.messages)} messages) ===")
    for msg in session.messages:
        print(f"{msg.speaker}: {msg.content[:200]}...")


if __name__ == "__main__":
    main()
