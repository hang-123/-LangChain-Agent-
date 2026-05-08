from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


StateLike = Mapping[str, Any]


def _copy(value: Any) -> Any:
    return deepcopy(value)


def get_background(state: StateLike) -> dict[str, Any]:
    return {
        "run": {
            "run_id": _copy(state.get("run_id", "")),
            "research_case": _copy(state.get("research_case") or {}),
            "run_manifest": _copy(state.get("run_manifest") or {}),
        },
        "request": {
            "query": _copy(state.get("query", "")),
            "user_id": _copy(state.get("user_id", "")),
            "intent": _copy(state.get("intent", "")),
            "query_profile": _copy(state.get("query_profile") or {}),
            "memory_summary": _copy(state.get("memory_summary", "")),
            "memory_artifact_refs": _copy(state.get("memory_artifact_refs") or {}),
        },
        "candidate": {
            "candidate_profile": _copy(state.get("candidate_profile") or {}),
            "resume_evidence": _copy(state.get("resume_evidence") or []),
        },
        "job_input": {
            "job_posting": _copy(state.get("job_posting") or {}),
            "raw_jd_text": _copy(state.get("raw_jd_text", "")),
            "source_url": _copy(state.get("source_url", "")),
        },
        "policy": _copy(state.get("policy") or {}),
    }


def get_working_set(state: StateLike) -> dict[str, Any]:
    insights = dict(state.get("insights") or {})
    return {
        "retrieval": {
            "query_pack": _copy(state.get("query_pack") or []),
            "evidence_items": _copy(state.get("evidence_items") or []),
            "context": _copy(state.get("context") or []),
            "retrieval_diagnostics": _copy(state.get("retrieval_diagnostics") or {}),
        },
        "analysis": {
            "query_result": _copy(insights.get("query_result") or {}),
            "insight_result": _copy(insights.get("insight_result") or {}),
            "quality_metrics": _copy(insights.get("quality_metrics") or {}),
            "render_metadata": _copy(insights.get("render_metadata") or {}),
        },
        "review": {
            "review_feedback": _copy(state.get("review_feedback", "")),
        },
    }


def get_artifacts(state: StateLike) -> dict[str, Any]:
    return {
        "job": {
            "external_evidence_pack": _copy(state.get("external_evidence_pack") or {}),
            "job_snapshot": _copy(state.get("job_snapshot") or {}),
        },
        "matching": {
            "match_assessment": _copy(state.get("match_assessment") or {}),
        },
        "resume": {
            "tailor_plan": _copy(state.get("tailor_plan") or {}),
            "resume_version": _copy(state.get("resume_version") or {}),
            "fact_check_report": _copy(state.get("fact_check_report") or {}),
        },
        "report": {
            "report_content": _copy(state.get("report_content", "")),
        },
    }


def get_control(state: StateLike) -> dict[str, Any]:
    return {
        "retry_count": _copy(state.get("retry_count", 0)),
        "quality_mode": _copy(state.get("quality_mode", "normal")),
        "warning_message": _copy(state.get("warning_message", "")),
        "root_cause": _copy(state.get("root_cause", "")),
        "root_cause_history": _copy(state.get("root_cause_history") or []),
        "status": _copy(state.get("status", "")),
    }


def get_telemetry(state: StateLike) -> dict[str, Any]:
    return {
        "run_trace": _copy(state.get("run_trace") or []),
        "quality_summary": _copy(state.get("quality_summary") or {}),
        "perf_bill": _copy(state.get("perf_bill") or {}),
        "perf_bill_path": _copy(state.get("perf_bill_path", "")),
        "security_events": _copy(state.get("security_events") or []),
    }


def get_workflow_state_view(state: StateLike) -> dict[str, Any]:
    return {
        "background": get_background(state),
        "working_set": get_working_set(state),
        "artifacts": get_artifacts(state),
        "control": get_control(state),
        "telemetry": get_telemetry(state),
    }
