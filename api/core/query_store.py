from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from api.core.contracts import CaseEvaluation, PerfBill, RunTraceEntry, SecurityAuditEvent
from api.core.harness import utc_now_iso
from api.core.run_manifest import RunManifest


class SQLiteQueryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    research_case_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    code_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    rollout_percentage INTEGER NOT NULL,
                    assignment_source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    quality_mode TEXT NOT NULL DEFAULT '',
                    root_cause TEXT NOT NULL DEFAULT '',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    manifest_json TEXT NOT NULL,
                    quality_summary_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS run_traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    node TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    root_cause TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS node_perf (
                    run_id TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    llm_calls INTEGER NOT NULL,
                    tool_calls INTEGER NOT NULL,
                    token_in INTEGER NOT NULL,
                    token_out INTEGER NOT NULL,
                    token_total INTEGER NOT NULL,
                    token_estimated INTEGER NOT NULL,
                    fallback_triggered INTEGER NOT NULL,
                    fallback_target TEXT NOT NULL,
                    models_json TEXT NOT NULL,
                    error_count INTEGER NOT NULL,
                    PRIMARY KEY (run_id, node_name, attempt)
                );

                CREATE TABLE IF NOT EXISTS eval_results (
                    run_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    expected_intent TEXT NOT NULL,
                    actual_intent TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    quality_mode TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    code_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    failures_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    node_scores_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, case_id)
                );

                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    rail_type TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    content_summary TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )

    def save_run_started(self, manifest: RunManifest) -> None:
        payload = manifest.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, query, requested_at, research_case_id, prompt_version, policy_version,
                    code_version, model_name, experiment_id, variant, rollout_percentage, assignment_source,
                    status, quality_mode, root_cause, retry_count, manifest_json, quality_summary_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'started', '', '', 0, ?, '{}', ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    query = excluded.query,
                    requested_at = excluded.requested_at,
                    research_case_id = excluded.research_case_id,
                    prompt_version = excluded.prompt_version,
                    policy_version = excluded.policy_version,
                    code_version = excluded.code_version,
                    model_name = excluded.model_name,
                    experiment_id = excluded.experiment_id,
                    variant = excluded.variant,
                    rollout_percentage = excluded.rollout_percentage,
                    assignment_source = excluded.assignment_source,
                    status = 'started',
                    manifest_json = excluded.manifest_json,
                    updated_at = excluded.updated_at
                """,
                (
                    manifest.run_id,
                    manifest.query,
                    manifest.requested_at,
                    manifest.research_case_id,
                    manifest.prompt_version,
                    manifest.policy_version,
                    manifest.code_version,
                    manifest.model_name,
                    manifest.experiment_id,
                    manifest.variant,
                    manifest.rollout_percentage,
                    manifest.assignment_source,
                    json.dumps(payload, ensure_ascii=False),
                    manifest.requested_at,
                ),
            )

    def save_run_completed(self, manifest: RunManifest, state: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'completed',
                    quality_mode = ?,
                    root_cause = ?,
                    retry_count = ?,
                    quality_summary_json = ?,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    str(state.get("quality_mode") or ""),
                    str(state.get("root_cause") or ""),
                    int(state.get("retry_count") or 0),
                    json.dumps(dict(state.get("quality_summary") or {}), ensure_ascii=False),
                    utc_now_iso(),
                    manifest.run_id,
                ),
            )

    def append_run_trace(self, trace_entry: RunTraceEntry) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO run_traces (
                    run_id, node, phase, timestamp, retry_count, root_cause, detail, metrics_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_entry.run_id,
                    trace_entry.node,
                    trace_entry.phase,
                    trace_entry.timestamp,
                    trace_entry.retry_count,
                    trace_entry.root_cause,
                    trace_entry.detail,
                    json.dumps(trace_entry.metrics, ensure_ascii=False),
                    trace_entry.error,
                ),
            )

    def save_perf_bill(self, perf_bill: PerfBill) -> None:
        with self._connect() as connection:
            for node in perf_bill.nodes:
                connection.execute(
                    """
                    INSERT INTO node_perf (
                        run_id, node_name, attempt, duration_ms, llm_calls, tool_calls, token_in, token_out,
                        token_total, token_estimated, fallback_triggered, fallback_target, models_json, error_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, node_name, attempt) DO UPDATE SET
                        duration_ms = excluded.duration_ms,
                        llm_calls = excluded.llm_calls,
                        tool_calls = excluded.tool_calls,
                        token_in = excluded.token_in,
                        token_out = excluded.token_out,
                        token_total = excluded.token_total,
                        token_estimated = excluded.token_estimated,
                        fallback_triggered = excluded.fallback_triggered,
                        fallback_target = excluded.fallback_target,
                        models_json = excluded.models_json,
                        error_count = excluded.error_count
                    """,
                    (
                        perf_bill.run_id,
                        node.node_name,
                        node.attempt,
                        node.duration_ms,
                        node.llm_calls,
                        node.tool_calls,
                        node.token_in,
                        node.token_out,
                        node.token_total,
                        1 if node.token_estimated else 0,
                        1 if node.fallback_triggered else 0,
                        node.fallback_target,
                        json.dumps(node.models, ensure_ascii=False),
                        node.error_count,
                    ),
                )

    def save_eval_result(self, evaluation: CaseEvaluation) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO eval_results (
                    run_id, case_id, passed, score, expected_intent, actual_intent, root_cause, quality_mode,
                    prompt_version, policy_version, code_version, model_name, experiment_id, variant,
                    failures_json, metrics_json, node_scores_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, case_id) DO UPDATE SET
                    passed = excluded.passed,
                    score = excluded.score,
                    expected_intent = excluded.expected_intent,
                    actual_intent = excluded.actual_intent,
                    root_cause = excluded.root_cause,
                    quality_mode = excluded.quality_mode,
                    prompt_version = excluded.prompt_version,
                    policy_version = excluded.policy_version,
                    code_version = excluded.code_version,
                    model_name = excluded.model_name,
                    experiment_id = excluded.experiment_id,
                    variant = excluded.variant,
                    failures_json = excluded.failures_json,
                    metrics_json = excluded.metrics_json,
                    node_scores_json = excluded.node_scores_json
                """,
                (
                    evaluation.metadata.run_id,
                    evaluation.case_id,
                    1 if evaluation.passed else 0,
                    evaluation.score,
                    evaluation.expected_intent,
                    evaluation.actual_intent,
                    evaluation.root_cause,
                    evaluation.quality_mode,
                    evaluation.metadata.prompt_version,
                    evaluation.metadata.policy_version,
                    evaluation.metadata.code_version,
                    evaluation.metadata.model_name,
                    evaluation.metadata.experiment_id,
                    evaluation.metadata.variant,
                    json.dumps(evaluation.failures, ensure_ascii=False),
                    json.dumps(evaluation.metrics, ensure_ascii=False),
                    evaluation.node_scores.model_dump_json(),
                ),
            )

    def save_security_event(self, event: SecurityAuditEvent) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO security_events (
                    run_id, rail_type, reason_code, action_taken, content_hash, content_summary, timestamp, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.rail_type,
                    event.reason_code,
                    event.action_taken,
                    event.content_hash,
                    event.content_summary,
                    event.timestamp,
                    json.dumps(event.metadata, ensure_ascii=False),
                ),
            )
