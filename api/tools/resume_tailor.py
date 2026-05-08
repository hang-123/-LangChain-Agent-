"""ResumeTailor Tool — deterministic resume tailoring, 0 LLM.
Migrated from api/agents/resume_tailor_agent.py."""

from __future__ import annotations

from typing import Any

# Reuse existing deterministic logic
from api.agents.resume_tailor_agent import build_resume_tailoring_artifacts


async def run_resume_tailor(state: dict[str, Any]) -> dict[str, Any]:
    """ResumeTailor Tool — generate tailoring plan determinedly."""
    candidate_profile = dict(state.get("candidate_profile") or {})
    resume_evidence = list(state.get("resume_evidence") or [])
    job_snapshot = dict(state.get("job_snapshot") or {})
    match_assessment = dict(state.get("match_assessment") or {})

    # Phase 2: validation
    if not candidate_profile or not resume_evidence:
        return {
            "tailor_plan": {},
            "resume_version": {},
            "fact_check_report": {},
            "status": "ResumeTailor 未生成产物：缺少候选人画像或简历证据。",
        }

    if not match_assessment:
        return {
            "tailor_plan": {},
            "resume_version": {},
            "fact_check_report": {},
            "status": "ResumeTailor 需要匹配评估结果，请先运行岗位匹配。",
        }

    artifacts = build_resume_tailoring_artifacts(
        candidate_profile=candidate_profile,
        resume_evidence=resume_evidence,
        job_snapshot=job_snapshot,
        match_assessment=match_assessment,
    )

    if not artifacts:
        return {
            "tailor_plan": {},
            "resume_version": {},
            "fact_check_report": {},
            "status": "ResumeTailor 未生成简历定制产物。",
        }

    return {
        **artifacts,
        "status": "ResumeTailor 已完成简历定制计划生成。",
    }
