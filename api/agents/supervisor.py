"""Supervisor Agent — intent routing + workflow selection + missing-param detection.
Merges the Phase 1 IntentRouter. Deterministic rules first, LLM fallback."""

from __future__ import annotations

from typing import Any

from api.core.contracts import (
    QueryProfile,
    ResearchIntent,
    SupervisorResponse,
    WorkflowId,
)
from api.core.job_query import build_query_profile
from api.core.llm import invoke_structured_output
from api.core.prompt_loader import load_prompt
from pydantic import BaseModel, Field


class _SupervisorLLMResponse(BaseModel):
    intent: str = Field(default="general", description="intent分类")
    reason: str = Field(default="", description="理由")
    company: str = Field(default="", description="目标公司")
    role: str = Field(default="", description="目标岗位")
    team_hint: str = Field(default="")
    domain_hint: str = Field(default="")


SUPERVISOR_SYSTEM_PROMPT = load_prompt("supervisor_system.txt")


def _deterministic_route(query: str, state: dict[str, Any]) -> SupervisorResponse | None:
    """Try deterministic keyword-based routing first."""
    text = query.lower()

    # 1. Resume file upload detection
    if state.get("resume_file") or any(kw in text for kw in ["上传简历", "解析简历", "简历文件"]):
        return SupervisorResponse(
            intent="profile_bootstrap",
            workflow_id="wf_profile_bootstrap",
            query_profile=QueryProfile(company="", role=""),
            missing_artifacts=_detect_missing("wf_profile_bootstrap", state),
            warnings=[],
            reasoning="检测到简历文件上传意图，进入简历解析工作流。",
        )

    # 2. Offer comparison
    if any(kw in text for kw in ["对比", "选 offer", "两个 offer", "多个 offer", "offer 对比", "选哪个"]):
        missing = _detect_missing("wf_offer_compare", state)
        return SupervisorResponse(
            intent="offer_compare",
            workflow_id="wf_offer_compare",
            query_profile=QueryProfile(company="", role=""),
            missing_artifacts=missing,
            warnings=["请提供至少两个offer的数据"] if missing else [],
            reasoning="检测到offer对比意图。",
        )

    # 3. Resume tailoring
    if any(kw in text for kw in ["改简历", "优化简历", "定制简历", "修改简历", "简历优化", "简历定制"]):
        missing = _detect_missing("wf_resume_tailor_v2", state)
        return SupervisorResponse(
            intent="resume_tailor",
            workflow_id="wf_resume_tailor_v2",
            query_profile=QueryProfile(company="", role=""),
            missing_artifacts=missing,
            warnings=["缺少候选人画像，请先上传简历" if "candidate_profile" in missing else ""],
            reasoning="检测到简历优化意图。",
        )

    # 4. Interview preparation
    if any(kw in text for kw in ["面试", "会问什么", "准备包", "面试准备", "面试题", "模拟面试"]):
        missing = _detect_missing("wf_interview_prep_v2", state)
        return SupervisorResponse(
            intent="interview_prep",
            workflow_id="wf_interview_prep_v2",
            query_profile=QueryProfile(company="", role=""),
            missing_artifacts=missing,
            warnings=["缺少匹配分析，建议先运行岗位匹配" if "match_assessment" in missing else ""],
            reasoning="检测到面试准备意图。",
        )

    # 5. Match analysis (broad catch)
    if any(kw in text for kw in ["匹配", "适合吗", "怎么样", "分析", "评估", "帮我看看", "岗位", "工作"]):
        missing = _detect_missing("wf_match_v2", state)
        return SupervisorResponse(
            intent="match",
            workflow_id="wf_match_v2",
            query_profile=QueryProfile(company="", role=""),
            missing_artifacts=missing,
            warnings=(
                ["无候选人画像，分析偏保守" if "candidate_profile" in missing else ""]
                + (["无简历证据，匹配分数可能偏低" if "resume_evidence" in missing else ""])
            ),
            reasoning="检测到岗位分析/匹配意图。",
        )

    return None


