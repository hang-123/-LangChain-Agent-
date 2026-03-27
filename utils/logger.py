"""
Lightweight logging helpers shared by all agents.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

LOG_DIR = Path("logs")


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize(content: str) -> str:
    return content.replace("\r", "\\r").replace("\n", "\\n")


def _write(agent_name: str, payload: str) -> None:
    _ensure_log_dir()
    path = LOG_DIR / f"{agent_name}.log"
    timestamp = datetime.utcnow().isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {payload}\n")


def log_agent_run(
    agent_name: str,
    query: str,
    summary: Optional[str] = None,
    events: Optional[Iterable[object]] = None,
) -> None:
    """
    Append a structured line to logs/<agent_name>.log describing the latest run.
    """

    parts = [f"Query={query}"]
    if summary:
        parts.append(f"Summary={summary}")
    if events:
        formatted = []
        for event in events:
            stage = getattr(event, "stage", None)
            detail = getattr(event, "detail", None)
            if stage and detail:
                formatted.append(f"{stage}:{detail}")
            else:
                formatted.append(str(event))
        if formatted:
            parts.append("Events=" + "; ".join(formatted))
    _write(agent_name, _sanitize(" | ".join(parts)))


def log_forum_message(speaker: str, content: str) -> None:
    """
    Log a cross-agent forum message into logs/forum.log.
    """

    payload = f"{speaker}: {content}"
    _write("forum", _sanitize(payload))

