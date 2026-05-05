from __future__ import annotations

from typing import Any, AsyncIterator

from api.core.constants import MAX_RETRIES, NODE_START_MESSAGES
from api.core.contracts import RunTraceEntry, SecurityAuditEvent
from api.core.graph import (
    GRAPH_NODE_ORDER,
    AgentState,
    build_agent_message_event,
    build_initial_state,
    merge_state_update,
    parse_review_feedback_json,
)
from api.core.guardrails import inspect_query_input
from api.core.harness import append_root_cause_history, append_run_trace, build_event_metrics, build_quality_summary, new_run_id, utc_now_iso
from api.core.llm import coerce_message_text
from api.core.metrics import observe_fallback, observe_llm_tokens, observe_node_latency
from api.core.otel import get_tracer, start_span
from api.core.perf import NodePerfTracker
from api.core.persistence import build_repository
from api.core.policy_loader import load_policy
from api.core.run_manifest import build_run_manifest
from api.core.settings import get_settings


def _resolve_graph_node_name(event: dict[str, Any]) -> str | None:
    metadata = event.get("metadata") or {}
    langgraph_node = metadata.get("langgraph_node")
    if isinstance(langgraph_node, str) and langgraph_node in GRAPH_NODE_ORDER:
        return langgraph_node

    name = event.get("name")
    if isinstance(name, str) and name in GRAPH_NODE_ORDER:
        return name
    return None


def _is_node_start_event(event: dict[str, Any], node_name: str | None) -> bool:
    kind = str(event.get("event") or "")
    name = event.get("name")
    if kind == "on_node_start" and node_name is not None:
        return True
    return kind == "on_chain_start" and node_name is not None and name == node_name


def _is_node_end_event(event: dict[str, Any], node_name: str | None) -> bool:
    kind = str(event.get("event") or "")
    name = event.get("name")
    if kind == "on_node_end" and node_name is not None:
        return True
    return kind == "on_chain_end" and node_name is not None and name == node_name


