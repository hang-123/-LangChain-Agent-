from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return f"run-{uuid4().hex[:12]}"


def build_quality_summary(state: dict[str, Any]) -> dict[str, Any]:
    insights = dict(state.get("insights") or {})
    quality_metrics = dict(insights.get("quality_metrics") or {})
    fallback_flags = dict(insights.get("fallback_flags") or {})
    retrieval_diagnostics = dict(state.get("retrieval_diagnostics") or {})
    return {
        "run_id": str(state.get("run_id") or ""),
        "quality_mode": str(state.get("quality_mode") or "normal"),
        "warning_message": str(state.get("warning_message") or ""),
        "root_cause": str(state.get("root_cause") or insights.get("root_cause_hint") or ""),
        "root_cause_history": list(state.get("root_cause_history") or []),
        "evidence_count": int(insights.get("evidence_count") or 0),
        "company_specific_source_count": int(insights.get("company_specific_source_count") or 0),
        "claim_evidence_coverage": int(quality_metrics.get("claim_evidence_coverage") or 0),
        "action_plan_source_coverage": int(insights.get("action_plan_source_coverage") or 0),
        "fallback_report": bool(fallback_flags.get("report")),
        "fallback_query": bool(fallback_flags.get("query")),
        "fallback_insight": bool(fallback_flags.get("insight")),
        "retrieval_cached": bool(retrieval_diagnostics.get("cached")),
        "query_pack_size": int(retrieval_diagnostics.get("query_pack_size") or 0),
        "guardrail_events": len(list(state.get("security_events") or [])),
    }


def build_event_metrics(state: dict[str, Any]) -> dict[str, Any]:
    summary = build_quality_summary(state)
    return {
        "retry_count": int(state.get("retry_count") or 0),
        "quality_mode": summary["quality_mode"],
        "root_cause": summary["root_cause"],
        "evidence_count": summary["evidence_count"],
        "company_specific_source_count": summary["company_specific_source_count"],
        "claim_evidence_coverage": summary["claim_evidence_coverage"],
        "action_plan_source_coverage": summary["action_plan_source_coverage"],
        "query_pack_size": summary["query_pack_size"],
    }


def append_root_cause_history(state: dict[str, Any], *, node: str, root_cause: str | None) -> None:
    clean = str(root_cause or "").strip()
    if not clean:
        return
    history = list(state.get("root_cause_history") or [])
    entry = {
        "node": node,
        "root_cause": clean,
        "retry_count": int(state.get("retry_count") or 0),
        "timestamp": utc_now_iso(),
    }
    if history:
        last = history[-1]
        if (
            last.get("node") == entry["node"]
            and last.get("root_cause") == entry["root_cause"]
            and int(last.get("retry_count") or 0) == entry["retry_count"]
        ):
            state["root_cause_history"] = history
            return
    history.append(entry)
    state["root_cause_history"] = history


def append_run_trace(
    state: dict[str, Any],
    *,
    node: str,
    phase: str,
    detail: str,
    error: str = "",
) -> dict[str, Any]:
    entry = {
        "run_id": str(state.get("run_id") or ""),
        "node": node,
        "phase": phase,
        "detail": detail,
        "timestamp": utc_now_iso(),
        "retry_count": int(state.get("retry_count") or 0),
        "root_cause": str(state.get("root_cause") or ""),
        "metrics": build_event_metrics(state),
    }
    if error:
        entry["error"] = error
    trace = list(state.get("run_trace") or [])
    trace.append(entry)
    state["run_trace"] = trace
    state["quality_summary"] = build_quality_summary(state)
    return entry
