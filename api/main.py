from __future__ import annotations

import json
import traceback
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from utils.logger import _write as _log_raw

from api.core.executor import ResearchExecutionSession
from api.core.graph import build_career_research_graph, parse_review_feedback_json
from api.core.metrics import render_metrics_response
from api.core.otel import initialize_otel, start_span
from api.core.persistence import build_repository
from api.core.policy_loader import load_policy
from api.evals.harness import CaseEvaluation, EvalSuiteSummary, ResearchCase, load_research_cases, score_case_result, summarize_eval_suite


class ResearchRunRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=600, description="Company + role + research goal.")
    candidate_profile: dict[str, Any] = Field(default_factory=dict)
    resume_evidence: list[dict[str, Any]] = Field(default_factory=list)
    job_posting: dict[str, Any] = Field(default_factory=dict)
    match_assessment: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_tailoring_payload(self) -> "ResearchRunRequest":
        has_candidate_profile = bool(self.candidate_profile)
        has_resume_evidence = bool(self.resume_evidence)
        if has_candidate_profile != has_resume_evidence:
            raise ValueError("candidate_profile and resume_evidence must be provided together")

        if has_candidate_profile:
            candidate_id = str(self.candidate_profile.get("candidate_id") or "").strip()
            if not candidate_id:
                raise ValueError("candidate_profile must include candidate_id")

        for index, item in enumerate(self.resume_evidence, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"resume_evidence[{index}] must be an object")
            evidence_id = str(item.get("evidence_id") or "").strip()
            if not evidence_id:
                raise ValueError(f"resume_evidence[{index}] must include evidence_id")
            section = str(item.get("section") or item.get("evidence_type") or "").strip()
            if not section:
                raise ValueError(f"resume_evidence[{index}] must include section or evidence_type")

        return self


class ResearchRunResponse(BaseModel):
    run_id: str
    report_markdown: str
    insights: dict[str, Any] = Field(default_factory=dict)
    tailor_plan: dict[str, Any] = Field(default_factory=dict)
    resume_version: dict[str, Any] = Field(default_factory=dict)
    fact_check_report: dict[str, Any] = Field(default_factory=dict)
    external_evidence_pack: dict[str, Any] = Field(default_factory=dict)
    job_snapshot: dict[str, Any] = Field(default_factory=dict)
    match_assessment: dict[str, Any] = Field(default_factory=dict)
    run_manifest: dict[str, Any] = Field(default_factory=dict)
    review: dict[str, Any] | None = None
    retry_count: int = 0
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    quality_mode: str = "normal"
    warning_message: str = ""
    root_cause: str = ""


class ResearchCaseRunRequest(BaseModel):
    case_id: str = Field(..., min_length=3)


class EvalRunRequest(BaseModel):
    case_ids: list[str] = Field(default_factory=list)


app = FastAPI(
    title="Career Research Assistant API",
    version="2.1.0",
    description="基于 LangGraph + Tavily + SSE 的多 Agent 求职研究助手 API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_graph = build_career_research_graph()
_policy = load_policy()
_repository = build_repository(_policy)
initialize_otel()


def _log_exception(context: str, exc: Exception) -> str:
    trace = traceback.format_exc()
    payload = f"{context}: {exc!r}\n{trace}"
    try:
        _log_raw("forum_error", payload)
    except Exception:
        pass
    print(payload)
    return trace


def _as_sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "career-research-assistant"}


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> Response:
    payload = render_metrics_response()
    if payload is None:
        raise HTTPException(status_code=404, detail="metrics disabled or prometheus_client unavailable")
    content, content_type = payload
    return Response(content=content, media_type=content_type)


@app.post("/api/research/run", response_model=ResearchRunResponse)
@app.post("/api/forum/run", response_model=ResearchRunResponse, include_in_schema=False)
async def run_research(payload: ResearchRunRequest) -> ResearchRunResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    with start_span("http.research.run", {"http.route": "/api/research/run", "research.query": query}):
        try:
            session = ResearchExecutionSession(
                _graph,
                query,
                candidate_profile=dict(payload.candidate_profile or {}),
                resume_evidence=list(payload.resume_evidence or []),
                job_posting=dict(payload.job_posting or {}),
                match_assessment=dict(payload.match_assessment or {}),
            )
            async for _ in session.stream_events():
                pass
            final_state = session.state
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            _log_exception("run_research", exc)
            raise HTTPException(status_code=500, detail=f"LangGraph failed: {str(exc)}") from exc

    review = parse_review_feedback_json(final_state) if isinstance(final_state, dict) else None
    report_content = str(final_state.get("report_content") or "") if isinstance(final_state, dict) else ""
    insights = dict(final_state.get("insights") or {}) if isinstance(final_state, dict) else {}
    retry_count = int(final_state.get("retry_count") or 0) if isinstance(final_state, dict) else 0
    return ResearchRunResponse(
        run_id=str(final_state.get("run_id") or ""),
        report_markdown=report_content,
        insights=insights,
        tailor_plan=dict(final_state.get("tailor_plan") or {}),
        resume_version=dict(final_state.get("resume_version") or {}),
        fact_check_report=dict(final_state.get("fact_check_report") or {}),
        external_evidence_pack=dict(final_state.get("external_evidence_pack") or {}),
        job_snapshot=dict(final_state.get("job_snapshot") or {}),
        match_assessment=dict(final_state.get("match_assessment") or {}),
        run_manifest=dict(final_state.get("run_manifest") or {}) if isinstance(final_state, dict) else {},
        review=review,
        retry_count=retry_count,
        quality_summary=dict(final_state.get("quality_summary") or {}),
        trace=list(final_state.get("run_trace") or []),
        quality_mode=str(final_state.get("quality_mode") or "normal") if isinstance(final_state, dict) else "normal",
        warning_message=str(final_state.get("warning_message") or "") if isinstance(final_state, dict) else "",
        root_cause=str(final_state.get("root_cause") or "") if isinstance(final_state, dict) else "",
    )


