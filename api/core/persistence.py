from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from api.core.contracts import CaseEvaluation, PerfBill, ResearchCase, RunTraceEntry, SecurityAuditEvent, UserFeedbackRecord
from api.core.policies import HarnessPolicy
from api.core.query_store import SQLiteQueryStore
from api.core.run_manifest import RunManifest
from api.core.settings import get_settings


class HarnessRepository(Protocol):
    def save_run_started(self, manifest: RunManifest, *, research_case: dict | None = None) -> None: ...

    def append_run_trace(self, trace_entry: RunTraceEntry) -> None: ...

    def save_run_completed(self, manifest: RunManifest, state: dict) -> None: ...

    def save_perf_bill(self, run_id: str, perf_bill: PerfBill) -> Path | None: ...

    def save_research_case(self, research_case: ResearchCase) -> None: ...

    def save_eval_result(self, evaluation: CaseEvaluation) -> None: ...

    def save_user_feedback(self, feedback: UserFeedbackRecord) -> None: ...

    def save_security_event(self, event: SecurityAuditEvent) -> None: ...


class NullHarnessRepository:
    def save_run_started(self, manifest: RunManifest, *, research_case: dict | None = None) -> None:
        return None

    def append_run_trace(self, trace_entry: RunTraceEntry) -> None:
        return None

    def save_run_completed(self, manifest: RunManifest, state: dict) -> None:
        return None

    def save_perf_bill(self, run_id: str, perf_bill: PerfBill) -> Path | None:
        del run_id, perf_bill
        return None

    def save_research_case(self, research_case: ResearchCase) -> None:
        return None

    def save_eval_result(self, evaluation: CaseEvaluation) -> None:
        return None

    def save_user_feedback(self, feedback: UserFeedbackRecord) -> None:
        return None

    def save_security_event(self, event: SecurityAuditEvent) -> None:
        return None


class FileHarnessRepository:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_path = self.base_dir / "runs.jsonl"
        self.traces_path = self.base_dir / "run_traces.jsonl"
        self.research_cases_path = self.base_dir / "research_cases.jsonl"
        self.eval_results_path = self.base_dir / "eval_results.jsonl"
        self.feedback_path = self.base_dir / "user_feedback.jsonl"
        self.security_events_path = self.base_dir / "security_events.jsonl"
        settings = get_settings()
        self.query_store = SQLiteQueryStore(settings.query_store_path) if settings.enable_query_store else None

    def _append_jsonl(self, path: Path, payload: dict) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _run_dir(self, run_id: str) -> Path:
        path = self.base_dir / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_run_started(self, manifest: RunManifest, *, research_case: dict | None = None) -> None:
        self._run_dir(manifest.run_id)
        payload = {"event": "run_started", "manifest": manifest.model_dump(mode="json"), "research_case": research_case or {}}
        self._append_jsonl(self.runs_path, payload)
        if self.query_store is not None:
            self.query_store.save_run_started(manifest)

    def append_run_trace(self, trace_entry: RunTraceEntry) -> None:
        self._append_jsonl(self.traces_path, trace_entry.model_dump(mode="json"))
        if self.query_store is not None:
            self.query_store.append_run_trace(trace_entry)

    def save_run_completed(self, manifest: RunManifest, state: dict) -> None:
        self._run_dir(manifest.run_id)
        payload = {
            "event": "run_completed",
            "manifest": manifest.model_dump(mode="json"),
            "quality_summary": dict(state.get("quality_summary") or {}),
            "report_excerpt": str(state.get("report_content") or "")[:1000],
            "retry_count": int(state.get("retry_count") or 0),
            "root_cause": str(state.get("root_cause") or ""),
        }
        self._append_jsonl(self.runs_path, payload)
        if self.query_store is not None:
            self.query_store.save_run_completed(manifest, state)

    def save_perf_bill(self, run_id: str, perf_bill: PerfBill) -> Path | None:
        path = self._run_dir(run_id) / "perf_bill.json"
        path.write_text(perf_bill.model_dump_json(indent=2), encoding="utf-8")
        if self.query_store is not None:
            self.query_store.save_perf_bill(perf_bill)
        return path

    def save_research_case(self, research_case: ResearchCase) -> None:
        self._append_jsonl(self.research_cases_path, research_case.model_dump(mode="json"))

    def save_eval_result(self, evaluation: CaseEvaluation) -> None:
        self._append_jsonl(self.eval_results_path, evaluation.model_dump(mode="json"))
        if self.query_store is not None:
            self.query_store.save_eval_result(evaluation)

    def save_user_feedback(self, feedback: UserFeedbackRecord) -> None:
        self._append_jsonl(self.feedback_path, feedback.model_dump(mode="json"))

    def save_security_event(self, event: SecurityAuditEvent) -> None:
        self._append_jsonl(self.security_events_path, event.model_dump(mode="json"))
        if self.query_store is not None:
            self.query_store.save_security_event(event)


def build_repository(policy: HarnessPolicy) -> HarnessRepository:
    persistence = policy.persistence_policy
    if not persistence.enabled:
        return NullHarnessRepository()
    return FileHarnessRepository(persistence.base_dir)
