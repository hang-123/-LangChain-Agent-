from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List
from uuid import uuid4


MEMORY_DIR = Path("memory_store")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fff]{2,}")


@dataclass
class SessionMemoryMessage:
    session_id: str
    role: str
    agent: str
    content: str
    timestamp: str
    metadata: dict[str, Any] | None = None


def create_session(topic: str | None = None) -> str:
    session_id = str(uuid4())
    session_dir = _session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "session_id": session_id,
        "topic": topic or "",
        "created_at": _now(),
        "last_updated": _now(),
        "turn_count": 0,
        "current_turn_id": None,
        "current_turn_query": "",
        "user_goal": "",
        "company": "",
        "role": "",
        "focus_points": [],
        "prep_status": [],
        "preferences": {},
        "last_report_summary": "",
        "memory_mode": "progressive_local",
    }
    _write_json(_summary_path(session_id), summary)
    return session_id


def append_session_message(
    session_id: str,
    *,
    role: str,
    agent: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    session_dir = _session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _now()
    raw_payload = {
        "session_id": session_id,
        "role": role,
        "agent": agent,
        "content": content,
        "timestamp": timestamp,
        "metadata": metadata or None,
    }
    _append_json_line(_raw_messages_path(session_id), raw_payload)

    summary = _load_summary(session_id)
    if role == "user":
        turn_id = f"turn_{summary['turn_count'] + 1}"
        summary["turn_count"] += 1
        summary["current_turn_id"] = turn_id
        summary["current_turn_query"] = content
        summary["user_goal"] = content
        summary["last_updated"] = timestamp
        _write_json(_summary_path(session_id), summary)
        capsule = {
            "turn_id": turn_id,
            "session_id": session_id,
            "user_query_summary": _shorten(content, 180),
            "query_agent_summary": "",
            "insight_agent_summary": "",
            "report_agent_summary": "",
            "structured": {},
            "tags": _extract_tokens(content)[:8],
            "timestamp": timestamp,
        }
        _append_json_line(_capsules_path(session_id), capsule)
        return

    _update_capsule(session_id, agent, content, metadata, timestamp)
    _update_summary(summary, agent, content, metadata, timestamp)
    _write_json(_summary_path(session_id), summary)


def load_recent_session_messages(session_id: str, limit: int = 12) -> List[SessionMemoryMessage]:
    path = _raw_messages_path(session_id)
    if not path.exists():
        return []

    messages: List[SessionMemoryMessage] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            messages.append(
                SessionMemoryMessage(
                    session_id=str(payload.get("session_id") or session_id),
                    role=str(payload.get("role") or "assistant"),
                    agent=str(payload.get("agent") or "System"),
                    content=str(payload.get("content") or ""),
                    timestamp=str(payload.get("timestamp") or ""),
                    metadata=payload.get("metadata"),
                )
            )
    except Exception:
        return []

    return messages[-limit:]


def build_memory_snippet(session_id: str, query: str, limit: int = 8, max_chars: int = 1200) -> str:
    summary = _load_summary(session_id)
    capsules = _load_capsules(session_id)
    if not summary and not capsules:
        return ""

    sections: List[str] = []
    summary_block = _build_summary_block(summary)
    if summary_block:
        sections.append(summary_block)

    selected_capsules = _select_relevant_capsules(query, capsules, limit=limit)
    if selected_capsules:
        lines = ["## 相关历史轮次"]
        for capsule in selected_capsules:
            lines.append(f"- 用户问题: {capsule.get('user_query_summary') or '无'}")
            if capsule.get("query_agent_summary"):
                lines.append(f"  QueryAgent: {capsule['query_agent_summary']}")
            if capsule.get("insight_agent_summary"):
                lines.append(f"  InsightAgent: {capsule['insight_agent_summary']}")
            if capsule.get("report_agent_summary"):
                lines.append(f"  ReportAgent: {capsule['report_agent_summary']}")
        sections.append("\n".join(lines))

    snippet = "\n\n".join(sections).strip()
    return _shorten(snippet, max_chars)


def get_memory_mode(session_id: str) -> str:
    return "progressive_local" if _summary_path(session_id).exists() else "ephemeral"


def _update_capsule(
    session_id: str,
    agent: str,
    content: str,
    metadata: dict[str, Any] | None,
    timestamp: str,
) -> None:
    capsules = _load_capsules(session_id)
    if not capsules:
        return
    latest = capsules[-1]
    summary_text = _summarize_agent_message(agent, content, metadata)
    if agent == "QueryAgent":
        latest["query_agent_summary"] = summary_text
    elif agent == "InsightAgent":
        latest["insight_agent_summary"] = summary_text
    elif agent == "ReportAgent":
        latest["report_agent_summary"] = summary_text

    if metadata:
        structured = latest.get("structured") or {}
        structured[agent] = _compact_metadata(metadata)
        latest["structured"] = structured

    latest["tags"] = _merge_tags(latest.get("tags") or [], _extract_tags_from_metadata(metadata, content))
    latest["timestamp"] = timestamp
    _rewrite_jsonl(_capsules_path(session_id), capsules)


def _update_summary(
    summary: dict[str, Any],
    agent: str,
    content: str,
    metadata: dict[str, Any] | None,
    timestamp: str,
) -> None:
    summary["last_updated"] = timestamp
    if metadata:
        if agent == "QueryAgent":
            summary["company"] = str(metadata.get("company") or summary.get("company") or "")
            summary["role"] = str(metadata.get("role") or summary.get("role") or "")
            summary["focus_points"] = _normalize_list(metadata.get("focus_points"), limit=4)
        elif agent == "InsightAgent":
            summary["prep_status"] = _normalize_list(metadata.get("prep_strategy"), limit=4)
        elif agent == "ReportAgent":
            summary["last_report_summary"] = _shorten(content, 240)
    if agent == "System" and not summary.get("last_report_summary"):
        summary["last_report_summary"] = _shorten(content, 120)


def _build_summary_block(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    lines = ["## 会话摘要"]
    if summary.get("user_goal"):
        lines.append(f"- 当前目标: {summary['user_goal']}")
    if summary.get("company"):
        lines.append(f"- 目标公司: {summary['company']}")
    if summary.get("role"):
        lines.append(f"- 目标岗位: {summary['role']}")
    if summary.get("focus_points"):
        lines.append("- 关注重点: " + "；".join(summary["focus_points"][:3]))
    if summary.get("prep_status"):
        lines.append("- 当前准备状态: " + "；".join(summary["prep_status"][:3]))
    if summary.get("last_report_summary"):
        lines.append(f"- 最近结论: {summary['last_report_summary']}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _select_relevant_capsules(query: str, capsules: Iterable[dict[str, Any]], limit: int) -> List[dict[str, Any]]:
    query_tokens = set(_extract_tokens(query))
    compact_query = " ".join(str(token) for token in query_tokens)
    allow_recent_fallback = len(compact_query) <= 18 or len(query.strip()) <= 12
    scored = []
    indexed_capsules = list(capsules)
    total = max(len(indexed_capsules), 1)
    for idx, capsule in enumerate(indexed_capsules):
        haystack = " ".join(
            [
                str(capsule.get("user_query_summary") or ""),
                str(capsule.get("query_agent_summary") or ""),
                str(capsule.get("insight_agent_summary") or ""),
                str(capsule.get("report_agent_summary") or ""),
                " ".join(str(tag) for tag in capsule.get("tags") or []),
            ]
        )
        capsule_tokens = set(_extract_tokens(haystack))
        overlap = len(query_tokens & capsule_tokens)
        recency_bonus = idx / total
        score = overlap * 2 + recency_bonus
        if overlap > 0 or allow_recent_fallback:
            scored.append((score, idx, capsule))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [capsule for _, _, capsule in scored[:limit]]
    selected.sort(key=lambda item: str(item.get("timestamp") or ""))
    return selected


def _summarize_agent_message(agent: str, content: str, metadata: dict[str, Any] | None) -> str:
    if metadata:
        if agent == "QueryAgent":
            company = metadata.get("company") or "目标公司"
            role = metadata.get("role") or "目标岗位"
            goal = metadata.get("candidate_goal") or content
            return _shorten(f"{company} / {role} / {goal}", 180)
        if agent == "InsightAgent":
            prep = _normalize_list(metadata.get("prep_strategy"), limit=2)
            return _shorten("；".join(prep) or content, 180)
        if agent == "ReportAgent":
            return _shorten(content, 180)
    return _shorten(content, 180)


def _extract_tags_from_metadata(metadata: dict[str, Any] | None, content: str) -> List[str]:
    if not metadata:
        return _extract_tokens(content)[:8]
    values: List[str] = []
    for key in ("company", "role", "candidate_goal", "focus_points", "prep_strategy"):
        value = metadata.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return _extract_tokens(" ".join(values))[:8]


def _compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "company",
        "role",
        "candidate_goal",
        "focus_points",
        "likely_questions",
        "prep_actions",
        "candidate_risks",
        "prep_strategy",
        "interviewer_focus",
        "generation_mode",
        "detail_level",
    ):
        if key in metadata and metadata[key] not in (None, "", []):
            compact[key] = metadata[key]
    return compact


def _normalize_list(value: Any, limit: int = 4) -> List[str]:
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items[:limit]


def _merge_tags(existing: List[str], incoming: List[str]) -> List[str]:
    merged = list(existing)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    return merged[:12]


def _extract_tokens(text: str) -> List[str]:
    tokens = [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
    if tokens:
        return tokens
    compact = text.replace(" ", "").strip()
    return [compact] if compact else []


def _shorten(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _load_summary(session_id: str) -> dict[str, Any]:
    path = _summary_path(session_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_capsules(session_id: str) -> List[dict[str, Any]]:
    path = _capsules_path(session_id)
    if not path.exists():
        return []
    items: List[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            items.append(json.loads(line))
    except Exception:
        return []
    return items


def _session_dir(session_id: str) -> Path:
    return MEMORY_DIR / session_id


def _summary_path(session_id: str) -> Path:
    return _session_dir(session_id) / "session_summary.json"


def _capsules_path(session_id: str) -> Path:
    return _session_dir(session_id) / "turn_capsules.jsonl"


def _raw_messages_path(session_id: str) -> Path:
    return _session_dir(session_id) / "raw_messages.jsonl"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_json_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _rewrite_jsonl(path: Path, rows: List[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.utcnow().isoformat()
