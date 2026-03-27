from __future__ import annotations

"""
Simple PostgreSQL-backed conversation storage.

This module is intentionally lightweight and defensive:
- If the database or tables are not available, all functions
  fail silently and the rest of the system continues工作。
"""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from utils.logger import _write as _log_raw  # reuse existing logger backend


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "bettafish")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")


_engine: Optional[Engine] = None


def _build_engine() -> Engine:
  """
  Lazily construct a SQLAlchemy engine using psycopg3.
  """

  url = f"postgresql+psycopg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
  return create_engine(url, future=True)


def get_engine() -> Engine:
  """
  Return a process-wide Engine instance.
  """

  global _engine
  if _engine is None:
      _engine = _build_engine()
  return _engine


def _log_error(payload: str) -> None:
  """
  Log low-level conversation store errors to logs/conversation.log.
  """

  try:
      _log_raw("conversation", payload)
  except Exception:
      # Logging must never break业务逻辑
      pass


@dataclass
class ConversationMessage:
  conversation_id: str
  role: str
  agent: str
  content: str
  created_at: Optional[datetime] = None


def create_conversation(topic: str, user_id: Optional[str] = None) -> str:
  """
  Create a new conversation row in `conversations` and return its id.

  The function is best-effort: if the INSERT fails (missing table, etc.),
  it still returns a syntactically valid id so上层逻辑可以继续运行。
  """

  conversation_id = str(uuid4())
  try:
      engine = get_engine()
      with engine.begin() as conn:
          if user_id is None:
              conn.execute(
                  text("INSERT INTO conversations (id, topic) VALUES (:id, :topic)"),
                  {"id": conversation_id, "topic": topic},
              )
          else:
              conn.execute(
                  text(
                      "INSERT INTO conversations (id, topic, user_id) "
                      "VALUES (:id, :topic, :user_id)"
                  ),
                  {"id": conversation_id, "topic": topic, "user_id": user_id},
              )
  except Exception as exc:  # pragma: no cover - defensive
      _log_error(f"create_conversation failed: {exc!r}")

  return conversation_id


def append_message(
  conversation_id: str,
  *,
  role: str,
  agent: str,
  content: str,
) -> None:
  """
  Append a单条消息到 conversation_messages。
  """

  try:
      engine = get_engine()
      with engine.begin() as conn:
          conn.execute(
              text(
                  "INSERT INTO conversation_messages "
                  "(conversation_id, role, agent, content) "
                  "VALUES (:conversation_id, :role, :agent, :content)"
              ),
              {
                  "conversation_id": conversation_id,
                  "role": role,
                  "agent": agent,
                  "content": content,
              },
          )
  except Exception as exc:  # pragma: no cover - defensive
      _log_error(f"append_message failed: {exc!r}")


def load_recent_messages(
  conversation_id: str,
  *,
  limit: int = 10,
) -> List[ConversationMessage]:
  """
  Load up to `limit` recent messages for a given会话。

  The implementation only relies on常见列:
  - id (自增主键)
  - conversation_id
  - role
  - agent
  - content
  If the query失败，返回空列表。
  """

  try:
      engine = get_engine()
      with engine.begin() as conn:
          result = conn.execute(
              text(
                  "SELECT conversation_id, role, agent, content "
                  "FROM conversation_messages "
                  "WHERE conversation_id = :conversation_id "
                  "ORDER BY id DESC "
                  "LIMIT :limit"
              ),
              {"conversation_id": conversation_id, "limit": limit},
          )
          rows = list(result)
  except Exception as exc:  # pragma: no cover - defensive
      _log_error(f"load_recent_messages failed: {exc!r}")
      return []

  messages: List[ConversationMessage] = []
  for row in rows:
      messages.append(
          ConversationMessage(
              conversation_id=str(row[0]),
              role=str(row[1]),
              agent=str(row[2]),
              content=str(row[3]),
              created_at=None,
          )
      )
  # We selected DESC order, but多数提示希望从旧到新阅读
  messages.reverse()
  return messages