@app.get("/api/research/cases", response_model=list[ResearchCase])
async def list_research_cases() -> list[ResearchCase]:
    cases = load_research_cases()
    for case in cases:
        _repository.save_research_case(case)
    return cases


@app.post("/api/research/cases/run", response_model=ResearchRunResponse)
async def run_research_case(payload: ResearchCaseRunRequest) -> ResearchRunResponse:
    cases = {item.case_id: item for item in load_research_cases()}
    target = cases.get(payload.case_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"unknown case_id: {payload.case_id}")
    with start_span(
        "http.research.case_run",
        {"http.route": "/api/research/cases/run", "research.case_id": payload.case_id},
    ):
        session = ResearchExecutionSession(_graph, target.query, research_case=target.model_dump())
        async for _ in session.stream_events():
            pass
        final_state = session.state
    return ResearchRunResponse(
        run_id=str(final_state.get("run_id") or ""),
        report_markdown=str(final_state.get("report_content") or ""),
        insights=dict(final_state.get("insights") or {}),
        tailor_plan=dict(final_state.get("tailor_plan") or {}),
        resume_version=dict(final_state.get("resume_version") or {}),
        fact_check_report=dict(final_state.get("fact_check_report") or {}),
        external_evidence_pack=dict(final_state.get("external_evidence_pack") or {}),
        job_snapshot=dict(final_state.get("job_snapshot") or {}),
        match_assessment=dict(final_state.get("match_assessment") or {}),
        run_manifest=dict(final_state.get("run_manifest") or {}),
        review=parse_review_feedback_json(final_state) if isinstance(final_state, dict) else None,
        retry_count=int(final_state.get("retry_count") or 0),
        quality_summary=dict(final_state.get("quality_summary") or {}),
        trace=list(final_state.get("run_trace") or []),
        quality_mode=str(final_state.get("quality_mode") or "normal"),
        warning_message=str(final_state.get("warning_message") or ""),
        root_cause=str(final_state.get("root_cause") or ""),
    )


@app.post("/api/research/eval", response_model=EvalSuiteSummary)
async def run_eval_suite(payload: EvalRunRequest) -> EvalSuiteSummary:
    cases = load_research_cases()
    selected = [case for case in cases if not payload.case_ids or case.case_id in payload.case_ids]
    if not selected:
        raise HTTPException(status_code=400, detail="no cases selected")

    with start_span(
        "http.research.eval",
        {"http.route": "/api/research/eval", "eval.case_count": len(selected)},
    ):
        results: list[CaseEvaluation] = []
        for case in selected:
            _repository.save_research_case(case)
            session = ResearchExecutionSession(_graph, case.query, research_case=case.model_dump())
            async for _ in session.stream_events():
                pass
            result = score_case_result(case, session.state)
            _repository.save_eval_result(result)
            results.append(result)
        return summarize_eval_suite(_policy.eval_policy.suite_name, results)


async def _stream_research_response(payload: ResearchRunRequest) -> StreamingResponse:
    clean_query = payload.query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    async def event_generator() -> AsyncIterator[str]:
        with start_span("http.research.stream", {"http.route": "/api/research/stream", "research.query": clean_query}):
            session = ResearchExecutionSession(
                _graph,
                clean_query,
                candidate_profile=dict(payload.candidate_profile or {}),
                resume_evidence=list(payload.resume_evidence or []),
                job_posting=dict(payload.job_posting or {}),
                match_assessment=dict(payload.match_assessment or {}),
            )
            try:
                async for event in session.stream_events():
                    yield _as_sse(event)
            except ValueError as exc:
                _log_exception("stream_research.validation", exc)
                yield _as_sse(
                    {
                        "type": "error",
                        "run_id": str(session.state.get("run_id") or ""),
                        "node": "System",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "error_type": "validation_error",
                        "detail": f"请求参数错误: {str(exc)}",
                    }
                )
            except Exception as exc:
                trace = _log_exception("stream_research.runtime", exc)
                yield _as_sse(
                    {
                        "type": "error",
                        "run_id": str(session.state.get("run_id") or ""),
                        "node": "System",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "error_type": "runtime_error",
                        "detail": f"LangGraph执行失败: {str(exc)}",
                        "traceback": trace,
                    }
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/research/stream")
@app.get("/api/forum/stream", include_in_schema=False)
async def stream_research(
    query: str = Query(..., min_length=2, description="Company + role + research goal."),
) -> StreamingResponse:
    return await _stream_research_response(ResearchRunRequest(query=query))


@app.post("/api/research/stream", include_in_schema=False)
@app.post("/api/forum/stream", include_in_schema=False)
async def stream_research_with_payload(payload: ResearchRunRequest) -> StreamingResponse:
    return await _stream_research_response(payload)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=9000, reload=True)