class ResearchExecutionSession:
    def __init__(
        self,
        graph: Any,
        query: str,
        *,
        candidate_profile: dict[str, Any] | None = None,
        resume_evidence: list[dict[str, Any]] | None = None,
        job_posting: dict[str, Any] | None = None,
        match_assessment: dict[str, Any] | None = None,
        research_case: dict[str, Any] | None = None,
    ) -> None:
        self.graph = graph
        self.settings = get_settings()
        self.node_perf_enabled = bool(self.settings.enable_node_perf)
        self.policy = load_policy()
        self.repository = build_repository(self.policy)
        run_id = new_run_id()
        sanitized_query, input_security_events, blocked = inspect_query_input(query, run_id)
        if blocked:
            raise ValueError("query blocked by guardrails: detected prompt exfiltration pattern")
        self.query = sanitized_query
        research_case_id = str((research_case or {}).get("case_id") or "")
        self.run_manifest = build_run_manifest(
            run_id=run_id,
            query=self.query,
            policy=self.policy,
            research_case_id=research_case_id,
        )
        self.state: AgentState = build_initial_state(
            self.query,
            run_id=run_id,
            candidate_profile=candidate_profile,
            resume_evidence=resume_evidence,
            job_posting=job_posting,
            match_assessment=match_assessment,
            policy=self.policy.as_serializable(),
            run_manifest=self.run_manifest.model_dump(mode="json"),
            research_case=research_case,
        )
        self.state["security_events"] = [event.model_dump(mode="json") for event in input_security_events]
        self.state["quality_summary"] = build_quality_summary(self.state)
        self.perf_tracker = NodePerfTracker(run_id) if self.node_perf_enabled else None
        self.repository.save_run_started(self.run_manifest, research_case=research_case)
        for event in input_security_events:
            self.repository.save_security_event(event)

    def _persist_security_events(self, raw_events: list[dict[str, Any]] | None) -> None:
        for raw_event in raw_events or []:
            try:
                event = SecurityAuditEvent.model_validate(raw_event)
            except Exception:
                continue
            self.repository.save_security_event(event)

    async def stream_events(self) -> AsyncIterator[dict[str, Any]]:
        state = self.state
        max_retries = int((dict(state.get("policy") or {}).get("retry_policy") or {}).get("max_retries") or MAX_RETRIES)
        tracer = get_tracer()
        node_spans: dict[str, Any] = {}
        node_attempts: dict[str, int] = {}

        with start_span(
            "research.session",
            {
                "run.id": state["run_id"],
                "research.query": self.query,
                "policy.version": dict(state.get("run_manifest") or {}).get("policy_version", ""),
                "prompt.version": dict(state.get("run_manifest") or {}).get("prompt_version", ""),
                "experiment.id": dict(state.get("run_manifest") or {}).get("experiment_id", ""),
                "experiment.variant": dict(state.get("run_manifest") or {}).get("variant", "control"),
            },
        ) as session_span:
            try:
                yield {
                    "type": "meta",
                    "run_id": state["run_id"],
                    "query": self.query,
                    "max_retries": max_retries,
                    "started_at": utc_now_iso(),
                    "timestamp": utc_now_iso(),
                    "metrics": build_event_metrics(state),
                    "run_manifest": state.get("run_manifest"),
                    "policy_version": dict(state.get("run_manifest") or {}).get("policy_version", ""),
                }

                async for event in self.graph.astream_events(
                    build_initial_state(
                        self.query,
                        run_id=state["run_id"],
                        candidate_profile=state.get("candidate_profile"),
                        resume_evidence=list(state.get("resume_evidence") or []),
                        job_posting=state.get("job_posting"),
                        match_assessment=state.get("match_assessment"),
                        policy=state.get("policy"),
                        run_manifest=state.get("run_manifest"),
                        research_case=state.get("research_case"),
                    ),
                    version="v2",
                ):
                    node_name = _resolve_graph_node_name(event)
                    kind = str(event.get("event") or "")
                    if self.perf_tracker is not None and node_name is not None:
                        self.perf_tracker.observe_lang_event(node_name, event)
                    if node_name is not None and tracer is not None and kind in {"on_chat_model_start", "on_tool_start"}:
                        span = node_spans.get(node_name)
                        if span is not None:
                            span.add_event(kind, attributes={"event.name": str(event.get("name") or "")})
                    if _is_node_start_event(event, node_name):
                        node = str(node_name or "unknown")
                        detail = NODE_START_MESSAGES.get(node, f"正在执行 {node}")
                        if self.perf_tracker is not None:
                            self.perf_tracker.start_node(node)
                        if tracer is not None:
                            node_attempts[node] = node_attempts.get(node, 0) + 1
                            span = tracer.start_span(f"agent.node.{node}")
                            span.set_attribute("run.id", state["run_id"])
                            span.set_attribute("node.name", node)
                            span.set_attribute("node.attempt", node_attempts[node])
                            node_spans[node] = span
                        trace_entry = append_run_trace(state, node=node, phase="started", detail=detail)
                        self.repository.append_run_trace(RunTraceEntry.model_validate(trace_entry))
                        yield {
                            "type": "status",
                            "run_id": state["run_id"],
                            "node": node,
                            "agent": node,
                            "phase": "started",
                            "detail": detail,
                            "retry_count": state.get("retry_count", 0),
                            "timestamp": utc_now_iso(),
                            "metrics": build_event_metrics(state),
                        }
                        continue

                    if kind == "on_chat_model_stream" and node_name == "ReportAgent":
                        chunk = coerce_message_text((event.get("data") or {}).get("chunk"))
                        if chunk:
                            yield {
                                "type": "chunk",
                                "run_id": state["run_id"],
                                "node": "ReportAgent",
                                "timestamp": utc_now_iso(),
                                "content": chunk,
                            }
                        continue

                    if _is_node_end_event(event, node_name):
                        node = str(node_name or "unknown")
                        output = (event.get("data") or {}).get("output")
                        previous_retry_count = int(state.get("retry_count") or 0)
                        if isinstance(output, dict):
                            self._persist_security_events(list(output.get("security_events") or []))
                            merge_state_update(state, output)
                        append_root_cause_history(state, node=node, root_cause=str(state.get("root_cause") or ""))
                        state["quality_summary"] = build_quality_summary(state)
                        detail = str(state.get("status") or f"{node} 已完成")
                        if self.perf_tracker is not None:
                            node_perf = self.perf_tracker.complete_node(node)
                            observe_node_latency(node, node_perf.duration_ms)
                            model_name = node_perf.models[0] if node_perf.models else "unknown"
                            observe_llm_tokens(model_name, token_in=node_perf.token_in, token_out=node_perf.token_out)
                            if node == "ReviewAgent" and int(state.get("retry_count") or 0) > previous_retry_count:
                                parsed_review = parse_review_feedback_json(state) or {}
                                retry_target = str(parsed_review.get("retry_target") or "report")
                                self.perf_tracker.record_fallback("ReviewAgent", retry_target)
                                observe_fallback("ReviewAgent", retry_target)
                        span = node_spans.pop(node, None)
                        if span is not None:
                            if self.perf_tracker is not None:
                                span.set_attribute("node.duration_ms", node_perf.duration_ms)
                            span.set_attribute("node.retry_count", int(state.get("retry_count") or 0))
                            span.set_attribute("quality.mode", str(state.get("quality_mode") or "normal"))
                            span.set_attribute("root.cause", str(state.get("root_cause") or ""))
                            span.end()
                        trace_entry = append_run_trace(state, node=node, phase="completed", detail=detail)
                        self.repository.append_run_trace(RunTraceEntry.model_validate(trace_entry))
                        payload = {
                            "type": "status",
                            "run_id": state["run_id"],
                            "node": node,
                            "agent": node,
                            "phase": "completed",
                            "detail": detail,
                            "retry_count": state.get("retry_count", 0),
                            "timestamp": utc_now_iso(),
                            "metrics": build_event_metrics(state),
                        }
                        yield payload

                        message = build_agent_message_event(node, state)
                        if message is not None:
                            message["run_id"] = state["run_id"]
                            message["node"] = node
                            message["metrics"] = build_event_metrics(state)
                            yield message
            finally:
                for span in node_spans.values():
                    try:
                        span.end()
                    except Exception:
                        continue
                if session_span is not None:
                    session_span.set_attribute("run.retry_count", int(state.get("retry_count") or 0))
                    session_span.set_attribute("quality.mode", str(state.get("quality_mode") or "normal"))
                    session_span.set_attribute("root.cause", str(state.get("root_cause") or ""))

        state["quality_summary"] = build_quality_summary(state)
        if self.perf_tracker is not None:
            perf_bill = self.perf_tracker.build_bill()
            perf_bill_path = self.repository.save_perf_bill(state["run_id"], perf_bill)
            state["perf_bill"] = perf_bill.model_dump(mode="json")
            state["perf_bill_path"] = str(perf_bill_path or "")
        self.repository.save_run_completed(self.run_manifest, state)
        yield {
            "type": "done",
            "run_id": state["run_id"],
            "node": "System",
            "timestamp": utc_now_iso(),
            "report_markdown": state.get("report_content"),
            "tailor_plan": dict(state.get("tailor_plan") or {}),
            "resume_version": dict(state.get("resume_version") or {}),
            "fact_check_report": dict(state.get("fact_check_report") or {}),
            "external_evidence_pack": dict(state.get("external_evidence_pack") or {}),
            "job_snapshot": dict(state.get("job_snapshot") or {}),
            "match_assessment": dict(state.get("match_assessment") or {}),
            "retry_count": state.get("retry_count", 0),
            "quality_summary": state.get("quality_summary"),
            "perf_bill": state.get("perf_bill"),
            "perf_bill_path": state.get("perf_bill_path"),
            "trace": state.get("run_trace"),
            "metrics": build_event_metrics(state),
        }
