from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

from api.core.contracts import NodePerf, PerfBill
from api.core.harness import utc_now_iso
from api.core.llm import coerce_message_text


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9_./:+-]+")


def _estimate_tokens_from_text(text: str) -> int:
    clean = " ".join(text.split()).strip()
    if not clean:
        return 0
    cjk_count = len(_CJK_RE.findall(clean))
    latin_tokens = sum(max(1, math.ceil(len(token) / 4)) for token in _LATIN_TOKEN_RE.findall(clean))
    whitespace_tokens = max(1, math.ceil(len(clean) / 24))
    return max(cjk_count + latin_tokens, whitespace_tokens)


def _extract_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return " ".join(part for part in (_extract_text(item) for item in payload) if part)
    if isinstance(payload, dict):
        preferred_keys = [
            "text",
            "content",
            "prompt",
            "prompts",
            "input",
            "inputs",
            "messages",
            "message",
        ]
        parts = [_extract_text(payload.get(key)) for key in preferred_keys if key in payload]
        return " ".join(part for part in parts if part)
    content = getattr(payload, "content", None)
    if content is not None:
        return _extract_text(content)
    text = getattr(payload, "text", None)
    if text is not None:
        return _extract_text(text)
    return ""


def _extract_token_usage_from_payload(payload: Any) -> tuple[int, int, int] | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        if any(key in payload for key in ("input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "total_tokens")):
            input_tokens = int(payload.get("input_tokens") or payload.get("prompt_tokens") or 0)
            output_tokens = int(payload.get("output_tokens") or payload.get("completion_tokens") or 0)
            total_tokens = int(payload.get("total_tokens") or (input_tokens + output_tokens))
            return input_tokens, output_tokens, total_tokens
        for key in ("usage_metadata", "token_usage", "usage", "response_metadata"):
            nested = payload.get(key)
            parsed = _extract_token_usage_from_payload(nested)
            if parsed is not None:
                return parsed
        return None

    for attr in ("usage_metadata", "token_usage", "usage", "response_metadata"):
        nested = getattr(payload, attr, None)
        parsed = _extract_token_usage_from_payload(nested)
        if parsed is not None:
            return parsed
    return None


def _extract_model_name(event: dict[str, Any]) -> str:
    metadata = event.get("metadata") or {}
    data = event.get("data") or {}
    for container in (metadata, data, data.get("output") if isinstance(data, dict) else None, data.get("chunk") if isinstance(data, dict) else None):
        if not container:
            continue
        if isinstance(container, dict):
            for key in ("model_name", "ls_model_name", "model"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return "unknown"


@dataclass
class _NodePerfState:
    node_name: str
    attempt: int
    started_at: str = ""
    finished_at: str = ""
    started_perf: float = 0.0
    finished_perf: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    token_in: int = 0
    token_out: int = 0
    token_total: int = 0
    token_estimated: bool = False
    fallback_triggered: bool = False
    fallback_target: str = ""
    models: set[str] = field(default_factory=set)
    error_count: int = 0
    input_fragments: list[str] = field(default_factory=list)
    output_fragments: list[str] = field(default_factory=list)
    completed: bool = False


class NodePerfTracker:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.started_at = utc_now_iso()
        self.started_perf = time.perf_counter()
        self._attempts: dict[str, int] = {}
        self._entries: list[_NodePerfState] = []

    def _active_entry(self, node_name: str) -> _NodePerfState | None:
        for entry in reversed(self._entries):
            if entry.node_name == node_name and not entry.completed:
                return entry
        return None

    def _ensure_entry(self, node_name: str) -> _NodePerfState:
        active = self._active_entry(node_name)
        if active is not None:
            return active
        attempt = self._attempts.get(node_name, 0) + 1
        self._attempts[node_name] = attempt
        entry = _NodePerfState(
            node_name=node_name,
            attempt=attempt,
            started_at=utc_now_iso(),
            started_perf=time.perf_counter(),
        )
        self._entries.append(entry)
        return entry

    def start_node(self, node_name: str) -> _NodePerfState:
        attempt = self._attempts.get(node_name, 0) + 1
        self._attempts[node_name] = attempt
        entry = _NodePerfState(
            node_name=node_name,
            attempt=attempt,
            started_at=utc_now_iso(),
            started_perf=time.perf_counter(),
        )
        self._entries.append(entry)
        return entry

    def observe_lang_event(self, node_name: str, event: dict[str, Any]) -> None:
        entry = self._ensure_entry(node_name)
        kind = str(event.get("event") or "")
        data = event.get("data") or {}
        if kind in {"on_chat_model_start", "on_llm_start"}:
            entry.llm_calls += 1
            model_name = _extract_model_name(event)
            if model_name:
                entry.models.add(model_name)
            entry.input_fragments.append(_extract_text(data))
            usage = _extract_token_usage_from_payload(data)
            if usage is not None:
                token_in, token_out, token_total = usage
                entry.token_in += token_in
                entry.token_out += token_out
                entry.token_total += token_total
            return

        if kind == "on_chat_model_stream":
            if entry.llm_calls == 0:
                entry.llm_calls = 1
            model_name = _extract_model_name(event)
            if model_name:
                entry.models.add(model_name)
            chunk = data.get("chunk") if isinstance(data, dict) else None
            chunk_text = coerce_message_text(chunk)
            if chunk_text:
                entry.output_fragments.append(chunk_text)
            usage = _extract_token_usage_from_payload(chunk)
            if usage is not None:
                token_in, token_out, token_total = usage
                entry.token_in += token_in
                entry.token_out += token_out
                entry.token_total += token_total
            return

        if kind in {"on_chat_model_end", "on_llm_end"}:
            if entry.llm_calls == 0:
                entry.llm_calls = 1
            model_name = _extract_model_name(event)
            if model_name:
                entry.models.add(model_name)
            output = data.get("output") if isinstance(data, dict) else None
            entry.output_fragments.append(_extract_text(output or data))
            usage = _extract_token_usage_from_payload(output or data)
            if usage is not None:
                token_in, token_out, token_total = usage
                entry.token_in += token_in
                entry.token_out += token_out
                entry.token_total += token_total
            return

        if kind == "on_tool_start":
            entry.tool_calls += 1
            return

    def record_fallback(self, from_node: str, to_node: str) -> None:
        entry = self._active_entry(from_node)
        if entry is None:
            for candidate in reversed(self._entries):
                if candidate.node_name == from_node:
                    entry = candidate
                    break
        if entry is None:
            return
        entry.fallback_triggered = True
        entry.fallback_target = to_node

    def complete_node(self, node_name: str, *, error: str = "") -> NodePerf:
        entry = self._ensure_entry(node_name)
        if entry.completed:
            return self._to_model(entry)
        entry.finished_at = utc_now_iso()
        entry.finished_perf = time.perf_counter()
        entry.completed = True
        if error:
            entry.error_count += 1
        if entry.llm_calls > 0 and entry.token_total == 0:
            estimated_in = _estimate_tokens_from_text(" ".join(entry.input_fragments))
            estimated_out = _estimate_tokens_from_text(" ".join(entry.output_fragments))
            entry.token_in = max(entry.token_in, estimated_in)
            entry.token_out = max(entry.token_out, estimated_out)
            entry.token_total = max(entry.token_total, entry.token_in + entry.token_out)
            entry.token_estimated = True
        return self._to_model(entry)

    def build_bill(self) -> PerfBill:
        nodes = [self._to_model(entry) for entry in self._entries]
        return PerfBill(
            run_id=self.run_id,
            generated_at=utc_now_iso(),
            total_duration_ms=max(0, int((time.perf_counter() - self.started_perf) * 1000)),
            total_llm_calls=sum(item.llm_calls for item in nodes),
            total_tool_calls=sum(item.tool_calls for item in nodes),
            total_token_in=sum(item.token_in for item in nodes),
            total_token_out=sum(item.token_out for item in nodes),
            total_token_total=sum(item.token_total for item in nodes),
            node_count=len(nodes),
            nodes=nodes,
        )

    def _to_model(self, entry: _NodePerfState) -> NodePerf:
        end_perf = entry.finished_perf if entry.completed and entry.finished_perf else time.perf_counter()
        duration_ms = max(0, int((end_perf - entry.started_perf) * 1000))
        return NodePerf(
            node_name=entry.node_name,
            attempt=entry.attempt,
            started_at=entry.started_at,
            finished_at=entry.finished_at,
            duration_ms=duration_ms,
            llm_calls=entry.llm_calls,
            tool_calls=entry.tool_calls,
            token_in=entry.token_in,
            token_out=entry.token_out,
            token_total=entry.token_total,
            token_estimated=entry.token_estimated,
            fallback_triggered=entry.fallback_triggered,
            fallback_target=entry.fallback_target,
            models=sorted(entry.models),
            error_count=entry.error_count,
        )