def _detect_missing(workflow_id: WorkflowId, state: dict[str, Any]) -> list[str]:
    """Detect missing required artifacts for a workflow."""
    missing: list[str] = []

    candidate_profile = state.get("candidate_profile") or {}
    resume_evidence = state.get("resume_evidence") or []
    match_assessment = state.get("match_assessment") or {}
    job_snapshot = state.get("job_snapshot") or {}
    offer_list = state.get("offer_list") or []

    wf_needs: dict[str, list[str]] = {
        "wf_match_v2": ["query"],
        "wf_resume_tailor_v2": ["candidate_profile", "resume_evidence"],
        "wf_interview_prep_v2": ["candidate_profile", "resume_evidence"],
        "wf_profile_bootstrap": ["resume_file"],
        "wf_offer_compare": ["offer_list"],
    }

    needs = wf_needs.get(workflow_id, ["query"])
    for need in needs:
        if need == "query" and not str(state.get("query", "")).strip():
            missing.append("query")
        elif need == "candidate_profile" and not candidate_profile:
            missing.append("candidate_profile")
        elif need == "resume_evidence" and not resume_evidence:
            missing.append("resume_evidence")
        elif need == "match_assessment" and not match_assessment:
            missing.append("match_assessment")
        elif need == "resume_file" and not state.get("resume_file"):
            missing.append("resume_file")
        elif need == "offer_list" and (not offer_list or len(offer_list) < 2):
            missing.append("offer_list")
        elif need == "job_snapshot" and not job_snapshot:
            missing.append("job_snapshot")

    return missing


async def _llm_route(query: str) -> _SupervisorLLMResponse:
    """LLM-based intent classification as fallback."""
    try:
        result = await invoke_structured_output(
            _SupervisorLLMResponse,
            system_prompt=SUPERVISOR_SYSTEM_PROMPT,
            human_prompt="用户输入：\n{query}\n\n请判断意图并输出JSON。",
            variables={"query": query},
            temperature=0.0,
        )
        return result
    except Exception:
        return _SupervisorLLMResponse(intent="general", reason="LLM调用失败，使用默认意图")


async def supervisor_node(state: dict[str, Any]) -> dict[str, Any]:
    """Supervisor node — the system entry point."""
    query = str(state.get("query") or "").strip()
    if not query and not state.get("resume_file"):
        return {
            "intent": "general",
            "workflow_id": "wf_match_v2",
            "query_profile": {"company": "", "role": ""},
            "missing_artifacts": ["query"],
            "warnings": ["查询为空"],
            "reasoning": "无用户输入，返回默认工作流",
            "status": "已完成意图识别",
        }

    # Step 1: Try deterministic routing
    result = _deterministic_route(query, state)
    if result is not None and result.intent != "match":
        return _supervisor_output(state, result)

    # Step 2: LLM routing for remaining cases
    llm_resp = await _llm_route(query)

    # Map LLM intent to workflow
    intent = llm_resp.intent
    intent_to_workflow: dict[str, WorkflowId] = {
        "profile_bootstrap": "wf_profile_bootstrap",
        "offer_compare": "wf_offer_compare",
        "resume_tailor": "wf_resume_tailor_v2",
        "interview_prep": "wf_interview_prep_v2",
        "match": "wf_match_v2",
        "tech_coding": "wf_match_v2",
        "salary_culture": "wf_match_v2",
        "general": "wf_match_v2",
    }

    workflow_id = intent_to_workflow.get(intent, "wf_match_v2")
    missing = _detect_missing(workflow_id, state)

    # Build query_profile from LLM extraction
    query_profile = QueryProfile(
        company=llm_resp.company or "",
        role=llm_resp.role or "",
        team_hint=llm_resp.team_hint or "",
        domain_hint=llm_resp.domain_hint or "",
    )

    # If LLM gave no company/role, try heuristic
    if not query_profile.company and not query_profile.role:
        try:
            from api.core.job_query import build_query_profile
            qp = build_query_profile(query, intent=intent)
            query_profile = QueryProfile.model_validate(qp)
        except Exception:
            pass

    resp = SupervisorResponse(
        intent=intent,  # type: ignore[arg-type]
        workflow_id=workflow_id,
        query_profile=query_profile,
        missing_artifacts=missing,
        warnings=(
            (["无候选人画像，分析偏保守"] if "candidate_profile" in missing else [])
            + (["无简历证据，匹配分数可能偏低"] if "resume_evidence" in missing else [])
        ),
        reasoning=llm_resp.reason or f"LLM判定意图为{intent}",
    )
    return _supervisor_output(state, resp)


def _supervisor_output(state: dict[str, Any], resp: SupervisorResponse) -> dict[str, Any]:
    """Build the state update from SupervisorResponse."""
    insights = dict(state.get("insights") or {})
    qp = resp.query_profile.model_dump()

    insights.update({
        "intent_reason": resp.reasoning,
        "company": qp.get("company"),
        "role": qp.get("role"),
        "workflow_id": resp.workflow_id,
        "missing_artifacts": resp.missing_artifacts,
    })

    return {
        "intent": resp.intent,
        "workflow_id": resp.workflow_id,
        "query_profile": qp,
        "insights": insights,
        "missing_artifacts": resp.missing_artifacts,
        "warnings": resp.warnings,
        "status": f"已识别意图为 {resp.intent}，选择工作流 {resp.workflow_id}",
    }
