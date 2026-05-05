from __future__ import annotations

import hashlib
import re
from typing import Any

from api.core.contracts import SecurityAuditEvent
from api.core.harness import utc_now_iso
from api.core.settings import get_settings


INJECTION_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "external_instruction": [
        re.compile(r"ignore\s+(all|any|the)\s+(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"忽略(所有|之前|以上).{0,8}(指令|要求|规则)"),
        re.compile(r"(system prompt|developer message|hidden instruction)", re.IGNORECASE),
        re.compile(r"(泄露|显示|输出).{0,8}(系统提示词|prompt|密钥|token)"),
    ],
    "prompt_exfiltration": [
        re.compile(r"(reveal|show|print).{0,12}(prompt|secret|token|api key)", re.IGNORECASE),
        re.compile(r"(导出|发送|上传).{0,12}(数据|密钥|token|api)"),
    ],
}

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "api_key_like": re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_\-]{12,}\b"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}\b", re.IGNORECASE),
    "password_assignment": re.compile(r"(?i)\b(password|passwd|secret)\s*[:=]\s*\S+"),
}

ALLOWED_SEARCH_TOOLS = {
    "company_profile_searcher",
    "jd_searcher",
    "interview_searcher",
    "salary_culture_searcher",
    "tech_stack_searcher",
}


def guardrails_enabled() -> bool:
    return bool(get_settings().enable_guardrails)


def guardrails_mode() -> str:
    return str(get_settings().guardrails_mode or "minimal_blocking").strip().lower()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _summary(label: str, text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return f"{label}; len={len(compact)}"


def _event(
    *,
    run_id: str,
    rail_type: str,
    reason_code: str,
    action_taken: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> SecurityAuditEvent:
    return SecurityAuditEvent(
        run_id=run_id,
        rail_type=rail_type,
        reason_code=reason_code,
        action_taken=action_taken,  # type: ignore[arg-type]
        content_hash=_hash_text(text),
        content_summary=_summary(f"{rail_type}:{reason_code}", text),
        timestamp=utc_now_iso(),
        metadata=metadata or {},
    )


def inspect_query_input(query: str, run_id: str) -> tuple[str, list[SecurityAuditEvent], bool]:
    if not guardrails_enabled():
        return query, [], False

    events: list[SecurityAuditEvent] = []
    blocked = False
    for reason_code, patterns in INJECTION_PATTERNS.items():
        if any(pattern.search(query) for pattern in patterns):
            action_taken = "block" if reason_code == "prompt_exfiltration" and guardrails_mode() == "minimal_blocking" else "warn"
            events.append(
                _event(
                    run_id=run_id,
                    rail_type="input",
                    reason_code=reason_code,
                    action_taken=action_taken,
                    text=query,
                )
            )
            blocked = blocked or action_taken == "block"
    return query, events, blocked


def enforce_tool_whitelist(
    run_id: str,
    task_specs: list[tuple[str, Any]],
) -> tuple[list[tuple[str, Any]], list[SecurityAuditEvent]]:
    if not guardrails_enabled():
        return task_specs, []

    filtered: list[tuple[str, Any]] = []
    events: list[SecurityAuditEvent] = []
    for task_spec in task_specs:
        tool_name = str(task_spec[0] or "")
        if tool_name in ALLOWED_SEARCH_TOOLS:
            filtered.append(task_spec)
            continue
        events.append(
            _event(
                run_id=run_id,
                rail_type="execution",
                reason_code="tool_not_allowlisted",
                action_taken="block",
                text=tool_name,
                metadata={"tool_name": tool_name},
            )
        )
    return filtered, events


def filter_selected_sources(
    run_id: str,
    selected: list[tuple[Any, str, str, bool]],
) -> tuple[list[tuple[Any, str, str, bool]], list[SecurityAuditEvent]]:
    if not guardrails_enabled():
        return selected, []

    filtered: list[tuple[Any, str, str, bool]] = []
    events: list[SecurityAuditEvent] = []
    for source, source_class, relevance_hint, company_specific in selected:
        haystack = " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "query", "") or ""),
                str(getattr(source, "url", "") or ""),
            ]
        )
        blocked = False
        for reason_code, patterns in INJECTION_PATTERNS.items():
            if any(pattern.search(haystack) for pattern in patterns):
                events.append(
                    _event(
                        run_id=run_id,
                        rail_type="retrieval",
                        reason_code=reason_code,
                        action_taken="block" if guardrails_mode() == "minimal_blocking" else "warn",
                        text=haystack,
                        metadata={"source_class": source_class, "url_hash": _hash_text(str(getattr(source, "url", "") or ""))},
                    )
                )
                blocked = guardrails_mode() == "minimal_blocking"
                break
        if not blocked:
            filtered.append((source, source_class, relevance_hint, company_specific))
    return filtered, events


def sanitize_output_text(run_id: str, text: str) -> tuple[str, list[SecurityAuditEvent]]:
    if not guardrails_enabled():
        return text, []

    sanitized = text
    events: list[SecurityAuditEvent] = []
    for reason_code, pattern in SECRET_PATTERNS.items():
        if not pattern.search(sanitized):
            continue
        events.append(
            _event(
                run_id=run_id,
                rail_type="output",
                reason_code=reason_code,
                action_taken="redact",
                text=sanitized,
            )
        )
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized, events

