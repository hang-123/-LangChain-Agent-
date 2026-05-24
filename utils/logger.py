"""Structured logger for bettafish — file-per-agent append-only with levels.

v2.0: structured JSON output with levels and error tracing.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core write function ──


def _write(agent_name: str, payload: dict) -> None:
    """Append a timestamped structured line to logs/<agent_name>.log."""
    payload["_ts"] = _utc_now()
    log_path = LOG_DIR / f"{agent_name}.log"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass  # logging failure must never crash the app


# ── Public API ──


def log_agent_run(
    agent_name: str,
    query: str,
    summary: str = "",
    events: list[dict] | None = None,
) -> None:
    _write(agent_name, {
        "event": "agent_run",
        "query": query[:500],
        "summary": summary[:500],
        "events": events or [],
    })


def log_forum_message(speaker: str, content: str) -> None:
    _write("forum", {
        "event": "forum_message",
        "speaker": speaker,
        "content": content[:2000],
    })


def log_error(context: str, exc: Exception, *, run_id: str = "", node: str = "") -> None:
    """Log an error with structured context and traceback."""
    trace = ""
    try:
        import traceback as _tb
        trace = _tb.format_exc()
    except Exception:
        trace = str(exc)

    _write("errors", {
        "event": "error",
        "context": context,
        "error_type": type(exc).__name__,
        "error_message": str(exc)[:500],
        "traceback": trace[:2000],
        "run_id": run_id,
        "node": node,
    })


def log_warning(message: str, *, run_id: str = "", node: str = "") -> None:
    _write("warnings", {
        "event": "warning",
        "message": message[:500],
        "run_id": run_id,
        "node": node,
    })


def log_event(
    event_type: str,
    message: str,
    *,
    run_id: str = "",
    node: str = "",
    extra: dict | None = None,
) -> None:
    """Generic structured event log."""
    payload = {
        "event": event_type,
        "message": message[:500],
        "run_id": run_id,
        "node": node,
    }
    if extra:
        payload.update(extra)
    _write("events", payload)


# ── Stdlib logging bridge ──


def setup_root_logger(level: str = "INFO") -> logging.Logger:
    """Configure Python stdlib root logger with structured JSON format.

    Falls back gracefully — logging is never fatal.
    """
    root = logging.getLogger("bettafish")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            '{"ts":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","msg":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)
    return root
